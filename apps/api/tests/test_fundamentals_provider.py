import pytest

from app.core.config import get_settings
from app.services.fundamentals.fmp import (
    FMPProviderError,
    FinancialModelingPrepProvider,
)
from app.services.fundamentals.provider import (
    NotConnectedFundamentalsProvider,
    get_fundamentals_provider,
)


def clear_provider_caches() -> None:
    get_settings.cache_clear()
    get_fundamentals_provider.cache_clear()


@pytest.fixture(autouse=True)
def clear_fmp_env(monkeypatch):
    monkeypatch.delenv("FMP_API_KEY", raising=False)
    monkeypatch.delenv("FMP_BASE_URL", raising=False)
    clear_provider_caches()

    yield

    clear_provider_caches()


def test_missing_fmp_credentials_use_not_connected_provider() -> None:
    provider = get_fundamentals_provider()

    assert isinstance(provider, NotConnectedFundamentalsProvider)
    assert provider.provider_status()["state"] == "not_connected"
    assert provider.provider_status()["requiredEnvironmentVariables"] == [
        "FMP_API_KEY",
    ]


def test_fmp_credentials_select_fmp_provider(monkeypatch) -> None:
    monkeypatch.setenv("FMP_API_KEY", "test-fmp-key")
    monkeypatch.setenv("FMP_BASE_URL", "https://example-fmp.test")
    clear_provider_caches()

    provider = get_fundamentals_provider()

    assert isinstance(provider, FinancialModelingPrepProvider)
    assert provider.base_url == "https://example-fmp.test"
    assert provider.provider_status()["state"] == "connected"


def test_fmp_profile_normalizes_canonical_contract(monkeypatch) -> None:
    provider = FinancialModelingPrepProvider(
        api_key="test-fmp-key",
        base_url="https://example-fmp.test",
    )

    def fake_request_json(path, params):
        assert path == "/profile"
        assert params == {"symbol": "AAPL"}

        return [
            {
                "symbol": "AAPL",
                "companyName": "Apple Inc.",
                "exchangeShortName": "NASDAQ",
                "sector": "Technology",
                "industry": "Consumer Electronics",
                "country": "US",
                "website": "https://www.apple.com",
                "currency": "USD",
                "marketCap": 2800000000000,
                "beta": 1.2,
                "price": 190.12,
                "description": "Profile text.",
            }
        ]

    monkeypatch.setattr(provider, "_request_json", fake_request_json)

    payload = provider.get_company_profile("aapl")
    profile = payload["profile"]

    assert payload["provider"]["state"] == "connected"
    assert profile["ticker"] == "AAPL"
    assert profile["name"] == "Apple Inc."
    assert profile["exchange"] == "NASDAQ"
    assert profile["marketCap"] == 2800000000000.0
    assert profile["provider"] == "fmp"
    assert profile["sourceSymbol"] == "AAPL"
    assert profile["currency"] == "USD"
    assert profile["qualityFlags"] == []


def test_fmp_profile_cache_uses_normalized_key(monkeypatch) -> None:
    provider = FinancialModelingPrepProvider(
        api_key="test-fmp-key",
        base_url="https://example-fmp.test",
        profile_cache_ttl_seconds=60,
    )
    calls = []

    def fake_request_json(path, params):
        calls.append((path, params))

        return [
            {
                "symbol": "AAPL",
                "companyName": "Apple Inc.",
                "currency": "USD",
            }
        ]

    monkeypatch.setattr(provider, "_request_json", fake_request_json)

    first_payload = provider.get_company_profile("aapl")
    second_payload = provider.get_company_profile(" AAPL ")

    assert len(calls) == 1
    assert first_payload == second_payload
    assert second_payload["ticker"] == "AAPL"


def test_fmp_statement_cache_hit_and_miss(monkeypatch) -> None:
    provider = FinancialModelingPrepProvider(
        api_key="test-fmp-key",
        base_url="https://example-fmp.test",
        income_statement_cache_ttl_seconds=60,
    )
    calls = []

    def fake_request_json(path, params):
        calls.append((path, params))

        return [
            {
                "symbol": "AAPL",
                "date": "2025-09-27",
                "reportedCurrency": "USD",
                "fiscalYear": "2025",
                "period": "FY",
                "revenue": 1000,
                "grossProfit": 450,
                "operatingIncome": 300,
                "netIncome": 220,
                "weightedAverageShsOutDil": 44,
            }
        ]

    monkeypatch.setattr(provider, "_request_json", fake_request_json)

    first_payload = provider.get_income_statement("aapl", "annual", 5)
    second_payload = provider.get_income_statement(" AAPL ", "ANNUAL", 5)
    third_payload = provider.get_income_statement("AAPL", "annual", 4)

    assert len(calls) == 2
    assert first_payload == second_payload
    assert third_payload["limit"] == 4


def test_fmp_statement_cache_can_be_disabled(monkeypatch) -> None:
    provider = FinancialModelingPrepProvider(
        api_key="test-fmp-key",
        base_url="https://example-fmp.test",
        income_statement_cache_ttl_seconds=0,
    )
    calls = []

    def fake_request_json(path, params):
        calls.append((path, params))

        return [
            {
                "symbol": "AAPL",
                "date": "2025-09-27",
                "reportedCurrency": "USD",
                "fiscalYear": "2025",
                "period": "FY",
                "revenue": 1000,
                "grossProfit": 450,
                "operatingIncome": 300,
                "netIncome": 220,
                "weightedAverageShsOutDil": 44,
            }
        ]

    monkeypatch.setattr(provider, "_request_json", fake_request_json)

    provider.get_income_statement("AAPL", "annual", 5)
    provider.get_income_statement("AAPL", "annual", 5)

    assert len(calls) == 2


def test_fmp_provider_errors_are_not_cached(monkeypatch) -> None:
    provider = FinancialModelingPrepProvider(
        api_key="test-fmp-key",
        base_url="https://example-fmp.test",
        income_statement_cache_ttl_seconds=60,
    )
    calls = []

    def fake_request_json(path, params):
        calls.append((path, params))

        if len(calls) == 1:
            raise FMPProviderError("temporary failure")

        return [
            {
                "symbol": "AAPL",
                "date": "2025-09-27",
                "reportedCurrency": "USD",
                "fiscalYear": "2025",
                "period": "FY",
                "revenue": 1000,
                "grossProfit": 450,
                "operatingIncome": 300,
                "netIncome": 220,
                "weightedAverageShsOutDil": 44,
            }
        ]

    monkeypatch.setattr(provider, "_request_json", fake_request_json)

    first_payload = provider.get_income_statement("AAPL", "annual", 5)
    second_payload = provider.get_income_statement("AAPL", "annual", 5)

    assert len(calls) == 2
    assert first_payload["provider"]["state"] == "degraded"
    assert second_payload["provider"]["state"] == "connected"


def test_fmp_statement_quality_flags_for_missing_core_fields(monkeypatch) -> None:
    provider = FinancialModelingPrepProvider(
        api_key="test-fmp-key",
        base_url="https://example-fmp.test",
    )

    def fake_request_json(path, params):
        return [
            {
                "symbol": "AAPL",
                "date": None,
                "period": "FY",
                "revenue": 1000,
            }
        ]

    monkeypatch.setattr(provider, "_request_json", fake_request_json)

    payload = provider.get_income_statement("AAPL", "annual", 5)
    flags = payload["incomeStatements"][0]["qualityFlags"]

    assert "currency_missing" in flags
    assert "fiscal_year_missing" in flags
    assert "provider_anomaly:missing_date" in flags
    assert "missing_core_field:grossProfit" in flags
    assert "missing_core_field:operatingIncome" in flags
    assert "missing_core_field:netIncome" in flags
    assert "missing_core_field:sharesDiluted" in flags
    assert "shares_missing" in flags


def test_fmp_income_statement_normalizes_annual_rows(monkeypatch) -> None:
    provider = FinancialModelingPrepProvider(
        api_key="test-fmp-key",
        base_url="https://example-fmp.test",
    )

    def fake_request_json(path, params):
        assert path == "/income-statement"
        assert params == {"symbol": "AAPL", "period": "annual", "limit": "5"}

        return [
            {
                "symbol": "AAPL",
                "date": "2025-09-27",
                "reportedCurrency": "USD",
                "fiscalYear": "2025",
                "period": "FY",
                "revenue": 1000,
                "grossProfit": 450,
                "operatingIncome": 300,
                "ebitda": 350,
                "netIncome": 220,
                "eps": 5.1,
                "epsdiluted": 5,
                "weightedAverageShsOutDil": 44,
            }
        ]

    monkeypatch.setattr(provider, "_request_json", fake_request_json)

    payload = provider.get_income_statement("aapl", "annual", 5)
    row = payload["incomeStatements"][0]

    assert payload["period"] == "annual"
    assert row["revenue"] == 1000.0
    assert row["operatingIncome"] == 300.0
    assert row["epsDiluted"] == 5.0
    assert row["sharesDiluted"] == 44.0
    assert row["fiscalYear"] == "2025"
    assert row["fiscalPeriod"] == "FY"
    assert row["qualityFlags"] == []
    assert "weightedAverageShsOutDil" not in row


def test_fmp_balance_sheet_normalizes_quarterly_rows(monkeypatch) -> None:
    provider = FinancialModelingPrepProvider(
        api_key="test-fmp-key",
        base_url="https://example-fmp.test",
    )

    def fake_request_json(path, params):
        assert path == "/balance-sheet-statement"
        assert params == {"symbol": "AAPL", "period": "quarter", "limit": "2"}

        return [
            {
                "symbol": "AAPL",
                "date": "2026-03-28",
                "reportedCurrency": "USD",
                "fiscalYear": "2026",
                "period": "Q2",
                "cashAndCashEquivalents": 100,
                "totalAssets": 500,
                "totalCurrentAssets": 250,
                "totalLiabilities": 300,
                "totalCurrentLiabilities": 125,
                "totalDebt": 90,
                "totalStockholdersEquity": 200,
                "retainedEarnings": 50,
            }
        ]

    monkeypatch.setattr(provider, "_request_json", fake_request_json)

    payload = provider.get_balance_sheet("aapl", "quarter", 2)
    row = payload["balanceSheets"][0]

    assert payload["period"] == "quarter"
    assert row["cashAndEquivalents"] == 100.0
    assert row["totalAssets"] == 500.0
    assert row["totalDebt"] == 90.0
    assert row["shareholdersEquity"] == 200.0
    assert row["fiscalPeriod"] == "Q2"
    assert row["qualityFlags"] == []
    assert "totalStockholdersEquity" not in row


def test_fmp_cash_flow_normalizes_canonical_rows(monkeypatch) -> None:
    provider = FinancialModelingPrepProvider(
        api_key="test-fmp-key",
        base_url="https://example-fmp.test",
    )

    def fake_request_json(path, params):
        assert path == "/cash-flow-statement"

        return [
            {
                "symbol": "AAPL",
                "date": "2025-09-27",
                "reportedCurrency": "USD",
                "calendarYear": "2025",
                "period": "FY",
                "operatingCashFlow": 400,
                "capitalExpenditure": -50,
                "freeCashFlow": 350,
                "dividendsPaid": -20,
                "commonStockRepurchased": -80,
                "debtRepayment": -10,
                "debtIssuance": 5,
                "netChangeInCash": 15,
            }
        ]

    monkeypatch.setattr(provider, "_request_json", fake_request_json)

    payload = provider.get_cash_flow_statement("aapl", "annual", 3)
    row = payload["cashFlowStatements"][0]

    assert row["operatingCashFlow"] == 400.0
    assert row["capitalExpenditures"] == -50.0
    assert row["freeCashFlow"] == 350.0
    assert row["dividendsPaid"] == -20.0
    assert row["shareRepurchases"] == -80.0
    assert row["fiscalYear"] == "2025"
    assert row["qualityFlags"] == []
    assert "capitalExpenditure" not in row


def test_fmp_key_metrics_are_ingested_as_provider_metrics(monkeypatch) -> None:
    provider = FinancialModelingPrepProvider(
        api_key="test-fmp-key",
        base_url="https://example-fmp.test",
    )

    def fake_request_json(path, params):
        assert path == "/key-metrics"

        return [
            {
                "symbol": "AAPL",
                "date": "2025-09-27",
                "reportedCurrency": "USD",
                "fiscalYear": "2025",
                "period": "FY",
                "revenuePerShare": 22,
                "netIncomePerShare": 6,
                "freeCashFlowPerShare": 7,
                "bookValuePerShare": 4,
                "roic": 0.35,
                "roe": 1.2,
                "debtToEquity": 1.4,
                "currentRatio": 0.9,
                "peRatio": 30,
                "pbRatio": 12,
                "priceToSalesRatio": 7,
                "enterpriseValueOverEBITDA": 24,
            }
        ]

    monkeypatch.setattr(provider, "_request_json", fake_request_json)

    payload = provider.get_key_metrics("aapl", "annual", 5)
    row = payload["metrics"][0]

    assert "provisional" in payload["message"]
    assert row["returnOnInvestedCapital"] == 0.35
    assert row["debtToEquity"] == 1.4
    assert row["priceToEarnings"] == 30.0
    assert row["enterpriseValueToEbitda"] == 24.0
    assert row["qualityFlags"] == []
    assert "roic" not in row
    assert "peRatio" not in row


def test_fmp_ttm_period_returns_not_implemented_without_provider_call(monkeypatch) -> None:
    provider = FinancialModelingPrepProvider(
        api_key="test-fmp-key",
        base_url="https://example-fmp.test",
    )

    def fake_request_json(path, params):
        raise AssertionError("TTM should not call FMP in Phase 2A")

    monkeypatch.setattr(provider, "_request_json", fake_request_json)

    payload = provider.get_income_statement("aapl", "ttm", 5)

    assert payload["ticker"] == "AAPL"
    assert payload["period"] == "ttm"
    assert payload["incomeStatements"] == []
    assert payload["provider"]["state"] == "not_implemented"


def test_fmp_provider_reports_degraded_state_and_redacts_key(monkeypatch) -> None:
    provider = FinancialModelingPrepProvider(
        api_key="test-fmp-key",
        base_url="https://example-fmp.test",
    )

    def fake_request_json(path, params):
        raise FMPProviderError("HTTP 401 for test-fmp-key")

    monkeypatch.setattr(provider, "_request_json", fake_request_json)

    payload = provider.get_income_statement("AAPL", "annual", 5)
    status = provider.provider_status()

    assert payload["provider"]["state"] == "degraded"
    assert status["state"] == "degraded"
    assert "test-fmp-key" not in status["lastErrorMessage"]
    assert "[redacted]" in status["lastErrorMessage"]
