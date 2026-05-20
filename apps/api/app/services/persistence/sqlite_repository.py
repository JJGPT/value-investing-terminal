import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

SCHEMA_VERSION = 1


class SQLiteSnapshotRepository:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS securities_universe (
                    universe_name TEXT NOT NULL,
                    ticker TEXT NOT NULL,
                    company_name TEXT,
                    currency TEXT,
                    source TEXT NOT NULL,
                    active INTEGER NOT NULL DEFAULT 1,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (universe_name, ticker)
                );

                CREATE TABLE IF NOT EXISTS fundamentals_snapshots (
                    ticker TEXT NOT NULL,
                    period TEXT NOT NULL,
                    snapshot_type TEXT NOT NULL,
                    schema_version INTEGER NOT NULL,
                    provider TEXT,
                    provider_version TEXT,
                    source_symbol TEXT,
                    fetched_at TEXT,
                    fiscal_year TEXT,
                    fiscal_period TEXT,
                    refreshed_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    PRIMARY KEY (ticker, period, snapshot_type)
                );

                CREATE TABLE IF NOT EXISTS computed_metric_snapshots (
                    ticker TEXT NOT NULL,
                    period TEXT NOT NULL,
                    schema_version INTEGER NOT NULL,
                    provider TEXT,
                    provider_version TEXT,
                    source_symbol TEXT,
                    fetched_at TEXT,
                    fiscal_year TEXT,
                    fiscal_period TEXT,
                    computed_at TEXT,
                    refreshed_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    PRIMARY KEY (ticker, period)
                );

                CREATE TABLE IF NOT EXISTS screener_row_snapshots (
                    ticker TEXT NOT NULL,
                    period TEXT NOT NULL,
                    schema_version INTEGER NOT NULL,
                    provider TEXT,
                    provider_version TEXT,
                    source_symbol TEXT,
                    fetched_at TEXT,
                    fiscal_year TEXT,
                    fiscal_period TEXT,
                    computed_at TEXT,
                    refreshed_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    PRIMARY KEY (ticker, period)
                );

                CREATE TABLE IF NOT EXISTS snapshot_refresh_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    period TEXT NOT NULL,
                    status TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    completed_at TEXT NOT NULL,
                    universe_size INTEGER NOT NULL,
                    refreshed_count INTEGER NOT NULL,
                    failed_count INTEGER NOT NULL,
                    error_message TEXT
                );

                CREATE TABLE IF NOT EXISTS valuation_scenarios (
                    scenario_id TEXT PRIMARY KEY,
                    ticker TEXT NOT NULL,
                    schema_version INTEGER NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active',
                    parent_scenario_id TEXT,
                    latest_version_id TEXT,
                    latest_version_number INTEGER NOT NULL DEFAULT 1,
                    archived_at TEXT,
                    deleted_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_valuation_scenarios_ticker_updated
                ON valuation_scenarios(ticker, updated_at);

                CREATE TABLE IF NOT EXISTS valuation_scenario_versions (
                    version_id TEXT PRIMARY KEY,
                    scenario_id TEXT NOT NULL,
                    ticker TEXT NOT NULL,
                    version_number INTEGER NOT NULL,
                    schema_version INTEGER NOT NULL,
                    model_version TEXT,
                    parent_scenario_id TEXT,
                    prior_version_id TEXT,
                    created_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_valuation_versions_scenario
                ON valuation_scenario_versions(ticker, scenario_id, version_number);

                CREATE TABLE IF NOT EXISTS valuation_audit_events (
                    event_id TEXT PRIMARY KEY,
                    scenario_id TEXT NOT NULL,
                    ticker TEXT NOT NULL,
                    version_id TEXT,
                    version_number INTEGER,
                    change_type TEXT NOT NULL,
                    field_path TEXT,
                    previous_value_json TEXT,
                    new_value_json TEXT,
                    created_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_valuation_audit_scenario
                ON valuation_audit_events(ticker, scenario_id, created_at);

                CREATE TABLE IF NOT EXISTS valuation_notes (
                    note_id TEXT PRIMARY KEY,
                    scenario_id TEXT NOT NULL,
                    ticker TEXT NOT NULL,
                    version_id TEXT,
                    version_number INTEGER,
                    attachment_type TEXT NOT NULL,
                    field_path TEXT,
                    warning_code TEXT,
                    created_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_valuation_notes_scenario
                ON valuation_notes(ticker, scenario_id, created_at);

                CREATE TABLE IF NOT EXISTS ranking_runs (
                    run_id TEXT PRIMARY KEY,
                    strategy TEXT NOT NULL,
                    period TEXT NOT NULL,
                    schema_version INTEGER NOT NULL,
                    ranking_engine_version TEXT NOT NULL,
                    computed_at TEXT NOT NULL,
                    universe_json TEXT NOT NULL,
                    eligibility_settings_json TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_ranking_runs_strategy_period
                ON ranking_runs(strategy, period, computed_at);

                CREATE TABLE IF NOT EXISTS ranking_row_snapshots (
                    run_id TEXT NOT NULL,
                    ticker TEXT NOT NULL,
                    strategy TEXT NOT NULL,
                    period TEXT NOT NULL,
                    rank INTEGER,
                    eligibility_status TEXT NOT NULL,
                    score REAL,
                    computed_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    PRIMARY KEY (run_id, ticker)
                );

                CREATE INDEX IF NOT EXISTS idx_ranking_row_snapshots_run
                ON ranking_row_snapshots(run_id, eligibility_status, rank);

                CREATE TABLE IF NOT EXISTS ranking_saved_screens (
                    screen_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    name TEXT NOT NULL,
                    strategy TEXT NOT NULL,
                    period TEXT NOT NULL,
                    limit_value INTEGER NOT NULL,
                    schema_version INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    archived_at TEXT,
                    deleted_at TEXT,
                    payload_json TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_ranking_saved_screens_status
                ON ranking_saved_screens(status, updated_at);

                CREATE TABLE IF NOT EXISTS ranking_refresh_runs (
                    refresh_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    strategy TEXT NOT NULL,
                    period TEXT NOT NULL,
                    scope_json TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT,
                    failed_at TEXT,
                    duration_ms INTEGER,
                    warnings_json TEXT NOT NULL,
                    errors_json TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_ranking_refresh_runs_strategy
                ON ranking_refresh_runs(strategy, period, started_at);

                CREATE TABLE IF NOT EXISTS refresh_jobs (
                    job_id TEXT PRIMARY KEY,
                    job_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    schema_version INTEGER NOT NULL,
                    scope_json TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT,
                    failed_at TEXT,
                    duration_ms INTEGER,
                    warnings_json TEXT NOT NULL,
                    errors_json TEXT NOT NULL,
                    result_metadata_json TEXT NOT NULL,
                    job_json TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_refresh_jobs_type_status
                ON refresh_jobs(job_type, status, created_at);

                CREATE TABLE IF NOT EXISTS refresh_job_events (
                    event_id TEXT PRIMARY KEY,
                    job_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    event_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    message TEXT,
                    created_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_refresh_job_events_job
                ON refresh_job_events(job_id, sequence);

                CREATE TABLE IF NOT EXISTS refresh_policies (
                    policy_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    target TEXT NOT NULL,
                    strategy TEXT NOT NULL,
                    period TEXT NOT NULL,
                    enabled INTEGER NOT NULL,
                    schedule_hint TEXT NOT NULL,
                    stale_after_seconds INTEGER NOT NULL,
                    last_run_at TEXT,
                    next_run_hint TEXT,
                    schema_version INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_refresh_policies_enabled
                ON refresh_policies(enabled, next_run_hint, updated_at);

                CREATE TABLE IF NOT EXISTS watchlists (
                    watchlist_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT,
                    schema_version INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    archived_at TEXT,
                    deleted_at TEXT,
                    payload_json TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_watchlists_status
                ON watchlists(status, updated_at);

                CREATE TABLE IF NOT EXISTS watchlist_items (
                    watchlist_id TEXT NOT NULL,
                    ticker TEXT NOT NULL,
                    company_name TEXT,
                    added_at TEXT NOT NULL,
                    notes TEXT,
                    tags_json TEXT NOT NULL,
                    target_price REAL,
                    thesis_status TEXT,
                    priority TEXT,
                    workflow_state TEXT,
                    updated_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    PRIMARY KEY (watchlist_id, ticker)
                );

                CREATE INDEX IF NOT EXISTS idx_watchlist_items_ticker
                ON watchlist_items(ticker);

                CREATE TABLE IF NOT EXISTS watchlist_views (
                    view_id TEXT PRIMARY KEY,
                    watchlist_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    name TEXT NOT NULL,
                    filters_json TEXT NOT NULL,
                    sorting_json TEXT,
                    visible_columns_json TEXT NOT NULL,
                    schema_version INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    archived_at TEXT,
                    deleted_at TEXT,
                    payload_json TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_watchlist_views_watchlist_status
                ON watchlist_views(watchlist_id, status, updated_at);

                CREATE TABLE IF NOT EXISTS watchlist_alert_events (
                    alert_id TEXT PRIMARY KEY,
                    watchlist_id TEXT NOT NULL,
                    ticker TEXT NOT NULL,
                    alert_type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    acknowledged_at TEXT,
                    acknowledged_by TEXT,
                    dismissed_at TEXT,
                    schema_version INTEGER NOT NULL,
                    payload_json TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_watchlist_alert_events_watchlist
                ON watchlist_alert_events(watchlist_id, status, created_at);
                """
            )
            ensure_columns(
                connection,
                "valuation_scenarios",
                {
                    "status": "TEXT NOT NULL DEFAULT 'active'",
                    "parent_scenario_id": "TEXT",
                    "latest_version_id": "TEXT",
                    "latest_version_number": "INTEGER NOT NULL DEFAULT 1",
                    "archived_at": "TEXT",
                    "deleted_at": "TEXT",
                },
            )
            ensure_columns(
                connection,
                "watchlists",
                {
                    "status": "TEXT NOT NULL DEFAULT 'active'",
                    "archived_at": "TEXT",
                    "deleted_at": "TEXT",
                },
            )
            ensure_columns(
                connection,
                "watchlist_items",
                {
                    "company_name": "TEXT",
                    "tags_json": "TEXT NOT NULL DEFAULT '[]'",
                    "target_price": "REAL",
                    "thesis_status": "TEXT",
                    "priority": "TEXT",
                    "workflow_state": "TEXT",
                    "updated_at": "TEXT",
                },
            )
            ensure_columns(
                connection,
                "watchlist_views",
                {
                    "archived_at": "TEXT",
                    "deleted_at": "TEXT",
                },
            )
            ensure_columns(
                connection,
                "watchlist_alert_events",
                {
                    "acknowledged_at": "TEXT",
                    "acknowledged_by": "TEXT",
                    "dismissed_at": "TEXT",
                },
            )

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row

        return connection

    def repository_status(self) -> dict:
        try:
            with self.connect() as connection:
                connection.execute("SELECT 1").fetchone()

            return {
                "provider": "sqlite",
                "state": "connected",
                "message": "SQLite snapshot repository is available.",
                "path": self.db_path,
            }
        except sqlite3.Error as error:
            return {
                "provider": "sqlite",
                "state": "degraded",
                "message": f"SQLite snapshot repository failed: {error}",
                "path": self.db_path,
            }

    def upsert_universe(
        self,
        universe_name: str,
        tickers: list[str],
        source: str,
    ) -> None:
        now = utc_now()
        normalized_tickers = normalize_tickers(tickers)

        with self.connect() as connection:
            for ticker in normalized_tickers:
                connection.execute(
                    """
                    INSERT INTO securities_universe (
                        universe_name, ticker, source, active, updated_at
                    )
                    VALUES (?, ?, ?, 1, ?)
                    ON CONFLICT(universe_name, ticker) DO UPDATE SET
                        source = excluded.source,
                        active = 1,
                        updated_at = excluded.updated_at
                    """,
                    (universe_name, ticker, source, now),
                )

            if normalized_tickers:
                placeholders = ",".join("?" for _ in normalized_tickers)
                connection.execute(
                    f"""
                    UPDATE securities_universe
                    SET active = 0, updated_at = ?
                    WHERE universe_name = ?
                    AND ticker NOT IN ({placeholders})
                    """,
                    [now, universe_name, *normalized_tickers],
                )

    def list_universe(self, universe_name: str) -> list[str]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT ticker
                FROM securities_universe
                WHERE universe_name = ? AND active = 1
                ORDER BY ticker
                """,
                (universe_name,),
            ).fetchall()

        return [row["ticker"] for row in rows]

    def upsert_fundamentals_snapshot(
        self,
        ticker: str,
        period: str,
        snapshot_type: str,
        payload: dict,
    ) -> None:
        self.upsert_snapshot(
            "fundamentals_snapshots",
            normalize_ticker(ticker),
            normalize_period(period),
            payload,
            snapshot_type=snapshot_type,
        )

    def get_fundamentals_snapshot(
        self,
        ticker: str,
        period: str,
        snapshot_type: str,
    ) -> Optional[dict]:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM fundamentals_snapshots
                WHERE ticker = ? AND period = ? AND snapshot_type = ?
                """,
                (normalize_ticker(ticker), normalize_period(period), snapshot_type),
            ).fetchone()

        return row_to_snapshot(row)

    def upsert_computed_metrics_snapshot(
        self,
        ticker: str,
        period: str,
        payload: dict,
    ) -> None:
        self.upsert_snapshot(
            "computed_metric_snapshots",
            normalize_ticker(ticker),
            normalize_period(period),
            payload,
        )

    def get_computed_metrics_snapshot(
        self,
        ticker: str,
        period: str,
    ) -> Optional[dict]:
        return self.get_period_snapshot(
            "computed_metric_snapshots",
            ticker,
            period,
        )

    def upsert_screener_row_snapshot(
        self,
        ticker: str,
        period: str,
        payload: dict,
    ) -> None:
        self.upsert_snapshot(
            "screener_row_snapshots",
            normalize_ticker(ticker),
            normalize_period(period),
            payload,
        )

    def get_screener_row_snapshot(
        self,
        ticker: str,
        period: str,
    ) -> Optional[dict]:
        return self.get_period_snapshot("screener_row_snapshots", ticker, period)

    def get_screener_row_snapshots(
        self,
        tickers: list[str],
        period: str,
    ) -> dict[str, dict]:
        normalized_tickers = normalize_tickers(tickers)

        if not normalized_tickers:
            return {}

        placeholders = ",".join("?" for _ in normalized_tickers)

        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT *
                FROM screener_row_snapshots
                WHERE period = ?
                AND ticker IN ({placeholders})
                """,
                [normalize_period(period), *normalized_tickers],
            ).fetchall()

        snapshots = {}

        for row in rows:
            snapshot = row_to_snapshot(row)

            if snapshot is not None:
                snapshots[row["ticker"]] = snapshot

        return snapshots

    def get_period_snapshot(
        self,
        table_name: str,
        ticker: str,
        period: str,
    ) -> Optional[dict]:
        with self.connect() as connection:
            row = connection.execute(
                f"""
                SELECT *
                FROM {table_name}
                WHERE ticker = ? AND period = ?
                """,
                (normalize_ticker(ticker), normalize_period(period)),
            ).fetchone()

        return row_to_snapshot(row)

    def upsert_snapshot(
        self,
        table_name: str,
        ticker: str,
        period: str,
        payload: dict,
        snapshot_type: Optional[str] = None,
    ) -> None:
        validate_payload(payload)
        provenance = payload.get("provenance") or {}
        refreshed_at = payload.get("refreshedAt") or utc_now()
        fiscal_year, fiscal_period = payload_fiscal_period(payload)
        computed_at = payload.get("computedAt")
        params = {
            "ticker": ticker,
            "period": period,
            "schema_version": payload["schemaVersion"],
            "provider": provenance.get("provider"),
            "provider_version": provenance.get("providerVersion"),
            "source_symbol": provenance.get("sourceSymbol"),
            "fetched_at": provenance.get("fetchedAt"),
            "fiscal_year": fiscal_year,
            "fiscal_period": fiscal_period,
            "computed_at": computed_at,
            "refreshed_at": refreshed_at,
            "payload_json": json.dumps(payload, sort_keys=True),
        }

        with self.connect() as connection:
            if table_name == "fundamentals_snapshots":
                connection.execute(
                    """
                    INSERT INTO fundamentals_snapshots (
                        ticker, period, snapshot_type, schema_version, provider,
                        provider_version, source_symbol, fetched_at, fiscal_year,
                        fiscal_period, refreshed_at, payload_json
                    )
                    VALUES (
                        :ticker, :period, :snapshot_type, :schema_version,
                        :provider, :provider_version, :source_symbol, :fetched_at,
                        :fiscal_year, :fiscal_period, :refreshed_at, :payload_json
                    )
                    ON CONFLICT(ticker, period, snapshot_type) DO UPDATE SET
                        schema_version = excluded.schema_version,
                        provider = excluded.provider,
                        provider_version = excluded.provider_version,
                        source_symbol = excluded.source_symbol,
                        fetched_at = excluded.fetched_at,
                        fiscal_year = excluded.fiscal_year,
                        fiscal_period = excluded.fiscal_period,
                        refreshed_at = excluded.refreshed_at,
                        payload_json = excluded.payload_json
                    """,
                    {**params, "snapshot_type": snapshot_type},
                )
                return

            connection.execute(
                f"""
                INSERT INTO {table_name} (
                    ticker, period, schema_version, provider, provider_version,
                    source_symbol, fetched_at, fiscal_year, fiscal_period,
                    computed_at, refreshed_at, payload_json
                )
                VALUES (
                    :ticker, :period, :schema_version, :provider,
                    :provider_version, :source_symbol, :fetched_at,
                    :fiscal_year, :fiscal_period, :computed_at,
                    :refreshed_at, :payload_json
                )
                ON CONFLICT(ticker, period) DO UPDATE SET
                    schema_version = excluded.schema_version,
                    provider = excluded.provider,
                    provider_version = excluded.provider_version,
                    source_symbol = excluded.source_symbol,
                    fetched_at = excluded.fetched_at,
                    fiscal_year = excluded.fiscal_year,
                    fiscal_period = excluded.fiscal_period,
                    computed_at = excluded.computed_at,
                    refreshed_at = excluded.refreshed_at,
                    payload_json = excluded.payload_json
                """,
                params,
            )

    def record_refresh_run(
        self,
        period: str,
        status: str,
        started_at: str,
        completed_at: str,
        universe_size: int,
        refreshed_count: int,
        failed_count: int,
        error_message: Optional[str],
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO snapshot_refresh_runs (
                    period, status, started_at, completed_at, universe_size,
                    refreshed_count, failed_count, error_message
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    normalize_period(period),
                    status,
                    started_at,
                    completed_at,
                    universe_size,
                    refreshed_count,
                    failed_count,
                    error_message,
                ),
            )

    def snapshot_freshness(
        self,
        universe_name: str,
        configured_tickers: list[str],
        periods: list[str],
        stale_after_seconds: int,
    ) -> list[dict]:
        persisted_universe = self.list_universe(universe_name)
        tickers = persisted_universe or normalize_tickers(configured_tickers)
        summaries = []

        for period in periods:
            snapshots = self.get_screener_row_snapshots(tickers, period)
            ages = [
                snapshot_age_seconds(snapshot)
                for snapshot in snapshots.values()
                if snapshot.get("refreshedAt")
            ]
            fresh_count = sum(
                1
                for snapshot in snapshots.values()
                if not snapshot_is_stale(snapshot, stale_after_seconds)
            )
            stale_count = len(snapshots) - fresh_count

            summaries.append(
                {
                    "period": normalize_period(period),
                    "universeSize": len(tickers),
                    "persistedCount": len(snapshots),
                    "freshCount": fresh_count,
                    "staleCount": stale_count,
                    "missingCount": max(len(tickers) - len(snapshots), 0),
                    "oldestRefreshedAt": oldest_refreshed_at(snapshots.values()),
                    "newestRefreshedAt": newest_refreshed_at(snapshots.values()),
                    "maxAgeSeconds": max(ages) if ages else None,
                    "staleAfterSeconds": stale_after_seconds,
                }
            )

        return summaries

    def upsert_valuation_scenario(
        self,
        ticker: str,
        scenario_id: str,
        payload: dict,
    ) -> None:
        validate_valuation_payload(payload)
        normalized_ticker = normalize_ticker(ticker)
        scenario = payload.get("scenario") or {}
        created_at = scenario.get("createdAt") or payload.get("createdAt") or utc_now()
        updated_at = scenario.get("updatedAt") or payload.get("updatedAt") or created_at
        parent_scenario_id = scenario.get("parentScenarioId")
        status = scenario.get("status") or "active"
        archived_at = scenario.get("archivedAt")
        deleted_at = scenario.get("deletedAt")
        audit_events = payload.pop("_auditEvents", [])

        with self.connect() as connection:
            existing = connection.execute(
                """
                SELECT latest_version_number, latest_version_id, status,
                    created_at, parent_scenario_id
                FROM valuation_scenarios
                WHERE scenario_id = ? AND ticker = ?
                """,
                (scenario_id, normalized_ticker),
            ).fetchone()
            version_number = scenario.get("versionNumber")

            if not isinstance(version_number, int):
                version_number = (
                    int(existing["latest_version_number"]) + 1
                    if existing is not None
                    else 1
                )

            prior_version_id = scenario.get("priorVersionId")

            if not prior_version_id and existing is not None:
                prior_version_id = existing["latest_version_id"]

            if not parent_scenario_id and existing is not None:
                parent_scenario_id = existing["parent_scenario_id"]

            version_id = scenario.get("versionId") or f"{scenario_id}-v{version_number}"
            scenario["versionNumber"] = version_number
            scenario["versionId"] = version_id
            scenario["priorVersionId"] = prior_version_id
            scenario["parentScenarioId"] = parent_scenario_id
            scenario["modelVersion"] = scenario.get("modelVersion") or (
                payload.get("modelMetadata") or {}
            ).get("dcfEngineVersion")
            scenario["status"] = status
            scenario["archivedAt"] = archived_at
            scenario["deletedAt"] = deleted_at
            scenario["updatedAt"] = updated_at
            payload["scenario"] = scenario
            payload_json = json.dumps(payload, sort_keys=True)
            connection.execute(
                """
                INSERT INTO valuation_scenarios (
                    scenario_id, ticker, schema_version, status,
                    parent_scenario_id, latest_version_id,
                    latest_version_number, archived_at, deleted_at,
                    created_at, updated_at, payload_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(scenario_id) DO UPDATE SET
                    ticker = excluded.ticker,
                    schema_version = excluded.schema_version,
                    status = excluded.status,
                    parent_scenario_id = excluded.parent_scenario_id,
                    latest_version_id = excluded.latest_version_id,
                    latest_version_number = excluded.latest_version_number,
                    archived_at = excluded.archived_at,
                    deleted_at = excluded.deleted_at,
                    updated_at = excluded.updated_at,
                    payload_json = excluded.payload_json
                """,
                (
                    scenario_id,
                    normalized_ticker,
                    payload["schemaVersion"],
                    status,
                    parent_scenario_id,
                    version_id,
                    version_number,
                    archived_at,
                    deleted_at,
                    created_at,
                    updated_at,
                    payload_json,
                ),
            )
            connection.execute(
                """
                INSERT INTO valuation_scenario_versions (
                    version_id, scenario_id, ticker, version_number,
                    schema_version, model_version, parent_scenario_id,
                    prior_version_id, created_at, payload_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    version_id,
                    scenario_id,
                    normalized_ticker,
                    version_number,
                    payload["schemaVersion"],
                    scenario.get("modelVersion"),
                    parent_scenario_id,
                    prior_version_id,
                    updated_at,
                    payload_json,
                ),
            )

            if not audit_events:
                audit_events = [
                    {
                        "changeType": "create" if existing is None else "version",
                        "fieldPath": None,
                        "previousValue": None,
                        "newValue": scenario.get("name"),
                    }
                ]

            for event in audit_events:
                record_valuation_audit_event(
                    connection,
                    normalized_ticker,
                    scenario_id,
                    version_id,
                    version_number,
                    event,
                    updated_at,
                )

    def get_latest_valuation_scenario(self, ticker: str) -> Optional[dict]:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT payload_json
                FROM valuation_scenarios
                WHERE ticker = ?
                AND status = 'active'
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                (normalize_ticker(ticker),),
            ).fetchone()

        return valuation_row_to_payload(row)

    def list_valuation_scenarios(
        self,
        ticker: str,
        limit: int,
        include_archived: bool = False,
        include_deleted: bool = False,
    ) -> list[dict]:
        normalized_limit = max(min(limit, 50), 1)
        statuses = ["active"]

        if include_archived:
            statuses.append("archived")

        if include_deleted:
            statuses.append("deleted")

        placeholders = ",".join("?" for _ in statuses)

        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT payload_json
                FROM valuation_scenarios
                WHERE ticker = ?
                AND status IN ({placeholders})
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (normalize_ticker(ticker), *statuses, normalized_limit),
            ).fetchall()

        return [
            payload
            for payload in (valuation_row_to_payload(row) for row in rows)
            if payload is not None
        ]

    def get_valuation_scenario(
        self,
        ticker: str,
        scenario_id: str,
    ) -> Optional[dict]:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT payload_json
                FROM valuation_scenarios
                WHERE ticker = ? AND scenario_id = ?
                """,
                (normalize_ticker(ticker), scenario_id),
            ).fetchone()

        return valuation_row_to_payload(row)

    def get_valuation_scenario_version(
        self,
        ticker: str,
        scenario_id: str,
        version_id: str,
    ) -> Optional[dict]:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT payload_json
                FROM valuation_scenario_versions
                WHERE ticker = ? AND scenario_id = ? AND version_id = ?
                """,
                (normalize_ticker(ticker), scenario_id, version_id),
            ).fetchone()

        return valuation_row_to_payload(row)

    def list_valuation_scenario_versions(
        self,
        ticker: str,
        scenario_id: str,
    ) -> list[dict]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT payload_json
                FROM valuation_scenario_versions
                WHERE ticker = ? AND scenario_id = ?
                ORDER BY version_number DESC
                """,
                (normalize_ticker(ticker), scenario_id),
            ).fetchall()

        return [
            payload
            for payload in (valuation_row_to_payload(row) for row in rows)
            if payload is not None
        ]

    def list_valuation_audit_events(
        self,
        ticker: str,
        scenario_id: str,
    ) -> list[dict]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT payload_json
                FROM valuation_audit_events
                WHERE ticker = ? AND scenario_id = ?
                ORDER BY created_at DESC
                """,
                (normalize_ticker(ticker), scenario_id),
            ).fetchall()

        return [json.loads(row["payload_json"]) for row in rows]

    def add_valuation_note(
        self,
        ticker: str,
        scenario_id: str,
        payload: dict,
    ) -> dict:
        note_id = payload.get("id") or f"note-{scenario_id}-{uuid_suffix()}"
        timestamp = payload.get("createdAt") or utc_now()
        normalized_ticker = normalize_ticker(ticker)
        note = {
            **payload,
            "id": note_id,
            "ticker": normalized_ticker,
            "scenarioId": scenario_id,
            "schemaVersion": payload.get("schemaVersion") or SCHEMA_VERSION,
            "createdAt": timestamp,
            "immutable": True,
        }

        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO valuation_notes (
                    note_id, scenario_id, ticker, version_id, version_number,
                    attachment_type, field_path, warning_code, created_at,
                    payload_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    note_id,
                    scenario_id,
                    normalized_ticker,
                    note.get("versionId"),
                    note.get("versionNumber"),
                    note.get("attachmentType") or "scenario_version",
                    note.get("fieldPath"),
                    note.get("warningCode"),
                    timestamp,
                    json.dumps(note, sort_keys=True),
                ),
            )

        return note

    def list_valuation_notes(
        self,
        ticker: str,
        scenario_id: str,
    ) -> list[dict]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT payload_json
                FROM valuation_notes
                WHERE ticker = ? AND scenario_id = ?
                ORDER BY created_at DESC
                """,
                (normalize_ticker(ticker), scenario_id),
            ).fetchall()

        return [json.loads(row["payload_json"]) for row in rows]

    def valuation_repository_diagnostics(
        self,
        ticker: str,
        stale_after_seconds: int,
    ) -> dict:
        normalized_ticker = normalize_ticker(ticker)

        with self.connect() as connection:
            scenario_rows = connection.execute(
                """
                SELECT scenario_id, updated_at, payload_json
                FROM valuation_scenarios
                WHERE ticker = ?
                """,
                (normalized_ticker,),
            ).fetchall()
            version_rows = connection.execute(
                """
                SELECT version_id, model_version, payload_json
                FROM valuation_scenario_versions
                WHERE ticker = ?
                """,
                (normalized_ticker,),
            ).fetchall()
            orphaned_version_count = connection.execute(
                """
                SELECT COUNT(*) AS count
                FROM valuation_scenario_versions versions
                LEFT JOIN valuation_scenarios scenarios
                    ON scenarios.scenario_id = versions.scenario_id
                    AND scenarios.ticker = versions.ticker
                WHERE versions.ticker = ? AND scenarios.scenario_id IS NULL
                """,
                (normalized_ticker,),
            ).fetchone()["count"]
            audit_event_count = connection.execute(
                """
                SELECT COUNT(*) AS count
                FROM valuation_audit_events
                WHERE ticker = ?
                """,
                (normalized_ticker,),
            ).fetchone()["count"]
            note_count = connection.execute(
                """
                SELECT COUNT(*) AS count
                FROM valuation_notes
                WHERE ticker = ?
                """,
                (normalized_ticker,),
            ).fetchone()["count"]
            model_rows = connection.execute(
                """
                SELECT COALESCE(model_version, 'unknown') AS model_version,
                    COUNT(*) AS count
                FROM valuation_scenario_versions
                WHERE ticker = ?
                GROUP BY COALESCE(model_version, 'unknown')
                ORDER BY count DESC, model_version
                """,
                (normalized_ticker,),
            ).fetchall()

        stale_count = 0
        reproducibility_complete_count = 0

        for row in scenario_rows:
            payload = valuation_row_to_payload(row) or {}

            if valuation_payload_is_stale(payload, stale_after_seconds):
                stale_count += 1

            if valuation_reproducibility_complete(payload):
                reproducibility_complete_count += 1

        return {
            "scenarioCount": len(scenario_rows),
            "versionCount": len(version_rows),
            "auditEventCount": audit_event_count,
            "noteCount": note_count,
            "orphanedScenarioVersionCount": orphaned_version_count,
            "modelVersionDistribution": [
                {
                    "modelVersion": row["model_version"],
                    "count": row["count"],
                }
                for row in model_rows
            ],
            "staleScenarioCount": stale_count,
            "staleAfterSeconds": stale_after_seconds,
            "reproducibility": {
                "completeScenarioCount": reproducibility_complete_count,
                "incompleteScenarioCount": max(
                    len(scenario_rows) - reproducibility_complete_count,
                    0,
                ),
            },
        }

    def create_ranking_run(self, payload: dict) -> dict:
        validate_ranking_run_payload(payload)
        rows = payload.get("rows") or []

        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO ranking_runs (
                    run_id, strategy, period, schema_version,
                    ranking_engine_version, computed_at, universe_json,
                    eligibility_settings_json, payload_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload["runId"],
                    payload["strategy"],
                    payload["period"],
                    payload["schemaVersion"],
                    payload["rankingEngineVersion"],
                    payload["computedAt"],
                    json.dumps(payload.get("universe") or {}, sort_keys=True),
                    json.dumps(payload.get("eligibilitySettings") or {}, sort_keys=True),
                    json.dumps(payload, sort_keys=True),
                ),
            )

            for row in rows:
                connection.execute(
                    """
                    INSERT INTO ranking_row_snapshots (
                        run_id, ticker, strategy, period, rank,
                        eligibility_status, score, computed_at, payload_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        payload["runId"],
                        row["ticker"],
                        payload["strategy"],
                        payload["period"],
                        row.get("rank"),
                        row.get("eligibilityStatus") or "unranked_missing_data",
                        row.get("score"),
                        payload["computedAt"],
                        json.dumps(row, sort_keys=True),
                    ),
                )

        return payload

    def list_ranking_runs(
        self,
        strategy: Optional[str],
        period: Optional[str],
        limit: int,
    ) -> list[dict]:
        normalized_limit = max(min(limit, 100), 1)
        clauses = []
        params = []

        if strategy:
            clauses.append("strategy = ?")
            params.append(strategy.strip().lower())

        if period:
            clauses.append("period = ?")
            params.append(normalize_period(period))

        where_clause = f"WHERE {' AND '.join(clauses)}" if clauses else ""

        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT payload_json
                FROM ranking_runs
                {where_clause}
                ORDER BY computed_at DESC
                LIMIT ?
                """,
                [*params, normalized_limit],
            ).fetchall()

        return [
            ranking_run_summary(payload)
            for payload in (ranking_row_to_payload(row) for row in rows)
            if payload is not None
        ]

    def get_ranking_run(self, run_id: str) -> Optional[dict]:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT payload_json
                FROM ranking_runs
                WHERE run_id = ?
                """,
                (run_id,),
            ).fetchone()

        return ranking_row_to_payload(row)

    def get_previous_ranking_run(
        self,
        strategy: str,
        period: str,
        before_computed_at: str,
    ) -> Optional[dict]:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT payload_json
                FROM ranking_runs
                WHERE strategy = ?
                AND period = ?
                AND computed_at < ?
                ORDER BY computed_at DESC
                LIMIT 1
                """,
                (strategy.strip().lower(), normalize_period(period), before_computed_at),
            ).fetchone()

        return ranking_row_to_payload(row)

    def ranking_repository_diagnostics(self, stale_after_seconds: int) -> dict:
        with self.connect() as connection:
            run_count = connection.execute(
                "SELECT COUNT(*) AS count FROM ranking_runs"
            ).fetchone()["count"]
            row_snapshot_count = connection.execute(
                "SELECT COUNT(*) AS count FROM ranking_row_snapshots"
            ).fetchone()["count"]
            latest_rows = connection.execute(
                """
                SELECT payload_json
                FROM ranking_runs
                ORDER BY computed_at DESC
                LIMIT 25
                """
            ).fetchall()
            version_rows = connection.execute(
                """
                SELECT ranking_engine_version, COUNT(*) AS count
                FROM ranking_runs
                GROUP BY ranking_engine_version
                ORDER BY count DESC, ranking_engine_version
                """
            ).fetchall()
            saved_screen_rows = connection.execute(
                """
                SELECT status, COUNT(*) AS count
                FROM ranking_saved_screens
                GROUP BY status
                """
            ).fetchall()
            refresh_run_count = connection.execute(
                "SELECT COUNT(*) AS count FROM ranking_refresh_runs"
            ).fetchone()["count"]
            refresh_status_rows = connection.execute(
                """
                SELECT status, COUNT(*) AS count
                FROM ranking_refresh_runs
                GROUP BY status
                """
            ).fetchall()
            failed_refresh_count = connection.execute(
                """
                SELECT COUNT(*) AS count
                FROM ranking_refresh_runs
                WHERE status = 'failed'
                """
            ).fetchone()["count"]
            latest_refresh_rows = connection.execute(
                """
                SELECT payload_json
                FROM ranking_refresh_runs
                ORDER BY COALESCE(started_at, completed_at, failed_at) DESC
                LIMIT 25
                """
            ).fetchall()

        latest_payloads = [
            payload
            for payload in (ranking_row_to_payload(row) for row in latest_rows)
            if payload is not None
        ]
        latest_runs = [ranking_run_summary(payload) for payload in latest_payloads]
        latest_by_strategy = {}

        for run in latest_runs:
            key = f"{run['strategy']}:{run['period']}"

            if key not in latest_by_strategy:
                latest_by_strategy[key] = run

        stale_run_count = sum(
            1
            for payload in latest_payloads
            if ranking_payload_is_stale(payload, stale_after_seconds)
        )
        latest_refreshes = [
            ranking_refresh_summary(payload)
            for payload in (ranking_row_to_payload(row) for row in latest_refresh_rows)
            if payload is not None
        ]
        latest_refresh_by_strategy = {}

        for refresh in latest_refreshes:
            key = f"{refresh['strategy']}:{refresh['period']}"

            if key not in latest_refresh_by_strategy:
                latest_refresh_by_strategy[key] = refresh

        return {
            "repository": self.repository_status(),
            "runCount": run_count,
            "rowSnapshotCount": row_snapshot_count,
            "savedScreenCounts": {
                row["status"]: row["count"]
                for row in saved_screen_rows
            },
            "refreshRunCount": refresh_run_count,
            "workflowStatusDistribution": [
                {
                    "status": row["status"],
                    "count": row["count"],
                }
                for row in refresh_status_rows
            ],
            "failedRefreshCount": failed_refresh_count,
            "latestRefreshes": latest_refreshes,
            "latestRefreshByStrategy": latest_refresh_by_strategy,
            "latestRuns": latest_runs,
            "latestRunByStrategy": latest_by_strategy,
            "engineVersionDistribution": [
                {
                    "rankingEngineVersion": row["ranking_engine_version"],
                    "count": row["count"],
                }
                for row in version_rows
            ],
            "staleRunCount": stale_run_count,
            "staleAfterSeconds": stale_after_seconds,
        }

    def create_refresh_job(self, payload: dict) -> dict:
        validate_refresh_job_payload(payload)

        with self.connect() as connection:
            upsert_refresh_job_row(connection, payload)

        return payload

    def update_refresh_job(self, payload: dict) -> dict:
        validate_refresh_job_payload(payload)

        with self.connect() as connection:
            upsert_refresh_job_row(connection, payload)

        return payload

    def get_refresh_job(self, job_id: str) -> Optional[dict]:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT job_json
                FROM refresh_jobs
                WHERE job_id = ?
                """,
                (job_id,),
            ).fetchone()

        return refresh_job_row_to_payload(row)

    def list_refresh_jobs(
        self,
        job_type: Optional[str],
        status: Optional[str],
        limit: int,
    ) -> list[dict]:
        clauses = []
        params = []
        normalized_limit = max(min(limit, 100), 1)

        if job_type:
            clauses.append("job_type = ?")
            params.append(job_type.strip().lower())

        if status:
            clauses.append("status = ?")
            params.append(status.strip().lower())

        where_clause = f"WHERE {' AND '.join(clauses)}" if clauses else ""

        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT job_json
                FROM refresh_jobs
                {where_clause}
                ORDER BY created_at DESC
                LIMIT ?
                """,
                [*params, normalized_limit],
            ).fetchall()

        return [
            payload
            for payload in (refresh_job_row_to_payload(row) for row in rows)
            if payload is not None
        ]

    def append_refresh_job_event(self, job_id: str, payload: dict) -> dict:
        validate_refresh_job_event_payload(payload)

        with self.connect() as connection:
            next_sequence = connection.execute(
                """
                SELECT COALESCE(MAX(sequence), 0) + 1 AS sequence
                FROM refresh_job_events
                WHERE job_id = ?
                """,
                (job_id,),
            ).fetchone()["sequence"]
            event = {
                **payload,
                "jobId": job_id,
                "sequence": next_sequence,
            }
            connection.execute(
                """
                INSERT INTO refresh_job_events (
                    event_id, job_id, sequence, event_type, status, message,
                    created_at, payload_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event["eventId"],
                    job_id,
                    next_sequence,
                    event["eventType"],
                    event["status"],
                    event.get("message"),
                    event["createdAt"],
                    json.dumps(event, sort_keys=True),
                ),
            )

        return event

    def list_refresh_job_events(self, job_id: str) -> list[dict]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT payload_json
                FROM refresh_job_events
                WHERE job_id = ?
                ORDER BY sequence ASC
                """,
                (job_id,),
            ).fetchall()

        return [json.loads(row["payload_json"]) for row in rows]

    def cancel_refresh_job(self, job_id: str, timestamp: str) -> Optional[dict]:
        job = self.get_refresh_job(job_id)

        if job is None:
            return None

        if job.get("status") != "queued":
            return {
                **job,
                "cancelled": False,
                "message": "Only queued jobs can be cancelled in Phase 4D.",
            }

        duration = duration_ms(job.get("createdAt"), timestamp)
        cancelled = {
            **job,
            "status": "cancelled",
            "completedAt": timestamp,
            "durationMs": duration,
            "resultMetadata": {
                **(job.get("resultMetadata") or {}),
                "cancelled": True,
            },
            "message": "Queued refresh job was cancelled before execution.",
        }
        self.update_refresh_job(cancelled)
        self.append_refresh_job_event(
            job_id,
            {
                "eventId": refresh_job_event_id(job_id, "cancelled"),
                "eventType": "job_cancelled",
                "status": "cancelled",
                "message": "Queued refresh job was cancelled before execution.",
                "createdAt": timestamp,
                "payload": {},
            },
        )

        return {**cancelled, "cancelled": True}

    def refresh_job_repository_diagnostics(self, stale_after_seconds: int) -> dict:
        with self.connect() as connection:
            job_count = connection.execute(
                "SELECT COUNT(*) AS count FROM refresh_jobs"
            ).fetchone()["count"]
            event_count = connection.execute(
                "SELECT COUNT(*) AS count FROM refresh_job_events"
            ).fetchone()["count"]
            status_rows = connection.execute(
                """
                SELECT status, COUNT(*) AS count
                FROM refresh_jobs
                GROUP BY status
                """
            ).fetchall()
            type_rows = connection.execute(
                """
                SELECT job_type, COUNT(*) AS count
                FROM refresh_jobs
                GROUP BY job_type
                """
            ).fetchall()
            latest_row = connection.execute(
                """
                SELECT job_json
                FROM refresh_jobs
                ORDER BY created_at DESC
                LIMIT 1
                """
            ).fetchone()
            failed_count = connection.execute(
                """
                SELECT COUNT(*) AS count
                FROM refresh_jobs
                WHERE status = 'failed'
                """
            ).fetchone()["count"]
            queued_count = connection.execute(
                """
                SELECT COUNT(*) AS count
                FROM refresh_jobs
                WHERE status = 'queued'
                """
            ).fetchone()["count"]
            running_count = connection.execute(
                """
                SELECT COUNT(*) AS count
                FROM refresh_jobs
                WHERE status = 'running'
                """
            ).fetchone()["count"]

        latest_job = refresh_job_row_to_payload(latest_row)

        return {
            "repository": self.repository_status(),
            "jobCount": job_count,
            "eventCount": event_count,
            "statusCounts": {
                row["status"]: row["count"]
                for row in status_rows
            },
            "jobTypeDistribution": [
                {
                    "jobType": row["job_type"],
                    "count": row["count"],
                }
                for row in type_rows
            ],
            "queuedCount": queued_count,
            "runningCount": running_count,
            "failedCount": failed_count,
            "latestJob": refresh_job_summary(latest_job) if latest_job else None,
            "staleAfterSeconds": stale_after_seconds,
        }

    def upsert_refresh_policy(self, payload: dict) -> dict:
        validate_refresh_policy_payload(payload)

        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO refresh_policies (
                    policy_id, name, target, strategy, period, enabled,
                    schedule_hint, stale_after_seconds, last_run_at,
                    next_run_hint, schema_version, created_at, updated_at,
                    payload_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(policy_id) DO UPDATE SET
                    name = excluded.name,
                    target = excluded.target,
                    strategy = excluded.strategy,
                    period = excluded.period,
                    enabled = excluded.enabled,
                    schedule_hint = excluded.schedule_hint,
                    stale_after_seconds = excluded.stale_after_seconds,
                    last_run_at = excluded.last_run_at,
                    next_run_hint = excluded.next_run_hint,
                    schema_version = excluded.schema_version,
                    updated_at = excluded.updated_at,
                    payload_json = excluded.payload_json
                """,
                (
                    payload["policyId"],
                    payload["name"],
                    payload.get("target") or "ranking",
                    payload.get("strategy") or "magic_formula",
                    payload.get("period") or "annual",
                    1 if payload.get("enabled") else 0,
                    payload.get("scheduleHint") or "manual",
                    payload.get("staleAfterSeconds") or 86400,
                    payload.get("lastRunAt"),
                    payload.get("nextRunHint"),
                    payload["schemaVersion"],
                    payload["createdAt"],
                    payload["updatedAt"],
                    json.dumps(payload, sort_keys=True),
                ),
            )

        return payload

    def list_refresh_policies(
        self,
        include_disabled: bool,
        limit: int,
    ) -> list[dict]:
        normalized_limit = max(min(limit, 100), 1)
        where_clause = "" if include_disabled else "WHERE enabled = 1"

        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT payload_json
                FROM refresh_policies
                {where_clause}
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (normalized_limit,),
            ).fetchall()

        return [json.loads(row["payload_json"]) for row in rows]

    def get_refresh_policy(self, policy_id: str) -> Optional[dict]:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT payload_json
                FROM refresh_policies
                WHERE policy_id = ?
                """,
                (policy_id,),
            ).fetchone()

        return json.loads(row["payload_json"]) if row else None

    def refresh_policy_repository_diagnostics(self, stale_after_seconds: int) -> dict:
        now = utc_now()
        with self.connect() as connection:
            policy_count = connection.execute(
                "SELECT COUNT(*) AS count FROM refresh_policies"
            ).fetchone()["count"]
            enabled_count = connection.execute(
                """
                SELECT COUNT(*) AS count
                FROM refresh_policies
                WHERE enabled = 1
                """
            ).fetchone()["count"]
            due_count = connection.execute(
                """
                SELECT COUNT(*) AS count
                FROM refresh_policies
                WHERE enabled = 1
                  AND next_run_hint IS NOT NULL
                  AND next_run_hint <= ?
                """,
                (now,),
            ).fetchone()["count"]
            target_rows = connection.execute(
                """
                SELECT target, COUNT(*) AS count
                FROM refresh_policies
                GROUP BY target
                """
            ).fetchall()

        latest_policy_jobs = [
            refresh_job_summary(job)
            for job in self.list_refresh_jobs(None, None, 20)
            if (job.get("payload") or {}).get("policyId")
        ][:5]

        return {
            "repository": self.repository_status(),
            "policyCount": policy_count,
            "enabledPolicyCount": enabled_count,
            "duePolicyCount": due_count,
            "targetDistribution": [
                {
                    "target": row["target"],
                    "count": row["count"],
                }
                for row in target_rows
            ],
            "latestPolicyTriggeredJobs": latest_policy_jobs,
            "staleOnlyRefreshReady": True,
            "staleAfterSeconds": stale_after_seconds,
        }

    def upsert_ranking_screen(self, payload: dict) -> dict:
        validate_ranking_screen_payload(payload)
        status = payload.get("status") or "active"

        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO ranking_saved_screens (
                    screen_id, status, name, strategy, period, limit_value,
                    schema_version, created_at, updated_at, archived_at,
                    deleted_at, payload_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(screen_id) DO UPDATE SET
                    status = excluded.status,
                    name = excluded.name,
                    strategy = excluded.strategy,
                    period = excluded.period,
                    limit_value = excluded.limit_value,
                    schema_version = excluded.schema_version,
                    updated_at = excluded.updated_at,
                    archived_at = excluded.archived_at,
                    deleted_at = excluded.deleted_at,
                    payload_json = excluded.payload_json
                """,
                (
                    payload["screenId"],
                    status,
                    payload["name"],
                    payload["strategy"],
                    payload["period"],
                    payload["limit"],
                    payload["schemaVersion"],
                    payload["createdAt"],
                    payload["updatedAt"],
                    payload.get("archivedAt"),
                    payload.get("deletedAt"),
                    json.dumps(payload, sort_keys=True),
                ),
            )

        return payload

    def list_ranking_screens(
        self,
        include_archived: bool,
        include_deleted: bool,
        limit: int,
    ) -> list[dict]:
        statuses = ["active"]

        if include_archived:
            statuses.append("archived")

        if include_deleted:
            statuses.append("deleted")

        placeholders = ",".join("?" for _ in statuses)
        normalized_limit = max(min(limit, 100), 1)

        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT payload_json
                FROM ranking_saved_screens
                WHERE status IN ({placeholders})
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                [*statuses, normalized_limit],
            ).fetchall()

        return [
            payload
            for payload in (ranking_row_to_payload(row) for row in rows)
            if payload is not None
        ]

    def get_ranking_screen(self, screen_id: str) -> Optional[dict]:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT payload_json
                FROM ranking_saved_screens
                WHERE screen_id = ?
                """,
                (screen_id,),
            ).fetchone()

        return ranking_row_to_payload(row)

    def record_ranking_refresh_run(self, payload: dict) -> dict:
        validate_ranking_refresh_payload(payload)

        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO ranking_refresh_runs (
                    refresh_id, status, strategy, period, scope_json,
                    started_at, completed_at, failed_at, duration_ms,
                    warnings_json, errors_json, payload_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(refresh_id) DO UPDATE SET
                    status = excluded.status,
                    strategy = excluded.strategy,
                    period = excluded.period,
                    scope_json = excluded.scope_json,
                    started_at = excluded.started_at,
                    completed_at = excluded.completed_at,
                    failed_at = excluded.failed_at,
                    duration_ms = excluded.duration_ms,
                    warnings_json = excluded.warnings_json,
                    errors_json = excluded.errors_json,
                    payload_json = excluded.payload_json
                """,
                (
                    payload["refreshId"],
                    payload["status"],
                    payload["strategy"],
                    payload["period"],
                    json.dumps(payload.get("scope") or {}, sort_keys=True),
                    payload.get("startedAt"),
                    payload.get("completedAt"),
                    payload.get("failedAt"),
                    payload.get("durationMs"),
                    json.dumps(payload.get("warnings") or [], sort_keys=True),
                    json.dumps(payload.get("errors") or [], sort_keys=True),
                    json.dumps(payload, sort_keys=True),
                ),
            )

        return payload

    def list_ranking_refresh_runs(
        self,
        strategy: Optional[str],
        period: Optional[str],
        limit: int,
    ) -> list[dict]:
        clauses = []
        params = []
        normalized_limit = max(min(limit, 100), 1)

        if strategy:
            clauses.append("strategy = ?")
            params.append(strategy.strip().lower())

        if period:
            clauses.append("period = ?")
            params.append(normalize_period(period))

        where_clause = f"WHERE {' AND '.join(clauses)}" if clauses else ""

        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT payload_json
                FROM ranking_refresh_runs
                {where_clause}
                ORDER BY COALESCE(started_at, completed_at, failed_at) DESC
                LIMIT ?
                """,
                [*params, normalized_limit],
            ).fetchall()

        return [
            payload
            for payload in (ranking_row_to_payload(row) for row in rows)
            if payload is not None
        ]

    def upsert_watchlist(self, payload: dict) -> dict:
        validate_watchlist_payload(payload)
        watchlist_id = payload["watchlistId"]
        status = payload.get("status") or "active"

        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO watchlists (
                    watchlist_id, status, name, description, schema_version,
                    created_at, updated_at, archived_at, deleted_at,
                    payload_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(watchlist_id) DO UPDATE SET
                    status = excluded.status,
                    name = excluded.name,
                    description = excluded.description,
                    schema_version = excluded.schema_version,
                    updated_at = excluded.updated_at,
                    archived_at = excluded.archived_at,
                    deleted_at = excluded.deleted_at,
                    payload_json = excluded.payload_json
                """,
                (
                    watchlist_id,
                    status,
                    payload["name"],
                    payload.get("description"),
                    payload["schemaVersion"],
                    payload["createdAt"],
                    payload["updatedAt"],
                    payload.get("archivedAt"),
                    payload.get("deletedAt"),
                    json.dumps(watchlist_payload_without_items(payload), sort_keys=True),
                ),
            )

        return self.get_watchlist(watchlist_id) or payload

    def list_watchlists(
        self,
        include_archived: bool,
        include_deleted: bool,
        limit: int,
    ) -> list[dict]:
        statuses = ["active"]

        if include_archived:
            statuses.append("archived")

        if include_deleted:
            statuses.append("deleted")

        placeholders = ",".join("?" for _ in statuses)
        normalized_limit = max(min(limit, 100), 1)

        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT payload_json
                FROM watchlists
                WHERE status IN ({placeholders})
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                [*statuses, normalized_limit],
            ).fetchall()

        return [
            self.watchlist_with_items(payload)
            for payload in (watchlist_row_to_payload(row) for row in rows)
            if payload is not None
        ]

    def get_watchlist(self, watchlist_id: str) -> Optional[dict]:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT payload_json
                FROM watchlists
                WHERE watchlist_id = ?
                """,
                (watchlist_id,),
            ).fetchone()

        payload = watchlist_row_to_payload(row)

        if payload is None:
            return None

        return self.watchlist_with_items(payload)

    def update_watchlist_status(
        self,
        watchlist_id: str,
        status: str,
        timestamp: str,
    ) -> Optional[dict]:
        existing = self.get_watchlist(watchlist_id)

        if existing is None:
            return None

        normalized_status = status if status in {"active", "archived", "deleted"} else "active"
        updated = {
            **watchlist_payload_without_items(existing),
            "status": normalized_status,
            "updatedAt": timestamp,
            "archivedAt": timestamp if normalized_status == "archived" else None,
            "deletedAt": timestamp if normalized_status == "deleted" else None,
            "message": watchlist_status_message(normalized_status),
        }

        if normalized_status == "active":
            updated["archivedAt"] = None
            updated["deletedAt"] = None

        return self.upsert_watchlist(updated)

    def upsert_watchlist_item(
        self,
        watchlist_id: str,
        payload: dict,
    ) -> Optional[dict]:
        validate_watchlist_item_payload(payload)
        existing = self.get_watchlist(watchlist_id)

        if existing is None:
            return None

        item = normalize_watchlist_item_payload(payload)
        metadata = {
            **watchlist_payload_without_items(existing),
            "updatedAt": item["updatedAt"],
            "message": "Watchlist item was saved.",
        }

        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO watchlist_items (
                    watchlist_id, ticker, company_name, added_at, notes,
                    tags_json, target_price, thesis_status, priority, workflow_state,
                    updated_at, payload_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(watchlist_id, ticker) DO UPDATE SET
                    company_name = excluded.company_name,
                    notes = excluded.notes,
                    tags_json = excluded.tags_json,
                    target_price = excluded.target_price,
                    thesis_status = excluded.thesis_status,
                    priority = excluded.priority,
                    workflow_state = excluded.workflow_state,
                    updated_at = excluded.updated_at,
                    payload_json = excluded.payload_json
                """,
                (
                    watchlist_id,
                    item["ticker"],
                    item.get("companyName"),
                    item["addedAt"],
                    item.get("notes"),
                    json.dumps(item.get("tags") or [], sort_keys=True),
                    item.get("targetPrice"),
                    item.get("thesisStatus"),
                    item.get("priority"),
                    item.get("workflowState"),
                    item["updatedAt"],
                    json.dumps(item, sort_keys=True),
                ),
            )
            connection.execute(
                """
                UPDATE watchlists
                SET updated_at = ?,
                    payload_json = ?
                WHERE watchlist_id = ?
                """,
                (
                    item["updatedAt"],
                    json.dumps(metadata, sort_keys=True),
                    watchlist_id,
                ),
            )

        return self.get_watchlist(watchlist_id)

    def remove_watchlist_item(
        self,
        watchlist_id: str,
        ticker: str,
        timestamp: str,
    ) -> Optional[dict]:
        existing = self.get_watchlist(watchlist_id)

        if existing is None:
            return None

        metadata = {
            **watchlist_payload_without_items(existing),
            "updatedAt": timestamp,
            "message": f"{normalize_ticker(ticker)} was removed from the watchlist.",
        }

        with self.connect() as connection:
            connection.execute(
                """
                DELETE FROM watchlist_items
                WHERE watchlist_id = ? AND ticker = ?
                """,
                (watchlist_id, normalize_ticker(ticker)),
            )
            connection.execute(
                """
                UPDATE watchlists
                SET updated_at = ?,
                    payload_json = ?
                WHERE watchlist_id = ?
                """,
                (timestamp, json.dumps(metadata, sort_keys=True), watchlist_id),
            )

        return self.get_watchlist(watchlist_id)

    def watchlist_repository_diagnostics(self, stale_after_seconds: int) -> dict:
        with self.connect() as connection:
            watchlist_count = connection.execute(
                """
                SELECT COUNT(*) AS count
                FROM watchlists
                WHERE status != 'deleted'
                """
            ).fetchone()["count"]
            active_count = connection.execute(
                """
                SELECT COUNT(*) AS count
                FROM watchlists
                WHERE status = 'active'
                """
            ).fetchone()["count"]
            archived_count = connection.execute(
                """
                SELECT COUNT(*) AS count
                FROM watchlists
                WHERE status = 'archived'
                """
            ).fetchone()["count"]
            item_count = connection.execute(
                """
                SELECT COUNT(*) AS count
                FROM watchlist_items items
                JOIN watchlists watchlists
                    ON watchlists.watchlist_id = items.watchlist_id
                WHERE watchlists.status != 'deleted'
                """
            ).fetchone()["count"]
            stale_items = connection.execute(
                """
                SELECT COUNT(DISTINCT items.ticker) AS count
                FROM watchlist_items items
                JOIN watchlists watchlists
                    ON watchlists.watchlist_id = items.watchlist_id
                LEFT JOIN screener_row_snapshots snapshots
                    ON snapshots.ticker = items.ticker
                    AND snapshots.period = 'annual'
                WHERE watchlists.status != 'deleted'
                  AND (
                    snapshots.refreshed_at IS NULL
                    OR snapshots.refreshed_at <= ?
                  )
                """,
                (stale_cutoff(stale_after_seconds),),
            ).fetchone()["count"]
            view_count = connection.execute(
                """
                SELECT COUNT(*) AS count
                FROM watchlist_views
                WHERE status != 'deleted'
                """
            ).fetchone()["count"]
            active_alert_count = connection.execute(
                """
                SELECT COUNT(*) AS count
                FROM watchlist_alert_events
                WHERE status IN ('active', 'acknowledged')
                  AND dismissed_at IS NULL
                """
            ).fetchone()["count"]
            acknowledged_alert_count = connection.execute(
                """
                SELECT COUNT(*) AS count
                FROM watchlist_alert_events
                WHERE acknowledged_at IS NOT NULL
                """
            ).fetchone()["count"]
            dismissed_alert_count = connection.execute(
                """
                SELECT COUNT(*) AS count
                FROM watchlist_alert_events
                WHERE dismissed_at IS NOT NULL
                """
            ).fetchone()["count"]

        return {
            "repository": self.repository_status(),
            "watchlistCount": watchlist_count,
            "activeWatchlistCount": active_count,
            "archivedWatchlistCount": archived_count,
            "itemCount": item_count,
            "staleWatchlistItemCount": stale_items,
            "savedViewCount": view_count,
            "activeAlertCount": active_alert_count,
            "acknowledgedAlertCount": acknowledged_alert_count,
            "dismissedAlertCount": dismissed_alert_count,
            "staleAfterSeconds": stale_after_seconds,
        }

    def watchlist_with_items(self, payload: dict) -> dict:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT payload_json
                FROM watchlist_items
                WHERE watchlist_id = ?
                ORDER BY added_at ASC, ticker ASC
                """,
                (payload["watchlistId"],),
            ).fetchall()

        items = [
            item
            for item in (watchlist_item_row_to_payload(row) for row in rows)
            if item is not None
        ]

        return {
            **payload,
            "id": payload["watchlistId"],
            "items": items,
        }

    def upsert_watchlist_view(self, payload: dict) -> dict:
        validate_watchlist_view_payload(payload)
        view = normalize_watchlist_view_payload(payload)

        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO watchlist_views (
                    view_id, watchlist_id, status, name, filters_json,
                    sorting_json, visible_columns_json, schema_version,
                    created_at, updated_at, archived_at, deleted_at,
                    payload_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(view_id) DO UPDATE SET
                    watchlist_id = excluded.watchlist_id,
                    status = excluded.status,
                    name = excluded.name,
                    filters_json = excluded.filters_json,
                    sorting_json = excluded.sorting_json,
                    visible_columns_json = excluded.visible_columns_json,
                    schema_version = excluded.schema_version,
                    updated_at = excluded.updated_at,
                    archived_at = excluded.archived_at,
                    deleted_at = excluded.deleted_at,
                    payload_json = excluded.payload_json
                """,
                (
                    view["viewId"],
                    view["watchlistId"],
                    view.get("status") or "active",
                    view["name"],
                    json.dumps(view.get("filters") or [], sort_keys=True),
                    json.dumps(view.get("sorting"), sort_keys=True),
                    json.dumps(view.get("visibleColumns") or [], sort_keys=True),
                    view["schemaVersion"],
                    view["createdAt"],
                    view["updatedAt"],
                    view.get("archivedAt"),
                    view.get("deletedAt"),
                    json.dumps(view, sort_keys=True),
                ),
            )

        return view

    def list_watchlist_views(
        self,
        watchlist_id: str,
        include_archived: bool,
        include_deleted: bool,
        limit: int,
    ) -> list[dict]:
        statuses = ["active"]

        if include_archived:
            statuses.append("archived")

        if include_deleted:
            statuses.append("deleted")

        placeholders = ",".join("?" for _ in statuses)
        normalized_limit = max(min(limit, 100), 1)

        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT payload_json
                FROM watchlist_views
                WHERE watchlist_id = ?
                AND status IN ({placeholders})
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                [watchlist_id, *statuses, normalized_limit],
            ).fetchall()

        return [
            payload
            for payload in (watchlist_row_to_payload(row) for row in rows)
            if payload is not None
        ]

    def get_watchlist_view(
        self,
        watchlist_id: str,
        view_id: str,
    ) -> Optional[dict]:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT payload_json
                FROM watchlist_views
                WHERE watchlist_id = ? AND view_id = ?
                """,
                (watchlist_id, view_id),
            ).fetchone()

        return watchlist_row_to_payload(row)

    def update_watchlist_view_status(
        self,
        watchlist_id: str,
        view_id: str,
        status: str,
        timestamp: str,
    ) -> Optional[dict]:
        existing = self.get_watchlist_view(watchlist_id, view_id)

        if existing is None:
            return None

        normalized_status = status if status in {"active", "archived", "deleted"} else "active"
        updated = {
            **existing,
            "status": normalized_status,
            "updatedAt": timestamp,
            "archivedAt": timestamp if normalized_status == "archived" else None,
            "deletedAt": timestamp if normalized_status == "deleted" else None,
        }

        if normalized_status == "active":
            updated["archivedAt"] = None
            updated["deletedAt"] = None

        return self.upsert_watchlist_view(updated)

    def upsert_watchlist_alert(self, payload: dict) -> dict:
        validate_watchlist_alert_payload(payload)
        existing = self.get_watchlist_alert(payload["watchlistId"], payload["alertId"])
        alert = normalize_watchlist_alert_payload(payload, existing)

        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO watchlist_alert_events (
                    alert_id, watchlist_id, ticker, alert_type, severity,
                    status, created_at, acknowledged_at, acknowledged_by,
                    dismissed_at, schema_version, payload_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(alert_id) DO UPDATE SET
                    watchlist_id = excluded.watchlist_id,
                    ticker = excluded.ticker,
                    alert_type = excluded.alert_type,
                    severity = excluded.severity,
                    status = excluded.status,
                    acknowledged_at = excluded.acknowledged_at,
                    acknowledged_by = excluded.acknowledged_by,
                    dismissed_at = excluded.dismissed_at,
                    schema_version = excluded.schema_version,
                    payload_json = excluded.payload_json
                """,
                (
                    alert["alertId"],
                    alert["watchlistId"],
                    alert["ticker"],
                    alert["type"],
                    alert["severity"],
                    alert["status"],
                    alert["createdAt"],
                    alert.get("acknowledgedAt"),
                    alert.get("acknowledgedBy"),
                    alert.get("dismissedAt"),
                    alert["schemaVersion"],
                    json.dumps(alert, sort_keys=True),
                ),
            )

        return alert

    def list_watchlist_alerts(
        self,
        watchlist_id: str,
        include_dismissed: bool,
        limit: int,
    ) -> list[dict]:
        normalized_limit = max(min(limit, 500), 1)
        where_clause = "WHERE watchlist_id = ?"
        params = [watchlist_id]

        if not include_dismissed:
            where_clause += " AND dismissed_at IS NULL"

        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT payload_json
                FROM watchlist_alert_events
                {where_clause}
                ORDER BY created_at DESC
                LIMIT ?
                """,
                [*params, normalized_limit],
            ).fetchall()

        return [
            payload
            for payload in (watchlist_row_to_payload(row) for row in rows)
            if payload is not None
        ]

    def get_watchlist_alert(
        self,
        watchlist_id: str,
        alert_id: str,
    ) -> Optional[dict]:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT payload_json
                FROM watchlist_alert_events
                WHERE watchlist_id = ? AND alert_id = ?
                """,
                (watchlist_id, alert_id),
            ).fetchone()

        return watchlist_row_to_payload(row)

    def update_watchlist_alert_status(
        self,
        watchlist_id: str,
        alert_id: str,
        action: str,
        timestamp: str,
        acknowledged_by: Optional[str] = None,
    ) -> Optional[dict]:
        existing = self.get_watchlist_alert(watchlist_id, alert_id)

        if existing is None:
            return None

        updated = dict(existing)

        if action == "acknowledge":
            updated["acknowledgedAt"] = timestamp
            updated["acknowledgedBy"] = acknowledged_by or "local-user"
            updated["status"] = "acknowledged"
        elif action == "dismiss":
            updated["dismissedAt"] = timestamp
            updated["status"] = "dismissed"
        elif action == "restore":
            updated["dismissedAt"] = None
            updated["_clearDismissedAt"] = True
            updated["status"] = "acknowledged" if updated.get("acknowledgedAt") else "active"
        else:
            return None

        return self.upsert_watchlist_alert(updated)


def validate_payload(payload: dict) -> None:
    if payload.get("schemaVersion") != SCHEMA_VERSION:
        raise ValueError("Snapshot payload must include schemaVersion = 1.")

    provenance = payload.get("provenance")

    if not isinstance(provenance, dict):
        raise ValueError("Snapshot payload must include provenance metadata.")

    for key in ["provider", "providerVersion", "fetchedAt", "sourceSymbol"]:
        if not provenance.get(key):
            raise ValueError(f"Snapshot provenance must include {key}.")


def validate_valuation_payload(payload: dict) -> None:
    if payload.get("schemaVersion") != SCHEMA_VERSION:
        raise ValueError("Valuation payload must include schemaVersion = 1.")

    scenario = payload.get("scenario")

    if not isinstance(scenario, dict) or not scenario.get("id"):
        raise ValueError("Valuation payload must include scenario.id.")

    if not scenario.get("createdAt") or not scenario.get("updatedAt"):
        raise ValueError("Valuation scenario must include timestamps.")


def validate_ranking_run_payload(payload: dict) -> None:
    if payload.get("schemaVersion") != SCHEMA_VERSION:
        raise ValueError("Ranking run payload must include schemaVersion = 1.")

    for key in [
        "runId",
        "strategy",
        "period",
        "computedAt",
        "rankingEngineVersion",
        "universe",
        "eligibilitySettings",
        "rows",
    ]:
        if key not in payload:
            raise ValueError(f"Ranking run payload must include {key}.")

    if not isinstance(payload.get("rows"), list):
        raise ValueError("Ranking run payload rows must be a list.")


def validate_ranking_screen_payload(payload: dict) -> None:
    if payload.get("schemaVersion") != SCHEMA_VERSION:
        raise ValueError("Ranking screen payload must include schemaVersion = 1.")

    for key in [
        "screenId",
        "name",
        "strategy",
        "period",
        "limit",
        "createdAt",
        "updatedAt",
    ]:
        if not payload.get(key):
            raise ValueError(f"Ranking screen payload must include {key}.")


def validate_ranking_refresh_payload(payload: dict) -> None:
    if payload.get("schemaVersion") != SCHEMA_VERSION:
        raise ValueError("Ranking refresh payload must include schemaVersion = 1.")

    for key in ["refreshId", "status", "strategy", "period", "scope"]:
        if key not in payload:
            raise ValueError(f"Ranking refresh payload must include {key}.")

    if payload.get("status") not in {"queued", "running", "completed", "failed"}:
        raise ValueError("Ranking refresh status is invalid.")


def validate_refresh_job_payload(payload: dict) -> None:
    if payload.get("schemaVersion") != SCHEMA_VERSION:
        raise ValueError("Refresh job payload must include schemaVersion = 1.")

    for key in [
        "jobId",
        "jobType",
        "status",
        "scope",
        "payload",
        "createdAt",
        "warnings",
        "errors",
        "resultMetadata",
    ]:
        if key not in payload:
            raise ValueError(f"Refresh job payload must include {key}.")

    if payload.get("status") not in {
        "queued",
        "running",
        "completed",
        "failed",
        "cancelled",
    }:
        raise ValueError("Refresh job status is invalid.")


def validate_refresh_job_event_payload(payload: dict) -> None:
    for key in ["eventId", "eventType", "status", "createdAt"]:
        if key not in payload:
            raise ValueError(f"Refresh job event must include {key}.")


def validate_refresh_policy_payload(payload: dict) -> None:
    if payload.get("schemaVersion") != SCHEMA_VERSION:
        raise ValueError("Refresh policy payload must include schemaVersion = 1.")

    for key in [
        "policyId",
        "name",
        "target",
        "strategy",
        "period",
        "scope",
        "staleAfterSeconds",
        "enabled",
        "scheduleHint",
        "createdAt",
        "updatedAt",
    ]:
        if key not in payload:
            raise ValueError(f"Refresh policy payload must include {key}.")


def validate_watchlist_payload(payload: dict) -> None:
    if payload.get("schemaVersion") != SCHEMA_VERSION:
        raise ValueError("Watchlist payload must include schemaVersion = 1.")

    for key in ["watchlistId", "name", "createdAt", "updatedAt"]:
        if not payload.get(key):
            raise ValueError(f"Watchlist payload must include {key}.")

    if payload.get("status") not in {None, "active", "archived", "deleted"}:
        raise ValueError("Watchlist status is invalid.")


def validate_watchlist_item_payload(payload: dict) -> None:
    if not payload.get("ticker"):
        raise ValueError("Watchlist item payload must include ticker.")

    if not payload.get("addedAt") or not payload.get("updatedAt"):
        raise ValueError("Watchlist item payload must include timestamps.")


def validate_watchlist_view_payload(payload: dict) -> None:
    if payload.get("schemaVersion") != SCHEMA_VERSION:
        raise ValueError("Watchlist view payload must include schemaVersion = 1.")

    for key in ["viewId", "watchlistId", "name", "createdAt", "updatedAt"]:
        if not payload.get(key):
            raise ValueError(f"Watchlist view payload must include {key}.")

    if payload.get("status") not in {None, "active", "archived", "deleted"}:
        raise ValueError("Watchlist view status is invalid.")


def validate_watchlist_alert_payload(payload: dict) -> None:
    if payload.get("schemaVersion") != SCHEMA_VERSION:
        raise ValueError("Watchlist alert payload must include schemaVersion = 1.")

    for key in ["alertId", "watchlistId", "ticker", "type", "severity", "message", "createdAt"]:
        if not payload.get(key):
            raise ValueError(f"Watchlist alert payload must include {key}.")

    if payload.get("status") not in {None, "active", "acknowledged", "dismissed"}:
        raise ValueError("Watchlist alert status is invalid.")


def normalize_watchlist_item_payload(payload: dict) -> dict:
    tags = payload.get("tags") or []

    if not isinstance(tags, list):
        tags = []

    normalized_tags = []

    for tag in tags:
        if not isinstance(tag, str):
            continue

        normalized = " ".join(tag.strip().split())

        if normalized and normalized not in normalized_tags:
            normalized_tags.append(normalized[:40])

    return {
        **payload,
        "ticker": normalize_ticker(payload["ticker"]),
        "companyName": nullable_text(payload.get("companyName")),
        "notes": nullable_text(payload.get("notes")),
        "tags": normalized_tags[:12],
        "targetPrice": nullable_number(payload.get("targetPrice")),
        "thesisStatus": nullable_text(payload.get("thesisStatus")),
        "priority": nullable_text(payload.get("priority")),
        "workflowState": normalize_workflow_state(payload.get("workflowState")),
    }


def normalize_workflow_state(value) -> str:
    normalized = nullable_text(value) or "not_started"

    if normalized not in {
        "not_started",
        "monitoring",
        "needs_review",
        "under_review",
        "thesis_ready",
        "archived",
    }:
        return "not_started"

    return normalized


def normalize_watchlist_view_payload(payload: dict) -> dict:
    filters = payload.get("filters") if isinstance(payload.get("filters"), list) else []
    sorting = payload.get("sorting") if isinstance(payload.get("sorting"), dict) else None
    visible_columns = (
        payload.get("visibleColumns")
        if isinstance(payload.get("visibleColumns"), list)
        else []
    )

    return {
        **payload,
        "name": nullable_text(payload.get("name")) or "Untitled view",
        "filters": filters,
        "sorting": sorting,
        "visibleColumns": [
            column
            for column in visible_columns
            if isinstance(column, str) and column.strip()
        ],
        "status": payload.get("status") or "active",
    }


def normalize_watchlist_alert_payload(payload: dict, existing: Optional[dict]) -> dict:
    force_clear_dismissed_at = bool(payload.get("_clearDismissedAt"))
    acknowledged_at = payload.get("acknowledgedAt")
    acknowledged_by = payload.get("acknowledgedBy")
    dismissed_at = payload.get("dismissedAt")
    status = payload.get("status")

    if existing is not None:
        acknowledged_at = acknowledged_at if acknowledged_at is not None else existing.get("acknowledgedAt")
        acknowledged_by = acknowledged_by if acknowledged_by is not None else existing.get("acknowledgedBy")
        dismissed_at = None if force_clear_dismissed_at else dismissed_at if dismissed_at is not None else existing.get("dismissedAt")
        status = status or existing.get("status")

    if dismissed_at:
        status = "dismissed"
    elif acknowledged_at:
        status = "acknowledged"
    else:
        status = status or "active"

    return {
        **{key: value for key, value in payload.items() if key != "_clearDismissedAt"},
        "createdAt": (existing or {}).get("createdAt") or payload["createdAt"],
        "acknowledgedAt": acknowledged_at,
        "acknowledgedBy": acknowledged_by,
        "dismissedAt": dismissed_at,
        "status": status,
    }


def watchlist_payload_without_items(payload: dict) -> dict:
    return {
        key: value
        for key, value in payload.items()
        if key not in {"items", "provider"}
    }


def watchlist_status_message(status: str) -> str:
    if status == "archived":
        return "Watchlist was archived. It remains queryable for auditability."

    if status == "deleted":
        return "Watchlist was soft deleted. Historical metadata remains persisted."

    return "Watchlist is active."


def ensure_columns(
    connection: sqlite3.Connection,
    table_name: str,
    columns: dict[str, str],
) -> None:
    existing_columns = {
        row["name"]
        for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    }

    for column_name, column_definition in columns.items():
        if column_name not in existing_columns:
            connection.execute(
                f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}"
            )


def upsert_refresh_job_row(connection: sqlite3.Connection, payload: dict) -> None:
    connection.execute(
        """
        INSERT INTO refresh_jobs (
            job_id, job_type, status, schema_version, scope_json,
            payload_json, created_at, started_at, completed_at, failed_at,
            duration_ms, warnings_json, errors_json, result_metadata_json,
            job_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(job_id) DO UPDATE SET
            job_type = excluded.job_type,
            status = excluded.status,
            schema_version = excluded.schema_version,
            scope_json = excluded.scope_json,
            payload_json = excluded.payload_json,
            started_at = excluded.started_at,
            completed_at = excluded.completed_at,
            failed_at = excluded.failed_at,
            duration_ms = excluded.duration_ms,
            warnings_json = excluded.warnings_json,
            errors_json = excluded.errors_json,
            result_metadata_json = excluded.result_metadata_json,
            job_json = excluded.job_json
        """,
        (
            payload["jobId"],
            payload["jobType"],
            payload["status"],
            payload["schemaVersion"],
            json.dumps(payload.get("scope") or {}, sort_keys=True),
            json.dumps(payload.get("payload") or {}, sort_keys=True),
            payload["createdAt"],
            payload.get("startedAt"),
            payload.get("completedAt"),
            payload.get("failedAt"),
            payload.get("durationMs"),
            json.dumps(payload.get("warnings") or [], sort_keys=True),
            json.dumps(payload.get("errors") or [], sort_keys=True),
            json.dumps(payload.get("resultMetadata") or {}, sort_keys=True),
            json.dumps(payload, sort_keys=True),
        ),
    )


def record_valuation_audit_event(
    connection: sqlite3.Connection,
    ticker: str,
    scenario_id: str,
    version_id: str,
    version_number: int,
    event: dict,
    timestamp: str,
) -> None:
    event_id = event.get("id") or f"audit-{scenario_id}-{version_number}-{uuid_suffix()}"
    payload = {
        "id": event_id,
        "scenarioId": scenario_id,
        "ticker": ticker,
        "versionId": version_id,
        "versionNumber": version_number,
        "changeType": event.get("changeType") or "version",
        "fieldPath": event.get("fieldPath"),
        "previousValue": event.get("previousValue"),
        "newValue": event.get("newValue"),
        "createdAt": event.get("createdAt") or timestamp,
        "message": event.get("message"),
    }

    connection.execute(
        """
        INSERT INTO valuation_audit_events (
            event_id, scenario_id, ticker, version_id, version_number,
            change_type, field_path, previous_value_json, new_value_json,
            created_at, payload_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            event_id,
            scenario_id,
            ticker,
            version_id,
            version_number,
            payload["changeType"],
            payload["fieldPath"],
            json.dumps(payload["previousValue"], sort_keys=True),
            json.dumps(payload["newValue"], sort_keys=True),
            payload["createdAt"],
            json.dumps(payload, sort_keys=True),
        ),
    )


def valuation_row_to_payload(row) -> Optional[dict]:
    if row is None:
        return None

    return json.loads(row["payload_json"])


def ranking_row_to_payload(row) -> Optional[dict]:
    if row is None:
        return None

    return json.loads(row["payload_json"])


def refresh_job_row_to_payload(row) -> Optional[dict]:
    if row is None:
        return None

    return json.loads(row["job_json"])


def watchlist_row_to_payload(row) -> Optional[dict]:
    if row is None:
        return None

    return json.loads(row["payload_json"])


def watchlist_item_row_to_payload(row) -> Optional[dict]:
    if row is None:
        return None

    return json.loads(row["payload_json"])


def ranking_run_summary(payload: dict) -> dict:
    return {
        "runId": payload.get("runId"),
        "strategy": payload.get("strategy"),
        "period": payload.get("period"),
        "schemaVersion": payload.get("schemaVersion"),
        "rankingEngineVersion": payload.get("rankingEngineVersion"),
        "computedAt": payload.get("computedAt"),
        "universe": payload.get("universe"),
        "eligibilitySettings": payload.get("eligibilitySettings"),
        "summary": payload.get("summary") or {},
    }


def refresh_job_summary(payload: dict) -> dict:
    return {
        "jobId": payload.get("jobId"),
        "jobType": payload.get("jobType"),
        "status": payload.get("status"),
        "scope": payload.get("scope"),
        "createdAt": payload.get("createdAt"),
        "startedAt": payload.get("startedAt"),
        "completedAt": payload.get("completedAt"),
        "failedAt": payload.get("failedAt"),
        "durationMs": payload.get("durationMs"),
        "warnings": payload.get("warnings") or [],
        "errors": payload.get("errors") or [],
        "resultMetadata": payload.get("resultMetadata") or {},
    }


def ranking_refresh_summary(payload: dict) -> dict:
    return {
        "refreshId": payload.get("refreshId"),
        "status": payload.get("status"),
        "strategy": payload.get("strategy"),
        "period": payload.get("period"),
        "scope": payload.get("scope"),
        "startedAt": payload.get("startedAt"),
        "completedAt": payload.get("completedAt"),
        "failedAt": payload.get("failedAt"),
        "durationMs": payload.get("durationMs"),
        "warnings": payload.get("warnings") or [],
        "errors": payload.get("errors") or [],
        "runId": payload.get("runId"),
    }


def row_to_snapshot(row) -> Optional[dict]:
    if row is None:
        return None

    payload = json.loads(row["payload_json"])

    return {
        **payload,
        "schemaVersion": row["schema_version"],
        "refreshedAt": row["refreshed_at"],
    }


def payload_fiscal_period(payload: dict) -> tuple[Optional[str], Optional[str]]:
    data = payload.get("data")
    row = None

    if isinstance(data, dict):
        for key in [
            "profile",
            "incomeStatements",
            "balanceSheets",
            "cashFlowStatements",
            "metrics",
            "computedMetrics",
        ]:
            value = data.get(key)

            if isinstance(value, dict):
                row = value
                break

            if isinstance(value, list) and value and isinstance(value[0], dict):
                row = value[0]
                break

    if row is None and isinstance(payload.get("row"), dict):
        source = payload["row"].get("source")

        if isinstance(source, dict):
            row = source

    if row is None:
        row = {}

    return nullable_text(row.get("fiscalYear")), nullable_text(row.get("fiscalPeriod"))


def snapshot_age_seconds(snapshot: dict) -> Optional[int]:
    refreshed_at = snapshot.get("refreshedAt")

    if not isinstance(refreshed_at, str):
        return None

    try:
        timestamp = datetime.fromisoformat(refreshed_at.replace("Z", "+00:00"))

        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)

        return max(int((datetime.now(timezone.utc) - timestamp).total_seconds()), 0)
    except ValueError:
        return None


def snapshot_is_stale(snapshot: dict, stale_after_seconds: int) -> bool:
    age_seconds = snapshot_age_seconds(snapshot)

    if age_seconds is None:
        return True

    return age_seconds > stale_after_seconds


def valuation_payload_is_stale(payload: dict, stale_after_seconds: int) -> bool:
    age_seconds = snapshot_age_seconds(
        {"refreshedAt": (payload.get("modelMetadata") or {}).get("computationTimestamp")}
    )

    if age_seconds is None:
        age_seconds = snapshot_age_seconds({"refreshedAt": payload.get("updatedAt")})

    if age_seconds is None:
        return True

    return age_seconds > stale_after_seconds


def ranking_payload_is_stale(payload: dict, stale_after_seconds: int) -> bool:
    age_seconds = snapshot_age_seconds({"refreshedAt": payload.get("computedAt")})

    if age_seconds is None:
        return True

    return age_seconds > stale_after_seconds


def valuation_reproducibility_complete(payload: dict) -> bool:
    reproducibility = payload.get("reproducibility")

    if not isinstance(reproducibility, dict):
        return False

    references = reproducibility.get("statementSnapshotReferences") or {}
    required_references = ["incomeStatement", "balanceSheet", "cashFlowStatement"]

    return all(isinstance(references.get(key), dict) for key in required_references)


def oldest_refreshed_at(snapshots) -> Optional[str]:
    values = [
        snapshot.get("refreshedAt")
        for snapshot in snapshots
        if isinstance(snapshot.get("refreshedAt"), str)
    ]

    return min(values) if values else None


def newest_refreshed_at(snapshots) -> Optional[str]:
    values = [
        snapshot.get("refreshedAt")
        for snapshot in snapshots
        if isinstance(snapshot.get("refreshedAt"), str)
    ]

    return max(values) if values else None


def normalize_tickers(tickers: list[str]) -> list[str]:
    normalized = []

    for ticker in tickers:
        normalized_ticker = normalize_ticker(ticker)

        if normalized_ticker and normalized_ticker not in normalized:
            normalized.append(normalized_ticker)

    return normalized


def normalize_ticker(ticker: str) -> str:
    return ticker.strip().upper()


def normalize_period(period: str) -> str:
    normalized = period.strip().lower()

    if normalized in {"annual", "quarter", "profile"}:
        return normalized

    return "annual"


def nullable_text(value) -> Optional[str]:
    if value is None:
        return None

    if isinstance(value, str):
        normalized = value.strip()

        return normalized if normalized else None

    return str(value)


def nullable_number(value) -> Optional[float]:
    if isinstance(value, bool):
        return None

    if isinstance(value, (int, float)):
        return float(value)

    if isinstance(value, str) and value.strip():
        try:
            return float(value)
        except ValueError:
            return None

    return None


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def stale_cutoff(stale_after_seconds: int) -> str:
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=max(stale_after_seconds, 0))

    return cutoff.isoformat()


def uuid_suffix() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")


def refresh_job_event_id(job_id: str, event_type: str) -> str:
    return f"event-{job_id}-{event_type}-{uuid_suffix()}"


def duration_ms(started_at: Optional[str], finished_at: Optional[str]) -> Optional[int]:
    if not started_at or not finished_at:
        return None

    try:
        started = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        finished = datetime.fromisoformat(finished_at.replace("Z", "+00:00"))

        return max(int((finished - started).total_seconds() * 1000), 0)
    except ValueError:
        return None
