from datetime import datetime, timedelta, timezone

import pytest

from app.services.persistence.sqlite_repository import (
    SCHEMA_VERSION,
    SQLiteSnapshotRepository,
)


def snapshot_payload(refreshed_at=None):
    timestamp = refreshed_at or datetime.now(timezone.utc).isoformat()

    return {
        "schemaVersion": SCHEMA_VERSION,
        "provenance": {
            "provider": "fmp",
            "providerVersion": "fmp-stable-v1",
            "fetchedAt": timestamp,
            "sourceSymbol": "AAPL",
        },
        "refreshedAt": timestamp,
        "data": {
            "ticker": "AAPL",
            "profile": {
                "provider": "fmp",
                "fetchedAt": timestamp,
                "sourceSymbol": "AAPL",
                "currency": "USD",
                "fiscalYear": None,
                "fiscalPeriod": None,
                "qualityFlags": [],
                "ticker": "AAPL",
                "name": "Apple Inc.",
            },
        },
    }


def screener_payload(refreshed_at=None):
    timestamp = refreshed_at or datetime.now(timezone.utc).isoformat()

    return {
        "schemaVersion": SCHEMA_VERSION,
        "provenance": {
            "provider": "platform",
            "providerVersion": "platform-screener-row-v1",
            "fetchedAt": timestamp,
            "sourceSymbol": "AAPL",
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
            "ticker": "AAPL",
            "companyName": "Apple Inc.",
            "currency": "USD",
            "period": "annual",
            "metrics": {"marketCap": 1000, "revenue": 100},
            "qualityFlags": [],
            "provider": {
                "provider": "fmp",
                "state": "connected",
                "message": "ok",
                "requiredEnvironmentVariables": [],
                "lastCheckedAt": None,
                "lastSuccessfulCallAt": timestamp,
                "lastErrorMessage": None,
            },
            "source": {
                "provider": "platform",
                "fetchedAt": timestamp,
                "sourceSymbol": "AAPL",
                "currency": "USD",
                "fiscalYear": "2025",
                "fiscalPeriod": "FY",
                "sourceProviders": ["fmp", "platform"],
            },
            "message": "snapshot row",
        },
    }


def valuation_payload(name, intrinsic_value, updated_at=None):
    timestamp = updated_at or datetime.now(timezone.utc).isoformat()

    return {
        "ticker": "AAPL",
        "schemaVersion": SCHEMA_VERSION,
        "scenario": {
            "id": f"dcf-aapl-{name.lower().replace(' ', '-')}",
            "ticker": "AAPL",
            "name": name,
            "schemaVersion": SCHEMA_VERSION,
            "createdAt": timestamp,
            "updatedAt": timestamp,
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
        "enterpriseValue": None,
        "netDebt": None,
        "equityValue": None,
        "intrinsicValuePerShare": intrinsic_value,
        "formulas": [],
        "provider": {
            "provider": "valuation_data",
            "state": "connected",
            "message": "ok",
            "requiredEnvironmentVariables": [],
            "lastCheckedAt": None,
            "lastSuccessfulCallAt": timestamp,
            "lastErrorMessage": None,
        },
        "qualityFlags": [],
        "createdAt": timestamp,
        "updatedAt": timestamp,
        "message": "valuation",
    }


def test_sqlite_repository_initializes_and_persists_universe(tmp_path) -> None:
    repository = SQLiteSnapshotRepository(str(tmp_path / "snapshots.db"))

    repository.upsert_universe("test-universe", [" aapl ", "MSFT", "AAPL"], "test")

    assert repository.repository_status()["state"] == "connected"
    assert repository.list_universe("test-universe") == ["AAPL", "MSFT"]


def test_sqlite_repository_upserts_versioned_fundamentals_snapshot(tmp_path) -> None:
    repository = SQLiteSnapshotRepository(str(tmp_path / "snapshots.db"))

    repository.upsert_fundamentals_snapshot(
        "aapl",
        "profile",
        "profile",
        snapshot_payload(),
    )
    snapshot = repository.get_fundamentals_snapshot("AAPL", "profile", "profile")

    assert snapshot is not None
    assert snapshot["schemaVersion"] == SCHEMA_VERSION
    assert snapshot["provenance"]["provider"] == "fmp"
    assert snapshot["provenance"]["providerVersion"] == "fmp-stable-v1"
    assert snapshot["data"]["profile"]["name"] == "Apple Inc."


def test_sqlite_repository_requires_schema_version_and_provenance(tmp_path) -> None:
    repository = SQLiteSnapshotRepository(str(tmp_path / "snapshots.db"))
    payload = snapshot_payload()
    payload.pop("schemaVersion")

    with pytest.raises(ValueError):
        repository.upsert_fundamentals_snapshot(
            "AAPL",
            "profile",
            "profile",
            payload,
        )


def test_sqlite_repository_reports_snapshot_freshness(tmp_path) -> None:
    repository = SQLiteSnapshotRepository(str(tmp_path / "snapshots.db"))
    old_timestamp = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()

    repository.upsert_universe("test-universe", ["AAPL", "MSFT"], "test")
    repository.upsert_screener_row_snapshot(
        "AAPL",
        "annual",
        screener_payload(old_timestamp),
    )

    summary = repository.snapshot_freshness(
        "test-universe",
        ["AAPL", "MSFT"],
        ["annual"],
        stale_after_seconds=60,
    )[0]

    assert summary["universeSize"] == 2
    assert summary["persistedCount"] == 1
    assert summary["freshCount"] == 0
    assert summary["staleCount"] == 1
    assert summary["missingCount"] == 1


def test_sqlite_repository_lists_valuation_scenarios_newest_first(tmp_path) -> None:
    repository = SQLiteSnapshotRepository(str(tmp_path / "snapshots.db"))
    older_timestamp = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    older = valuation_payload("Base case", 10, older_timestamp)
    newer = valuation_payload("Upside case", 20)

    repository.upsert_valuation_scenario("AAPL", older["scenario"]["id"], older)
    repository.upsert_valuation_scenario("AAPL", newer["scenario"]["id"], newer)

    scenarios = repository.list_valuation_scenarios("aapl", 10)
    latest = repository.get_latest_valuation_scenario("aapl")
    selected = repository.get_valuation_scenario("aapl", older["scenario"]["id"])

    assert [scenario["scenario"]["name"] for scenario in scenarios] == [
        "Upside case",
        "Base case",
    ]
    assert latest["scenario"]["name"] == "Upside case"
    assert selected["intrinsicValuePerShare"] == 10


def test_sqlite_repository_persists_valuation_notes_and_diagnostics(tmp_path) -> None:
    repository = SQLiteSnapshotRepository(str(tmp_path / "snapshots.db"))
    scenario = valuation_payload("Base case", 10)

    repository.upsert_valuation_scenario("AAPL", scenario["scenario"]["id"], scenario)
    version = repository.get_valuation_scenario_version(
        "AAPL",
        scenario["scenario"]["id"],
        scenario["scenario"]["versionId"],
    )
    note = repository.add_valuation_note(
        "AAPL",
        scenario["scenario"]["id"],
        {
            "schemaVersion": SCHEMA_VERSION,
            "attachmentType": "warning",
            "versionId": scenario["scenario"]["versionId"],
            "versionNumber": scenario["scenario"]["versionNumber"],
            "warningCode": "terminal_value_dominance",
            "text": "Review terminal value contribution.",
        },
    )
    notes = repository.list_valuation_notes("AAPL", scenario["scenario"]["id"])
    diagnostics = repository.valuation_repository_diagnostics("AAPL", 60)

    assert version is not None
    assert version["scenario"]["versionNumber"] == 1
    assert note["immutable"] is True
    assert notes[0]["warningCode"] == "terminal_value_dominance"
    assert diagnostics["scenarioCount"] == 1
    assert diagnostics["versionCount"] == 1
    assert diagnostics["noteCount"] == 1
    assert diagnostics["reproducibility"]["incompleteScenarioCount"] == 1
