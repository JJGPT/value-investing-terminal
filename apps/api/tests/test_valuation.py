import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app
from app.services.fundamentals.provider import get_fundamentals_provider
from app.services.market_data.provider import get_market_data_provider
from app.services.persistence.provider import get_snapshot_repository
from app.services.persistence.sqlite_repository import (
    SCHEMA_VERSION,
    SQLiteSnapshotRepository,
)
from app.services.provider_status import provider_connected, provider_not_connected
from app.services.valuation.dcf import build_dcf_comparison, build_dcf_result

client = TestClient(app)


@pytest.fixture(autouse=True)
def clear_provider_state(monkeypatch, tmp_path):
    monkeypatch.delenv("FMP_API_KEY", raising=False)
    monkeypatch.delenv("ALPACA_API_KEY", raising=False)
    monkeypatch.delenv("ALPACA_SECRET_KEY", raising=False)
    monkeypatch.setenv("VALUE_TERMINAL_DB_PATH", str(tmp_path / "valuation.db"))
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


def income_row(year, revenue, operating_income, net_income, shares=100):
    return {
        "provider": "fmp",
        "fetchedAt": "2026-05-18T00:00:00Z",
        "sourceSymbol": "AAPL",
        "currency": "USD",
        "fiscalYear": str(year),
        "fiscalPeriod": "FY",
        "qualityFlags": [],
        "date": f"{year}-12-31",
        "revenue": revenue,
        "grossProfit": revenue * 0.5,
        "operatingIncome": operating_income,
        "ebitda": None,
        "netIncome": net_income,
        "eps": None,
        "epsDiluted": None,
        "sharesDiluted": shares,
    }


def balance_row(year):
    return {
        "provider": "fmp",
        "fetchedAt": "2026-05-18T00:00:00Z",
        "sourceSymbol": "AAPL",
        "currency": "USD",
        "fiscalYear": str(year),
        "fiscalPeriod": "FY",
        "qualityFlags": [],
        "date": f"{year}-12-31",
        "cashAndEquivalents": 100,
        "totalAssets": 1500,
        "currentAssets": 500,
        "totalLiabilities": 650,
        "currentLiabilities": 250,
        "totalDebt": 300,
        "shareholdersEquity": 850,
        "retainedEarnings": None,
    }


def cash_flow_row(year, free_cash_flow):
    return {
        "provider": "fmp",
        "fetchedAt": "2026-05-18T00:00:00Z",
        "sourceSymbol": "AAPL",
        "currency": "USD",
        "fiscalYear": str(year),
        "fiscalPeriod": "FY",
        "qualityFlags": [],
        "date": f"{year}-12-31",
        "operatingCashFlow": free_cash_flow + 50,
        "capitalExpenditures": -50,
        "freeCashFlow": free_cash_flow,
        "dividendsPaid": None,
        "shareRepurchases": None,
        "debtRepayment": None,
        "debtIssuance": None,
        "netChangeInCash": None,
    }


class FakeFundamentalsProvider:
    def provider_status(self):
        return provider_connected("fmp", "fake fundamentals connected")

    def get_company_profile(self, ticker):
        return {
            "ticker": ticker.upper(),
            "profile": {
                "provider": "fmp",
                "fetchedAt": "2026-05-18T00:00:00Z",
                "sourceSymbol": ticker.upper(),
                "currency": "USD",
                "fiscalYear": None,
                "fiscalPeriod": None,
                "qualityFlags": [],
                "ticker": ticker.upper(),
                "name": "Apple Inc.",
                "exchange": "NASDAQ",
                "sector": "Technology",
                "industry": "Hardware",
                "country": "US",
                "website": None,
                "marketCap": 2000,
                "beta": 1.2,
                "price": 20,
                "description": None,
            },
            "provider": self.provider_status(),
            "message": "fake profile",
        }

    def get_income_statement(self, ticker, period, limit):
        return {
            "ticker": ticker.upper(),
            "period": period,
            "limit": limit,
            "incomeStatements": [
                income_row(2025, 1200, 300, 225),
                income_row(2024, 1000, 250, 190),
                income_row(2023, 900, 210, 160),
            ][:limit],
            "provider": self.provider_status(),
            "message": "fake income",
        }

    def get_balance_sheet(self, ticker, period, limit):
        return {
            "ticker": ticker.upper(),
            "period": period,
            "limit": limit,
            "balanceSheets": [balance_row(2025), balance_row(2024)][:limit],
            "provider": self.provider_status(),
            "message": "fake balance",
        }

    def get_cash_flow_statement(self, ticker, period, limit):
        return {
            "ticker": ticker.upper(),
            "period": period,
            "limit": limit,
            "cashFlowStatements": [
                cash_flow_row(2025, 210),
                cash_flow_row(2024, 180),
                cash_flow_row(2023, 150),
            ][:limit],
            "provider": self.provider_status(),
            "message": "fake cash flow",
        }

    def get_key_metrics(self, ticker, period, limit):
        return {
            "ticker": ticker.upper(),
            "period": period,
            "limit": limit,
            "metrics": [],
            "provider": self.provider_status(),
            "message": "fake metrics",
        }


class MissingFundamentalsProvider:
    def provider_status(self):
        return provider_not_connected("fmp", ["FMP_API_KEY"])

    def get_company_profile(self, ticker):
        return {
            "ticker": ticker.upper(),
            "profile": None,
            "provider": self.provider_status(),
            "message": "missing",
        }

    def get_income_statement(self, ticker, period, limit):
        return self.empty(ticker, period, limit, "incomeStatements")

    def get_balance_sheet(self, ticker, period, limit):
        return self.empty(ticker, period, limit, "balanceSheets")

    def get_cash_flow_statement(self, ticker, period, limit):
        return self.empty(ticker, period, limit, "cashFlowStatements")

    def get_key_metrics(self, ticker, period, limit):
        return self.empty(ticker, period, limit, "metrics")

    def empty(self, ticker, period, limit, key):
        return {
            "ticker": ticker.upper(),
            "period": period,
            "limit": limit,
            key: [],
            "provider": self.provider_status(),
            "message": "missing",
        }


class FakeMarketDataProvider:
    def provider_status(self):
        return provider_connected("alpaca", "fake market data connected")

    def get_market_snapshot(self, ticker):
        return {
            "ticker": ticker.upper(),
            "price": 20,
            "currency": "USD",
            "marketCap": None,
            "enterpriseValue": None,
            "volume": None,
            "asOf": "2026-05-18T00:00:00Z",
            "provider": self.provider_status(),
            "message": "fake snapshot",
        }

    def search_securities(self, query):
        raise AssertionError("DCF should not search securities")

    def get_security(self, ticker):
        raise AssertionError("DCF should not fetch security overview")


def test_dcf_calculates_fcff_and_intrinsic_value() -> None:
    result = build_dcf_result(
        "AAPL",
        FakeFundamentalsProvider(),
        FakeMarketDataProvider(),
        overrides={
            "discountRate": {"wacc": 0.09, "taxRate": 0.25},
            "growth": {"revenueGrowthRate": 0.05},
            "margin": {"operatingMargin": 0.25},
            "reinvestment": {"reinvestmentRate": 0.1},
            "terminalValue": {"terminalGrowthRate": 0.025},
        },
    )

    assert result["schemaVersion"] == SCHEMA_VERSION
    assert result["projections"][0]["revenue"] == pytest.approx(1260)
    assert result["projections"][0]["fcff"] == pytest.approx(230.25)
    assert result["terminalValue"] is not None
    assert result["enterpriseValue"] is not None
    assert result["intrinsicValuePerShare"] is not None
    assert (
        "intrinsicValuePerShare = equityValue / projectedSharesDiluted"
        in result["formulas"]
    )
    assert result["modelMetadata"]["valuationMethodologyVersion"] == "fcff-methodology-v1"
    assert result["projectedSharesDiluted"] is not None


def test_dcf_sensitivity_grid_has_three_by_three_cells() -> None:
    result = build_dcf_result(
        "AAPL",
        FakeFundamentalsProvider(),
        FakeMarketDataProvider(),
    )
    grid = result["sensitivity"]["waccTerminalGrowth"]

    assert len(grid["rowValues"]) == 3
    assert len(grid["columnValues"]) == 3
    assert len(grid["cells"]) == 3
    assert len(grid["cells"][0]) == 3
    assert result["sensitivityVisualization"]["heatmaps"]["waccTerminalGrowth"][
        "cells"
    ][0][0]["tone"] in {"low", "mid", "high", "unavailable"}
    assert result["reproducibility"]["statementSnapshotReferences"][
        "incomeStatement"
    ]["fiscalYear"] == "2025"
    assert result["reproducibility"]["valuationEngineVersions"][
        "dcfEngineVersion"
    ] == "platform-fcff-dcf-v1"


def test_dcf_persists_scenario_payload(tmp_path) -> None:
    repository = SQLiteSnapshotRepository(str(tmp_path / "valuation.db"))

    result = build_dcf_result(
        "AAPL",
        FakeFundamentalsProvider(),
        FakeMarketDataProvider(),
        persist=True,
        repository=repository,
    )
    persisted = repository.get_latest_valuation_scenario("AAPL")

    assert persisted is not None
    assert persisted["scenario"]["id"] == result["scenario"]["id"]
    assert persisted["schemaVersion"] == SCHEMA_VERSION
    assert persisted["scenario"]["discountRate"]["wacc"]["editable"] is True


def test_dcf_persists_named_scenarios_and_lists_newest_first(tmp_path) -> None:
    repository = SQLiteSnapshotRepository(str(tmp_path / "valuation.db"))

    base = build_dcf_result(
        "AAPL",
        FakeFundamentalsProvider(),
        FakeMarketDataProvider(),
        overrides={"scenarioName": "Base case"},
        persist=True,
        repository=repository,
    )
    upside = build_dcf_result(
        "AAPL",
        FakeFundamentalsProvider(),
        FakeMarketDataProvider(),
        overrides={
            "scenarioName": "Upside case",
            "growth": {"revenueGrowthRate": 0.08},
        },
        persist=True,
        repository=repository,
    )

    scenarios = repository.list_valuation_scenarios("AAPL", 10)
    comparison = build_dcf_comparison("AAPL", repository, 5)

    assert scenarios[0]["scenario"]["id"] == upside["scenario"]["id"]
    assert scenarios[1]["scenario"]["id"] == base["scenario"]["id"]
    assert comparison["rows"][0]["name"] == "Upside case"
    assert comparison["rows"][0]["assumptions"]["revenueGrowthRate"] == 0.08
    assert scenarios[0]["scenario"]["versionNumber"] == 1
    assert scenarios[0]["scenario"]["versionId"].endswith("-v1")


def test_dcf_creates_immutable_versions_and_audit_history(tmp_path) -> None:
    repository = SQLiteSnapshotRepository(str(tmp_path / "valuation.db"))
    base = build_dcf_result(
        "AAPL",
        FakeFundamentalsProvider(),
        FakeMarketDataProvider(),
        overrides={"scenarioName": "Base case"},
        persist=True,
        repository=repository,
    )
    updated = build_dcf_result(
        "AAPL",
        FakeFundamentalsProvider(),
        FakeMarketDataProvider(),
        overrides={
            "scenarioId": base["scenario"]["id"],
            "priorVersionId": base["scenario"]["versionId"],
            "scenarioName": "Base case",
            "growth": {"revenueGrowthRate": 0.07},
        },
    )
    updated["_auditEvents"] = [
        {
            "changeType": "assumption_update",
            "fieldPath": "growth.revenueGrowthRate",
            "previousValue": 0.05,
            "newValue": 0.07,
        }
    ]
    repository.upsert_valuation_scenario("AAPL", base["scenario"]["id"], updated)

    versions = repository.list_valuation_scenario_versions(
        "AAPL",
        base["scenario"]["id"],
    )
    events = repository.list_valuation_audit_events("AAPL", base["scenario"]["id"])

    assert [version["scenario"]["versionNumber"] for version in versions] == [2, 1]
    assert versions[0]["scenario"]["priorVersionId"] == base["scenario"]["versionId"]
    assert events[0]["changeType"] == "assumption_update"
    assert events[0]["fieldPath"] == "growth.revenueGrowthRate"


def test_dcf_flags_out_of_range_assumptions() -> None:
    result = build_dcf_result(
        "AAPL",
        FakeFundamentalsProvider(),
        FakeMarketDataProvider(),
        overrides={
            "discountRate": {"wacc": 0.01},
            "growth": {"revenueGrowthRate": 0.75},
            "terminalValue": {"terminalGrowthRate": 0.03},
        },
    )

    assert "out_of_range:revenueGrowthRate" in result["qualityFlags"]
    assert "invalid_terminal_spread:wacc_lte_terminal_growth" in result["qualityFlags"]
    assert "warning:wacc_lte_terminal_growth" in result["qualityFlags"]
    assert result["terminalValue"] is None
    assert any(warning["code"] == "projection_instability" for warning in result["warnings"])


def test_dcf_handles_missing_data_with_quality_flags() -> None:
    result = build_dcf_result(
        "AAPL",
        MissingFundamentalsProvider(),
        FakeMarketDataProvider(),
    )

    assert result["intrinsicValuePerShare"] is None
    assert "missing_input:projection" in result["qualityFlags"]
    assert result["provider"]["state"] == "degraded"


def test_dcf_route_contract_and_latest_get(tmp_path) -> None:
    repository = SQLiteSnapshotRepository(str(tmp_path / "valuation.db"))
    app.dependency_overrides[get_fundamentals_provider] = (
        lambda: FakeFundamentalsProvider()
    )
    app.dependency_overrides[get_market_data_provider] = lambda: FakeMarketDataProvider()
    app.dependency_overrides[get_snapshot_repository] = lambda: repository

    response = client.post(
        "/api/valuation/dcf/AAPL",
        json={"discountRate": {"wacc": 0.09}},
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["ticker"] == "AAPL"
    assert payload["scenario"]["discountRate"]["wacc"]["source"] == "user_override"

    latest_response = client.get("/api/valuation/dcf/AAPL")
    latest_payload = latest_response.json()

    assert latest_response.status_code == 200
    assert latest_payload["scenario"]["id"] == payload["scenario"]["id"]


def test_dcf_scenario_management_routes(tmp_path) -> None:
    repository = SQLiteSnapshotRepository(str(tmp_path / "valuation.db"))
    app.dependency_overrides[get_fundamentals_provider] = (
        lambda: FakeFundamentalsProvider()
    )
    app.dependency_overrides[get_market_data_provider] = lambda: FakeMarketDataProvider()
    app.dependency_overrides[get_snapshot_repository] = lambda: repository

    first = client.post(
        "/api/valuation/dcf/AAPL",
        json={"scenarioName": "Base case"},
    ).json()
    second = client.post(
        "/api/valuation/dcf/AAPL",
        json={
            "scenarioName": "Downside case",
            "growth": {"revenueGrowthRate": 0.01},
        },
    ).json()

    list_response = client.get("/api/valuation/dcf/AAPL/scenarios")
    list_payload = list_response.json()
    scenario_response = client.get(
        f"/api/valuation/dcf/AAPL/scenarios/{first['scenario']['id']}"
    )
    comparison_response = client.get("/api/valuation/dcf/AAPL/comparison")
    version_response = client.post(
        f"/api/valuation/dcf/AAPL/scenarios/{first['scenario']['id']}/versions",
        json={"growth": {"revenueGrowthRate": 0.06}},
    )
    history_response = client.get(
        f"/api/valuation/dcf/AAPL/scenarios/{first['scenario']['id']}/history"
    )
    rename_response = client.patch(
        f"/api/valuation/dcf/AAPL/scenarios/{first['scenario']['id']}/rename",
        json={"name": "Renamed case"},
    )
    duplicate_response = client.post(
        f"/api/valuation/dcf/AAPL/scenarios/{first['scenario']['id']}/duplicate",
        json={"name": "Bull case"},
    )
    archive_response = client.post(
        f"/api/valuation/dcf/AAPL/scenarios/{first['scenario']['id']}/archive"
    )
    restore_response = client.post(
        f"/api/valuation/dcf/AAPL/scenarios/{first['scenario']['id']}/restore"
    )
    delete_response = client.delete(
        f"/api/valuation/dcf/AAPL/scenarios/{first['scenario']['id']}"
    )
    missing_response = client.get("/api/valuation/dcf/AAPL/scenarios/missing")

    assert list_response.status_code == 200
    assert list_payload["count"] == 2
    assert list_payload["latestScenarioId"] == second["scenario"]["id"]
    assert scenario_response.status_code == 200
    assert scenario_response.json()["scenario"]["name"] == "Base case"
    assert comparison_response.status_code == 200
    assert comparison_response.json()["rows"][0]["name"] == "Downside case"
    assert version_response.status_code == 200
    assert version_response.json()["scenario"]["versionNumber"] == 2
    assert history_response.status_code == 200
    assert len(history_response.json()["versions"]) >= 2
    assert rename_response.status_code == 200
    assert rename_response.json()["scenario"]["name"] == "Renamed case"
    assert duplicate_response.status_code == 200
    assert duplicate_response.json()["scenario"]["parentScenarioId"] == first["scenario"]["id"]
    assert archive_response.json()["scenario"]["status"] == "archived"
    assert restore_response.json()["scenario"]["status"] == "active"
    assert delete_response.json()["scenario"]["status"] == "deleted"
    assert missing_response.status_code == 404


def test_dcf_compare_import_export_and_notes_routes(tmp_path) -> None:
    repository = SQLiteSnapshotRepository(str(tmp_path / "valuation.db"))
    app.dependency_overrides[get_fundamentals_provider] = (
        lambda: FakeFundamentalsProvider()
    )
    app.dependency_overrides[get_market_data_provider] = lambda: FakeMarketDataProvider()
    app.dependency_overrides[get_snapshot_repository] = lambda: repository

    base = client.post(
        "/api/valuation/dcf/AAPL",
        json={"scenarioName": "Base case"},
    ).json()
    bull = client.post(
        "/api/valuation/dcf/AAPL",
        json={
            "scenarioName": "Bull case",
            "growth": {"revenueGrowthRate": 0.08},
            "margin": {"operatingMargin": 0.28},
        },
    ).json()
    base_version = client.post(
        f"/api/valuation/dcf/AAPL/scenarios/{base['scenario']['id']}/versions",
        json={"growth": {"revenueGrowthRate": 0.04}},
    ).json()

    compare_response = client.get(
        "/api/valuation/dcf/AAPL/compare",
        params={
            "leftScenarioId": base["scenario"]["id"],
            "rightScenarioId": bull["scenario"]["id"],
        },
    )
    version_compare_response = client.get(
        "/api/valuation/dcf/AAPL/compare",
        params={
            "leftScenarioId": base["scenario"]["id"],
            "rightScenarioId": base["scenario"]["id"],
            "leftVersionId": base["scenario"]["versionId"],
            "rightVersionId": base_version["scenario"]["versionId"],
        },
    )
    export_response = client.get(
        f"/api/valuation/dcf/AAPL/export/{base['scenario']['id']}"
    )
    imported_response = client.post(
        "/api/valuation/dcf/AAPL/import",
        json=export_response.json(),
    )
    rejected_import_response = client.post(
        "/api/valuation/dcf/AAPL/import",
        json={"schemaVersion": 999, "modelVersion": "platform-fcff-dcf-v1"},
    )
    note_response = client.post(
        f"/api/valuation/dcf/AAPL/scenarios/{base['scenario']['id']}/notes",
        json={
            "attachmentType": "assumption",
            "fieldPath": "growth.revenueGrowthRate",
            "text": "Revenue case imported from model review.",
        },
    )
    notes_response = client.get(
        f"/api/valuation/dcf/AAPL/scenarios/{base['scenario']['id']}/notes"
    )

    assert compare_response.status_code == 200
    compare_payload = compare_response.json()
    assert compare_payload["left"]["name"] == "Base case"
    assert compare_payload["right"]["name"] == "Bull case"
    assert any(
        row["fieldPath"] == "growth.revenueGrowthRate"
        for row in compare_payload["assumptionDiffs"]
    )
    assert compare_payload["valuationDelta"]["intrinsicValuePerShare"]["delta"] is not None
    assert version_compare_response.status_code == 200
    assert version_compare_response.json()["left"]["versionNumber"] == 1
    assert version_compare_response.json()["right"]["versionNumber"] == 2
    assert export_response.status_code == 200
    assert export_response.json()["schemaVersion"] == SCHEMA_VERSION
    assert export_response.json()["modelVersion"] == "platform-fcff-dcf-v1"
    assert "growth" in export_response.json()["assumptions"]
    assert imported_response.status_code == 200
    assert imported_response.json()["importMetadata"]["schemaVersion"] == SCHEMA_VERSION
    assert rejected_import_response.status_code == 400
    assert note_response.status_code == 200
    assert note_response.json()["immutable"] is True
    assert notes_response.status_code == 200
    assert notes_response.json()["notes"][0]["fieldPath"] == "growth.revenueGrowthRate"


def test_dcf_sensitivity_route_contract(tmp_path) -> None:
    repository = SQLiteSnapshotRepository(str(tmp_path / "valuation.db"))
    app.dependency_overrides[get_fundamentals_provider] = (
        lambda: FakeFundamentalsProvider()
    )
    app.dependency_overrides[get_market_data_provider] = lambda: FakeMarketDataProvider()
    app.dependency_overrides[get_snapshot_repository] = lambda: repository

    response = client.get("/api/valuation/dcf/AAPL/sensitivity")
    payload = response.json()

    assert response.status_code == 200
    assert "waccTerminalGrowth" in payload
    assert "marginWacc" in payload
    assert "marginTerminalGrowth" in payload
