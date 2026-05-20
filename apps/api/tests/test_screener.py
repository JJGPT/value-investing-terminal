import json
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app
from app.services.fundamentals.provider import get_fundamentals_provider
from app.services.persistence.provider import get_snapshot_repository
from app.services.persistence.sqlite_repository import (
    SCHEMA_VERSION,
    SQLiteSnapshotRepository,
)
from app.services.provider_status import provider_connected, provider_degraded
from app.services.screener.engine import (
    apply_filters,
    apply_sort,
    build_screener_response,
    build_screener_row,
)

client = TestClient(app)


@pytest.fixture(autouse=True)
def clear_provider_state(monkeypatch, tmp_path):
    monkeypatch.delenv("FMP_API_KEY", raising=False)
    monkeypatch.setenv("VALUE_TERMINAL_DB_PATH", str(tmp_path / "snapshots.db"))
    get_settings.cache_clear()
    get_fundamentals_provider.cache_clear()
    get_snapshot_repository.cache_clear()
    app.dependency_overrides.clear()

    yield

    get_settings.cache_clear()
    get_fundamentals_provider.cache_clear()
    get_snapshot_repository.cache_clear()
    app.dependency_overrides.clear()


class FakeFundamentalsProvider:
    provider_name = "fmp"

    def __init__(self, state="connected", degraded_ticker=None):
        self.state = state
        self.degraded_ticker = degraded_ticker

    def provider_status(self):
        if self.state == "degraded":
            return provider_degraded(
                "fmp",
                "fake degraded provider",
                ["FMP_API_KEY"],
                last_error_message="fake provider error",
            )

        return provider_connected(
            "fmp",
            "fake provider connected",
            "2026-05-18T12:00:00+00:00",
        )

    def get_company_profile(self, ticker):
        normalized_ticker = ticker.strip().upper()

        if normalized_ticker == self.degraded_ticker:
            return self.empty_response(normalized_ticker, "profile")

        profile = {
            "provider": "fmp",
            "fetchedAt": "2026-05-18T12:00:00+00:00",
            "sourceSymbol": normalized_ticker,
            "currency": "USD",
            "fiscalYear": None,
            "fiscalPeriod": None,
            "qualityFlags": [],
            "ticker": normalized_ticker,
            "name": f"{normalized_ticker} Corp.",
            "exchange": "NYSE",
            "sector": "Industrials",
            "industry": "Testing",
            "country": "US",
            "website": None,
            "marketCap": self.revenue_for_ticker(normalized_ticker) * 10,
            "beta": None,
            "price": 25,
            "description": None,
        }

        return {
            "ticker": normalized_ticker,
            "profile": profile,
            "provider": self.provider_status(),
            "message": "fake profile",
        }

    def get_income_statement(self, ticker, period, limit):
        normalized_ticker = ticker.strip().upper()

        if normalized_ticker == self.degraded_ticker:
            return self.empty_statement(normalized_ticker, period, limit, "incomeStatements")

        revenue = self.revenue_for_ticker(normalized_ticker)
        fiscal_period = "Q4" if period == "quarter" else "FY"
        rows = [
            {
                "provider": "fmp",
                "fetchedAt": "2026-05-18T12:00:00+00:00",
                "sourceSymbol": normalized_ticker,
                "currency": "USD",
                "fiscalYear": "2025",
                "fiscalPeriod": fiscal_period,
                "qualityFlags": [],
                "date": "2025-12-31",
                "revenue": revenue,
                "grossProfit": revenue * 0.5,
                "operatingIncome": revenue * 0.2,
                "ebitda": revenue * 0.25,
                "netIncome": revenue * 0.1,
                "eps": None,
                "epsDiluted": None,
                "sharesDiluted": 5,
            },
            {
                "provider": "fmp",
                "fetchedAt": "2026-05-18T12:00:00+00:00",
                "sourceSymbol": normalized_ticker,
                "currency": "USD",
                "fiscalYear": "2024",
                "fiscalPeriod": fiscal_period,
                "qualityFlags": [],
                "date": "2024-12-31",
                "revenue": revenue * 0.8,
                "grossProfit": revenue * 0.4,
                "operatingIncome": revenue * 0.15,
                "ebitda": revenue * 0.2,
                "netIncome": revenue * 0.08,
                "eps": None,
                "epsDiluted": None,
                "sharesDiluted": 5,
            },
        ]

        return self.statement_response(
            normalized_ticker,
            period,
            limit,
            "incomeStatements",
            rows,
        )

    def get_balance_sheet(self, ticker, period, limit):
        normalized_ticker = ticker.strip().upper()

        if normalized_ticker == self.degraded_ticker:
            return self.empty_statement(normalized_ticker, period, limit, "balanceSheets")

        rows = [
            {
                "provider": "fmp",
                "fetchedAt": "2026-05-18T12:00:00+00:00",
                "sourceSymbol": normalized_ticker,
                "currency": "USD",
                "fiscalYear": "2025",
                "fiscalPeriod": "Q4" if period == "quarter" else "FY",
                "qualityFlags": [],
                "date": "2025-12-31",
                "cashAndEquivalents": 5,
                "totalAssets": 100,
                "currentAssets": 60,
                "totalLiabilities": 50,
                "currentLiabilities": 30,
                "totalDebt": 20,
                "shareholdersEquity": 50,
                "retainedEarnings": None,
            }
        ]

        return self.statement_response(
            normalized_ticker,
            period,
            limit,
            "balanceSheets",
            rows,
        )

    def get_cash_flow_statement(self, ticker, period, limit):
        normalized_ticker = ticker.strip().upper()

        if normalized_ticker == self.degraded_ticker:
            return self.empty_statement(
                normalized_ticker,
                period,
                limit,
                "cashFlowStatements",
            )

        rows = [
            {
                "provider": "fmp",
                "fetchedAt": "2026-05-18T12:00:00+00:00",
                "sourceSymbol": normalized_ticker,
                "currency": "USD",
                "fiscalYear": "2025",
                "fiscalPeriod": "Q4" if period == "quarter" else "FY",
                "qualityFlags": [],
                "date": "2025-12-31",
                "operatingCashFlow": 20,
                "capitalExpenditures": -8,
                "freeCashFlow": 12,
                "dividendsPaid": None,
                "shareRepurchases": None,
                "debtRepayment": None,
                "debtIssuance": None,
                "netChangeInCash": None,
            },
            {
                "provider": "fmp",
                "fetchedAt": "2026-05-18T12:00:00+00:00",
                "sourceSymbol": normalized_ticker,
                "currency": "USD",
                "fiscalYear": "2024",
                "fiscalPeriod": "Q4" if period == "quarter" else "FY",
                "qualityFlags": [],
                "date": "2024-12-31",
                "operatingCashFlow": 18,
                "capitalExpenditures": -8,
                "freeCashFlow": 10,
                "dividendsPaid": None,
                "shareRepurchases": None,
                "debtRepayment": None,
                "debtIssuance": None,
                "netChangeInCash": None,
            },
        ]

        return self.statement_response(
            normalized_ticker,
            period,
            limit,
            "cashFlowStatements",
            rows,
        )

    def get_key_metrics(self, ticker, period, limit):
        normalized_ticker = ticker.strip().upper()

        if normalized_ticker == self.degraded_ticker:
            return self.empty_statement(normalized_ticker, period, limit, "metrics")

        rows = [
            {
                "provider": "fmp",
                "fetchedAt": "2026-05-18T12:00:00+00:00",
                "sourceSymbol": normalized_ticker,
                "currency": "USD",
                "fiscalYear": "2025",
                "fiscalPeriod": "Q4" if period == "quarter" else "FY",
                "qualityFlags": [],
                "date": "2025-12-31",
                "priceToEarnings": 25,
                "priceToBook": 2.5,
                "priceToSales": 4,
            }
        ]

        return self.statement_response(
            normalized_ticker,
            period,
            limit,
            "metrics",
            rows,
        )

    def revenue_for_ticker(self, ticker):
        return {
            "AAA": 100,
            "BBB": 200,
            "CCC": 50,
        }.get(ticker, 100)

    def statement_response(self, ticker, period, limit, key, rows):
        return {
            "ticker": ticker,
            "period": period,
            "limit": limit,
            key: rows[:limit],
            "provider": self.provider_status(),
            "message": f"fake {key}",
        }

    def empty_response(self, ticker, response_type):
        return {
            "ticker": ticker,
            response_type: None,
            "provider": self.provider_status(),
            "message": "fake degraded response",
        }

    def empty_statement(self, ticker, period, limit, key):
        return {
            "ticker": ticker,
            "period": period,
            "limit": limit,
            key: [],
            "provider": self.provider_status(),
            "message": "fake degraded response",
        }


class StatusOnlyProvider:
    def provider_status(self):
        return provider_connected("fmp", "status only")

    def get_company_profile(self, ticker):
        raise AssertionError("Snapshot-backed read should not fetch profile")

    def get_income_statement(self, ticker, period, limit):
        raise AssertionError("Snapshot-backed read should not fetch income")

    def get_balance_sheet(self, ticker, period, limit):
        raise AssertionError("Snapshot-backed read should not fetch balance sheet")

    def get_cash_flow_statement(self, ticker, period, limit):
        raise AssertionError("Snapshot-backed read should not fetch cash flow")

    def get_key_metrics(self, ticker, period, limit):
        raise AssertionError("Snapshot-backed read should not fetch key metrics")


def screener_snapshot_payload(
    ticker="AAA",
    refreshed_at=None,
    market_cap=123,
    revenue=100,
):
    timestamp = refreshed_at or datetime.now(timezone.utc).isoformat()

    return {
        "schemaVersion": SCHEMA_VERSION,
        "provenance": {
            "provider": "platform",
            "providerVersion": "platform-screener-row-v1",
            "fetchedAt": timestamp,
            "sourceSymbol": ticker,
        },
        "computedFrom": {
            "statementPeriod": "annual",
            "incomeStatementFiscalYear": "2025",
            "incomeStatementFiscalPeriod": "FY",
            "balanceSheetFiscalYear": "2025",
            "balanceSheetFiscalPeriod": "FY",
            "cashFlowFiscalYear": "2025",
            "cashFlowFiscalPeriod": "FY",
            "keyMetricsFiscalYear": "2025",
            "keyMetricsFiscalPeriod": "FY",
        },
        "computedAt": timestamp,
        "refreshedAt": timestamp,
        "row": {
            "ticker": ticker,
            "companyName": f"{ticker} Snapshot Corp.",
            "currency": "USD",
            "period": "annual",
            "metrics": {
                "bookValuePerShare": None,
                "currentRatio": None,
                "debtToEquity": None,
                "freeCashFlowMargin": None,
                "freeCashFlowPerShare": None,
                "grossMargin": None,
                "marketCap": market_cap,
                "netMargin": None,
                "operatingMargin": None,
                "pbRatio": None,
                "peRatio": None,
                "price": None,
                "psRatio": None,
                "returnOnEquity": None,
                "returnOnInvestedCapital": None,
                "revenue": revenue,
                "revenueGrowthYoY": None,
            },
            "qualityFlags": [],
            "provider": provider_connected("fmp", "snapshot row provider"),
            "source": {
                "provider": "platform",
                "fetchedAt": timestamp,
                "sourceSymbol": ticker,
                "currency": "USD",
                "fiscalYear": "2025",
                "fiscalPeriod": "FY",
                "sourceProviders": ["fmp", "platform"],
            },
            "message": "snapshot row",
        },
    }


def test_filter_evaluation_supports_numeric_operators() -> None:
    rows = [
        {"metrics": {"returnOnEquity": 0.2}},
        {"metrics": {"returnOnEquity": 0.1}},
        {"metrics": {"returnOnEquity": None}},
    ]

    assert len(
        apply_filters(
            rows,
            [{"field": "returnOnEquity", "operator": "gte", "value": 0.15}],
        )
    ) == 1
    assert len(
        apply_filters(
            rows,
            [{"field": "returnOnEquity", "operator": "between", "value": [0.09, 0.21]}],
        )
    ) == 2


def test_sorting_places_missing_values_last() -> None:
    rows = [
        {"ticker": "AAA", "metrics": {"marketCap": 100}},
        {"ticker": "BBB", "metrics": {"marketCap": None}},
        {"ticker": "CCC", "metrics": {"marketCap": 200}},
    ]

    sorted_rows = apply_sort(rows, {"field": "marketCap", "direction": "desc"})

    assert [row["ticker"] for row in sorted_rows] == ["CCC", "AAA", "BBB"]


def test_screener_response_filters_sorts_and_paginates() -> None:
    payload = build_screener_response(
        FakeFundamentalsProvider(),
        period="annual",
        page=1,
        limit=2,
        filters=[{"field": "revenue", "operator": "gte", "value": 100}],
        sort={"field": "marketCap", "direction": "desc"},
        universe=["AAA", "BBB", "CCC"],
    )

    assert payload["provider"]["state"] == "connected"
    assert payload["pagination"] == {
        "page": 1,
        "limit": 2,
        "total": 2,
        "totalPages": 1,
        "hasNextPage": False,
        "hasPreviousPage": False,
    }
    assert [row["ticker"] for row in payload["rows"]] == ["BBB", "AAA"]
    assert payload["rows"][0]["metrics"]["grossMargin"] == 0.5
    assert payload["rows"][0]["metrics"]["revenueGrowthYoY"] == 0.25
    assert "provider_reference_metric:peRatio" in payload["rows"][0]["qualityFlags"]


def test_screener_row_handles_missing_metrics_and_quality_flags() -> None:
    provider = FakeFundamentalsProvider(degraded_ticker="AAA")

    row = build_screener_row(provider, "AAA", "annual")

    assert row["provider"]["state"] == "connected"
    assert row["metrics"]["revenue"] is None
    assert "missing_metric:revenue" in row["qualityFlags"]
    assert "missing_metric:returnOnInvestedCapital" in row["qualityFlags"]


def test_screener_supports_quarterly_mode() -> None:
    payload = build_screener_response(
        FakeFundamentalsProvider(),
        period="quarter",
        page=1,
        limit=1,
        filters=[],
        sort={"field": "revenue", "direction": "asc"},
        universe=["AAA", "BBB"],
    )

    assert payload["query"]["period"] == "quarter"
    assert payload["rows"][0]["period"] == "quarter"
    assert payload["rows"][0]["source"]["fiscalPeriod"] == "Q4"


def test_screener_reads_persisted_rows_without_provider_fetch(tmp_path) -> None:
    repository = SQLiteSnapshotRepository(str(tmp_path / "snapshots.db"))
    repository.upsert_universe("phase-2d-development-universe", ["AAA"], "test")
    repository.upsert_screener_row_snapshot(
        "AAA",
        "annual",
        screener_snapshot_payload("AAA", market_cap=999),
    )

    payload = build_screener_response(
        StatusOnlyProvider(),
        period="annual",
        page=1,
        limit=10,
        filters=[],
        sort=None,
        universe=["AAA"],
        repository=repository,
    )

    assert payload["rows"][0]["ticker"] == "AAA"
    assert payload["rows"][0]["metrics"]["marketCap"] == 999
    assert payload["rows"][0]["snapshot"]["state"] == "persisted"
    assert payload["rows"][0]["snapshot"]["schemaVersion"] == SCHEMA_VERSION


def test_screener_falls_back_to_provider_for_missing_snapshots(tmp_path) -> None:
    repository = SQLiteSnapshotRepository(str(tmp_path / "snapshots.db"))
    repository.upsert_universe("phase-2d-development-universe", ["AAA", "BBB"], "test")
    repository.upsert_screener_row_snapshot(
        "AAA",
        "annual",
        screener_snapshot_payload("AAA", market_cap=999),
    )

    payload = build_screener_response(
        FakeFundamentalsProvider(),
        period="annual",
        page=1,
        limit=10,
        filters=[],
        sort={"field": "marketCap", "direction": "desc"},
        universe=["AAA", "BBB"],
        repository=repository,
    )
    rows_by_ticker = {row["ticker"]: row for row in payload["rows"]}

    assert rows_by_ticker["AAA"]["snapshot"]["state"] == "persisted"
    assert rows_by_ticker["BBB"]["snapshot"]["state"] == "provider_fallback"
    assert rows_by_ticker["BBB"]["metrics"]["revenue"] == 200.0


def test_screener_uses_stale_snapshots_without_provider_fetch(tmp_path) -> None:
    repository = SQLiteSnapshotRepository(str(tmp_path / "snapshots.db"))
    old_timestamp = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
    repository.upsert_universe("phase-2d-development-universe", ["AAA"], "test")
    repository.upsert_screener_row_snapshot(
        "AAA",
        "annual",
        screener_snapshot_payload("AAA", refreshed_at=old_timestamp),
    )

    payload = build_screener_response(
        StatusOnlyProvider(),
        period="annual",
        page=1,
        limit=10,
        filters=[],
        sort=None,
        universe=["AAA"],
        repository=repository,
        stale_after_seconds=60,
    )

    assert payload["rows"][0]["snapshot"]["state"] == "persisted"
    assert payload["rows"][0]["snapshot"]["isStale"] is True


def test_screener_route_contract_without_credentials() -> None:
    response = client.get("/api/screener")

    assert response.status_code == 200
    payload = response.json()
    assert payload["rows"] == []
    assert payload["provider"]["state"] == "not_connected"
    assert payload["universe"]["size"] == 12
    assert payload["query"]["period"] == "annual"
    assert payload["pagination"]["total"] == 0


def test_screener_refresh_route_writes_snapshots(tmp_path) -> None:
    repository = SQLiteSnapshotRepository(str(tmp_path / "snapshots.db"))
    app.dependency_overrides[get_fundamentals_provider] = (
        lambda: FakeFundamentalsProvider()
    )
    app.dependency_overrides[get_snapshot_repository] = lambda: repository

    response = client.post("/api/screener/refresh", params={"period": "annual"})
    payload = response.json()

    assert response.status_code == 200
    assert payload["status"] == "completed"
    assert payload["refreshedCount"] == 12
    assert payload["failedCount"] == 0
    assert repository.list_universe("phase-2d-development-universe")
    snapshot = repository.get_screener_row_snapshot("AAPL", "annual")
    computed = repository.get_computed_metrics_snapshot("AAPL", "annual")

    assert snapshot is not None
    assert snapshot["schemaVersion"] == SCHEMA_VERSION
    assert snapshot["provenance"]["providerVersion"] == "platform-screener-row-v1"
    assert snapshot["computedFrom"]["incomeStatementFiscalYear"] == "2025"
    assert computed is not None
    assert computed["computedFrom"]["statementPeriod"] == "annual"


def test_screener_route_uses_mocked_provider_without_real_calls() -> None:
    app.dependency_overrides[get_fundamentals_provider] = (
        lambda: FakeFundamentalsProvider()
    )
    filters = json.dumps(
        [{"field": "returnOnInvestedCapital", "operator": "gt", "value": 0.1}]
    )

    response = client.get(
        "/api/screener",
        params={
            "filters": filters,
            "sort": "marketCap:desc",
            "period": "annual",
            "limit": 3,
        },
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["provider"]["state"] == "connected"
    assert payload["rows"]
    assert payload["rows"][0]["ticker"] == "AAPL"
    assert payload["rows"][0]["metrics"]["returnOnInvestedCapital"] is not None
    assert payload["rows"][0]["provider"]["state"] == "connected"


def test_screener_route_reports_degraded_provider() -> None:
    app.dependency_overrides[get_fundamentals_provider] = (
        lambda: FakeFundamentalsProvider(state="degraded")
    )

    response = client.get("/api/screener")
    payload = response.json()
    response_text = json.dumps(payload)

    assert response.status_code == 200
    assert payload["provider"]["state"] == "degraded"
    assert "fake provider error" in response_text
