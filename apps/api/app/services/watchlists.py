from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from app.services.fundamentals.provider import FundamentalsProvider
from app.services.jobs.runner import (
    create_job,
    job_event,
    mark_job_completed,
    mark_job_failed,
    mark_job_running,
)
from app.services.market_data.provider import MarketDataProvider
from app.services.persistence.repository import SnapshotRepository
from app.services.persistence.sqlite_repository import SCHEMA_VERSION
from app.services.provider_status import provider_connected, provider_degraded
from app.services.rankings.engine import ranking_changes, refresh_ranking_run
from app.services.screener.engine import refresh_screener_snapshots, snapshot_metadata
from app.services.valuation.dcf import scenario_summary

WATCHLIST_SCHEMA_VERSION = SCHEMA_VERSION
DEFAULT_WATCHLIST_LIMIT = 50
DEFAULT_WATCHLIST_PERIOD = "annual"
VALUATION_GAP_ALERT_THRESHOLD = 0.25
DEFAULT_VISIBLE_COLUMNS = [
    "ticker",
    "company",
    "price",
    "target",
    "valuationGap",
    "rank",
    "eligibility",
    "freshness",
    "staleness",
    "provider",
    "status",
    "workflowState",
    "priority",
    "alerts",
    "flags",
    "notes",
]
WATCHLIST_FILTER_FIELDS = {
    "ticker",
    "tags",
    "thesisStatus",
    "priority",
    "workflowState",
    "valuationGap",
    "rankingStatus",
    "alertType",
    "staleSnapshot",
    "missingCriticalData",
    "providerDegraded",
}
WATCHLIST_SORT_FIELDS = {
    "ticker",
    "priority",
    "valuationGap",
    "latestRank",
    "alertCount",
    "snapshotFreshness",
    "addedAt",
}
WATCHLIST_WORKFLOW_STATES = {
    "not_started",
    "monitoring",
    "needs_review",
    "under_review",
    "thesis_ready",
    "archived",
}
WATCHLIST_REFRESH_JOB_TYPE = "watchlist_refresh"


def list_watchlists_response(
    repository: SnapshotRepository,
    include_archived: bool = False,
    include_deleted: bool = False,
    limit: int = DEFAULT_WATCHLIST_LIMIT,
) -> dict:
    return {
        "watchlists": [
            with_provider(watchlist, repository)
            for watchlist in repository.list_watchlists(
                include_archived,
                include_deleted,
                limit,
            )
        ],
        "provider": watchlist_store_provider(repository),
        "message": "Watchlists are persisted in local SQLite JSON payloads.",
    }


def create_watchlist(repository: SnapshotRepository, payload: dict) -> dict:
    timestamp = utc_now()
    watchlist = {
        "watchlistId": watchlist_id(),
        "schemaVersion": WATCHLIST_SCHEMA_VERSION,
        "name": normalize_name(payload.get("name"), "Untitled watchlist"),
        "description": normalize_text(payload.get("description"), max_length=500),
        "status": "active",
        "items": [],
        "createdAt": timestamp,
        "updatedAt": timestamp,
        "archivedAt": None,
        "deletedAt": None,
        "message": (
            "Watchlist was created. Alerts are deterministic research signals, "
            "not recommendations."
        ),
    }

    persisted = repository.upsert_watchlist(watchlist)

    return with_provider(persisted, repository)


def update_watchlist(
    repository: SnapshotRepository,
    watchlist_id_value: str,
    payload: dict,
) -> Optional[dict]:
    existing = repository.get_watchlist(watchlist_id_value)

    if existing is None:
        return None

    updated = {
        **without_provider(existing),
        "name": normalize_name(payload.get("name") or existing.get("name"), "Untitled watchlist"),
        "description": (
            normalize_text(payload.get("description"), max_length=500)
            if "description" in payload
            else existing.get("description")
        ),
        "updatedAt": utc_now(),
        "message": "Watchlist metadata was updated.",
    }

    persisted = repository.upsert_watchlist(updated)

    return with_provider(persisted, repository)


def set_watchlist_lifecycle(
    repository: SnapshotRepository,
    watchlist_id_value: str,
    action: str,
) -> Optional[dict]:
    if action == "archive":
        result = repository.update_watchlist_status(
            watchlist_id_value,
            "archived",
            utc_now(),
        )

        return with_provider(result, repository) if result else None

    if action == "restore":
        result = repository.update_watchlist_status(
            watchlist_id_value,
            "active",
            utc_now(),
        )

        return with_provider(result, repository) if result else None

    if action == "delete":
        result = repository.update_watchlist_status(
            watchlist_id_value,
            "deleted",
            utc_now(),
        )

        return with_provider(result, repository) if result else None

    return None


def add_watchlist_item(
    repository: SnapshotRepository,
    watchlist_id_value: str,
    payload: dict,
) -> Optional[dict]:
    timestamp = utc_now()
    ticker = normalize_ticker(payload.get("ticker"))
    item = {
        "ticker": ticker,
        "companyName": normalize_text(payload.get("companyName"), max_length=180),
        "addedAt": timestamp,
        "updatedAt": timestamp,
        "notes": normalize_text(payload.get("notes"), max_length=1000),
        "tags": normalize_tags(payload.get("tags")),
        "targetPrice": normalize_optional_number(payload.get("targetPrice")),
        "thesisStatus": normalize_text(payload.get("thesisStatus"), max_length=80),
        "priority": normalize_text(payload.get("priority"), max_length=40),
        "workflowState": normalize_workflow_state(payload.get("workflowState")),
    }

    if not item["companyName"]:
        item["companyName"] = company_name_from_snapshots(repository, ticker)

    persisted = repository.upsert_watchlist_item(watchlist_id_value, item)

    return with_provider(persisted, repository) if persisted else None


def update_watchlist_item(
    repository: SnapshotRepository,
    watchlist_id_value: str,
    ticker: str,
    payload: dict,
) -> Optional[dict]:
    watchlist = repository.get_watchlist(watchlist_id_value)

    if watchlist is None:
        return None

    normalized_ticker = normalize_ticker(ticker)
    existing = next(
        (
            item
            for item in watchlist.get("items") or []
            if item.get("ticker") == normalized_ticker
        ),
        None,
    )

    if existing is None:
        return None

    updated = {
        **existing,
        "ticker": normalized_ticker,
        "companyName": (
            normalize_text(payload.get("companyName"), max_length=180)
            if "companyName" in payload
            else existing.get("companyName")
        ),
        "notes": (
            normalize_text(payload.get("notes"), max_length=1000)
            if "notes" in payload
            else existing.get("notes")
        ),
        "tags": (
            normalize_tags(payload.get("tags"))
            if "tags" in payload
            else existing.get("tags") or []
        ),
        "targetPrice": (
            normalize_optional_number(payload.get("targetPrice"))
            if "targetPrice" in payload
            else existing.get("targetPrice")
        ),
        "thesisStatus": (
            normalize_text(payload.get("thesisStatus"), max_length=80)
            if "thesisStatus" in payload
            else existing.get("thesisStatus")
        ),
        "priority": (
            normalize_text(payload.get("priority"), max_length=40)
            if "priority" in payload
            else existing.get("priority")
        ),
        "workflowState": (
            normalize_workflow_state(payload.get("workflowState"))
            if "workflowState" in payload
            else normalize_workflow_state(existing.get("workflowState"))
        ),
        "updatedAt": utc_now(),
    }

    persisted = repository.upsert_watchlist_item(watchlist_id_value, updated)

    return with_provider(persisted, repository) if persisted else None


def remove_watchlist_item(
    repository: SnapshotRepository,
    watchlist_id_value: str,
    ticker: str,
) -> Optional[dict]:
    result = repository.remove_watchlist_item(
        watchlist_id_value,
        normalize_ticker(ticker),
        utc_now(),
    )

    return with_provider(result, repository) if result else None


def build_watchlist_intelligence(
    repository: SnapshotRepository,
    market_data_provider: MarketDataProvider,
    watchlist_id_value: str,
    stale_after_seconds: int,
    filters: Optional[list[dict]] = None,
    sorting: Optional[dict] = None,
    view_id: Optional[str] = None,
) -> Optional[dict]:
    watchlist = repository.get_watchlist(watchlist_id_value)

    if watchlist is None:
        return None

    watchlist = with_provider(watchlist, repository)
    view = repository.get_watchlist_view(watchlist_id_value, view_id) if view_id else None
    resolved_filters = normalize_watchlist_filters(
        view.get("filters") if view and filters is None else filters
    )
    resolved_sorting = normalize_watchlist_sorting(
        view.get("sorting") if view and sorting is None else sorting
    )
    visible_columns = normalize_visible_columns(
        view.get("visibleColumns") if view else None
    )

    latest_ranking_run = latest_run(repository, "magic_formula", DEFAULT_WATCHLIST_PERIOD)
    previous_ranking_run = (
        repository.get_previous_ranking_run(
            latest_ranking_run["strategy"],
            latest_ranking_run["period"],
            latest_ranking_run["computedAt"],
        )
        if latest_ranking_run
        else None
    )
    ranking_change_lookup = {
        change["ticker"]: change
        for change in ranking_changes(latest_ranking_run, previous_ranking_run)
    } if latest_ranking_run else {}
    all_items = [
        build_watchlist_intelligence_item(
            repository,
            market_data_provider,
            watchlist,
            item,
            stale_after_seconds,
            latest_ranking_run,
            ranking_change_lookup,
        )
        for item in watchlist.get("items") or []
    ]
    all_items = sync_item_alerts(repository, all_items)
    filtered_items = apply_watchlist_filters(all_items, resolved_filters)
    items = apply_watchlist_sort(filtered_items, resolved_sorting)

    return {
        "watchlist": watchlist,
        "items": items,
        "allItemCount": len(all_items),
        "provider": intelligence_provider(items, repository, market_data_provider),
        "alertCount": sum(len(item.get("alerts") or []) for item in items),
        "activeAlertCount": sum(
            1
            for item in items
            for alert in item.get("alerts") or []
            if not alert.get("dismissedAt")
        ),
        "view": view,
        "query": {
            "filters": resolved_filters,
            "sorting": resolved_sorting,
            "visibleColumns": visible_columns,
        },
        "message": (
            "Watchlist intelligence aggregates deterministic snapshots, rankings, "
            "valuation scenarios, and provider status. It is not investment advice."
        ),
    }


def build_watchlist_alerts(
    repository: SnapshotRepository,
    market_data_provider: MarketDataProvider,
    watchlist_id_value: str,
    stale_after_seconds: int,
    include_dismissed: bool = False,
) -> Optional[dict]:
    intelligence = build_watchlist_intelligence(
        repository,
        market_data_provider,
        watchlist_id_value,
        stale_after_seconds,
    )

    if intelligence is None:
        return None

    alerts = repository.list_watchlist_alerts(
        watchlist_id_value,
        include_dismissed,
        500,
    )

    return {
        "watchlist": intelligence["watchlist"],
        "alerts": alerts,
        "provider": intelligence["provider"],
        "message": (
            "Alerts are rule-based research records only. They do not send "
            "notifications and are not recommendations."
        ),
    }


def build_watchlist_alert_history(
    repository: SnapshotRepository,
    market_data_provider: MarketDataProvider,
    watchlist_id_value: str,
    stale_after_seconds: int,
) -> Optional[dict]:
    result = build_watchlist_alerts(
        repository,
        market_data_provider,
        watchlist_id_value,
        stale_after_seconds,
        include_dismissed=True,
    )

    if result is None:
        return None

    return {
        **result,
        "message": (
            "Alert history includes active, acknowledged, and dismissed "
            "deterministic alert records. No notifications are sent."
        ),
    }


def build_watchlist_staleness(
    repository: SnapshotRepository,
    market_data_provider: MarketDataProvider,
    watchlist_id_value: str,
    stale_after_seconds: int,
) -> Optional[dict]:
    intelligence = build_watchlist_intelligence(
        repository,
        market_data_provider,
        watchlist_id_value,
        stale_after_seconds,
    )

    if intelligence is None:
        return None

    items = [
        {
            "ticker": item["ticker"],
            "companyName": item.get("companyName"),
            "workflowState": normalize_workflow_state(
                (item.get("item") or {}).get("workflowState")
            ),
            **item["staleness"],
        }
        for item in intelligence.get("items") or []
    ]

    return {
        "watchlist": intelligence["watchlist"],
        "items": items,
        "counts": staleness_counts(items),
        "provider": intelligence["provider"],
        "staleAfterSeconds": stale_after_seconds,
        "message": (
            "Watchlist staleness is deterministic metadata over snapshots, "
            "rankings, valuations, and provider status. It is not a recommendation."
        ),
    }


def build_watchlist_refresh_history(
    repository: SnapshotRepository,
    watchlist_id_value: str,
    limit: int = DEFAULT_WATCHLIST_LIMIT,
) -> Optional[dict]:
    watchlist = repository.get_watchlist(watchlist_id_value)

    if watchlist is None:
        return None

    jobs = [
        job
        for job in repository.list_refresh_jobs(WATCHLIST_REFRESH_JOB_TYPE, None, limit)
        if (job.get("payload") or {}).get("watchlistId") == watchlist_id_value
        or (job.get("scope") or {}).get("watchlistId") == watchlist_id_value
    ]

    return {
        "watchlist": with_provider(watchlist, repository),
        "jobs": jobs,
        "provider": watchlist_store_provider(repository),
        "message": "Watchlist refresh history is read from the local job store.",
    }


def run_watchlist_refresh_job(
    fundamentals_provider: FundamentalsProvider,
    market_data_provider: MarketDataProvider,
    repository: SnapshotRepository,
    watchlist_id_value: str,
    period: str,
    stale_after_seconds: int,
    strategy: str = "magic_formula",
    stale_only: bool = True,
) -> Optional[dict]:
    watchlist = repository.get_watchlist(watchlist_id_value)

    if watchlist is None:
        return None

    normalized_period = normalize_period(period)
    normalized_strategy = normalize_strategy(strategy)
    tickers = [
        normalize_ticker(item.get("ticker"))
        for item in watchlist.get("items") or []
        if normalize_ticker(item.get("ticker"))
    ]
    job = create_job(
        repository,
        WATCHLIST_REFRESH_JOB_TYPE,
        scope={
            "type": "watchlist",
            "watchlistId": watchlist_id_value,
            "tickers": tickers,
            "period": normalized_period,
            "strategy": normalized_strategy,
            "staleOnly": stale_only,
            "scopeVersion": "watchlist-refresh-scope-v1",
            "schemaVersion": WATCHLIST_SCHEMA_VERSION,
        },
        payload={
            "target": "watchlist",
            "watchlistId": watchlist_id_value,
            "period": normalized_period,
            "strategy": normalized_strategy,
            "tickers": tickers,
            "staleOnly": stale_only,
            "staleAfterSeconds": stale_after_seconds,
            "schemaVersion": WATCHLIST_SCHEMA_VERSION,
        },
    )
    running = mark_job_running(repository, job)
    started_at = running.get("startedAt") or utc_now()

    try:
        before = build_watchlist_staleness(
            repository,
            market_data_provider,
            watchlist_id_value,
            stale_after_seconds,
        )
        refresh_tickers = watchlist_refresh_tickers(
            tickers,
            (before or {}).get("items") or [],
            stale_only,
        )
        stale_metadata = watchlist_stale_only_metadata(
            tickers,
            (before or {}).get("items") or [],
            refresh_tickers,
            stale_only,
            stale_after_seconds,
        )

        running = {
            **running,
            "scope": {
                **(running.get("scope") or {}),
                "tickers": refresh_tickers,
                "staleOnly": stale_only,
            },
            "payload": {
                **(running.get("payload") or {}),
                "tickers": refresh_tickers,
            },
        }
        repository.update_refresh_job(running)

        if not refresh_tickers:
            result = watchlist_refresh_result(
                running,
                watchlist_id_value,
                normalized_strategy,
                normalized_period,
                tickers,
                refresh_tickers,
                stale_metadata,
                before,
                before,
                None,
                None,
                "completed",
                [],
                [],
                started_at,
            )

            return mark_job_completed(repository, running, result, [])

        screener_result = refresh_screener_snapshots(
            fundamentals_provider,
            repository,
            normalized_period,
            universe=refresh_tickers,
        )
        ranking_result = refresh_ranking_run(
            fundamentals_provider,
            market_data_provider,
            repository,
            normalized_strategy,
            normalized_period,
            stale_after_seconds=stale_after_seconds,
            scope_type="tickers",
            tickers=refresh_tickers,
            stale_only=stale_only,
        )
        after = build_watchlist_staleness(
            repository,
            market_data_provider,
            watchlist_id_value,
            stale_after_seconds,
        )
        status = watchlist_refresh_status(screener_result, ranking_result)
        errors = watchlist_refresh_errors(screener_result, ranking_result)
        warnings = watchlist_refresh_warnings(stale_only, refresh_tickers, tickers)
        result = watchlist_refresh_result(
            running,
            watchlist_id_value,
            normalized_strategy,
            normalized_period,
            tickers,
            refresh_tickers,
            stale_metadata,
            before,
            after,
            screener_result,
            ranking_result,
            status,
            warnings,
            errors,
            started_at,
        )
        repository.append_refresh_job_event(
            running["jobId"],
            job_event(
                running["jobId"],
                "watchlist_refresh_executed",
                "running",
                "Watchlist refresh executed screener and ranking refresh logic.",
                {
                    "watchlistId": watchlist_id_value,
                    "refreshedCount": len(refresh_tickers),
                    "status": status,
                },
            ),
        )

        if status == "failed":
            return mark_job_failed(repository, running, errors, result)

        return mark_job_completed(repository, running, result, warnings)
    except Exception as error:  # defensive job boundary
        return mark_job_failed(
            repository,
            running,
            errors=[{"message": sanitize_error(str(error))}],
            result=None,
        )


def update_watchlist_alert_lifecycle(
    repository: SnapshotRepository,
    market_data_provider: MarketDataProvider,
    watchlist_id_value: str,
    alert_id: str,
    action: str,
    stale_after_seconds: int,
    acknowledged_by: Optional[str] = None,
) -> Optional[dict]:
    history = build_watchlist_alert_history(
        repository,
        market_data_provider,
        watchlist_id_value,
        stale_after_seconds,
    )

    if history is None:
        return None

    updated = repository.update_watchlist_alert_status(
        watchlist_id_value,
        alert_id,
        action,
        utc_now(),
        acknowledged_by=acknowledged_by or "local-user",
    )

    return updated


def list_watchlist_views_response(
    repository: SnapshotRepository,
    watchlist_id_value: str,
    include_archived: bool = False,
    include_deleted: bool = False,
    limit: int = DEFAULT_WATCHLIST_LIMIT,
) -> Optional[dict]:
    if repository.get_watchlist(watchlist_id_value) is None:
        return None

    return {
        "watchlistId": watchlist_id_value,
        "views": repository.list_watchlist_views(
            watchlist_id_value,
            include_archived,
            include_deleted,
            limit,
        ),
        "message": "Saved watchlist views persist filters, sorting, and visible columns.",
    }


def create_watchlist_view(
    repository: SnapshotRepository,
    watchlist_id_value: str,
    payload: dict,
) -> Optional[dict]:
    if repository.get_watchlist(watchlist_id_value) is None:
        return None

    timestamp = utc_now()
    view = {
        "viewId": watchlist_view_id(),
        "watchlistId": watchlist_id_value,
        "schemaVersion": WATCHLIST_SCHEMA_VERSION,
        "name": normalize_name(payload.get("name"), "Untitled view"),
        "filters": normalize_watchlist_filters(payload.get("filters")),
        "sorting": normalize_watchlist_sorting(payload.get("sorting")),
        "visibleColumns": normalize_visible_columns(payload.get("visibleColumns")),
        "status": "active",
        "createdAt": timestamp,
        "updatedAt": timestamp,
        "archivedAt": None,
        "deletedAt": None,
        "message": "Saved watchlist view was created.",
    }

    return repository.upsert_watchlist_view(view)


def update_watchlist_view(
    repository: SnapshotRepository,
    watchlist_id_value: str,
    view_id: str,
    payload: dict,
) -> Optional[dict]:
    existing = repository.get_watchlist_view(watchlist_id_value, view_id)

    if existing is None:
        return None

    updated = {
        **existing,
        "name": normalize_name(payload.get("name") or existing.get("name"), "Untitled view"),
        "filters": (
            normalize_watchlist_filters(payload.get("filters"))
            if "filters" in payload
            else existing.get("filters") or []
        ),
        "sorting": (
            normalize_watchlist_sorting(payload.get("sorting"))
            if "sorting" in payload
            else existing.get("sorting")
        ),
        "visibleColumns": (
            normalize_visible_columns(payload.get("visibleColumns"))
            if "visibleColumns" in payload
            else normalize_visible_columns(existing.get("visibleColumns"))
        ),
        "updatedAt": utc_now(),
        "message": "Saved watchlist view was updated.",
    }

    return repository.upsert_watchlist_view(updated)


def duplicate_watchlist_view(
    repository: SnapshotRepository,
    watchlist_id_value: str,
    view_id: str,
    payload: Optional[dict] = None,
) -> Optional[dict]:
    existing = repository.get_watchlist_view(watchlist_id_value, view_id)

    if existing is None:
        return None

    timestamp = utc_now()
    duplicate = {
        **existing,
        "viewId": watchlist_view_id(),
        "name": normalize_name(
            (payload or {}).get("name") or f"{existing.get('name')} Copy",
            "Copied view",
        ),
        "status": "active",
        "parentViewId": existing.get("viewId"),
        "createdAt": timestamp,
        "updatedAt": timestamp,
        "archivedAt": None,
        "deletedAt": None,
        "message": "Saved watchlist view was duplicated.",
    }

    return repository.upsert_watchlist_view(duplicate)


def set_watchlist_view_lifecycle(
    repository: SnapshotRepository,
    watchlist_id_value: str,
    view_id: str,
    action: str,
) -> Optional[dict]:
    status = {
        "archive": "archived",
        "restore": "active",
        "delete": "deleted",
    }.get(action)

    if status is None:
        return None

    return repository.update_watchlist_view_status(
        watchlist_id_value,
        view_id,
        status,
        utc_now(),
    )


def staleness_counts(items: list[dict]) -> dict:
    counts = {
        "fresh": 0,
        "stale": 0,
        "missing": 0,
        "degraded": 0,
    }

    for item in items:
        state = item.get("state")

        if state in counts:
            counts[state] += 1

    return {
        **counts,
        "total": len(items),
    }


def watchlist_refresh_tickers(
    tickers: list[str],
    staleness_items: list[dict],
    stale_only: bool,
) -> list[str]:
    if not stale_only:
        return tickers

    stale_lookup = {
        item.get("ticker"): item.get("state")
        for item in staleness_items
    }

    return [
        ticker
        for ticker in tickers
        if stale_lookup.get(ticker) in {"stale", "missing", "degraded"}
    ]


def watchlist_stale_only_metadata(
    tickers: list[str],
    staleness_items: list[dict],
    refresh_tickers: list[str],
    stale_only: bool,
    stale_after_seconds: int,
) -> dict:
    refresh_set = set(refresh_tickers)
    classification = []
    counts = staleness_counts(staleness_items)

    for ticker in tickers:
        item = next(
            (
                staleness_item
                for staleness_item in staleness_items
                if staleness_item.get("ticker") == ticker
            ),
            None,
        )
        classification.append(
            {
                "ticker": ticker,
                "state": (item or {}).get("state") or "missing",
                "ageSeconds": (item or {}).get("maxAgeSeconds"),
                "refreshed": ticker in refresh_set,
                "reasons": (item or {}).get("staleReasons") or [],
            }
        )

    return {
        "enabled": stale_only,
        "staleAfterSeconds": stale_after_seconds,
        "universeSize": len(tickers),
        "freshCount": counts["fresh"],
        "staleCount": counts["stale"],
        "missingCount": counts["missing"],
        "degradedCount": counts["degraded"],
        "refreshedCount": len(refresh_tickers),
        "skippedFreshCount": len(tickers) - len(refresh_tickers) if stale_only else 0,
        "refreshTickers": refresh_tickers,
        "skippedTickers": [
            ticker
            for ticker in tickers
            if stale_only and ticker not in refresh_set
        ],
        "classification": classification,
    }


def watchlist_refresh_status(
    screener_result: Optional[dict],
    ranking_result: Optional[dict],
) -> str:
    statuses = [
        (screener_result or {}).get("status"),
        (ranking_result or {}).get("status") or (ranking_result or {}).get("state"),
    ]

    if all(status == "failed" for status in statuses):
        return "failed"

    if any(status in {"failed", "partial"} for status in statuses):
        return "partial"

    return "completed"


def watchlist_refresh_errors(
    screener_result: Optional[dict],
    ranking_result: Optional[dict],
) -> list[dict]:
    errors = []

    for failure in (screener_result or {}).get("failures") or []:
        errors.append(
            {
                "ticker": failure.get("ticker"),
                "message": sanitize_error(str(failure.get("message") or "Refresh failed.")),
            }
        )

    for error in (ranking_result or {}).get("errors") or []:
        errors.append(
            {
                "message": sanitize_error(str(error.get("message") if isinstance(error, dict) else error)),
            }
        )

    return errors


def watchlist_refresh_warnings(
    stale_only: bool,
    refresh_tickers: list[str],
    tickers: list[str],
) -> list[dict]:
    warnings = []

    if stale_only:
        warnings.append(
            {
                "code": "watchlist_stale_only_refresh",
                "message": "Only stale, missing, or degraded watchlist items were refreshed.",
            }
        )

    if refresh_tickers != tickers:
        warnings.append(
            {
                "code": "watchlist_partial_scope",
                "message": "Watchlist refresh ran against a subset of the workspace.",
            }
        )

    return warnings


def watchlist_refresh_result(
    job: dict,
    watchlist_id_value: str,
    strategy: str,
    period: str,
    tickers: list[str],
    refresh_tickers: list[str],
    stale_metadata: dict,
    staleness_before: Optional[dict],
    staleness_after: Optional[dict],
    screener_result: Optional[dict],
    ranking_result: Optional[dict],
    status: str,
    warnings: list[dict],
    errors: list[dict],
    started_at: str,
) -> dict:
    completed_at = utc_now()

    return {
        "refreshId": f"watchlist-refresh-{uuid4().hex[:12]}",
        "schemaVersion": WATCHLIST_SCHEMA_VERSION,
        "status": status,
        "state": status,
        "target": "watchlist",
        "watchlistId": watchlist_id_value,
        "strategy": strategy,
        "period": period,
        "scope": {
            "type": "watchlist",
            "watchlistId": watchlist_id_value,
            "tickers": refresh_tickers,
            "requestedTickers": tickers,
            "staleOnly": stale_metadata.get("enabled"),
            "schemaVersion": WATCHLIST_SCHEMA_VERSION,
        },
        "startedAt": started_at,
        "completedAt": completed_at,
        "failedAt": completed_at if status == "failed" else None,
        "durationMs": duration_ms(started_at, completed_at),
        "warnings": warnings,
        "errors": errors,
        "stateTransitions": [
            {
                "state": "queued",
                "at": job.get("createdAt"),
                "message": "Watchlist refresh job was queued.",
            },
            {
                "state": "running",
                "at": started_at,
                "message": "Watchlist refresh ran synchronously through the local job runner.",
            },
            {
                "state": status,
                "at": completed_at,
                "message": "Watchlist refresh finished.",
            },
        ],
        "metadata": {
            "synchronous": True,
            "target": "watchlist",
            "watchlistId": watchlist_id_value,
            "staleOnly": stale_metadata,
            "stalenessBefore": (staleness_before or {}).get("counts"),
            "stalenessAfter": (staleness_after or {}).get("counts"),
            "screenerRefresh": summarize_refresh_result(screener_result),
            "rankingRefresh": summarize_refresh_result(ranking_result),
        },
        "runId": (ranking_result or {}).get("runId"),
        "run": (ranking_result or {}).get("run"),
        "refreshedCount": len(refresh_tickers),
        "skippedFreshCount": stale_metadata.get("skippedFreshCount"),
        "message": (
            "Watchlist refresh completed through deterministic local job infrastructure. "
            "No recommendations, notifications, or trading actions were produced."
        ),
    }


def summarize_refresh_result(result: Optional[dict]) -> Optional[dict]:
    if result is None:
        return None

    return {
        "status": result.get("status") or result.get("state"),
        "refreshId": result.get("refreshId"),
        "runId": result.get("runId"),
        "refreshedCount": result.get("refreshedCount"),
        "failedCount": result.get("failedCount"),
        "completedAt": result.get("completedAt"),
    }


def refresh_job_summary(job: dict) -> dict:
    return {
        "jobId": job.get("jobId"),
        "jobType": job.get("jobType"),
        "status": job.get("status"),
        "scope": job.get("scope"),
        "createdAt": job.get("createdAt"),
        "startedAt": job.get("startedAt"),
        "completedAt": job.get("completedAt"),
        "failedAt": job.get("failedAt"),
        "durationMs": job.get("durationMs"),
        "resultMetadata": job.get("resultMetadata") or {},
        "message": job.get("message"),
    }


def build_watchlist_diagnostics(
    repository: SnapshotRepository,
    market_data_provider: MarketDataProvider,
    stale_after_seconds: int,
) -> dict:
    watchlists = repository.list_watchlists(True, False, 100)
    intelligence_results = [
        build_watchlist_intelligence(
            repository,
            market_data_provider,
            watchlist["watchlistId"],
            stale_after_seconds,
        )
        for watchlist in watchlists
    ]
    store = repository.watchlist_repository_diagnostics(stale_after_seconds)
    alert_count = sum(
        result.get("alertCount") or 0
        for result in intelligence_results
        if isinstance(result, dict)
    )
    staleness_items = [
        item
        for result in intelligence_results
        if isinstance(result, dict)
        for item in result.get("items") or []
    ]
    stale_counts = staleness_counts(
        [
            item.get("staleness") or {}
            for item in staleness_items
        ]
    )
    watchlist_refresh_jobs = repository.list_refresh_jobs(
        WATCHLIST_REFRESH_JOB_TYPE,
        None,
        100,
    )
    failed_watchlist_refresh_count = sum(
        1
        for job in watchlist_refresh_jobs
        if job.get("status") == "failed"
    )

    return {
        "provider": watchlist_store_provider(repository),
        "watchlistStore": store,
        "watchlistCount": store["watchlistCount"],
        "watchlistItemCount": store["itemCount"],
        "alertCount": alert_count,
        "staleWatchlistItemCount": store["staleWatchlistItemCount"],
        "savedWatchlistViewCount": store.get("savedViewCount", 0),
        "activeAlertCount": store.get("activeAlertCount", 0),
        "acknowledgedAlertCount": store.get("acknowledgedAlertCount", 0),
        "dismissedAlertCount": store.get("dismissedAlertCount", 0),
        "watchlistRefresh": {
            "ready": True,
            "jobType": WATCHLIST_REFRESH_JOB_TYPE,
            "jobCount": len(watchlist_refresh_jobs),
            "failedJobCount": failed_watchlist_refresh_count,
            "latestJob": refresh_job_summary(watchlist_refresh_jobs[0])
            if watchlist_refresh_jobs
            else None,
        },
        "staleness": {
            "counts": stale_counts,
            "staleItemCount": stale_counts.get("stale", 0)
            + stale_counts.get("missing", 0)
            + stale_counts.get("degraded", 0),
        },
        "alertStore": {
            "repository": store["repository"],
            "activeAlertCount": store.get("activeAlertCount", 0),
            "acknowledgedAlertCount": store.get("acknowledgedAlertCount", 0),
            "dismissedAlertCount": store.get("dismissedAlertCount", 0),
        },
        "endpointReadiness": [
            {
                "name": "List watchlists",
                "method": "GET",
                "path": "/api/watchlists",
                "state": "ready",
                "message": "SQLite-backed watchlists can be listed.",
            },
            {
                "name": "Watchlist intelligence",
                "method": "GET",
                "path": "/api/watchlists/{watchlistId}/intelligence",
                "state": "ready",
                "message": "Deterministic watchlist aggregation is available.",
            },
            {
                "name": "Watchlist alerts",
                "method": "GET",
                "path": "/api/watchlists/{watchlistId}/alerts",
                "state": "ready",
                "message": "Rule-based alert records are generated on read.",
            },
            {
                "name": "Watchlist views",
                "method": "GET",
                "path": "/api/watchlists/{watchlistId}/views",
                "state": "ready",
                "message": "Saved watchlist views can be listed from SQLite.",
            },
            {
                "name": "Alert history",
                "method": "GET",
                "path": "/api/watchlists/{watchlistId}/alerts/history",
                "state": "ready",
                "message": "Alert acknowledgement and dismissal history is queryable.",
            },
            {
                "name": "Watchlist staleness",
                "method": "GET",
                "path": "/api/watchlists/{watchlistId}/staleness",
                "state": "ready",
                "message": "Watchlist item freshness and missing dependencies are queryable.",
            },
            {
                "name": "Watchlist refresh",
                "method": "POST",
                "path": "/api/watchlists/{watchlistId}/refresh",
                "state": "ready",
                "message": "Watchlist-scoped refresh jobs run through the local job store.",
            },
        ],
        "message": (
            "Watchlist diagnostics report local store readiness and deterministic "
            "alert coverage. No trading or recommendation workflow is enabled."
        ),
    }


def build_watchlist_intelligence_item(
    repository: SnapshotRepository,
    market_data_provider: MarketDataProvider,
    watchlist: dict,
    item: dict,
    stale_after_seconds: int,
    latest_ranking_run: Optional[dict],
    ranking_change_lookup: dict[str, dict],
) -> dict:
    ticker = normalize_ticker(item.get("ticker"))
    normalized_item = {
        **item,
        "workflowState": normalize_workflow_state(item.get("workflowState")),
    }
    market_snapshot = safe_market_snapshot(market_data_provider, ticker)
    screener_snapshot = repository.get_screener_row_snapshot(
        ticker,
        DEFAULT_WATCHLIST_PERIOD,
    )
    computed_snapshot = repository.get_computed_metrics_snapshot(
        ticker,
        DEFAULT_WATCHLIST_PERIOD,
    )
    screener_row = (screener_snapshot or {}).get("row") or {}
    computed_row = latest_computed_metric_row(computed_snapshot)
    ranking = ranking_item(latest_ranking_run, ticker, ranking_change_lookup)
    valuation = valuation_summary(repository, ticker)
    valuation_gap = valuation_gap_summary(market_snapshot, valuation)
    freshness = snapshot_freshness(
        screener_snapshot,
        DEFAULT_WATCHLIST_PERIOD,
        stale_after_seconds,
    )
    quality_flags = item_quality_flags(
        market_snapshot,
        freshness,
        computed_row,
        ranking,
        valuation,
    )
    staleness = item_staleness(
        ticker,
        market_snapshot,
        freshness,
        computed_snapshot,
        ranking,
        valuation,
        stale_after_seconds,
    )
    alerts = deterministic_alerts(
        watchlist,
        normalized_item,
        market_snapshot,
        freshness,
        ranking,
        valuation_gap,
        quality_flags,
    )

    return {
        "ticker": ticker,
        "companyName": first_text(
            normalized_item.get("companyName"),
            screener_row.get("companyName"),
            (ranking or {}).get("companyName"),
            (valuation or {}).get("name"),
        ),
        "item": normalized_item,
        "marketSnapshot": market_snapshot,
        "fundamentalsSnapshot": freshness,
        "computedMetricsSnapshot": computed_snapshot_summary(computed_snapshot, computed_row),
        "ranking": ranking,
        "magicFormulaEligibility": magic_formula_eligibility(ranking),
        "valuation": valuation,
        "staleness": staleness,
        "valuationGap": valuation_gap,
        "qualityFlags": quality_flags,
        "alerts": alerts,
    }


def safe_market_snapshot(
    market_data_provider: MarketDataProvider,
    ticker: str,
) -> dict:
    try:
        return market_data_provider.get_market_snapshot(ticker)
    except Exception as error:
        return {
            "ticker": ticker,
            "price": None,
            "currency": None,
            "marketCap": None,
            "enterpriseValue": None,
            "volume": None,
            "asOf": None,
            "provider": provider_degraded(
                "market_data",
                "Market snapshot provider failed while building watchlist intelligence.",
                ["ALPACA_API_KEY", "ALPACA_SECRET_KEY"],
                last_error_message=sanitize_error(str(error)),
            ),
            "message": "Market snapshot could not be loaded safely.",
        }


def snapshot_freshness(
    snapshot: Optional[dict],
    period: str,
    stale_after_seconds: int,
) -> dict:
    if snapshot is None:
        return {
            "period": period,
            "state": "missing",
            "refreshedAt": None,
            "ageSeconds": None,
            "isStale": True,
            "metadata": None,
        }

    metadata = snapshot_metadata(snapshot, "persisted", stale_after_seconds)

    return {
        "period": period,
        "state": "stale" if metadata["isStale"] else "fresh",
        "refreshedAt": metadata["refreshedAt"],
        "ageSeconds": metadata["ageSeconds"],
        "isStale": metadata["isStale"],
        "metadata": metadata,
    }


def computed_snapshot_summary(
    snapshot: Optional[dict],
    computed_row: Optional[dict],
) -> Optional[dict]:
    if snapshot is None:
        return None

    return {
        "state": "persisted",
        "refreshedAt": snapshot.get("refreshedAt"),
        "computedAt": snapshot.get("computedAt"),
        "metrics": {
            "grossMargin": (computed_row or {}).get("grossMargin"),
            "operatingMargin": (computed_row or {}).get("operatingMargin"),
            "netMargin": (computed_row or {}).get("netMargin"),
            "freeCashFlowMargin": (computed_row or {}).get("freeCashFlowMargin"),
            "returnOnEquity": (computed_row or {}).get("returnOnEquity"),
            "returnOnInvestedCapital": (computed_row or {}).get("returnOnInvestedCapital"),
            "debtToEquity": (computed_row or {}).get("debtToEquity"),
        },
        "qualityFlags": (computed_row or {}).get("qualityFlags") or [],
    }


def item_staleness(
    ticker: str,
    market_snapshot: dict,
    fundamentals_freshness: dict,
    computed_snapshot: Optional[dict],
    ranking: Optional[dict],
    valuation: Optional[dict],
    stale_after_seconds: int,
) -> dict:
    components = {
        "fundamentals": staleness_component(
            "fundamentals",
            fundamentals_freshness.get("refreshedAt"),
            stale_after_seconds,
            missing=fundamentals_freshness.get("state") == "missing",
        ),
        "computedMetrics": staleness_component(
            "computed_metrics",
            (computed_snapshot or {}).get("computedAt")
            or (computed_snapshot or {}).get("refreshedAt"),
            stale_after_seconds,
            missing=computed_snapshot is None,
        ),
        "ranking": staleness_component(
            "ranking",
            (ranking or {}).get("computedAt"),
            stale_after_seconds,
            missing=ranking is None,
        ),
        "valuation": staleness_component(
            "valuation",
            (valuation or {}).get("updatedAt") or (valuation or {}).get("createdAt"),
            stale_after_seconds,
            missing=valuation is None,
        ),
        "marketData": market_data_staleness_component(
            market_snapshot,
            stale_after_seconds,
        ),
    }
    states = [component["state"] for component in components.values()]

    if "degraded" in states:
        state = "degraded"
    elif "missing" in states:
        state = "missing"
    elif "stale" in states:
        state = "stale"
    else:
        state = "fresh"

    reasons = [
        reason
        for component in components.values()
        for reason in component.get("reasons") or []
    ]
    missing_dependencies = [
        component["dependency"]
        for component in components.values()
        if component["state"] in {"missing", "degraded"}
    ]
    refreshed_candidates = [
        component.get("lastRefreshedAt")
        for component in components.values()
        if component.get("lastRefreshedAt")
    ]
    age_candidates = [
        component.get("ageSeconds")
        for component in components.values()
        if component.get("ageSeconds") is not None
    ]

    return {
        "ticker": ticker,
        "state": state,
        "staleReasons": reasons,
        "missingDependencies": missing_dependencies,
        "lastRefreshedAt": max(refreshed_candidates) if refreshed_candidates else None,
        "maxAgeSeconds": max(age_candidates) if age_candidates else None,
        "components": components,
        "schemaVersion": WATCHLIST_SCHEMA_VERSION,
    }


def staleness_component(
    dependency: str,
    timestamp: Optional[str],
    stale_after_seconds: int,
    missing: bool = False,
) -> dict:
    age_seconds = age_seconds_from_timestamp(timestamp)

    if missing or not timestamp:
        state = "missing"
        reasons = [f"missing:{dependency}"]
    elif age_seconds is None:
        state = "stale"
        reasons = [f"unknown_age:{dependency}"]
    elif age_seconds > stale_after_seconds:
        state = "stale"
        reasons = [f"stale:{dependency}"]
    else:
        state = "fresh"
        reasons = []

    return {
        "dependency": dependency,
        "state": state,
        "lastRefreshedAt": timestamp,
        "ageSeconds": age_seconds,
        "reasons": reasons,
    }


def market_data_staleness_component(
    market_snapshot: dict,
    stale_after_seconds: int,
) -> dict:
    provider = market_snapshot.get("provider") or {}
    provider_state = provider.get("state")
    component = staleness_component(
        "market_data",
        market_snapshot.get("asOf"),
        stale_after_seconds,
        missing=market_snapshot.get("asOf") is None,
    )

    if provider_state not in {None, "connected"}:
        return {
            **component,
            "state": "degraded",
            "reasons": [
                *component.get("reasons", []),
                f"provider:{provider_state}",
            ],
        }

    return component


def latest_computed_metric_row(snapshot: Optional[dict]) -> Optional[dict]:
    rows = ((snapshot or {}).get("data") or {}).get("computedMetrics")

    if isinstance(rows, list) and rows and isinstance(rows[0], dict):
        return rows[0]

    return None


def ranking_item(
    latest_ranking_run: Optional[dict],
    ticker: str,
    ranking_change_lookup: dict[str, dict],
) -> Optional[dict]:
    if not latest_ranking_run:
        return None

    row = next(
        (
            ranking_row
            for ranking_row in latest_ranking_run.get("rows") or []
            if ranking_row.get("ticker") == ticker
        ),
        None,
    )

    if row is None:
        return None

    change = ranking_change_lookup.get(ticker)

    return {
        "runId": latest_ranking_run.get("runId"),
        "strategy": latest_ranking_run.get("strategy"),
        "period": latest_ranking_run.get("period"),
        "rank": row.get("rank"),
        "score": row.get("score"),
        "companyName": row.get("companyName"),
        "eligibilityStatus": row.get("eligibilityStatus"),
        "eligibilityReasons": row.get("eligibilityReasons") or [],
        "qualityFlags": row.get("qualityFlags") or [],
        "computedAt": latest_ranking_run.get("computedAt"),
        "rankChange": change,
        "magicFormula": row.get("magicFormula"),
    }


def valuation_summary(
    repository: SnapshotRepository,
    ticker: str,
) -> Optional[dict]:
    scenario = repository.get_latest_valuation_scenario(ticker)

    if scenario is None:
        return None

    return scenario_summary(scenario)


def valuation_gap_summary(
    market_snapshot: dict,
    valuation: Optional[dict],
) -> dict:
    price = number(market_snapshot.get("price"))
    intrinsic = number((valuation or {}).get("intrinsicValuePerShare"))

    if price is None or intrinsic is None or price == 0:
        return {
            "price": price,
            "intrinsicValuePerShare": intrinsic,
            "gapPercent": None,
            "state": "unavailable",
            "message": "Price or intrinsic value is unavailable.",
        }

    gap = (intrinsic - price) / price

    return {
        "price": price,
        "intrinsicValuePerShare": intrinsic,
        "gapPercent": gap,
        "state": "available",
        "message": "Valuation gap is informational only and is not a recommendation.",
    }


def magic_formula_eligibility(ranking: Optional[dict]) -> dict:
    if ranking is None:
        return {
            "status": "unranked_missing_data",
            "reasons": ["missing_ranking_run"],
        }

    return {
        "status": ranking.get("eligibilityStatus"),
        "reasons": ranking.get("eligibilityReasons") or [],
    }


def item_quality_flags(
    market_snapshot: dict,
    freshness: dict,
    computed_row: Optional[dict],
    ranking: Optional[dict],
    valuation: Optional[dict],
) -> list[str]:
    flags = []

    if number(market_snapshot.get("price")) is None:
        flags.append("missing_market_price")

    provider_state = (market_snapshot.get("provider") or {}).get("state")

    if provider_state in {"not_connected", "degraded"}:
        flags.append(f"market_provider:{provider_state}")

    if freshness["state"] == "missing":
        flags.append("missing_fundamentals_snapshot")
    elif freshness["isStale"]:
        flags.append("stale_fundamentals_snapshot")

    if computed_row is None:
        flags.append("missing_computed_metrics_snapshot")

    if ranking is None:
        flags.append("missing_ranking_snapshot")

    if valuation is None:
        flags.append("missing_valuation_scenario")

    return sorted(set(flags))


def deterministic_alerts(
    watchlist: dict,
    item: dict,
    market_snapshot: dict,
    freshness: dict,
    ranking: Optional[dict],
    valuation_gap: dict,
    quality_flags: list[str],
) -> list[dict]:
    ticker = item["ticker"]
    alerts = []
    price = number(market_snapshot.get("price"))
    target_price = number(item.get("targetPrice"))

    if target_price is not None and price is not None:
        if price > target_price:
            alerts.append(
                alert_record(
                    watchlist,
                    ticker,
                    "priceAboveTarget",
                    "medium",
                    "Market price is above the watchlist target price.",
                    {"price": price, "targetPrice": target_price},
                )
            )
        elif price < target_price:
            alerts.append(
                alert_record(
                    watchlist,
                    ticker,
                    "priceBelowTarget",
                    "medium",
                    "Market price is below the watchlist target price.",
                    {"price": price, "targetPrice": target_price},
                )
            )

    gap_percent = number(valuation_gap.get("gapPercent"))

    if gap_percent is not None and gap_percent >= VALUATION_GAP_ALERT_THRESHOLD:
        alerts.append(
            alert_record(
                watchlist,
                ticker,
                "valuationGapAboveThreshold",
                "medium",
                "Intrinsic value gap exceeds the deterministic watchlist threshold.",
                {
                    "gapPercent": gap_percent,
                    "threshold": VALUATION_GAP_ALERT_THRESHOLD,
                },
            )
        )

    rank_change = (ranking or {}).get("rankChange")

    if rank_change and rank_change.get("changeType") != "unchanged":
        alerts.append(
            alert_record(
                watchlist,
                ticker,
                "rankingStatusChanged",
                "low",
                "Latest ranking status changed versus the previous run.",
                rank_change,
            )
        )

    if freshness.get("isStale"):
        alerts.append(
            alert_record(
                watchlist,
                ticker,
                "snapshotStale",
                "low",
                "Fundamentals snapshot is stale or missing.",
                {
                    "state": freshness.get("state"),
                    "refreshedAt": freshness.get("refreshedAt"),
                    "ageSeconds": freshness.get("ageSeconds"),
                },
            )
        )

    provider_state = (market_snapshot.get("provider") or {}).get("state")

    if provider_state in {"not_connected", "degraded"}:
        alerts.append(
            alert_record(
                watchlist,
                ticker,
                "providerDegraded",
                "medium" if provider_state == "degraded" else "low",
                "Market data provider is not fully connected for this item.",
                {"providerState": provider_state},
            )
        )

    critical_flags = [
        flag
        for flag in quality_flags
        if flag
        in {
            "missing_market_price",
            "missing_fundamentals_snapshot",
            "missing_computed_metrics_snapshot",
            "missing_ranking_snapshot",
            "missing_valuation_scenario",
        }
    ]

    if critical_flags:
        alerts.append(
            alert_record(
                watchlist,
                ticker,
                "missingCriticalData",
                "medium",
                "One or more critical watchlist intelligence inputs are unavailable.",
                {"qualityFlags": critical_flags},
            )
        )

    return alerts


def sync_item_alerts(
    repository: SnapshotRepository,
    items: list[dict],
) -> list[dict]:
    synced_items = []

    for item in items:
        synced_alerts = [
            repository.upsert_watchlist_alert(alert)
            for alert in item.get("alerts") or []
        ]
        visible_alerts = [
            alert
            for alert in synced_alerts
            if not alert.get("dismissedAt")
        ]
        synced_items.append({**item, "alerts": visible_alerts})

    return synced_items


def normalize_watchlist_filters(filters: Optional[list[dict]]) -> list[dict]:
    if not isinstance(filters, list):
        return []

    normalized = []

    for item in filters:
        if not isinstance(item, dict):
            continue

        field = item.get("field")

        if field not in WATCHLIST_FILTER_FIELDS:
            continue

        operator = item.get("operator") or "eq"
        value = item.get("value")

        normalized.append(
            {
                "field": field,
                "operator": operator,
                "value": value,
            }
        )

    return normalized


def normalize_watchlist_sorting(sort: Optional[dict]) -> Optional[dict]:
    if not isinstance(sort, dict):
        return None

    field = sort.get("field")

    if field not in WATCHLIST_SORT_FIELDS:
        return None

    return {
        "field": field,
        "direction": "asc" if str(sort.get("direction")).lower() == "asc" else "desc",
    }


def normalize_visible_columns(columns) -> list[str]:
    if not isinstance(columns, list) or not columns:
        return DEFAULT_VISIBLE_COLUMNS

    normalized = []

    for column in columns:
        if isinstance(column, str) and column.strip() and column not in normalized:
            normalized.append(column.strip())

    return normalized or DEFAULT_VISIBLE_COLUMNS


def apply_watchlist_filters(items: list[dict], filters: list[dict]) -> list[dict]:
    if not filters:
        return items

    return [
        item
        for item in items
        if all(watchlist_filter_matches(item, item_filter) for item_filter in filters)
    ]


def watchlist_filter_matches(item: dict, item_filter: dict) -> bool:
    field = item_filter["field"]
    operator = item_filter.get("operator") or "eq"
    expected = item_filter.get("value")
    value = watchlist_filter_value(item, field)

    if field in {"missingCriticalData", "providerDegraded", "staleSnapshot"}:
        return bool(value) == bool_value(expected)

    if field == "alertType":
        alert_types = value if isinstance(value, list) else []

        if isinstance(expected, list):
            return any(alert_type in alert_types for alert_type in expected)

        return str(expected) in alert_types

    if field == "tags":
        tags = value if isinstance(value, list) else []

        if isinstance(expected, list):
            return any(str(tag) in tags for tag in expected)

        return str(expected) in tags

    numeric_value = number(value)

    if operator in {"gt", "gte", "lt", "lte", "between"}:
        if numeric_value is None:
            return False

        expected_number = number(expected)

        if operator == "gt":
            return expected_number is not None and numeric_value > expected_number

        if operator == "gte":
            return expected_number is not None and numeric_value >= expected_number

        if operator == "lt":
            return expected_number is not None and numeric_value < expected_number

        if operator == "lte":
            return expected_number is not None and numeric_value <= expected_number

        if operator == "between" and isinstance(expected, list) and len(expected) == 2:
            lower = number(expected[0])
            upper = number(expected[1])

            return lower is not None and upper is not None and lower <= numeric_value <= upper

    if operator == "contains":
        return str(expected).strip().lower() in str(value or "").strip().lower()

    return str(value or "").strip().lower() == str(expected or "").strip().lower()


def watchlist_filter_value(item: dict, field: str):
    watchlist_item = item.get("item") or {}

    if field == "ticker":
        return item.get("ticker")

    if field == "tags":
        return watchlist_item.get("tags") or []

    if field == "thesisStatus":
        return watchlist_item.get("thesisStatus")

    if field == "priority":
        return watchlist_item.get("priority")

    if field == "workflowState":
        return normalize_workflow_state(watchlist_item.get("workflowState"))

    if field == "valuationGap":
        return (item.get("valuationGap") or {}).get("gapPercent")

    if field == "rankingStatus":
        return (item.get("magicFormulaEligibility") or {}).get("status")

    if field == "alertType":
        return [
            alert.get("type")
            for alert in item.get("alerts") or []
            if alert.get("type")
        ]

    if field == "staleSnapshot":
        return bool((item.get("fundamentalsSnapshot") or {}).get("isStale"))

    if field == "missingCriticalData":
        return "missingCriticalData" in watchlist_filter_value(item, "alertType")

    if field == "providerDegraded":
        return "providerDegraded" in watchlist_filter_value(item, "alertType")

    return None


def apply_watchlist_sort(items: list[dict], sorting: Optional[dict]) -> list[dict]:
    if sorting is None:
        return items

    descending = sorting["direction"] == "desc"

    return sorted(
        items,
        key=lambda item: watchlist_sort_key(item, sorting["field"], descending),
    )


def watchlist_sort_key(item: dict, field: str, descending: bool) -> tuple:
    value = watchlist_sort_value(item, field)

    if value is None:
        return (True, 0, item.get("ticker") or "")

    if isinstance(value, str):
        normalized = value.lower()

        return (False, normalized if not descending else invert_text(normalized), item.get("ticker") or "")

    return (False, -value if descending else value, item.get("ticker") or "")


def watchlist_sort_value(item: dict, field: str):
    watchlist_item = item.get("item") or {}

    if field == "ticker":
        return item.get("ticker")

    if field == "priority":
        return priority_rank(watchlist_item.get("priority"))

    if field == "valuationGap":
        return number((item.get("valuationGap") or {}).get("gapPercent"))

    if field == "latestRank":
        return number((item.get("ranking") or {}).get("rank"))

    if field == "alertCount":
        return len(item.get("alerts") or [])

    if field == "snapshotFreshness":
        return number((item.get("fundamentalsSnapshot") or {}).get("ageSeconds"))

    if field == "addedAt":
        return timestamp_seconds(watchlist_item.get("addedAt"))

    return None


def priority_rank(value) -> int:
    normalized = str(value or "").strip().lower()

    if normalized == "high":
        return 3

    if normalized == "medium":
        return 2

    if normalized == "low":
        return 1

    return 0


def invert_text(value: str) -> str:
    return "".join(chr(255 - ord(char)) for char in value)


def alert_record(
    watchlist: dict,
    ticker: str,
    alert_type: str,
    severity: str,
    message: str,
    metadata: dict,
) -> dict:
    return {
        "alertId": f"{watchlist['watchlistId']}:{ticker}:{alert_type}",
        "watchlistId": watchlist["watchlistId"],
        "ticker": ticker,
        "type": alert_type,
        "severity": severity,
        "message": message,
        "createdAt": utc_now(),
        "acknowledgedAt": None,
        "acknowledgedBy": None,
        "dismissedAt": None,
        "status": "active",
        "schemaVersion": WATCHLIST_SCHEMA_VERSION,
        "metadata": metadata,
    }


def latest_run(
    repository: SnapshotRepository,
    strategy: str,
    period: str,
) -> Optional[dict]:
    runs = repository.list_ranking_runs(strategy, period, 1)

    if not runs:
        return None

    return repository.get_ranking_run(runs[0]["runId"])


def company_name_from_snapshots(
    repository: SnapshotRepository,
    ticker: str,
) -> Optional[str]:
    screener_snapshot = repository.get_screener_row_snapshot(
        ticker,
        DEFAULT_WATCHLIST_PERIOD,
    )
    screener_row = (screener_snapshot or {}).get("row") or {}

    if screener_row.get("companyName"):
        return screener_row["companyName"]

    profile_snapshot = repository.get_fundamentals_snapshot(ticker, "profile", "profile")
    profile = ((profile_snapshot or {}).get("data") or {}).get("profile") or {}

    return profile.get("name")


def intelligence_provider(
    items: list[dict],
    repository: SnapshotRepository,
    market_data_provider: MarketDataProvider,
) -> dict:
    states = {
        ((item.get("marketSnapshot") or {}).get("provider") or {}).get("state")
        for item in items
    }
    store_state = repository.repository_status().get("state")

    if store_state != "connected" or "degraded" in states:
        return provider_degraded(
            "watchlist_intelligence",
            "Watchlist intelligence is available, but one or more inputs are degraded.",
            ["ALPACA_API_KEY", "ALPACA_SECRET_KEY"],
            last_error_message="One or more provider-backed inputs are degraded.",
        )

    if "not_connected" in states or market_data_provider.provider_status().get("state") == "not_connected":
        return provider_degraded(
            "watchlist_intelligence",
            "Watchlist store is connected, but market data is not fully connected.",
            ["ALPACA_API_KEY", "ALPACA_SECRET_KEY"],
        )

    return provider_connected(
        "watchlist_intelligence",
        "Watchlist intelligence is available from deterministic local snapshots and providers.",
        utc_now(),
    )


def watchlist_store_provider(repository: SnapshotRepository) -> dict:
    status = repository.repository_status()

    if status.get("state") == "connected":
        return provider_connected(
            "watchlist_store",
            "SQLite watchlist store is available.",
            utc_now(),
        )

    return provider_degraded(
        "watchlist_store",
        status.get("message") or "SQLite watchlist store is degraded.",
        [],
        last_error_message=status.get("message"),
    )


def with_provider(payload: dict, repository: SnapshotRepository) -> dict:
    return {
        **payload,
        "id": payload["watchlistId"],
        "provider": watchlist_store_provider(repository),
    }


def without_provider(payload: dict) -> dict:
    return {
        key: value
        for key, value in payload.items()
        if key not in {"provider"}
    }


def normalize_ticker(value) -> str:
    if not isinstance(value, str):
        return ""

    return value.strip().upper()[:16]


def normalize_name(value, fallback: str) -> str:
    if not isinstance(value, str):
        return fallback

    normalized = " ".join(value.strip().split())

    return normalized[:120] if normalized else fallback


def normalize_text(value, max_length: int) -> Optional[str]:
    if value is None:
        return None

    if not isinstance(value, str):
        value = str(value)

    normalized = " ".join(value.strip().split())

    return normalized[:max_length] if normalized else None


def normalize_workflow_state(value) -> str:
    normalized = normalize_text(value, 40) or "not_started"

    if normalized not in WATCHLIST_WORKFLOW_STATES:
        return "not_started"

    return normalized


def normalize_period(value) -> str:
    normalized = normalize_text(value, 20) or DEFAULT_WATCHLIST_PERIOD

    return normalized if normalized in {"annual", "quarter"} else DEFAULT_WATCHLIST_PERIOD


def normalize_strategy(value) -> str:
    normalized = normalize_text(value, 40) or "magic_formula"

    if normalized not in {"magic_formula", "quality", "value", "growth", "profitability"}:
        return "magic_formula"

    return normalized


def normalize_tags(value) -> list[str]:
    tags = value

    if isinstance(value, str):
        tags = value.split(",")

    if not isinstance(tags, list):
        return []

    normalized_tags = []

    for tag in tags:
        normalized = normalize_text(tag, 40)

        if normalized and normalized not in normalized_tags:
            normalized_tags.append(normalized)

    return normalized_tags[:12]


def normalize_optional_number(value) -> Optional[float]:
    return number(value)


def bool_value(value) -> bool:
    if isinstance(value, bool):
        return value

    if isinstance(value, (int, float)):
        return value != 0

    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}

    return False


def number(value) -> Optional[float]:
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


def timestamp_seconds(value) -> Optional[float]:
    if not isinstance(value, str) or not value:
        return None

    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))

        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)

        return parsed.timestamp()
    except ValueError:
        return None


def age_seconds_from_timestamp(value) -> Optional[int]:
    timestamp = timestamp_seconds(value)

    if timestamp is None:
        return None

    return max(int(datetime.now(timezone.utc).timestamp() - timestamp), 0)


def duration_ms(started_at: Optional[str], completed_at: Optional[str]) -> Optional[int]:
    if not started_at or not completed_at:
        return None

    started = timestamp_seconds(started_at)
    completed = timestamp_seconds(completed_at)

    if started is None or completed is None:
        return None

    return max(int((completed - started) * 1000), 0)


def first_text(*values) -> Optional[str]:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value

    return None


def sanitize_error(message: str) -> str:
    sanitized = message.replace("ALPACA_API_KEY", "[redacted]")
    sanitized = sanitized.replace("ALPACA_SECRET_KEY", "[redacted]")
    sanitized = sanitized.replace("FMP_API_KEY", "[redacted]")

    return sanitized[:240]


def watchlist_id() -> str:
    return f"watchlist-{uuid4().hex[:12]}"


def watchlist_view_id() -> str:
    return f"watchlist-view-{uuid4().hex[:12]}"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
