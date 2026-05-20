import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app
from app.services.fundamentals.provider import get_fundamentals_provider
from app.services.market_data.provider import get_market_data_provider
from app.services.persistence.provider import get_snapshot_repository
from app.services.persistence.sqlite_repository import SQLiteSnapshotRepository
from app.services.provider_status import provider_connected, provider_not_connected
from app.services.jobs.runner import (
    cancel_job,
    create_ranking_refresh_job,
    run_ranking_refresh_job,
    run_screener_refresh_job,
)
from app.services.rankings.engine import (
    build_ranking_run_changes,
    build_ranking_response,
    calculate_magic_formula,
    create_ranking_screen,
    refresh_ranking_run,
    set_ranking_screen_lifecycle,
    update_ranking_screen,
)
from app.services.refresh_policies import (
    create_refresh_policy,
    run_due_refresh_policies,
    set_refresh_policy_enabled,
    update_refresh_policy,
)
from app.services.screener.engine import refresh_screener_snapshots
from app.services.screener.universe import PHASE_2D_UNIVERSE_NAME

client = TestClient(app)


@pytest.fixture(autouse=True)
def clear_provider_state(monkeypatch, tmp_path):
    monkeypatch.delenv("FMP_API_KEY", raising=False)
    monkeypatch.delenv("ALPACA_API_KEY", raising=False)
    monkeypatch.delenv("ALPACA_SECRET_KEY", raising=False)
    monkeypatch.setenv("VALUE_TERMINAL_DB_PATH", str(tmp_path / "rankings.db"))
    get_settings.cache_clear()
    get_fundamentals_provider.cache_clear()
    get_market_data_provider.cache_clear()
    get_snapshot_repository.cache_clear()
    app.dependency_overrides.clear()

    yield

    get_settings.cache_clear()
    get_fundamentals_provider.cache_clear()
    get_market_data_provider.cache_clear()
    get_snapshot_repository.cache_clear()
    app.dependency_overrides.clear()


class RankingFundamentalsProvider:
    def provider_status(self):
        return provider_connected(
            "fmp",
            "fake fundamentals connected",
            "2026-05-18T12:00:00+00:00",
        )

    def get_company_profile(self, ticker):
        profile = self.profile(ticker.strip().upper())

        return {
            "ticker": ticker.strip().upper(),
            "profile": profile,
            "provider": self.provider_status(),
            "message": "fake profile",
        }

    def get_income_statement(self, ticker, period, limit):
        normalized_ticker = ticker.strip().upper()
        rows = [
            self.income_row(normalized_ticker, period, 2025),
            self.income_row(normalized_ticker, period, 2024),
        ]

        return self.statement_response(normalized_ticker, period, limit, "incomeStatements", rows)

    def get_balance_sheet(self, ticker, period, limit):
        normalized_ticker = ticker.strip().upper()
        row = self.balance_row(normalized_ticker, period)

        return self.statement_response(normalized_ticker, period, limit, "balanceSheets", [row])

    def get_cash_flow_statement(self, ticker, period, limit):
        normalized_ticker = ticker.strip().upper()
        rows = [
            self.cash_flow_row(normalized_ticker, period, 2025),
            self.cash_flow_row(normalized_ticker, period, 2024),
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
        row = self.key_metrics_row(normalized_ticker, period)

        return self.statement_response(normalized_ticker, period, limit, "metrics", [row])

    def profile(self, ticker):
        market_caps = {"AAA": 1000, "BBB": 500, "CCC": None}

        return {
            "provider": "fmp",
            "fetchedAt": "2026-05-18T12:00:00+00:00",
            "sourceSymbol": ticker,
            "currency": "USD",
            "fiscalYear": None,
            "fiscalPeriod": None,
            "qualityFlags": [],
            "ticker": ticker,
            "name": f"{ticker} Corp.",
            "exchange": "NYSE",
            "sector": "Industrials",
            "industry": "Testing",
            "country": "US",
            "website": None,
            "marketCap": market_caps.get(ticker, 750),
            "beta": None,
            "price": 25,
            "description": None,
        }

    def income_row(self, ticker, period, year):
        revenue = {"AAA": 1000, "BBB": 1000, "CCC": 1000}.get(ticker, 1000)
        ebit = {"AAA": 100, "BBB": 150, "CCC": None}.get(ticker, 100)

        return {
            "provider": "fmp",
            "fetchedAt": "2026-05-18T12:00:00+00:00",
            "sourceSymbol": ticker,
            "currency": "USD",
            "fiscalYear": str(year),
            "fiscalPeriod": "Q4" if period == "quarter" else "FY",
            "qualityFlags": [],
            "date": f"{year}-12-31",
            "revenue": revenue,
            "grossProfit": revenue * 0.5,
            "operatingIncome": ebit,
            "ebitda": None,
            "netIncome": 80 if ebit is not None else None,
            "eps": None,
            "epsDiluted": None,
            "sharesDiluted": 10,
        }

    def balance_row(self, ticker, period):
        debt = {"AAA": 100, "BBB": 50, "CCC": 100}.get(ticker, 100)
        equity = {"AAA": 500, "BBB": 600, "CCC": None}.get(ticker, 500)

        return {
            "provider": "fmp",
            "fetchedAt": "2026-05-18T12:00:00+00:00",
            "sourceSymbol": ticker,
            "currency": "USD",
            "fiscalYear": "2025",
            "fiscalPeriod": "Q4" if period == "quarter" else "FY",
            "qualityFlags": [],
            "date": "2025-12-31",
            "cashAndEquivalents": 50,
            "totalAssets": 1200,
            "currentAssets": 500,
            "totalLiabilities": 700,
            "currentLiabilities": 250,
            "totalDebt": debt,
            "shareholdersEquity": equity,
            "retainedEarnings": None,
        }

    def cash_flow_row(self, ticker, period, year):
        return {
            "provider": "fmp",
            "fetchedAt": "2026-05-18T12:00:00+00:00",
            "sourceSymbol": ticker,
            "currency": "USD",
            "fiscalYear": str(year),
            "fiscalPeriod": "Q4" if period == "quarter" else "FY",
            "qualityFlags": [],
            "date": f"{year}-12-31",
            "operatingCashFlow": 120,
            "capitalExpenditures": -40,
            "freeCashFlow": 80,
            "dividendsPaid": None,
            "shareRepurchases": None,
            "debtRepayment": None,
            "debtIssuance": None,
            "netChangeInCash": None,
        }

    def key_metrics_row(self, ticker, period):
        return {
            "provider": "fmp",
            "fetchedAt": "2026-05-18T12:00:00+00:00",
            "sourceSymbol": ticker,
            "currency": "USD",
            "fiscalYear": "2025",
            "fiscalPeriod": "Q4" if period == "quarter" else "FY",
            "qualityFlags": [],
            "date": "2025-12-31",
            "priceToEarnings": 15,
            "priceToBook": 2,
            "priceToSales": 1,
        }

    def statement_response(self, ticker, period, limit, key, rows):
        return {
            "ticker": ticker,
            "period": period,
            "limit": limit,
            key: rows[:limit],
            "provider": self.provider_status(),
            "message": f"fake {key}",
        }


class ChangedRankingFundamentalsProvider(RankingFundamentalsProvider):
    def income_row(self, ticker, period, year):
        row = super().income_row(ticker, period, year)

        if ticker == "AAA":
            row["operatingIncome"] = 400
            row["netIncome"] = 300

        return row


class FailingRankingFundamentalsProvider(RankingFundamentalsProvider):
    def get_company_profile(self, ticker):
        raise RuntimeError("upstream ranking fixture failure")


class FailingSecretFundamentalsProvider(RankingFundamentalsProvider):
    def get_company_profile(self, ticker):
        raise RuntimeError("FMP_API_KEY leaked fixture failure")


class NotConnectedFundamentalsProvider:
    def provider_status(self):
        return provider_not_connected("fmp", ["FMP_API_KEY"])

    def get_company_profile(self, ticker):
        raise AssertionError("Provider fallback should not run")

    def get_income_statement(self, ticker, period, limit):
        raise AssertionError("Provider fallback should not run")

    def get_balance_sheet(self, ticker, period, limit):
        raise AssertionError("Provider fallback should not run")

    def get_cash_flow_statement(self, ticker, period, limit):
        raise AssertionError("Provider fallback should not run")

    def get_key_metrics(self, ticker, period, limit):
        raise AssertionError("Provider fallback should not run")


class NotConnectedMarketDataProvider:
    def provider_status(self):
        return provider_not_connected("alpaca", ["ALPACA_API_KEY", "ALPACA_SECRET_KEY"])

    def get_market_snapshot(self, ticker):
        raise AssertionError("No market data should be fetched without credentials")

    def search_securities(self, query):
        raise AssertionError("Ranking should not search securities")

    def get_security(self, ticker):
        raise AssertionError("Ranking should not fetch security overview")


def test_magic_formula_calculation_uses_canonical_inputs() -> None:
    result = calculate_magic_formula(
        "AAA",
        {"marketCap": 1000, "currency": "USD"},
        {"operatingIncome": 100, "currency": "USD"},
        {
            "totalDebt": 100,
            "cashAndEquivalents": 50,
            "shareholdersEquity": 500,
            "currency": "USD",
        },
        {"investedCapital": 550},
        None,
    )

    assert result["earningsYield"] == pytest.approx(100 / 1050)
    assert result["returnOnCapital"] == pytest.approx(100 / 550)
    assert result["inputs"]["enterpriseValue"] == 1050
    assert result["inputs"]["investedCapital"] == 550
    assert result["qualityFlags"] == []


def test_magic_formula_missing_inputs_returns_null_and_flags() -> None:
    result = calculate_magic_formula("CCC", None, {}, None, None, None)

    assert result["earningsYield"] is None
    assert result["returnOnCapital"] is None
    assert "missing_input:ebit" in result["qualityFlags"]
    assert "missing_input:marketCap" in result["qualityFlags"]


def test_magic_formula_ranking_sorts_eligible_rows_and_keeps_missing_rows(tmp_path) -> None:
    repository = SQLiteSnapshotRepository(str(tmp_path / "rankings.db"))
    provider = RankingFundamentalsProvider()

    response = build_ranking_response(
        provider,
        NotConnectedMarketDataProvider(),
        repository,
        "magic_formula",
        "annual",
        10,
        universe=["AAA", "BBB", "CCC"],
    )

    assert response["strategy"] == "magic_formula"
    assert response["diagnostics"]["eligibleRows"] == 2
    assert response["diagnostics"]["excludedRows"] == 1
    assert [row["ticker"] for row in response["rows"][:2]] == ["BBB", "AAA"]
    assert response["rows"][0]["rank"] == 1
    assert response["rows"][-1]["ticker"] == "CCC"
    assert response["rows"][-1]["rank"] is None
    assert "excluded_from_ranking:missing_magic_formula_inputs" in response["rows"][-1]["qualityFlags"]


def test_rankings_read_persisted_snapshots_without_provider_fanout(tmp_path) -> None:
    repository = SQLiteSnapshotRepository(str(tmp_path / "rankings.db"))
    refresh_screener_snapshots(
        RankingFundamentalsProvider(),
        repository,
        "annual",
        universe=["AAA", "BBB"],
    )

    response = build_ranking_response(
        NotConnectedFundamentalsProvider(),
        NotConnectedMarketDataProvider(),
        repository,
        "magic_formula",
        "annual",
        10,
    )

    assert response["diagnostics"]["eligibleRows"] == 2
    assert all(row["source"]["snapshot"]["state"] == "persisted" for row in response["rows"])


def test_basic_strategy_ranking_uses_transparent_components(tmp_path) -> None:
    repository = SQLiteSnapshotRepository(str(tmp_path / "rankings.db"))
    response = build_ranking_response(
        RankingFundamentalsProvider(),
        NotConnectedMarketDataProvider(),
        repository,
        "profitability",
        "quarter",
        10,
        universe=["AAA", "BBB"],
    )

    assert response["strategy"] == "profitability"
    assert response["rows"][0]["rank"] == 1
    assert "operatingMargin" in response["rows"][0]["scoreComponents"]


def test_eligibility_rules_classify_ineligible_and_missing_rows(tmp_path) -> None:
    repository = SQLiteSnapshotRepository(str(tmp_path / "rankings.db"))
    response = build_ranking_response(
        RankingFundamentalsProvider(),
        NotConnectedMarketDataProvider(),
        repository,
        "magic_formula",
        "annual",
        10,
        universe=["AAA", "BBB", "CCC"],
        eligibility_settings={"minimumMarketCap": 750},
    )
    rows = {row["ticker"]: row for row in response["rows"]}

    assert rows["AAA"]["eligibilityStatus"] == "eligible"
    assert rows["BBB"]["eligibilityStatus"] == "ineligible"
    assert "below_minimum:marketCap" in rows["BBB"]["eligibilityReasons"]
    assert rows["CCC"]["eligibilityStatus"] == "unranked_missing_data"
    assert "missing_input:ebit" in rows["CCC"]["eligibilityReasons"]
    assert response["diagnostics"]["eligibleRows"] == 1
    assert response["diagnostics"]["ineligibleRows"] == 1
    assert response["diagnostics"]["unrankedMissingDataRows"] == 1


def test_saved_screen_lifecycle_and_ranking_filter_application(tmp_path) -> None:
    repository = SQLiteSnapshotRepository(str(tmp_path / "rankings.db"))
    screen = create_ranking_screen(
        repository,
        {
            "name": "High earnings yield",
            "strategy": "magic_formula",
            "period": "annual",
            "limit": 10,
            "filters": [
                {
                    "field": "earningsYield",
                    "operator": "gt",
                    "value": 0.1,
                }
            ],
            "sorting": {
                "field": "score",
                "direction": "asc",
            },
        },
    )
    updated = update_ranking_screen(
        repository,
        screen["screenId"],
        {"name": "High EY canonical"},
    )
    duplicated = create_ranking_screen(
        repository,
        {
            "name": "Temporary screen",
            "strategy": "quality",
            "period": "quarter",
        },
    )
    archived = set_ranking_screen_lifecycle(
        repository,
        duplicated["screenId"],
        "archive",
    )
    restored = set_ranking_screen_lifecycle(
        repository,
        duplicated["screenId"],
        "restore",
    )
    deleted = set_ranking_screen_lifecycle(
        repository,
        duplicated["screenId"],
        "delete",
    )
    response = build_ranking_response(
        RankingFundamentalsProvider(),
        NotConnectedMarketDataProvider(),
        repository,
        screen["strategy"],
        screen["period"],
        screen["limit"],
        universe=["AAA", "BBB"],
        filters=screen["filters"],
        sorting=screen["sorting"],
    )

    assert screen["schemaVersion"] == 1
    assert updated["name"] == "High EY canonical"
    assert archived["status"] == "archived"
    assert restored["status"] == "active"
    assert deleted["status"] == "deleted"
    assert [row["ticker"] for row in response["rows"]] == ["BBB"]


def test_ranking_run_persistence_and_change_history(tmp_path) -> None:
    repository = SQLiteSnapshotRepository(str(tmp_path / "rankings.db"))
    first_run = refresh_ranking_run(
        RankingFundamentalsProvider(),
        NotConnectedMarketDataProvider(),
        repository,
        "magic_formula",
        "annual",
        universe=["AAA", "BBB"],
    )
    second_run = refresh_ranking_run(
        ChangedRankingFundamentalsProvider(),
        NotConnectedMarketDataProvider(),
        repository,
        "magic_formula",
        "annual",
        universe=["AAA", "BBB"],
    )

    persisted = repository.get_ranking_run(first_run["runId"])
    run_summaries = repository.list_ranking_runs("magic_formula", "annual", 10)
    changes = build_ranking_run_changes(repository, second_run["runId"])
    change_rows = {row["ticker"]: row for row in changes["changes"]}
    diagnostics = repository.ranking_repository_diagnostics(86400)

    assert persisted["schemaVersion"] == 1
    assert persisted["rows"][0]["audit"]["rankingEngineVersion"]
    assert run_summaries[0]["runId"] == second_run["runId"]
    assert changes["previousRun"]["runId"] == first_run["runId"]
    assert change_rows["AAA"]["rankChange"] == 1
    assert change_rows["BBB"]["rankChange"] == -1
    assert diagnostics["runCount"] == 2
    assert diagnostics["rowSnapshotCount"] == 4


def test_refresh_workflow_records_state_scope_and_failures(tmp_path) -> None:
    repository = SQLiteSnapshotRepository(str(tmp_path / "rankings.db"))
    completed = refresh_ranking_run(
        RankingFundamentalsProvider(),
        NotConnectedMarketDataProvider(),
        repository,
        "magic_formula",
        "annual",
        scope_type="tickers",
        tickers=["AAA"],
        stale_only=True,
    )
    failed = refresh_ranking_run(
        FailingRankingFundamentalsProvider(),
        NotConnectedMarketDataProvider(),
        repository,
        "magic_formula",
        "annual",
        scope_type="universe",
        tickers=["AAA"],
    )
    refresh_runs = repository.list_ranking_refresh_runs("magic_formula", "annual", 10)
    diagnostics = repository.ranking_repository_diagnostics(86400)

    assert completed["status"] == "completed"
    assert [transition["state"] for transition in completed["stateTransitions"]] == [
        "queued",
        "running",
        "completed",
    ]
    assert completed["scope"]["type"] == "tickers"
    assert completed["scope"]["staleOnly"] is True
    assert completed["warnings"]
    assert completed["run"]["rows"][0]["ticker"] == "AAA"
    assert failed["status"] == "failed"
    assert failed["errors"][0]["message"]
    assert len(refresh_runs) == 2
    assert diagnostics["refreshRunCount"] == 2
    assert diagnostics["failedRefreshCount"] == 1


def test_ranking_routes_and_diagnostics_contract(tmp_path) -> None:
    repository = SQLiteSnapshotRepository(str(tmp_path / "rankings.db"))
    app.dependency_overrides[get_fundamentals_provider] = (
        lambda: RankingFundamentalsProvider()
    )
    app.dependency_overrides[get_market_data_provider] = (
        lambda: NotConnectedMarketDataProvider()
    )
    app.dependency_overrides[get_snapshot_repository] = lambda: repository

    magic_response = client.get(
        "/api/rankings/magic-formula",
        params={"period": "annual", "limit": 5},
    )
    strategy_response = client.get(
        "/api/rankings",
        params={"strategy": "quality", "period": "annual", "limit": 5},
    )
    diagnostics_response = client.get("/api/diagnostics/rankings")
    refresh_response = client.post(
        "/api/rankings/refresh",
        params={"strategy": "magic_formula", "period": "annual"},
    )

    assert magic_response.status_code == 200
    assert magic_response.json()["strategy"] == "magic_formula"
    assert magic_response.json()["rows"][0]["magicFormula"]["inputs"]["ebit"] is not None
    assert magic_response.json()["rows"][0]["eligibilityStatus"] == "eligible"
    assert strategy_response.status_code == 200
    assert strategy_response.json()["strategy"] == "quality"
    assert diagnostics_response.status_code == 200
    assert "magic_formula" in diagnostics_response.json()["availableStrategies"]
    assert diagnostics_response.json()["eligibleRows"] >= 1
    assert "rankingStore" in diagnostics_response.json()
    assert "jobStore" in diagnostics_response.json()
    assert refresh_response.status_code == 200

    refresh_job = refresh_response.json()
    run_id = refresh_job["resultMetadata"]["runId"]
    runs_response = client.get(
        "/api/rankings/runs",
        params={"strategy": "magic_formula", "period": "annual"},
    )
    run_response = client.get(f"/api/rankings/runs/{run_id}")
    changes_response = client.get(f"/api/rankings/runs/{run_id}/changes")

    assert runs_response.status_code == 200
    assert runs_response.json()["runs"][0]["runId"] == run_id
    assert run_response.status_code == 200
    assert run_response.json()["runId"] == run_id
    assert changes_response.status_code == 200
    assert changes_response.json()["summary"]["newEntrants"] >= 1


def test_saved_screen_and_refresh_routes_contract(tmp_path) -> None:
    repository = SQLiteSnapshotRepository(str(tmp_path / "rankings.db"))
    repository.upsert_universe(
        PHASE_2D_UNIVERSE_NAME,
        ["AAA", "BBB"],
        "ranking-route-test",
    )
    app.dependency_overrides[get_fundamentals_provider] = (
        lambda: RankingFundamentalsProvider()
    )
    app.dependency_overrides[get_market_data_provider] = (
        lambda: NotConnectedMarketDataProvider()
    )
    app.dependency_overrides[get_snapshot_repository] = lambda: repository

    create_response = client.post(
        "/api/rankings/screens",
        json={
            "name": "Route screen",
            "strategy": "magic_formula",
            "period": "annual",
            "filters": [
                {
                    "field": "earningsYield",
                    "operator": "gt",
                    "value": 0.1,
                }
            ],
        },
    )
    assert create_response.status_code == 200
    screen_id = create_response.json()["screenId"]

    list_response = client.get(
        "/api/rankings/screens",
        params={"includeArchived": True},
    )
    get_response = client.get(f"/api/rankings/screens/{screen_id}")
    patch_response = client.patch(
        f"/api/rankings/screens/{screen_id}",
        json={"name": "Route screen renamed"},
    )
    duplicate_response = client.post(
        f"/api/rankings/screens/{screen_id}/duplicate",
        json={"name": "Route screen copy"},
    )
    archive_response = client.post(f"/api/rankings/screens/{screen_id}/archive")
    restore_response = client.post(f"/api/rankings/screens/{screen_id}/restore")
    ranking_response = client.get(
        "/api/rankings",
        params={"screenId": screen_id, "limit": 10},
    )
    refresh_response = client.post(
        "/api/rankings/refresh",
        params={
            "screenId": screen_id,
            "scope": "tickers",
            "tickers": "AAA",
            "staleOnly": True,
        },
    )
    refresh_runs_response = client.get(
        "/api/rankings/refresh-runs",
        params={"strategy": "magic_formula", "period": "annual"},
    )
    diagnostics_response = client.get("/api/diagnostics/rankings")
    delete_response = client.delete(f"/api/rankings/screens/{screen_id}")

    assert list_response.status_code == 200
    assert list_response.json()["screens"][0]["screenId"] == screen_id
    assert get_response.status_code == 200
    assert patch_response.status_code == 200
    assert patch_response.json()["name"] == "Route screen renamed"
    assert duplicate_response.status_code == 200
    assert duplicate_response.json()["parentScreenId"] == screen_id
    assert archive_response.status_code == 200
    assert archive_response.json()["status"] == "archived"
    assert restore_response.status_code == 200
    assert restore_response.json()["status"] == "active"
    assert ranking_response.status_code == 200
    assert [row["ticker"] for row in ranking_response.json()["rows"]] == ["BBB"]
    assert refresh_response.status_code == 200
    assert refresh_response.json()["status"] == "completed"
    assert refresh_runs_response.status_code == 200
    assert refresh_runs_response.json()["refreshRuns"][0]["refreshId"] == refresh_response.json()["resultMetadata"]["refreshId"]
    assert diagnostics_response.status_code == 200
    assert diagnostics_response.json()["rankingStore"]["savedScreenCounts"]["active"] >= 1
    assert diagnostics_response.json()["rankingStore"]["refreshRunCount"] >= 1
    assert diagnostics_response.json()["jobStore"]["jobCount"] >= 1
    assert delete_response.status_code == 200
    assert delete_response.json()["status"] == "deleted"


def test_refresh_job_creation_events_and_cancel(tmp_path) -> None:
    repository = SQLiteSnapshotRepository(str(tmp_path / "rankings.db"))
    job = create_ranking_refresh_job(
        repository,
        "magic_formula",
        "annual",
        scope_type="tickers",
        tickers=["aaa", "AAA", "bbb"],
        stale_only=True,
    )
    events = repository.list_refresh_job_events(job["jobId"])
    cancelled = cancel_job(repository, job["jobId"])
    cancelled_events = repository.list_refresh_job_events(job["jobId"])

    assert job["status"] == "queued"
    assert job["scope"]["tickers"] == ["AAA", "BBB"]
    assert events[0]["eventType"] == "job_created"
    assert events[0]["sequence"] == 1
    assert cancelled["status"] == "cancelled"
    assert cancelled["cancelled"] is True
    assert cancelled_events[-1]["eventType"] == "job_cancelled"


def test_ranking_refresh_job_runs_and_records_result(tmp_path) -> None:
    repository = SQLiteSnapshotRepository(str(tmp_path / "rankings.db"))
    job = run_ranking_refresh_job(
        RankingFundamentalsProvider(),
        NotConnectedMarketDataProvider(),
        repository,
        "magic_formula",
        "annual",
        86400,
        scope_type="tickers",
        tickers=["AAA"],
    )
    events = repository.list_refresh_job_events(job["jobId"])
    diagnostics = repository.refresh_job_repository_diagnostics(86400)

    assert job["status"] == "completed"
    assert job["jobType"] == "ranking_refresh"
    assert job["resultMetadata"]["runId"] == job["result"]["runId"]
    assert job["result"]["run"]["rows"][0]["ticker"] == "AAA"
    assert [event["eventType"] for event in events] == [
        "job_created",
        "job_started",
        "ranking_refresh_completed",
        "job_completed",
    ]
    assert diagnostics["jobCount"] == 1
    assert diagnostics["eventCount"] == 4
    assert diagnostics["statusCounts"]["completed"] == 1


def test_ranking_refresh_job_degrades_to_failed_safely(tmp_path) -> None:
    repository = SQLiteSnapshotRepository(str(tmp_path / "rankings.db"))
    job = run_ranking_refresh_job(
        FailingRankingFundamentalsProvider(),
        NotConnectedMarketDataProvider(),
        repository,
        "magic_formula",
        "annual",
        86400,
        scope_type="tickers",
        tickers=["AAA"],
    )

    assert job["status"] == "failed"
    assert job["errors"][0]["message"]
    assert "FMP_API_KEY" not in job["errors"][0]["message"]


def test_refresh_job_routes_contract(tmp_path) -> None:
    repository = SQLiteSnapshotRepository(str(tmp_path / "rankings.db"))
    app.dependency_overrides[get_fundamentals_provider] = (
        lambda: RankingFundamentalsProvider()
    )
    app.dependency_overrides[get_market_data_provider] = (
        lambda: NotConnectedMarketDataProvider()
    )
    app.dependency_overrides[get_snapshot_repository] = lambda: repository

    create_response = client.post(
        "/api/jobs/ranking-refresh",
        params={
            "strategy": "magic_formula",
            "period": "annual",
            "scope": "tickers",
            "tickers": "AAA",
            "run": False,
        },
    )
    queued_job_id = create_response.json()["jobId"]
    cancel_response = client.post(f"/api/jobs/{queued_job_id}/cancel")
    run_response = client.post(
        "/api/jobs/ranking-refresh",
        params={
            "strategy": "magic_formula",
            "period": "annual",
            "scope": "tickers",
            "tickers": "AAA",
        },
    )
    job_id = run_response.json()["jobId"]
    list_response = client.get("/api/jobs", params={"jobType": "ranking_refresh"})
    get_response = client.get(f"/api/jobs/{job_id}")
    events_response = client.get(f"/api/jobs/{job_id}/events")

    assert create_response.status_code == 200
    assert create_response.json()["status"] == "queued"
    assert cancel_response.status_code == 200
    assert cancel_response.json()["status"] == "cancelled"
    assert run_response.status_code == 200
    assert run_response.json()["status"] == "completed"
    assert get_response.status_code == 200
    assert get_response.json()["jobId"] == job_id
    assert list_response.status_code == 200
    assert list_response.json()["jobs"][0]["jobType"] == "ranking_refresh"
    assert events_response.status_code == 200
    assert events_response.json()["events"][-1]["eventType"] == "job_completed"


def test_stale_only_refresh_skips_fresh_snapshots(tmp_path) -> None:
    repository = SQLiteSnapshotRepository(str(tmp_path / "rankings.db"))
    refresh_screener_snapshots(
        RankingFundamentalsProvider(),
        repository,
        "annual",
        universe=["AAA", "BBB"],
    )

    job = run_ranking_refresh_job(
        FailingRankingFundamentalsProvider(),
        NotConnectedMarketDataProvider(),
        repository,
        "magic_formula",
        "annual",
        86400,
        scope_type="stale_only",
        tickers=["AAA", "BBB"],
        stale_only=True,
    )

    assert job["status"] == "completed"
    assert job["resultMetadata"]["freshCount"] == 2
    assert job["resultMetadata"]["skippedFreshCount"] == 2
    assert job["resultMetadata"]["refreshedCount"] == 0
    assert job["resultMetadata"]["runId"] is None
    assert all(
        row["state"] == "fresh"
        for row in job["resultMetadata"]["staleOnly"]["classification"]
    )


def test_screener_stale_only_refreshes_missing_rows(tmp_path) -> None:
    repository = SQLiteSnapshotRepository(str(tmp_path / "rankings.db"))
    job = run_screener_refresh_job(
        RankingFundamentalsProvider(),
        repository,
        "annual",
        86400,
        scope_type="stale_only",
        tickers=["AAA"],
        stale_only=True,
    )

    assert job["status"] == "completed"
    assert job["jobType"] == "screener_refresh"
    assert job["resultMetadata"]["missingCount"] == 1
    assert job["resultMetadata"]["refreshedCount"] == 1
    assert job["result"]["refreshedCount"] == 1


def test_refresh_policy_lifecycle_run_now_and_due_runner(tmp_path) -> None:
    repository = SQLiteSnapshotRepository(str(tmp_path / "rankings.db"))
    policy = create_refresh_policy(
        repository,
        {
            "name": "Ranking stale policy",
            "target": "ranking",
            "strategy": "magic_formula",
            "period": "annual",
            "scope": {
                "type": "stale_only",
                "tickers": ["AAA"],
            },
            "scheduleHint": "always",
            "staleAfterSeconds": 60,
        },
    )
    renamed = update_refresh_policy(
        repository,
        policy["policyId"],
        {"name": "Ranking stale policy renamed"},
    )
    disabled = set_refresh_policy_enabled(repository, policy["policyId"], False)
    enabled = set_refresh_policy_enabled(repository, policy["policyId"], True)
    due_result = run_due_refresh_policies(
        RankingFundamentalsProvider(),
        NotConnectedMarketDataProvider(),
        repository,
    )
    diagnostics = repository.refresh_policy_repository_diagnostics(60)

    assert renamed["name"] == "Ranking stale policy renamed"
    assert disabled["enabled"] is False
    assert enabled["enabled"] is True
    assert due_result["policiesInspected"] == 1
    assert due_result["duePolicies"] == 1
    assert due_result["jobs"][0]["job"]["status"] == "completed"
    assert repository.get_refresh_policy(policy["policyId"])["lastRunAt"] is not None
    assert diagnostics["policyCount"] == 1
    assert diagnostics["enabledPolicyCount"] == 1
    assert diagnostics["latestPolicyTriggeredJobs"]


def test_refresh_policy_routes_and_no_secret_leakage(tmp_path) -> None:
    repository = SQLiteSnapshotRepository(str(tmp_path / "rankings.db"))
    app.dependency_overrides[get_fundamentals_provider] = (
        lambda: FailingSecretFundamentalsProvider()
    )
    app.dependency_overrides[get_market_data_provider] = (
        lambda: NotConnectedMarketDataProvider()
    )
    app.dependency_overrides[get_snapshot_repository] = lambda: repository

    create_response = client.post(
        "/api/refresh-policies",
        json={
            "name": "Route policy",
            "target": "ranking",
            "strategy": "magic_formula",
            "period": "annual",
            "scope": {
                "type": "stale_only",
                "tickers": ["AAA"],
            },
            "scheduleHint": "always",
            "staleAfterSeconds": 60,
        },
    )
    policy_id = create_response.json()["policyId"]
    list_response = client.get("/api/refresh-policies")
    get_response = client.get(f"/api/refresh-policies/{policy_id}")
    patch_response = client.patch(
        f"/api/refresh-policies/{policy_id}",
        json={"name": "Route policy patched"},
    )
    disable_response = client.post(f"/api/refresh-policies/{policy_id}/disable")
    enable_response = client.post(f"/api/refresh-policies/{policy_id}/enable")
    run_now_response = client.post(f"/api/refresh-policies/{policy_id}/run-now")
    due_response = client.post("/api/jobs/run-due-refresh-policies")
    app.dependency_overrides[get_fundamentals_provider] = (
        lambda: RankingFundamentalsProvider()
    )
    diagnostics_response = client.get("/api/diagnostics/rankings")
    run_now_text = str(run_now_response.json())

    assert create_response.status_code == 200
    assert list_response.status_code == 200
    assert list_response.json()["policies"][0]["policyId"] == policy_id
    assert get_response.status_code == 200
    assert patch_response.status_code == 200
    assert patch_response.json()["name"] == "Route policy patched"
    assert disable_response.status_code == 200
    assert disable_response.json()["enabled"] is False
    assert enable_response.status_code == 200
    assert enable_response.json()["enabled"] is True
    assert run_now_response.status_code == 200
    assert run_now_response.json()["job"]["status"] == "failed"
    assert "FMP_API_KEY" not in run_now_text
    assert due_response.status_code == 200
    assert diagnostics_response.status_code == 200
    assert diagnostics_response.json()["policyStore"]["policyCount"] == 1
    assert diagnostics_response.json()["policyStore"]["staleOnlyRefreshReady"] is True
