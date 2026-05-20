from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import uuid4

from app.services.fundamentals.provider import FundamentalsProvider
from app.services.jobs.runner import (
    run_ranking_refresh_job,
    run_screener_refresh_job,
)
from app.services.market_data.provider import MarketDataProvider
from app.services.persistence.repository import SnapshotRepository
from app.services.persistence.sqlite_repository import SCHEMA_VERSION

POLICY_TARGETS = {"ranking", "screener"}
POLICY_SCHEDULE_HINTS = {"manual", "stale_only", "hourly", "daily", "weekly", "always"}
POLICY_INTERVALS = {
    "hourly": 3600,
    "daily": 86400,
    "weekly": 604800,
}


def create_refresh_policy(repository: SnapshotRepository, payload: dict) -> dict:
    now = utc_now()
    schedule_hint = normalize_schedule_hint(payload.get("scheduleHint"))
    stale_after_seconds = positive_int(payload.get("staleAfterSeconds"), 86400)
    enabled = bool(payload.get("enabled", True))
    last_run_at = text_or_none(payload.get("lastRunAt"))
    policy = {
        "policyId": refresh_policy_id(),
        "schemaVersion": SCHEMA_VERSION,
        "name": policy_name(payload.get("name")),
        "target": normalize_target(payload.get("target")),
        "strategy": normalize_strategy(payload.get("strategy")),
        "period": normalize_period(payload.get("period")),
        "scope": normalize_policy_scope(payload.get("scope"), payload),
        "staleAfterSeconds": stale_after_seconds,
        "enabled": enabled,
        "scheduleHint": schedule_hint,
        "lastRunAt": last_run_at,
        "nextRunHint": next_run_hint(schedule_hint, last_run_at, stale_after_seconds, enabled),
        "createdAt": now,
        "updatedAt": now,
    }

    return repository.upsert_refresh_policy(policy)


def update_refresh_policy(
    repository: SnapshotRepository,
    policy_id: str,
    payload: dict,
) -> Optional[dict]:
    existing = repository.get_refresh_policy(policy_id)

    if existing is None:
        return None

    stale_after_seconds = positive_int(
        payload.get("staleAfterSeconds"),
        existing.get("staleAfterSeconds") or 86400,
    )
    schedule_hint = normalize_schedule_hint(
        payload.get("scheduleHint", existing.get("scheduleHint"))
    )
    last_run_at = text_or_none(payload.get("lastRunAt", existing.get("lastRunAt")))
    enabled = bool(payload.get("enabled", existing.get("enabled", True)))
    updated = {
        **existing,
        "name": policy_name(payload.get("name", existing.get("name"))),
        "target": normalize_target(payload.get("target", existing.get("target"))),
        "strategy": normalize_strategy(payload.get("strategy", existing.get("strategy"))),
        "period": normalize_period(payload.get("period", existing.get("period"))),
        "scope": normalize_policy_scope(
            payload.get("scope", existing.get("scope")),
            {
                **existing,
                **payload,
            },
        ),
        "staleAfterSeconds": stale_after_seconds,
        "enabled": enabled,
        "scheduleHint": schedule_hint,
        "lastRunAt": last_run_at,
        "nextRunHint": next_run_hint(
            schedule_hint,
            last_run_at,
            stale_after_seconds,
            enabled,
        ),
        "updatedAt": utc_now(),
    }

    return repository.upsert_refresh_policy(updated)


def set_refresh_policy_enabled(
    repository: SnapshotRepository,
    policy_id: str,
    enabled: bool,
) -> Optional[dict]:
    existing = repository.get_refresh_policy(policy_id)

    if existing is None:
        return None

    updated = {
        **existing,
        "enabled": enabled,
        "nextRunHint": next_run_hint(
            existing.get("scheduleHint"),
            existing.get("lastRunAt"),
            existing.get("staleAfterSeconds") or 86400,
            enabled,
        ),
        "updatedAt": utc_now(),
    }

    return repository.upsert_refresh_policy(updated)


def run_refresh_policy_now(
    fundamentals_provider: FundamentalsProvider,
    market_data_provider: MarketDataProvider,
    repository: SnapshotRepository,
    policy_id: str,
) -> Optional[dict]:
    policy = repository.get_refresh_policy(policy_id)

    if policy is None:
        return None

    job = run_policy_job(fundamentals_provider, market_data_provider, repository, policy)
    record_policy_run(repository, policy, job)

    return {
        "policy": repository.get_refresh_policy(policy_id),
        "job": job,
        "message": "Refresh policy ran through the local job foundation.",
    }


def run_due_refresh_policies(
    fundamentals_provider: FundamentalsProvider,
    market_data_provider: MarketDataProvider,
    repository: SnapshotRepository,
) -> dict:
    policies = repository.list_refresh_policies(include_disabled=False, limit=100)
    now = utc_now()
    jobs = []
    skipped = []

    for policy in policies:
        due = policy_is_due(policy, now)

        if not due:
            skipped.append(policy_summary(policy, "not_due"))
            continue

        job = run_policy_job(fundamentals_provider, market_data_provider, repository, policy)
        record_policy_run(repository, policy, job)
        jobs.append(
            {
                "policy": repository.get_refresh_policy(policy["policyId"]),
                "job": job,
            }
        )

    return {
        "schemaVersion": SCHEMA_VERSION,
        "policiesInspected": len(policies),
        "duePolicies": len(jobs),
        "skippedPolicies": skipped,
        "jobs": jobs,
        "ranAt": now,
        "message": (
            "Due refresh policies were evaluated and run synchronously. "
            "This is a local scheduler simulation, not a production scheduler."
        ),
    }


def run_policy_job(
    fundamentals_provider: FundamentalsProvider,
    market_data_provider: MarketDataProvider,
    repository: SnapshotRepository,
    policy: dict,
) -> dict:
    scope = policy.get("scope") or {}
    target = normalize_target(policy.get("target"))
    stale_only = bool(scope.get("staleOnly") or scope.get("type") == "stale_only")

    if target == "screener":
        return run_screener_refresh_job(
            fundamentals_provider,
            repository,
            policy.get("period") or "annual",
            policy.get("staleAfterSeconds") or 86400,
            scope_type=scope.get("type") or "universe",
            tickers=scope.get("tickers") or None,
            stale_only=stale_only,
            policy_id=policy.get("policyId"),
        )

    return run_ranking_refresh_job(
        fundamentals_provider,
        market_data_provider,
        repository,
        policy.get("strategy") or "magic_formula",
        policy.get("period") or "annual",
        policy.get("staleAfterSeconds") or 86400,
        scope_type=scope.get("type") or "universe",
        tickers=scope.get("tickers") or None,
        stale_only=stale_only,
        screen_id=scope.get("screenId"),
        policy_id=policy.get("policyId"),
    )


def record_policy_run(
    repository: SnapshotRepository,
    policy: dict,
    job: dict,
) -> None:
    completed_at = (
        job.get("completedAt")
        or job.get("failedAt")
        or job.get("startedAt")
        or utc_now()
    )
    updated = {
        **policy,
        "lastRunAt": completed_at,
        "nextRunHint": next_run_hint(
            policy.get("scheduleHint"),
            completed_at,
            policy.get("staleAfterSeconds") or 86400,
            bool(policy.get("enabled")),
        ),
        "updatedAt": utc_now(),
    }
    repository.upsert_refresh_policy(updated)


def policy_is_due(policy: dict, now: Optional[str] = None) -> bool:
    if not policy.get("enabled"):
        return False

    schedule_hint = normalize_schedule_hint(policy.get("scheduleHint"))

    if schedule_hint == "manual":
        return False

    if schedule_hint == "always":
        return True

    next_hint = text_or_none(policy.get("nextRunHint"))

    if next_hint:
        return parse_datetime(next_hint) <= parse_datetime(now or utc_now())

    last_run_at = text_or_none(policy.get("lastRunAt"))

    if not last_run_at:
        return True

    interval = POLICY_INTERVALS.get(
        schedule_hint,
        positive_int(policy.get("staleAfterSeconds"), 86400),
    )

    return parse_datetime(last_run_at) + timedelta(seconds=interval) <= parse_datetime(
        now or utc_now()
    )


def policy_summary(policy: dict, reason: str) -> dict:
    return {
        "policyId": policy.get("policyId"),
        "name": policy.get("name"),
        "target": policy.get("target"),
        "strategy": policy.get("strategy"),
        "period": policy.get("period"),
        "scheduleHint": policy.get("scheduleHint"),
        "nextRunHint": policy.get("nextRunHint"),
        "reason": reason,
    }


def next_run_hint(
    schedule_hint: Optional[str],
    last_run_at: Optional[str],
    stale_after_seconds: int,
    enabled: bool,
) -> Optional[str]:
    if not enabled:
        return None

    normalized_hint = normalize_schedule_hint(schedule_hint)

    if normalized_hint == "manual":
        return None

    if normalized_hint == "always":
        return utc_now()

    if not last_run_at:
        return utc_now()

    interval = POLICY_INTERVALS.get(normalized_hint, stale_after_seconds)

    return (
        parse_datetime(last_run_at) + timedelta(seconds=max(interval, 1))
    ).isoformat()


def normalize_policy_scope(raw_scope, payload: dict) -> dict:
    if isinstance(raw_scope, dict):
        raw_type = raw_scope.get("type")
        raw_tickers = raw_scope.get("tickers") or payload.get("tickers") or []
        raw_stale_only = raw_scope.get("staleOnly")
        screen_id = raw_scope.get("screenId") or payload.get("screenId")
    else:
        raw_type = raw_scope or payload.get("scope") or "stale_only"
        raw_tickers = payload.get("tickers") or []
        raw_stale_only = payload.get("staleOnly")
        screen_id = payload.get("screenId")

    scope_type = str(raw_type or "stale_only").strip().lower()

    if scope_type not in {"universe", "tickers", "stale_only", "scheduled"}:
        scope_type = "stale_only"

    tickers = normalize_tickers(raw_tickers)

    if scope_type == "tickers" and not tickers:
        scope_type = "universe"

    return {
        "type": scope_type,
        "tickers": tickers,
        "staleOnly": bool(raw_stale_only or scope_type == "stale_only"),
        "screenId": text_or_none(screen_id),
        "scopeVersion": "refresh-policy-scope-v1",
    }


def normalize_tickers(raw_tickers) -> list[str]:
    if raw_tickers is None:
        values = []
    elif isinstance(raw_tickers, str):
        values = raw_tickers.split(",")
    elif isinstance(raw_tickers, list):
        values = raw_tickers
    else:
        values = []

    normalized = []

    for ticker in values:
        value = str(ticker).strip().upper()

        if value and value not in normalized:
            normalized.append(value)

    return normalized


def normalize_target(value) -> str:
    target = str(value or "ranking").strip().lower()

    return target if target in POLICY_TARGETS else "ranking"


def normalize_strategy(value) -> str:
    strategy = str(value or "magic_formula").strip().lower()

    return strategy if strategy else "magic_formula"


def normalize_period(value) -> str:
    return "quarter" if str(value or "").strip().lower() == "quarter" else "annual"


def normalize_schedule_hint(value) -> str:
    schedule_hint = str(value or "manual").strip().lower()

    return schedule_hint if schedule_hint in POLICY_SCHEDULE_HINTS else "manual"


def policy_name(value) -> str:
    name = str(value or "").strip()

    return name[:120] if name else "Untitled refresh policy"


def positive_int(value, default: int) -> int:
    try:
        parsed = int(value)

        return parsed if parsed > 0 else default
    except (TypeError, ValueError):
        return default


def parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def text_or_none(value) -> Optional[str]:
    if value is None:
        return None

    text = str(value).strip()

    return text or None


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def refresh_policy_id() -> str:
    return f"policy-{uuid4().hex[:12]}"

