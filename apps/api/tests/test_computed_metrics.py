from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app
from app.services.cache import TTLCache
from app.services.fundamentals.computed_metrics import (
    build_computed_metrics_response,
    compute_metric_rows,
)
from app.services.fundamentals.provider import get_fundamentals_provider
from app.services.provider_status import provider_connected

client = TestClient(app)


def fresh_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


@pytest.fixture(autouse=True)
def clear_provider_state(monkeypatch):
    monkeypatch.delenv("FMP_API_KEY", raising=False)
    get_settings.cache_clear()
    get_fundamentals_provider.cache_clear()
    app.dependency_overrides.clear()

    yield

    get_settings.cache_clear()
    get_fundamentals_provider.cache_clear()
    app.dependency_overrides.clear()


def income_row(
    fiscal_year: str,
    fiscal_period: str,
    revenue: float,
    operating_income: float,
    net_income: float,
    shares_diluted: float,
) -> dict:
    return {
        "provider": "fmp",
        "fetchedAt": fresh_timestamp(),
        "sourceSymbol": "AAPL",
        "currency": "USD",
        "fiscalYear": fiscal_year,
        "fiscalPeriod": fiscal_period,
        "qualityFlags": [],
        "date": f"{fiscal_year}-09-30",
        "revenue": revenue,
        "grossProfit": revenue * 0.5,
        "operatingIncome": operating_income,
        "ebitda": None,
        "netIncome": net_income,
        "eps": None,
        "epsDiluted": None,
        "sharesDiluted": shares_diluted,
    }


def balance_row(
    fiscal_year: str,
    fiscal_period: str,
    shareholders_equity: float,
    current_liabilities: float = 250,
) -> dict:
    return {
        "provider": "fmp",
        "fetchedAt": fresh_timestamp(),
        "sourceSymbol": "AAPL",
        "currency": "USD",
        "fiscalYear": fiscal_year,
        "fiscalPeriod": fiscal_period,
        "qualityFlags": [],
        "date": f"{fiscal_year}-09-30",
        "cashAndEquivalents": 100,
        "totalAssets": 1600,
        "currentAssets": 500,
        "totalLiabilities": 800,
        "currentLiabilities": current_liabilities,
        "totalDebt": 300,
        "shareholdersEquity": shareholders_equity,
        "retainedEarnings": None,
    }


def cash_flow_row(fiscal_year: str, fiscal_period: str, free_cash_flow: float) -> dict:
    return {
        "provider": "fmp",
        "fetchedAt": fresh_timestamp(),
        "sourceSymbol": "AAPL",
        "currency": "USD",
        "fiscalYear": fiscal_year,
        "fiscalPeriod": fiscal_period,
        "qualityFlags": [],
        "date": f"{fiscal_year}-09-30",
        "operatingCashFlow": free_cash_flow + 50,
        "capitalExpenditures": -50,
        "freeCashFlow": free_cash_flow,
        "dividendsPaid": None,
        "shareRepurchases": None,
        "debtRepayment": None,
        "debtIssuance": None,
        "netChangeInCash": None,
    }


def test_computed_metrics_calculates_core_annual_metrics() -> None:
    rows = compute_metric_rows(
        "AAPL",
        "annual",
        5,
        [
            income_row("2025", "FY", 1200, 300, 240, 60),
            income_row("2024", "FY", 1000, 250, 200, 50),
        ],
        [
            balance_row("2025", "FY", 800),
            balance_row("2024", "FY", 700),
        ],
        [
            cash_flow_row("2025", "FY", 180),
            cash_flow_row("2024", "FY", 150),
        ],
    )

    row = rows[0]

    assert row["provider"] == "platform"
    assert row["sourceProviders"] == ["fmp"]
    assert row["grossMargin"] == pytest.approx(0.5)
    assert row["operatingMargin"] == pytest.approx(0.25)
    assert row["netMargin"] == pytest.approx(0.2)
    assert row["freeCashFlowMargin"] == pytest.approx(0.15)
    assert row["revenueGrowthYoY"] == pytest.approx(0.2)
    assert row["netIncomeGrowthYoY"] == pytest.approx(0.2)
    assert row["operatingIncomeGrowthYoY"] == pytest.approx(0.2)
    assert row["freeCashFlowGrowthYoY"] == pytest.approx(0.2)
    assert row["returnOnEquity"] == pytest.approx(0.3)
    assert row["debtToEquity"] == pytest.approx(0.375)
    assert row["currentRatio"] == pytest.approx(2)
    assert row["freeCashFlowPerShare"] == pytest.approx(3)
    assert row["bookValuePerShare"] == pytest.approx(800 / 60)
    assert row["earningsPerShareDiluted"] == pytest.approx(4)
    assert row["investedCapital"] == pytest.approx(1000)
    assert row["returnOnInvestedCapital"] == pytest.approx(0.3)
    assert row["qualityFlags"] == []


def test_computed_metrics_handles_missing_inputs() -> None:
    rows = compute_metric_rows(
        "AAPL",
        "annual",
        5,
        [income_row("2025", "FY", 1200, 300, 240, 60)],
        [],
        [],
    )

    row = rows[0]

    assert row["returnOnEquity"] is None
    assert row["freeCashFlowMargin"] is None
    assert "missing_statement:balance_sheet" in row["qualityFlags"]
    assert "missing_statement:cash_flow" in row["qualityFlags"]
    assert "missing_input:returnOnEquity" in row["qualityFlags"]
    assert "missing_input:freeCashFlowMargin" in row["qualityFlags"]


def test_computed_metrics_handles_zero_denominators() -> None:
    rows = compute_metric_rows(
        "AAPL",
        "annual",
        5,
        [income_row("2025", "FY", 0, 300, 240, 0)],
        [balance_row("2025", "FY", 0, current_liabilities=0)],
        [cash_flow_row("2025", "FY", 180)],
    )

    row = rows[0]

    assert row["grossMargin"] is None
    assert row["debtToEquity"] is None
    assert row["currentRatio"] is None
    assert row["freeCashFlowPerShare"] is None
    assert "zero_denominator:grossMargin" in row["qualityFlags"]
    assert "zero_denominator:debtToEquity" in row["qualityFlags"]
    assert "zero_denominator:currentRatio" in row["qualityFlags"]
    assert "zero_denominator:freeCashFlowPerShare" in row["qualityFlags"]


def test_computed_metrics_handles_negative_values_with_flags() -> None:
    rows = compute_metric_rows(
        "AAPL",
        "annual",
        5,
        [
            income_row("2025", "FY", -1000, -200, -300, 60),
            income_row("2024", "FY", -800, -100, -200, 50),
        ],
        [balance_row("2025", "FY", -500), balance_row("2024", "FY", -600)],
        [cash_flow_row("2025", "FY", -120), cash_flow_row("2024", "FY", -100)],
    )

    row = rows[0]

    assert row["netMargin"] == pytest.approx(0.3)
    assert row["revenueGrowthYoY"] == pytest.approx(-0.25)
    assert row["returnOnEquity"] == pytest.approx(0.6)
    assert "negative_denominator:netMargin" in row["qualityFlags"]
    assert "negative_prior_period:revenueGrowthYoY" in row["qualityFlags"]
    assert "negative_denominator:returnOnEquity" in row["qualityFlags"]
    assert "negative_invested_capital" in row["qualityFlags"]


def test_computed_metrics_flags_missing_shares_and_invested_capital() -> None:
    income = income_row("2025", "FY", 1200, 300, 240, 60)
    income["sharesDiluted"] = None
    balance = balance_row("2025", "FY", 800)
    balance["cashAndEquivalents"] = None

    rows = compute_metric_rows(
        "AAPL",
        "annual",
        5,
        [income],
        [balance],
        [cash_flow_row("2025", "FY", 180)],
    )

    flags = rows[0]["qualityFlags"]

    assert rows[0]["freeCashFlowPerShare"] is None
    assert rows[0]["investedCapital"] is None
    assert "shares_missing" in flags
    assert "invested_capital_unavailable" in flags


def test_computed_metrics_flags_statement_metadata_quality() -> None:
    income = income_row("2025", "FY", 1200, 300, 240, 60)
    income["currency"] = None
    income["fiscalYear"] = None
    income["fetchedAt"] = "2020-01-01T00:00:00Z"
    balance = balance_row("2025", "FY", 800)
    balance["currency"] = "EUR"

    rows = compute_metric_rows(
        "AAPL",
        "annual",
        5,
        [income],
        [balance],
        [cash_flow_row("2025", "FY", 180)],
    )

    flags = rows[0]["qualityFlags"]

    assert "currency_missing" in flags
    assert "fiscal_year_missing" in flags
    assert "currency_mismatch" in flags
    assert "stale_provider_response" in flags


def test_computed_metrics_uses_same_quarter_for_yoy_growth() -> None:
    rows = compute_metric_rows(
        "AAPL",
        "quarter",
        5,
        [
            income_row("2026", "Q2", 120, 30, 24, 60),
            income_row("2026", "Q1", 110, 25, 20, 60),
            income_row("2025", "Q4", 100, 22, 18, 60),
            income_row("2025", "Q3", 95, 20, 15, 60),
            income_row("2025", "Q2", 100, 20, 20, 60),
        ],
        [
            balance_row("2026", "Q2", 800),
            balance_row("2026", "Q1", 760),
            balance_row("2025", "Q4", 740),
            balance_row("2025", "Q3", 720),
            balance_row("2025", "Q2", 700),
        ],
        [
            cash_flow_row("2026", "Q2", 18),
            cash_flow_row("2026", "Q1", 16),
            cash_flow_row("2025", "Q4", 15),
            cash_flow_row("2025", "Q3", 14),
            cash_flow_row("2025", "Q2", 15),
        ],
    )

    row = rows[0]

    assert row["period"] == "quarter"
    assert row["revenueGrowthYoY"] == pytest.approx(0.2)
    assert row["freeCashFlowGrowthYoY"] == pytest.approx(0.2)


def test_computed_metrics_provider_fallback_without_credentials() -> None:
    response = client.get("/api/fundamentals/AAPL/computed-metrics")
    payload = response.json()

    assert response.status_code == 200
    assert payload["ticker"] == "AAPL"
    assert payload["computedMetrics"] == []
    assert payload["provider"]["state"] == "not_connected"


def test_computed_metrics_route_contract_with_mocked_provider() -> None:
    class FakeFundamentalsProvider:
        def provider_status(self):
            return provider_connected("fmp", "fake provider connected")

        def get_company_profile(self, ticker):
            raise AssertionError("computed metrics should not fetch profile")

        def get_income_statement(self, ticker, period, limit):
            return {
                "ticker": ticker,
                "period": period,
                "limit": limit,
                "incomeStatements": [
                    income_row("2025", "FY", 1200, 300, 240, 60),
                    income_row("2024", "FY", 1000, 250, 200, 50),
                ],
                "provider": self.provider_status(),
                "message": "fake income",
            }

        def get_balance_sheet(self, ticker, period, limit):
            return {
                "ticker": ticker,
                "period": period,
                "limit": limit,
                "balanceSheets": [
                    balance_row("2025", "FY", 800),
                    balance_row("2024", "FY", 700),
                ],
                "provider": self.provider_status(),
                "message": "fake balance",
            }

        def get_cash_flow_statement(self, ticker, period, limit):
            return {
                "ticker": ticker,
                "period": period,
                "limit": limit,
                "cashFlowStatements": [
                    cash_flow_row("2025", "FY", 180),
                    cash_flow_row("2024", "FY", 150),
                ],
                "provider": self.provider_status(),
                "message": "fake cash flow",
            }

        def get_key_metrics(self, ticker, period, limit):
            raise AssertionError("computed metrics should not fetch provider metrics")

    app.dependency_overrides[get_fundamentals_provider] = (
        lambda: FakeFundamentalsProvider()
    )

    response = client.get(
        "/api/fundamentals/aapl/computed-metrics",
        params={"period": "annual", "limit": 5},
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["ticker"] == "AAPL"
    assert payload["period"] == "annual"
    assert payload["provider"]["provider"] == "platform"
    assert payload["provider"]["state"] == "connected"
    assert payload["computedMetrics"][0]["grossMargin"] == pytest.approx(0.5)
    assert payload["computedMetrics"][0]["qualityFlags"] == []


def test_computed_metrics_cache_uses_normalized_key() -> None:
    class CachedFundamentalsProvider:
        computed_metrics_cache = TTLCache(60)

        def __init__(self):
            self.calls = []

        def provider_status(self):
            return provider_connected("fmp", "fake provider connected")

        def get_company_profile(self, ticker):
            raise AssertionError("unused")

        def get_income_statement(self, ticker, period, limit):
            self.calls.append(("income", ticker, period, limit))

            return {
                "ticker": ticker,
                "period": period,
                "limit": limit,
                "incomeStatements": [
                    income_row("2025", "FY", 1200, 300, 240, 60),
                    income_row("2024", "FY", 1000, 250, 200, 50),
                ],
                "provider": self.provider_status(),
                "message": "fake income",
            }

        def get_balance_sheet(self, ticker, period, limit):
            self.calls.append(("balance", ticker, period, limit))

            return {
                "ticker": ticker,
                "period": period,
                "limit": limit,
                "balanceSheets": [
                    balance_row("2025", "FY", 800),
                    balance_row("2024", "FY", 700),
                ],
                "provider": self.provider_status(),
                "message": "fake balance",
            }

        def get_cash_flow_statement(self, ticker, period, limit):
            self.calls.append(("cash", ticker, period, limit))

            return {
                "ticker": ticker,
                "period": period,
                "limit": limit,
                "cashFlowStatements": [
                    cash_flow_row("2025", "FY", 180),
                    cash_flow_row("2024", "FY", 150),
                ],
                "provider": self.provider_status(),
                "message": "fake cash",
            }

        def get_key_metrics(self, ticker, period, limit):
            raise AssertionError("unused")

    provider = CachedFundamentalsProvider()

    first_payload = build_computed_metrics_response(provider, "aapl", "annual", 5)
    second_payload = build_computed_metrics_response(provider, " AAPL ", "ANNUAL", 5)

    assert len(provider.calls) == 3
    assert first_payload == second_payload
    assert second_payload["ticker"] == "AAPL"


def test_computed_metrics_ttm_route_returns_not_implemented() -> None:
    response = client.get(
        "/api/fundamentals/AAPL/computed-metrics",
        params={"period": "ttm", "limit": 5},
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["computedMetrics"] == []
    assert payload["provider"]["state"] == "not_implemented"
    assert payload["period"] == "ttm"


def test_build_computed_metrics_response_preserves_degraded_provider() -> None:
    class DegradedProvider:
        def provider_status(self):
            return provider_connected("fmp", "fake")

        def get_income_statement(self, ticker, period, limit):
            return {
                "provider": {
                    "provider": "fmp",
                    "state": "degraded",
                    "message": "failed",
                    "requiredEnvironmentVariables": ["FMP_API_KEY"],
                    "lastCheckedAt": None,
                    "lastSuccessfulCallAt": None,
                    "lastErrorMessage": "failed",
                },
                "incomeStatements": [],
            }

        def get_balance_sheet(self, ticker, period, limit):
            raise AssertionError("Should stop after degraded provider state")

        def get_cash_flow_statement(self, ticker, period, limit):
            raise AssertionError("Should stop after degraded provider state")

        def get_company_profile(self, ticker):
            raise AssertionError("unused")

        def get_key_metrics(self, ticker, period, limit):
            raise AssertionError("unused")

    payload = build_computed_metrics_response(DegradedProvider(), "AAPL", "annual", 5)

    assert payload["computedMetrics"] == []
    assert payload["provider"]["state"] == "degraded"
    assert payload["provider"]["lastErrorMessage"] == "failed"
