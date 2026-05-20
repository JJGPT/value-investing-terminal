from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app
from app.services.fundamentals.provider import get_fundamentals_provider
from app.services.market_data.provider import get_market_data_provider
from app.services.persistence.provider import get_snapshot_repository
from app.services.persistence.sqlite_repository import SCHEMA_VERSION, SQLiteSnapshotRepository
from app.services.provider_status import provider_connected, provider_not_connected
from app.services.watchlists import (
    add_watchlist_item,
    build_watchlist_alerts,
    build_watchlist_alert_history,
    build_watchlist_diagnostics,
    build_watchlist_intelligence,
    build_watchlist_refresh_history,
    build_watchlist_staleness,
    create_watchlist,
    create_watchlist_view,
    duplicate_watchlist_view,
    remove_watchlist_item,
    run_watchlist_refresh_job,
    set_watchlist_view_lifecycle,
    update_watchlist_alert_lifecycle,
    update_watchlist_item,
    update_watchlist_view,
)

client = TestClient(app)


@pytest.fixture(autouse=True)
def clear_provider_state(monkeypatch, tmp_path):
    monkeypatch.delenv("FMP_API_KEY", raising=False)
    monkeypatch.delenv("ALPACA_API_KEY", raising=False)
    monkeypatch.delenv("ALPACA_SECRET_KEY", raising=False)
    monkeypatch.setenv("VALUE_TERMINAL_DB_PATH", str(tmp_path / "watchlists.db"))
    get_settings.cache_clear()
    get_market_data_provider.cache_clear()
    get_snapshot_repository.cache_clear()
    app.dependency_overrides.clear()

    yield

    get_settings.cache_clear()
    get_market_data_provider.cache_clear()
    get_snapshot_repository.cache_clear()
    app.dependency_overrides.clear()


class ConnectedMarketDataProvider:
    def provider_status(self):
        return provider_connected(
            "alpaca",
            "fake market data connected",
            "2026-05-18T12:00:00+00:00",
        )

    def search_securities(self, query):
        return {"query": query, "results": [], "provider": self.provider_status()}

    def get_security(self, ticker):
        return {
            "ticker": ticker.strip().upper(),
            "security": None,
            "provider": self.provider_status(),
        }

    def get_market_snapshot(self, ticker):
        return {
            "ticker": ticker.strip().upper(),
            "price": 80,
            "currency": "USD",
            "marketCap": 1000,
            "enterpriseValue": 1100,
            "volume": 1000000,
            "asOf": "2026-05-18T12:00:00+00:00",
            "provider": self.provider_status(),
            "message": "fake market snapshot",
        }


class NotConnectedMarketDataProvider:
    def provider_status(self):
        return provider_not_connected("alpaca", ["ALPACA_API_KEY", "ALPACA_SECRET_KEY"])

    def search_securities(self, query):
        return {"query": query, "results": [], "provider": self.provider_status()}

    def get_security(self, ticker):
        return {
            "ticker": ticker.strip().upper(),
            "security": None,
            "provider": self.provider_status(),
        }

    def get_market_snapshot(self, ticker):
        return {
            "ticker": ticker.strip().upper(),
            "price": None,
            "currency": None,
            "marketCap": None,
            "enterpriseValue": None,
            "volume": None,
            "asOf": None,
            "provider": self.provider_status(),
            "message": "market data is not connected",
        }


class WatchlistFundamentalsProvider:
    def provider_status(self):
        return provider_connected(
            "fmp",
            "fake fundamentals connected",
            "2026-05-18T12:00:00+00:00",
        )

    def get_company_profile(self, ticker):
        normalized = ticker.strip().upper()

        return {
            "ticker": normalized,
            "profile": {
                **self.source(normalized, None, None),
                "ticker": normalized,
                "name": f"{normalized} Corp.",
                "exchange": "NYSE",
                "sector": "Industrials",
                "industry": "Testing",
                "country": "US",
                "website": None,
                "marketCap": 1000,
                "beta": None,
                "price": 80,
                "description": None,
            },
            "provider": self.provider_status(),
            "message": "fake profile",
        }

    def get_income_statement(self, ticker, period, limit):
        normalized = ticker.strip().upper()

        return self.statement(normalized, period, limit, "incomeStatements", [
            {
                **self.source(normalized, "2025", "FY" if period == "annual" else "Q4"),
                "date": "2025-12-31",
                "revenue": 1000,
                "grossProfit": 500,
                "operatingIncome": 200,
                "ebitda": 250,
                "netIncome": 150,
                "eps": None,
                "epsDiluted": None,
                "sharesDiluted": 10,
            },
            {
                **self.source(normalized, "2024", "FY" if period == "annual" else "Q4"),
                "date": "2024-12-31",
                "revenue": 900,
                "grossProfit": 450,
                "operatingIncome": 180,
                "ebitda": 225,
                "netIncome": 135,
                "eps": None,
                "epsDiluted": None,
                "sharesDiluted": 10,
            },
        ])

    def get_balance_sheet(self, ticker, period, limit):
        normalized = ticker.strip().upper()

        return self.statement(normalized, period, limit, "balanceSheets", [
            {
                **self.source(normalized, "2025", "FY" if period == "annual" else "Q4"),
                "date": "2025-12-31",
                "cashAndEquivalents": 100,
                "totalAssets": 1200,
                "currentAssets": 500,
                "totalLiabilities": 500,
                "currentLiabilities": 250,
                "totalDebt": 200,
                "shareholdersEquity": 700,
                "sharesOutstanding": 10,
            }
        ])

    def get_cash_flow_statement(self, ticker, period, limit):
        normalized = ticker.strip().upper()

        return self.statement(normalized, period, limit, "cashFlowStatements", [
            {
                **self.source(normalized, "2025", "FY" if period == "annual" else "Q4"),
                "date": "2025-12-31",
                "operatingCashFlow": 180,
                "capitalExpenditures": -40,
                "freeCashFlow": 140,
                "dividendsPaid": -20,
                "shareRepurchases": -10,
            },
            {
                **self.source(normalized, "2024", "FY" if period == "annual" else "Q4"),
                "date": "2024-12-31",
                "operatingCashFlow": 160,
                "capitalExpenditures": -35,
                "freeCashFlow": 125,
                "dividendsPaid": -18,
                "shareRepurchases": -8,
            },
        ])

    def get_key_metrics(self, ticker, period, limit):
        normalized = ticker.strip().upper()

        return self.statement(normalized, period, limit, "metrics", [
            {
                **self.source(normalized, "2025", "FY" if period == "annual" else "Q4"),
                "date": "2025-12-31",
                "revenuePerShare": 100,
                "freeCashFlowPerShare": 14,
                "returnOnInvestedCapital": 0.2,
                "debtToEquity": 0.3,
                "priceToEarnings": 16,
                "priceToBook": 2,
                "priceToSales": 4,
            }
        ])

    def source(self, ticker, fiscal_year, fiscal_period):
        return {
            "provider": "fmp",
            "fetchedAt": "2026-05-18T12:00:00+00:00",
            "sourceSymbol": ticker,
            "currency": "USD",
            "fiscalYear": fiscal_year,
            "fiscalPeriod": fiscal_period,
            "qualityFlags": [],
        }

    def statement(self, ticker, period, limit, key, rows):
        return {
            "ticker": ticker,
            "period": period,
            key: rows[:limit],
            "provider": self.provider_status(),
            "message": "fake statement",
        }


def provider_status():
    return provider_connected("platform", "ok", "2026-05-18T12:00:00+00:00")


def timestamp(days_ago=0):
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()


def screener_payload(ticker="AAA", refreshed_at=None):
    refreshed_at = refreshed_at or timestamp()

    return {
        "schemaVersion": SCHEMA_VERSION,
        "provenance": {
            "provider": "platform",
            "providerVersion": "platform-screener-row-v1",
            "fetchedAt": refreshed_at,
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
        "computedAt": refreshed_at,
        "refreshedAt": refreshed_at,
        "row": {
            "ticker": ticker,
            "companyName": f"{ticker} Corp.",
            "currency": "USD",
            "period": "annual",
            "metrics": {"marketCap": 1000, "price": 80},
            "qualityFlags": [],
            "provider": provider_status(),
            "source": {
                "provider": "platform",
                "fetchedAt": refreshed_at,
                "sourceSymbol": ticker,
                "currency": "USD",
                "fiscalYear": "2025",
                "fiscalPeriod": "FY",
                "sourceProviders": ["fmp", "platform"],
            },
            "message": "snapshot row",
        },
    }


def computed_metrics_payload(ticker="AAA", refreshed_at=None):
    refreshed_at = refreshed_at or timestamp()

    return {
        "schemaVersion": SCHEMA_VERSION,
        "provenance": {
            "provider": "platform",
            "providerVersion": "platform-metrics-engine-v1",
            "fetchedAt": refreshed_at,
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
        "computedAt": refreshed_at,
        "refreshedAt": refreshed_at,
        "data": {
            "ticker": ticker,
            "computedMetrics": [
                {
                    "provider": "platform",
                    "fetchedAt": refreshed_at,
                    "sourceSymbol": ticker,
                    "currency": "USD",
                    "fiscalYear": "2025",
                    "fiscalPeriod": "FY",
                    "qualityFlags": [],
                    "grossMargin": 0.5,
                    "operatingMargin": 0.2,
                    "netMargin": 0.15,
                    "freeCashFlowMargin": 0.12,
                    "returnOnEquity": 0.18,
                    "returnOnInvestedCapital": 0.16,
                    "debtToEquity": 0.4,
                }
            ],
        },
    }


def ranking_run_payload(run_id, computed_at, status="eligible", rank=1):
    return {
        "runId": run_id,
        "schemaVersion": SCHEMA_VERSION,
        "strategy": "magic_formula",
        "period": "annual",
        "rankingEngineVersion": "platform-ranking-engine-v1",
        "computedAt": computed_at,
        "universe": {"name": "test", "size": 1, "tickers": ["AAA"]},
        "eligibilitySettings": {},
        "summary": {
            "eligibleRows": 1 if status == "eligible" else 0,
            "ineligibleRows": 1 if status == "ineligible" else 0,
            "unrankedMissingDataRows": 0,
            "excludedRows": 0 if status == "eligible" else 1,
            "engineVersion": "platform-ranking-engine-v1",
        },
        "provider": provider_status(),
        "rows": [
            {
                "rank": rank,
                "ticker": "AAA",
                "companyName": "AAA Corp.",
                "currency": "USD",
                "strategy": "magic_formula",
                "score": 2,
                "scoreComponents": {"earningsYield": 0.1, "returnOnCapital": 0.2},
                "magicFormula": {
                    "inputs": {
                        "ticker": "AAA",
                        "ebit": 100,
                        "enterpriseValue": 1000,
                        "marketCap": 900,
                        "totalDebt": 150,
                        "cashAndEquivalents": 50,
                        "investedCapital": 500,
                        "tangibleCapital": 500,
                        "price": 80,
                        "volume": 1000000,
                        "sector": "Industrials",
                        "industry": "Testing",
                        "currency": "USD",
                        "qualityFlags": [],
                    },
                    "earningsYield": 0.1,
                    "returnOnCapital": 0.2,
                    "earningsYieldRank": 1,
                    "returnOnCapitalRank": 1,
                    "combinedRankScore": 2,
                    "qualityFlags": [],
                    "methodology": "test",
                },
                "eligibilityStatus": status,
                "eligibilityReasons": [] if status == "eligible" else ["below_minimum:marketCap"],
                "qualityFlags": [],
                "provider": provider_status(),
                "source": {},
                "computedAt": computed_at,
                "rankingEngineVersion": "platform-ranking-engine-v1",
                "audit": {},
                "message": "ranking row",
            }
        ],
        "message": "ranking run",
    }


def valuation_payload(updated_at=None):
    updated_at = updated_at or timestamp()

    return {
        "ticker": "AAA",
        "schemaVersion": SCHEMA_VERSION,
        "scenario": {
            "id": "dcf-aaa-base",
            "ticker": "AAA",
            "name": "Base case",
            "schemaVersion": SCHEMA_VERSION,
            "createdAt": updated_at,
            "updatedAt": updated_at,
            "discountRate": {},
            "growth": {},
            "margin": {},
            "reinvestment": {},
            "terminalValue": {},
            "qualityFlags": [],
        },
        "projections": [],
        "sensitivity": {},
        "baseFinancials": {"currency": "USD"},
        "terminalValue": None,
        "presentValueTerminalValue": None,
        "enterpriseValue": 1200,
        "netDebt": None,
        "equityValue": 1200,
        "intrinsicValuePerShare": 120,
        "formulas": [],
        "provider": provider_status(),
        "qualityFlags": [],
        "warnings": [],
        "createdAt": updated_at,
        "updatedAt": updated_at,
        "message": "valuation",
    }


def seed_watchlist_context(repository):
    repository.upsert_screener_row_snapshot("AAA", "annual", screener_payload("AAA"))
    repository.upsert_computed_metrics_snapshot(
        "AAA",
        "annual",
        computed_metrics_payload("AAA"),
    )
    older = timestamp(days_ago=1)
    newer = timestamp()
    repository.create_ranking_run(ranking_run_payload("ranking-old", older, "ineligible", 2))
    repository.create_ranking_run(ranking_run_payload("ranking-new", newer, "eligible", 1))
    scenario = valuation_payload()
    repository.upsert_valuation_scenario("AAA", scenario["scenario"]["id"], scenario)


def test_watchlist_lifecycle_and_item_updates(tmp_path) -> None:
    repository = SQLiteSnapshotRepository(str(tmp_path / "watchlists.db"))
    watchlist = create_watchlist(
        repository,
        {"name": "Compounders", "description": "Quality candidates"},
    )
    updated = add_watchlist_item(
        repository,
        watchlist["watchlistId"],
        {
            "ticker": "aaa",
            "notes": "Initial note",
            "tags": ["quality", "moat"],
            "targetPrice": 100,
            "thesisStatus": "watching",
            "priority": "high",
        },
    )
    patched = update_watchlist_item(
        repository,
        watchlist["watchlistId"],
        "AAA",
        {"notes": "Updated note", "tags": ["quality"], "targetPrice": 110},
    )
    archived = repository.update_watchlist_status(
        watchlist["watchlistId"],
        "archived",
        timestamp(),
    )
    restored = repository.update_watchlist_status(
        watchlist["watchlistId"],
        "active",
        timestamp(),
    )
    removed = remove_watchlist_item(repository, watchlist["watchlistId"], "AAA")

    assert watchlist["schemaVersion"] == 1
    assert updated["items"][0]["ticker"] == "AAA"
    assert patched["items"][0]["notes"] == "Updated note"
    assert patched["items"][0]["targetPrice"] == 110
    assert archived["status"] == "archived"
    assert restored["status"] == "active"
    assert removed["items"] == []


def test_watchlist_intelligence_and_alerts(tmp_path) -> None:
    repository = SQLiteSnapshotRepository(str(tmp_path / "watchlists.db"))
    seed_watchlist_context(repository)
    watchlist = create_watchlist(repository, {"name": "Research", "description": None})
    add_watchlist_item(
        repository,
        watchlist["watchlistId"],
        {"ticker": "AAA", "targetPrice": 100, "notes": "Review"},
    )

    intelligence = build_watchlist_intelligence(
        repository,
        ConnectedMarketDataProvider(),
        watchlist["watchlistId"],
        86400,
    )
    alerts = build_watchlist_alerts(
        repository,
        ConnectedMarketDataProvider(),
        watchlist["watchlistId"],
        86400,
    )
    item = intelligence["items"][0]
    alert_types = {alert["type"] for alert in alerts["alerts"]}

    assert item["marketSnapshot"]["price"] == 80
    assert item["fundamentalsSnapshot"]["state"] == "fresh"
    assert item["computedMetricsSnapshot"]["metrics"]["operatingMargin"] == 0.2
    assert item["ranking"]["rank"] == 1
    assert item["magicFormulaEligibility"]["status"] == "eligible"
    assert item["valuation"]["intrinsicValuePerShare"] == 120
    assert item["valuationGap"]["gapPercent"] == pytest.approx(0.5)
    assert "priceBelowTarget" in alert_types
    assert "valuationGapAboveThreshold" in alert_types
    assert "rankingStatusChanged" in alert_types


def test_saved_watchlist_views_filter_sort_and_lifecycle(tmp_path) -> None:
    repository = SQLiteSnapshotRepository(str(tmp_path / "watchlists.db"))
    seed_watchlist_context(repository)
    watchlist = create_watchlist(repository, {"name": "Research", "description": None})
    add_watchlist_item(
        repository,
        watchlist["watchlistId"],
        {
            "ticker": "AAA",
            "tags": ["quality"],
            "priority": "high",
            "thesisStatus": "researching",
        },
    )
    add_watchlist_item(
        repository,
        watchlist["watchlistId"],
        {
            "ticker": "BBB",
            "tags": ["cyclical"],
            "priority": "low",
            "thesisStatus": "watching",
        },
    )

    view = create_watchlist_view(
        repository,
        watchlist["watchlistId"],
        {
            "name": "Quality work",
            "filters": [{"field": "tags", "operator": "contains", "value": "quality"}],
            "sorting": {"field": "ticker", "direction": "asc"},
            "visibleColumns": ["ticker", "alerts"],
        },
    )
    intelligence = build_watchlist_intelligence(
        repository,
        ConnectedMarketDataProvider(),
        watchlist["watchlistId"],
        86400,
        view_id=view["viewId"],
    )
    updated = update_watchlist_view(
        repository,
        watchlist["watchlistId"],
        view["viewId"],
        {
            "name": "High priority",
            "filters": [{"field": "priority", "operator": "eq", "value": "high"}],
            "sorting": {"field": "priority", "direction": "desc"},
        },
    )
    duplicated = duplicate_watchlist_view(
        repository,
        watchlist["watchlistId"],
        view["viewId"],
        {"name": "Copied lens"},
    )
    archived = set_watchlist_view_lifecycle(
        repository,
        watchlist["watchlistId"],
        view["viewId"],
        "archive",
    )
    restored = set_watchlist_view_lifecycle(
        repository,
        watchlist["watchlistId"],
        view["viewId"],
        "restore",
    )
    deleted = set_watchlist_view_lifecycle(
        repository,
        watchlist["watchlistId"],
        view["viewId"],
        "delete",
    )

    assert view["schemaVersion"] == 1
    assert view["filters"][0]["field"] == "tags"
    assert intelligence["items"][0]["ticker"] == "AAA"
    assert intelligence["allItemCount"] == 2
    assert updated["name"] == "High priority"
    assert updated["filters"][0]["field"] == "priority"
    assert duplicated["parentViewId"] == view["viewId"]
    assert archived["status"] == "archived"
    assert restored["status"] == "active"
    assert deleted["status"] == "deleted"


def test_alert_acknowledgement_dismiss_restore_history(tmp_path) -> None:
    repository = SQLiteSnapshotRepository(str(tmp_path / "watchlists.db"))
    seed_watchlist_context(repository)
    watchlist = create_watchlist(repository, {"name": "Alerts", "description": None})
    add_watchlist_item(
        repository,
        watchlist["watchlistId"],
        {"ticker": "AAA", "targetPrice": 100, "notes": "Review"},
    )
    alerts = build_watchlist_alerts(
        repository,
        ConnectedMarketDataProvider(),
        watchlist["watchlistId"],
        86400,
    )
    alert_id = alerts["alerts"][0]["alertId"]

    acknowledged = update_watchlist_alert_lifecycle(
        repository,
        ConnectedMarketDataProvider(),
        watchlist["watchlistId"],
        alert_id,
        "acknowledge",
        86400,
        acknowledged_by="analyst",
    )
    dismissed = update_watchlist_alert_lifecycle(
        repository,
        ConnectedMarketDataProvider(),
        watchlist["watchlistId"],
        alert_id,
        "dismiss",
        86400,
    )
    restored = update_watchlist_alert_lifecycle(
        repository,
        ConnectedMarketDataProvider(),
        watchlist["watchlistId"],
        alert_id,
        "restore",
        86400,
    )
    history = build_watchlist_alert_history(
        repository,
        ConnectedMarketDataProvider(),
        watchlist["watchlistId"],
        86400,
    )

    assert acknowledged["status"] == "acknowledged"
    assert acknowledged["acknowledgedBy"] == "analyst"
    assert dismissed["status"] == "dismissed"
    assert dismissed["dismissedAt"] is not None
    assert restored["status"] == "acknowledged"
    assert restored["dismissedAt"] is None
    assert any(alert["alertId"] == alert_id for alert in history["alerts"])


def test_missing_inputs_remain_unavailable_and_generate_alerts(tmp_path) -> None:
    repository = SQLiteSnapshotRepository(str(tmp_path / "watchlists.db"))
    watchlist = create_watchlist(repository, {"name": "Sparse", "description": None})
    add_watchlist_item(repository, watchlist["watchlistId"], {"ticker": "MISSING"})

    intelligence = build_watchlist_intelligence(
        repository,
        NotConnectedMarketDataProvider(),
        watchlist["watchlistId"],
        60,
    )
    item = intelligence["items"][0]
    alert_types = {alert["type"] for alert in item["alerts"]}

    assert item["marketSnapshot"]["price"] is None
    assert item["computedMetricsSnapshot"] is None
    assert item["ranking"] is None
    assert item["valuation"] is None
    assert item["valuationGap"]["gapPercent"] is None
    assert "missingCriticalData" in alert_types
    assert "providerDegraded" in alert_types
    assert "snapshotStale" in alert_types


def test_watchlist_staleness_classification_and_workflow_state(tmp_path) -> None:
    repository = SQLiteSnapshotRepository(str(tmp_path / "watchlists.db"))
    seed_watchlist_context(repository)
    watchlist = create_watchlist(repository, {"name": "Workflow", "description": None})
    add_watchlist_item(
        repository,
        watchlist["watchlistId"],
        {"ticker": "AAA", "workflowState": "needs_review"},
    )

    staleness = build_watchlist_staleness(
        repository,
        ConnectedMarketDataProvider(),
        watchlist["watchlistId"],
        86400,
    )
    updated = update_watchlist_item(
        repository,
        watchlist["watchlistId"],
        "AAA",
        {"workflowState": "under_review"},
    )
    filtered = build_watchlist_intelligence(
        repository,
        ConnectedMarketDataProvider(),
        watchlist["watchlistId"],
        86400,
        filters=[{"field": "workflowState", "operator": "eq", "value": "under_review"}],
    )

    assert staleness["items"][0]["state"] in {"fresh", "missing", "stale", "degraded"}
    assert "components" in staleness["items"][0]
    assert updated["items"][0]["workflowState"] == "under_review"
    assert filtered["items"][0]["ticker"] == "AAA"


def test_watchlist_refresh_job_and_history(tmp_path) -> None:
    repository = SQLiteSnapshotRepository(str(tmp_path / "watchlists.db"))
    watchlist = create_watchlist(repository, {"name": "Refresh", "description": None})
    add_watchlist_item(
        repository,
        watchlist["watchlistId"],
        {"ticker": "AAA", "workflowState": "needs_review"},
    )

    job = run_watchlist_refresh_job(
        WatchlistFundamentalsProvider(),
        ConnectedMarketDataProvider(),
        repository,
        watchlist["watchlistId"],
        "annual",
        86400,
        stale_only=False,
    )
    history = build_watchlist_refresh_history(
        repository,
        watchlist["watchlistId"],
        10,
    )

    assert job["jobType"] == "watchlist_refresh"
    assert job["scope"]["watchlistId"] == watchlist["watchlistId"]
    assert job["status"] in {"completed", "failed"}
    assert job["resultMetadata"]["target"] == "watchlist"
    assert history["jobs"][0]["jobId"] == job["jobId"]


def test_watchlist_routes_and_diagnostics_contract(tmp_path) -> None:
    repository = SQLiteSnapshotRepository(str(tmp_path / "watchlists.db"))
    seed_watchlist_context(repository)
    app.dependency_overrides[get_snapshot_repository] = lambda: repository
    app.dependency_overrides[get_market_data_provider] = (
        lambda: ConnectedMarketDataProvider()
    )
    app.dependency_overrides[get_fundamentals_provider] = (
        lambda: WatchlistFundamentalsProvider()
    )

    create_response = client.post(
        "/api/watchlists",
        json={"name": "Route watchlist", "description": "Route test"},
    )
    watchlist_id = create_response.json()["watchlistId"]
    add_response = client.post(
        f"/api/watchlists/{watchlist_id}/items",
        json={
            "ticker": "AAA",
            "notes": "Route note",
            "tags": ["quality"],
            "targetPrice": 100,
            "workflowState": "needs_review",
        },
    )
    list_response = client.get("/api/watchlists")
    get_response = client.get(f"/api/watchlists/{watchlist_id}")
    patch_response = client.patch(
        f"/api/watchlists/{watchlist_id}/items/AAA",
        json={
            "priority": "high",
            "thesisStatus": "researching",
            "workflowState": "under_review",
        },
    )
    intelligence_response = client.get(f"/api/watchlists/{watchlist_id}/intelligence")
    alerts_response = client.get(f"/api/watchlists/{watchlist_id}/alerts")
    alert_id = alerts_response.json()["alerts"][0]["alertId"]
    create_view_response = client.post(
        f"/api/watchlists/{watchlist_id}/views",
        json={
            "name": "Route view",
            "filters": [{"field": "ticker", "operator": "contains", "value": "AAA"}],
            "sorting": {"field": "ticker", "direction": "asc"},
            "visibleColumns": ["ticker", "alerts"],
        },
    )
    view_id = create_view_response.json()["viewId"]
    list_views_response = client.get(f"/api/watchlists/{watchlist_id}/views")
    view_intelligence_response = client.get(
        f"/api/watchlists/{watchlist_id}/intelligence?viewId={view_id}"
    )
    acknowledge_response = client.post(
        f"/api/watchlists/{watchlist_id}/alerts/{alert_id}/acknowledge",
        json={"acknowledgedBy": "route-test"},
    )
    dismiss_response = client.post(
        f"/api/watchlists/{watchlist_id}/alerts/{alert_id}/dismiss"
    )
    history_response = client.get(f"/api/watchlists/{watchlist_id}/alerts/history")
    restore_alert_response = client.post(
        f"/api/watchlists/{watchlist_id}/alerts/{alert_id}/restore"
    )
    staleness_response = client.get(f"/api/watchlists/{watchlist_id}/staleness")
    refresh_response = client.post(
        f"/api/watchlists/{watchlist_id}/refresh",
        params={"period": "annual", "staleOnly": "true"},
    )
    refresh_history_response = client.get(
        f"/api/watchlists/{watchlist_id}/refresh-history"
    )
    diagnostics_response = client.get("/api/diagnostics/watchlists")
    archive_response = client.post(f"/api/watchlists/{watchlist_id}/archive")
    restore_response = client.post(f"/api/watchlists/{watchlist_id}/restore")
    remove_response = client.delete(f"/api/watchlists/{watchlist_id}/items/AAA")

    assert create_response.status_code == 201
    assert add_response.status_code == 201
    assert list_response.status_code == 200
    assert list_response.json()["provider"]["state"] == "connected"
    assert get_response.status_code == 200
    assert patch_response.status_code == 200
    assert patch_response.json()["items"][0]["priority"] == "high"
    assert patch_response.json()["items"][0]["workflowState"] == "under_review"
    assert intelligence_response.status_code == 200
    assert intelligence_response.json()["items"][0]["valuationGap"]["gapPercent"] == pytest.approx(0.5)
    assert alerts_response.status_code == 200
    assert alerts_response.json()["alerts"]
    assert create_view_response.status_code == 201
    assert list_views_response.status_code == 200
    assert list_views_response.json()["views"][0]["viewId"] == view_id
    assert view_intelligence_response.status_code == 200
    assert view_intelligence_response.json()["view"]["viewId"] == view_id
    assert acknowledge_response.status_code == 200
    assert acknowledge_response.json()["acknowledgedBy"] == "route-test"
    assert dismiss_response.status_code == 200
    assert dismiss_response.json()["status"] == "dismissed"
    assert history_response.status_code == 200
    assert any(alert["alertId"] == alert_id for alert in history_response.json()["alerts"])
    assert restore_alert_response.status_code == 200
    assert restore_alert_response.json()["dismissedAt"] is None
    assert staleness_response.status_code == 200
    assert staleness_response.json()["items"][0]["components"]
    assert refresh_response.status_code == 200
    assert refresh_response.json()["jobType"] == "watchlist_refresh"
    assert refresh_history_response.status_code == 200
    assert refresh_history_response.json()["jobs"]
    assert diagnostics_response.status_code == 200
    assert diagnostics_response.json()["watchlistCount"] == 1
    assert diagnostics_response.json()["watchlistItemCount"] == 1
    assert diagnostics_response.json()["alertCount"] >= 1
    assert diagnostics_response.json()["savedWatchlistViewCount"] == 1
    assert diagnostics_response.json()["acknowledgedAlertCount"] >= 1
    assert diagnostics_response.json()["watchlistRefresh"]["jobCount"] >= 1
    assert archive_response.status_code == 200
    assert archive_response.json()["status"] == "archived"
    assert restore_response.status_code == 200
    assert restore_response.json()["status"] == "active"
    assert remove_response.status_code == 200
    assert remove_response.json()["items"] == []


def test_watchlist_diagnostics_counts_stale_items(tmp_path) -> None:
    repository = SQLiteSnapshotRepository(str(tmp_path / "watchlists.db"))
    repository.upsert_screener_row_snapshot(
        "AAA",
        "annual",
        screener_payload("AAA", timestamp(days_ago=2)),
    )
    watchlist = create_watchlist(repository, {"name": "Stale", "description": None})
    add_watchlist_item(repository, watchlist["watchlistId"], {"ticker": "AAA"})

    diagnostics = build_watchlist_diagnostics(
        repository,
        NotConnectedMarketDataProvider(),
        stale_after_seconds=60,
    )

    assert diagnostics["watchlistCount"] == 1
    assert diagnostics["watchlistItemCount"] == 1
    assert diagnostics["staleWatchlistItemCount"] == 1
