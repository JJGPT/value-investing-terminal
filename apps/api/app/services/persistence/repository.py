from typing import Optional, Protocol


class SnapshotRepository(Protocol):
    def repository_status(self) -> dict:
        """Return safe repository readiness metadata."""

    def upsert_universe(
        self,
        universe_name: str,
        tickers: list[str],
        source: str,
    ) -> None:
        """Persist the active controlled ticker universe."""

    def list_universe(self, universe_name: str) -> list[str]:
        """Return persisted universe tickers."""

    def upsert_fundamentals_snapshot(
        self,
        ticker: str,
        period: str,
        snapshot_type: str,
        payload: dict,
    ) -> None:
        """Persist a versioned normalized fundamentals snapshot."""

    def get_fundamentals_snapshot(
        self,
        ticker: str,
        period: str,
        snapshot_type: str,
    ) -> Optional[dict]:
        """Read a normalized fundamentals snapshot."""

    def upsert_computed_metrics_snapshot(
        self,
        ticker: str,
        period: str,
        payload: dict,
    ) -> None:
        """Persist a versioned platform-computed metrics snapshot."""

    def get_computed_metrics_snapshot(
        self,
        ticker: str,
        period: str,
    ) -> Optional[dict]:
        """Read a platform-computed metrics snapshot."""

    def upsert_screener_row_snapshot(
        self,
        ticker: str,
        period: str,
        payload: dict,
    ) -> None:
        """Persist a versioned screener row snapshot."""

    def get_screener_row_snapshot(
        self,
        ticker: str,
        period: str,
    ) -> Optional[dict]:
        """Read a screener row snapshot."""

    def get_screener_row_snapshots(
        self,
        tickers: list[str],
        period: str,
    ) -> dict[str, dict]:
        """Read screener row snapshots for a ticker list."""

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
        """Persist manual refresh run metadata."""

    def snapshot_freshness(
        self,
        universe_name: str,
        configured_tickers: list[str],
        periods: list[str],
        stale_after_seconds: int,
    ) -> list[dict]:
        """Return snapshot freshness summaries by period."""

    def upsert_valuation_scenario(
        self,
        ticker: str,
        scenario_id: str,
        payload: dict,
    ) -> None:
        """Persist a versioned valuation scenario separately from snapshots."""

    def get_latest_valuation_scenario(self, ticker: str) -> Optional[dict]:
        """Return the most recently updated valuation scenario for a ticker."""

    def list_valuation_scenarios(
        self,
        ticker: str,
        limit: int,
        include_archived: bool = False,
        include_deleted: bool = False,
    ) -> list[dict]:
        """Return recent valuation scenarios for a ticker."""

    def get_valuation_scenario(
        self,
        ticker: str,
        scenario_id: str,
    ) -> Optional[dict]:
        """Return one persisted valuation scenario."""

    def get_valuation_scenario_version(
        self,
        ticker: str,
        scenario_id: str,
        version_id: str,
    ) -> Optional[dict]:
        """Return one immutable valuation scenario version."""

    def list_valuation_scenario_versions(
        self,
        ticker: str,
        scenario_id: str,
    ) -> list[dict]:
        """Return immutable versions for one valuation scenario."""

    def list_valuation_audit_events(
        self,
        ticker: str,
        scenario_id: str,
    ) -> list[dict]:
        """Return audit events for one valuation scenario."""

    def add_valuation_note(
        self,
        ticker: str,
        scenario_id: str,
        payload: dict,
    ) -> dict:
        """Persist an immutable analyst note attached to a scenario version."""

    def list_valuation_notes(
        self,
        ticker: str,
        scenario_id: str,
    ) -> list[dict]:
        """Return immutable analyst notes for one valuation scenario."""

    def valuation_repository_diagnostics(
        self,
        ticker: str,
        stale_after_seconds: int,
    ) -> dict:
        """Return repository-level valuation integrity diagnostics."""

    def create_ranking_run(self, payload: dict) -> dict:
        """Persist one immutable ranking run and its row snapshots."""

    def list_ranking_runs(
        self,
        strategy: Optional[str],
        period: Optional[str],
        limit: int,
    ) -> list[dict]:
        """Return recent ranking run summaries."""

    def get_ranking_run(self, run_id: str) -> Optional[dict]:
        """Return one persisted ranking run payload."""

    def get_previous_ranking_run(
        self,
        strategy: str,
        period: str,
        before_computed_at: str,
    ) -> Optional[dict]:
        """Return the previous ranking run for change comparisons."""

    def ranking_repository_diagnostics(self, stale_after_seconds: int) -> dict:
        """Return ranking-run repository diagnostics."""

    def upsert_ranking_screen(self, payload: dict) -> dict:
        """Persist a saved ranking screen definition."""

    def list_ranking_screens(
        self,
        include_archived: bool,
        include_deleted: bool,
        limit: int,
    ) -> list[dict]:
        """Return saved ranking screens."""

    def get_ranking_screen(self, screen_id: str) -> Optional[dict]:
        """Return one saved ranking screen."""

    def record_ranking_refresh_run(self, payload: dict) -> dict:
        """Persist ranking refresh workflow execution metadata."""

    def list_ranking_refresh_runs(
        self,
        strategy: Optional[str],
        period: Optional[str],
        limit: int,
    ) -> list[dict]:
        """Return recent ranking refresh workflow runs."""

    def create_refresh_job(self, payload: dict) -> dict:
        """Persist a refresh job."""

    def update_refresh_job(self, payload: dict) -> dict:
        """Update a persisted refresh job."""

    def get_refresh_job(self, job_id: str) -> Optional[dict]:
        """Return one refresh job."""

    def list_refresh_jobs(
        self,
        job_type: Optional[str],
        status: Optional[str],
        limit: int,
    ) -> list[dict]:
        """Return recent refresh jobs."""

    def append_refresh_job_event(self, job_id: str, payload: dict) -> dict:
        """Append an immutable refresh job event."""

    def list_refresh_job_events(self, job_id: str) -> list[dict]:
        """Return immutable events for one refresh job."""

    def cancel_refresh_job(self, job_id: str, timestamp: str) -> Optional[dict]:
        """Best-effort cancel of a queued refresh job."""

    def refresh_job_repository_diagnostics(self, stale_after_seconds: int) -> dict:
        """Return refresh job repository diagnostics."""

    def upsert_refresh_policy(self, payload: dict) -> dict:
        """Persist a refresh policy definition."""

    def list_refresh_policies(
        self,
        include_disabled: bool,
        limit: int,
    ) -> list[dict]:
        """Return refresh policies."""

    def get_refresh_policy(self, policy_id: str) -> Optional[dict]:
        """Return one refresh policy."""

    def refresh_policy_repository_diagnostics(self, stale_after_seconds: int) -> dict:
        """Return refresh policy repository diagnostics."""

    def upsert_watchlist(self, payload: dict) -> dict:
        """Persist a watchlist metadata payload."""

    def list_watchlists(
        self,
        include_archived: bool,
        include_deleted: bool,
        limit: int,
    ) -> list[dict]:
        """Return persisted watchlists."""

    def get_watchlist(self, watchlist_id: str) -> Optional[dict]:
        """Return one persisted watchlist with items."""

    def update_watchlist_status(
        self,
        watchlist_id: str,
        status: str,
        timestamp: str,
    ) -> Optional[dict]:
        """Archive, restore, or soft delete a watchlist."""

    def upsert_watchlist_item(
        self,
        watchlist_id: str,
        payload: dict,
    ) -> Optional[dict]:
        """Add or update one watchlist item."""

    def remove_watchlist_item(
        self,
        watchlist_id: str,
        ticker: str,
        timestamp: str,
    ) -> Optional[dict]:
        """Remove one watchlist item."""

    def watchlist_repository_diagnostics(self, stale_after_seconds: int) -> dict:
        """Return watchlist repository diagnostics."""

    def upsert_watchlist_view(self, payload: dict) -> dict:
        """Persist a saved watchlist view definition."""

    def list_watchlist_views(
        self,
        watchlist_id: str,
        include_archived: bool,
        include_deleted: bool,
        limit: int,
    ) -> list[dict]:
        """Return saved views for one watchlist."""

    def get_watchlist_view(
        self,
        watchlist_id: str,
        view_id: str,
    ) -> Optional[dict]:
        """Return one saved watchlist view."""

    def update_watchlist_view_status(
        self,
        watchlist_id: str,
        view_id: str,
        status: str,
        timestamp: str,
    ) -> Optional[dict]:
        """Archive, restore, or soft delete a saved watchlist view."""

    def upsert_watchlist_alert(self, payload: dict) -> dict:
        """Persist or refresh one deterministic watchlist alert record."""

    def list_watchlist_alerts(
        self,
        watchlist_id: str,
        include_dismissed: bool,
        limit: int,
    ) -> list[dict]:
        """Return persisted watchlist alert history."""

    def get_watchlist_alert(
        self,
        watchlist_id: str,
        alert_id: str,
    ) -> Optional[dict]:
        """Return one persisted alert record."""

    def update_watchlist_alert_status(
        self,
        watchlist_id: str,
        alert_id: str,
        action: str,
        timestamp: str,
        acknowledged_by: Optional[str] = None,
    ) -> Optional[dict]:
        """Acknowledge, dismiss, or restore a deterministic alert."""
