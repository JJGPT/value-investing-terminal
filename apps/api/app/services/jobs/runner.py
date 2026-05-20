from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from app.services.fundamentals.provider import FundamentalsProvider
from app.services.market_data.provider import MarketDataProvider
from app.services.persistence.repository import SnapshotRepository
from app.services.persistence.sqlite_repository import SCHEMA_VERSION
from app.services.rankings.engine import refresh_ranking_run
from app.services.screener.engine import refresh_screener_snapshots
from app.services.screener.universe import PHASE_2D_TICKERS, PHASE_2D_UNIVERSE_NAME

JOB_TYPE_RANKING_REFRESH = "ranking_refresh"
JOB_TYPE_SCREENER_REFRESH = "screener_refresh"
JOB_STATUSES = {"queued", "running", "completed", "failed", "cancelled"}


def create_ranking_refresh_job(
    repository: SnapshotRepository,
    strategy: str,
    period: str,
    scope_type: str = "universe",
    tickers: Optional[list[str]] = None,
    stale_only: bool = False,
    screen_id: Optional[str] = None,
    policy_id: Optional[str] = None,
    stale_after_seconds: Optional[int] = None,
) -> dict:
    payload = {
        "target": "ranking",
        "strategy": strategy,
        "period": period,
        "screenId": screen_id,
        "scopeType": scope_type,
        "tickers": normalize_tickers(tickers or []),
        "staleOnly": stale_only,
        "policyId": policy_id,
        "staleAfterSeconds": stale_after_seconds,
    }
    job = create_job(
        repository,
        JOB_TYPE_RANKING_REFRESH,
        scope={
            "type": scope_type,
            "tickers": payload["tickers"],
            "staleOnly": stale_only,
            "screenId": screen_id,
            "policyId": policy_id,
            "scopeVersion": "refresh-job-scope-v1",
        },
        payload=payload,
    )

    return job


def run_ranking_refresh_job(
    fundamentals_provider: FundamentalsProvider,
    market_data_provider: MarketDataProvider,
    repository: SnapshotRepository,
    strategy: str,
    period: str,
    stale_after_seconds: int,
    scope_type: str = "universe",
    tickers: Optional[list[str]] = None,
    stale_only: bool = False,
    screen_id: Optional[str] = None,
    policy_id: Optional[str] = None,
) -> dict:
    job = create_ranking_refresh_job(
        repository,
        strategy,
        period,
        scope_type=scope_type,
        tickers=tickers,
        stale_only=stale_only,
        screen_id=screen_id,
        policy_id=policy_id,
        stale_after_seconds=stale_after_seconds,
    )

    return run_existing_ranking_refresh_job(
        fundamentals_provider,
        market_data_provider,
        repository,
        job["jobId"],
        stale_after_seconds,
    )


def run_existing_ranking_refresh_job(
    fundamentals_provider: FundamentalsProvider,
    market_data_provider: MarketDataProvider,
    repository: SnapshotRepository,
    job_id: str,
    stale_after_seconds: int,
) -> dict:
    job = repository.get_refresh_job(job_id)

    if job is None:
        return not_found_job(job_id)

    if job["status"] == "cancelled":
        return {
            **job,
            "result": None,
            "message": "Cancelled jobs are not run.",
        }

    if job["status"] not in {"queued"}:
        return {
            **job,
            "result": None,
            "message": "Only queued jobs can be run by the Phase 4D runner.",
        }

    running = mark_job_running(repository, job)
    payload = running.get("payload") or {}
    effective_stale_after = int(payload.get("staleAfterSeconds") or stale_after_seconds)
    stale_metadata = stale_only_metadata(
        repository,
        payload.get("period") or "annual",
        payload.get("tickers") or [],
        effective_stale_after,
        enabled=bool(payload.get("staleOnly")),
    )

    try:
        if payload.get("staleOnly"):
            payload = {
                **payload,
                "scopeType": "tickers",
                "tickers": stale_metadata["refreshTickers"],
            }
            running = {
                **running,
                "payload": payload,
                "scope": {
                    **(running.get("scope") or {}),
                    "type": "stale_only",
                    "tickers": stale_metadata["refreshTickers"],
                    "staleOnly": True,
                },
            }
            repository.update_refresh_job(running)

            if not stale_metadata["refreshTickers"]:
                return mark_job_completed(
                    repository,
                    running,
                    result=skipped_refresh_result(
                        running,
                        payload,
                        stale_metadata,
                        "ranking",
                    ),
                    warnings=[],
                )

        result = refresh_ranking_run(
            fundamentals_provider,
            market_data_provider,
            repository,
            payload.get("strategy") or "magic_formula",
            payload.get("period") or "annual",
            stale_after_seconds=effective_stale_after,
            screen_id=payload.get("screenId"),
            scope_type=payload.get("scopeType") or "universe",
            tickers=payload.get("tickers") or None,
            stale_only=bool(payload.get("staleOnly")),
        )
        result = with_job_metadata(
            result,
            running,
            stale_metadata,
            "ranking",
        )

        if result.get("status") == "failed":
            return mark_job_failed(
                repository,
                running,
                errors=result.get("errors") or [{"message": result.get("message")}],
                result=result,
            )

        repository.append_refresh_job_event(
            running["jobId"],
            job_event(
                running["jobId"],
                "ranking_refresh_completed",
                "running",
                "Ranking refresh execution produced a persisted result.",
                {"refreshId": result.get("refreshId"), "runId": result.get("runId")},
            ),
        )

        return mark_job_completed(
            repository,
            running,
            result=result,
            warnings=result.get("warnings") or [],
        )
    except Exception as error:  # defensive job boundary
        return mark_job_failed(
            repository,
            running,
            errors=[{"message": sanitize_error_message(str(error))}],
            result=None,
        )


def cancel_job(repository: SnapshotRepository, job_id: str) -> Optional[dict]:
    return repository.cancel_refresh_job(job_id, utc_now())


def create_screener_refresh_job(
    repository: SnapshotRepository,
    period: str,
    scope_type: str = "universe",
    tickers: Optional[list[str]] = None,
    stale_only: bool = False,
    policy_id: Optional[str] = None,
    stale_after_seconds: Optional[int] = None,
) -> dict:
    payload = {
        "target": "screener",
        "strategy": "screener",
        "period": period,
        "scopeType": scope_type,
        "tickers": normalize_tickers(tickers or []),
        "staleOnly": stale_only,
        "policyId": policy_id,
        "staleAfterSeconds": stale_after_seconds,
    }

    return create_job(
        repository,
        JOB_TYPE_SCREENER_REFRESH,
        scope={
            "type": scope_type,
            "tickers": payload["tickers"],
            "staleOnly": stale_only,
            "policyId": policy_id,
            "scopeVersion": "refresh-job-scope-v1",
        },
        payload=payload,
    )


def run_screener_refresh_job(
    fundamentals_provider: FundamentalsProvider,
    repository: SnapshotRepository,
    period: str,
    stale_after_seconds: int,
    scope_type: str = "universe",
    tickers: Optional[list[str]] = None,
    stale_only: bool = False,
    policy_id: Optional[str] = None,
) -> dict:
    job = create_screener_refresh_job(
        repository,
        period,
        scope_type=scope_type,
        tickers=tickers,
        stale_only=stale_only,
        policy_id=policy_id,
        stale_after_seconds=stale_after_seconds,
    )

    return run_existing_screener_refresh_job(
        fundamentals_provider,
        repository,
        job["jobId"],
        stale_after_seconds,
    )


def run_existing_screener_refresh_job(
    fundamentals_provider: FundamentalsProvider,
    repository: SnapshotRepository,
    job_id: str,
    stale_after_seconds: int,
) -> dict:
    job = repository.get_refresh_job(job_id)

    if job is None:
        return not_found_job(job_id, JOB_TYPE_SCREENER_REFRESH)

    if job["status"] == "cancelled":
        return {
            **job,
            "result": None,
            "message": "Cancelled jobs are not run.",
        }

    if job["status"] not in {"queued"}:
        return {
            **job,
            "result": None,
            "message": "Only queued jobs can be run by the Phase 4E runner.",
        }

    running = mark_job_running(repository, job)
    payload = running.get("payload") or {}
    effective_stale_after = int(payload.get("staleAfterSeconds") or stale_after_seconds)
    stale_metadata = stale_only_metadata(
        repository,
        payload.get("period") or "annual",
        payload.get("tickers") or [],
        effective_stale_after,
        enabled=bool(payload.get("staleOnly")),
    )

    try:
        refresh_tickers = payload.get("tickers") or None

        if payload.get("staleOnly"):
            refresh_tickers = stale_metadata["refreshTickers"]
            running = {
                **running,
                "payload": {
                    **payload,
                    "tickers": refresh_tickers,
                },
                "scope": {
                    **(running.get("scope") or {}),
                    "type": "stale_only",
                    "tickers": refresh_tickers,
                    "staleOnly": True,
                },
            }
            repository.update_refresh_job(running)

            if not refresh_tickers:
                return mark_job_completed(
                    repository,
                    running,
                    result=skipped_refresh_result(
                        running,
                        {
                            **payload,
                            "tickers": refresh_tickers,
                        },
                        stale_metadata,
                        "screener",
                    ),
                    warnings=[],
                )

        result = refresh_screener_snapshots(
            fundamentals_provider,
            repository,
            payload.get("period") or "annual",
            universe=refresh_tickers,
        )
        result = with_job_metadata(result, running, stale_metadata, "screener")

        if result.get("status") == "failed":
            return mark_job_failed(
                repository,
                running,
                errors=result.get("failures") or [{"message": result.get("message")}],
                result=result,
            )

        repository.append_refresh_job_event(
            running["jobId"],
            job_event(
                running["jobId"],
                "screener_refresh_completed",
                "running",
                "Screener snapshot refresh produced durable snapshot metadata.",
                {
                    "status": result.get("status"),
                    "refreshedCount": result.get("refreshedCount"),
                    "failedCount": result.get("failedCount"),
                },
            ),
        )

        return mark_job_completed(
            repository,
            running,
            result=result,
            warnings=result.get("warnings") or [],
        )
    except Exception as error:  # defensive job boundary
        return mark_job_failed(
            repository,
            running,
            errors=[{"message": sanitize_error_message(str(error))}],
            result=None,
        )


def create_job(
    repository: SnapshotRepository,
    job_type: str,
    scope: dict,
    payload: dict,
) -> dict:
    now = utc_now()
    job = {
        "jobId": job_id(job_type),
        "jobType": job_type,
        "status": "queued",
        "scope": scope,
        "payload": payload,
        "schemaVersion": SCHEMA_VERSION,
        "createdAt": now,
        "startedAt": None,
        "completedAt": None,
        "failedAt": None,
        "durationMs": None,
        "warnings": [],
        "errors": [],
        "resultMetadata": {},
        "result": None,
        "message": "Refresh job was queued in the local SQLite job store.",
    }
    repository.create_refresh_job(job)
    repository.append_refresh_job_event(
        job["jobId"],
        job_event(
            job["jobId"],
            "job_created",
            "queued",
            "Refresh job was queued.",
            {"jobType": job_type, "scope": scope},
        ),
    )

    return job


def mark_job_running(repository: SnapshotRepository, job: dict) -> dict:
    started_at = utc_now()
    updated = {
        **job,
        "status": "running",
        "startedAt": started_at,
        "message": "Refresh job is running synchronously in Phase 4D.",
    }
    repository.update_refresh_job(updated)
    repository.append_refresh_job_event(
        updated["jobId"],
        job_event(
            updated["jobId"],
            "job_started",
            "running",
            "Refresh job started synchronous execution.",
            {},
        ),
    )

    return updated


def mark_job_completed(
    repository: SnapshotRepository,
    job: dict,
    result: dict,
    warnings: list[dict],
) -> dict:
    completed_at = utc_now()
    updated = {
        **job,
        "status": "completed",
        "completedAt": completed_at,
        "durationMs": duration_ms(
            job.get("startedAt") or job["createdAt"],
            completed_at,
        ),
        "warnings": warnings,
        "errors": [],
        "resultMetadata": result_metadata(result),
        "result": result,
        "message": "Refresh job completed successfully.",
    }
    repository.update_refresh_job(updated)
    repository.append_refresh_job_event(
        updated["jobId"],
        job_event(
            updated["jobId"],
            "job_completed",
            "completed",
            "Refresh job completed successfully.",
            updated["resultMetadata"],
        ),
    )

    return updated


def mark_job_failed(
    repository: SnapshotRepository,
    job: dict,
    errors: list[dict],
    result: Optional[dict],
) -> dict:
    failed_at = utc_now()
    safe_result = sanitize_result_payload(result)
    sanitized_errors = [
        {
            "message": sanitize_error_message(
                error.get("message") if isinstance(error, dict) else str(error)
            )
        }
        for error in errors
    ]
    updated = {
        **job,
        "status": "failed",
        "failedAt": failed_at,
        "durationMs": duration_ms(job.get("startedAt") or job["createdAt"], failed_at),
        "warnings": (safe_result or {}).get("warnings") or [],
        "errors": sanitized_errors,
        "resultMetadata": result_metadata(safe_result),
        "result": safe_result,
        "message": "Refresh job failed. See job events and errors for details.",
    }
    repository.update_refresh_job(updated)
    repository.append_refresh_job_event(
        updated["jobId"],
        job_event(
            updated["jobId"],
            "job_failed",
            "failed",
            sanitized_errors[0]["message"] if sanitized_errors else "Refresh job failed.",
            {"errors": sanitized_errors},
        ),
    )

    return updated


def job_event(
    current_job_id: str,
    event_type: str,
    status: str,
    message: str,
    payload: dict,
) -> dict:
    return {
        "eventId": f"event-{current_job_id}-{event_type}-{uuid4().hex[:10]}",
        "eventType": event_type,
        "status": status,
        "message": message,
        "createdAt": utc_now(),
        "payload": payload,
    }


def result_metadata(result: Optional[dict]) -> dict:
    if not isinstance(result, dict):
        return {}

    metadata = result.get("metadata") or {}
    stale_only = metadata.get("staleOnly") or {}

    return {
        "refreshId": result.get("refreshId"),
        "runId": result.get("runId"),
        "strategy": result.get("strategy"),
        "period": result.get("period"),
        "target": result.get("target") or metadata.get("target"),
        "policyId": result.get("policyId") or metadata.get("policyId"),
        "status": result.get("status"),
        "scope": result.get("scope"),
        "startedAt": result.get("startedAt"),
        "completedAt": result.get("completedAt"),
        "failedAt": result.get("failedAt"),
        "refreshedCount": result.get("refreshedCount")
        or stale_only.get("refreshedCount"),
        "skippedFreshCount": stale_only.get("skippedFreshCount"),
        "freshCount": stale_only.get("freshCount"),
        "staleCount": stale_only.get("staleCount"),
        "missingCount": stale_only.get("missingCount"),
        "staleOnly": stale_only,
    }


def with_job_metadata(
    result: dict,
    job: dict,
    stale_metadata: dict,
    target: str,
) -> dict:
    metadata = {
        **(result.get("metadata") or {}),
        "target": target,
        "policyId": (job.get("payload") or {}).get("policyId"),
        "staleOnly": stale_metadata,
    }

    return {
        **result,
        "target": target,
        "policyId": (job.get("payload") or {}).get("policyId"),
        "metadata": metadata,
    }


def skipped_refresh_result(
    job: dict,
    payload: dict,
    stale_metadata: dict,
    target: str,
) -> dict:
    completed_at = utc_now()
    return {
        "refreshId": None,
        "schemaVersion": SCHEMA_VERSION,
        "status": "completed",
        "state": "completed",
        "target": target,
        "policyId": payload.get("policyId"),
        "strategy": payload.get("strategy") or target,
        "period": payload.get("period") or "annual",
        "scope": job.get("scope") or {},
        "startedAt": job.get("startedAt"),
        "completedAt": completed_at,
        "failedAt": None,
        "durationMs": duration_ms(job.get("startedAt") or job["createdAt"], completed_at),
        "warnings": [],
        "errors": [],
        "stateTransitions": [
            {
                "state": "completed",
                "at": completed_at,
                "message": "Stale-only refresh skipped because all rows were fresh.",
            }
        ],
        "metadata": {
            "synchronous": True,
            "target": target,
            "policyId": payload.get("policyId"),
            "staleOnly": stale_metadata,
        },
        "runId": None,
        "run": None,
        "message": "Stale-only refresh skipped; no stale or missing rows were found.",
    }


def stale_only_metadata(
    repository: SnapshotRepository,
    period: str,
    requested_tickers: list[str],
    stale_after_seconds: int,
    enabled: bool,
) -> dict:
    tickers = refresh_universe(repository, requested_tickers)
    snapshots = repository.get_screener_row_snapshots(tickers, period)
    classification = []
    refresh_tickers = []
    skipped_tickers = []
    counts = {
        "fresh": 0,
        "stale": 0,
        "missing": 0,
    }

    for ticker in tickers:
        snapshot = snapshots.get(ticker)
        age_seconds = snapshot_age_seconds(snapshot) if snapshot else None
        state = snapshot_state(snapshot, age_seconds, stale_after_seconds)
        should_refresh = enabled and state in {"stale", "missing"}

        counts[state] += 1

        if should_refresh:
            refresh_tickers.append(ticker)
        else:
            skipped_tickers.append(ticker)

        classification.append(
            {
                "ticker": ticker,
                "state": state,
                "ageSeconds": age_seconds,
                "refreshed": should_refresh,
            }
        )

    return {
        "enabled": enabled,
        "staleAfterSeconds": stale_after_seconds,
        "universeSize": len(tickers),
        "freshCount": counts["fresh"],
        "staleCount": counts["stale"],
        "missingCount": counts["missing"],
        "refreshedCount": len(refresh_tickers) if enabled else len(tickers),
        "skippedFreshCount": counts["fresh"] if enabled else 0,
        "refreshTickers": refresh_tickers if enabled else tickers,
        "skippedTickers": skipped_tickers if enabled else [],
        "classification": classification,
    }


def refresh_universe(
    repository: SnapshotRepository,
    requested_tickers: list[str],
) -> list[str]:
    normalized_requested = normalize_tickers(requested_tickers or [])

    if normalized_requested:
        return normalized_requested

    persisted = repository.list_universe(PHASE_2D_UNIVERSE_NAME)

    return persisted or PHASE_2D_TICKERS


def snapshot_state(
    snapshot: Optional[dict],
    age_seconds: Optional[int],
    stale_after_seconds: int,
) -> str:
    if snapshot is None:
        return "missing"

    if age_seconds is None or age_seconds > stale_after_seconds:
        return "stale"

    return "fresh"


def snapshot_age_seconds(snapshot: Optional[dict]) -> Optional[int]:
    if not snapshot:
        return None

    timestamp = snapshot.get("refreshedAt") or snapshot.get("computedAt")

    if not timestamp:
        return None

    try:
        refreshed_at = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError:
        return None

    return max(int((datetime.now(timezone.utc) - refreshed_at).total_seconds()), 0)


def normalize_tickers(tickers: list[str]) -> list[str]:
    normalized = []

    for ticker in tickers:
        normalized_ticker = ticker.strip().upper()

        if normalized_ticker and normalized_ticker not in normalized:
            normalized.append(normalized_ticker)

    return normalized


def not_found_job(
    current_job_id: str,
    job_type: str = JOB_TYPE_RANKING_REFRESH,
) -> dict:
    return {
        "jobId": current_job_id,
        "jobType": job_type,
        "status": "failed",
        "schemaVersion": SCHEMA_VERSION,
        "scope": {},
        "payload": {},
        "createdAt": utc_now(),
        "startedAt": None,
        "completedAt": None,
        "failedAt": utc_now(),
        "durationMs": None,
        "warnings": [],
        "errors": [{"message": "Refresh job was not found."}],
        "resultMetadata": {},
        "result": None,
        "message": "Refresh job was not found.",
    }


def job_id(job_type: str) -> str:
    return f"job-{job_type}-{uuid4().hex[:12]}"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def duration_ms(started_at: str, finished_at: str) -> Optional[int]:
    try:
        started = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        finished = datetime.fromisoformat(finished_at.replace("Z", "+00:00"))

        return max(int((finished - started).total_seconds() * 1000), 0)
    except ValueError:
        return None


def sanitize_error_message(message: str) -> str:
    sanitized = (message or "").replace("\n", " ").strip()
    sanitized = redact_secret_names(sanitized)

    return sanitized[:500] or "Unknown refresh job error."


def redact_secret_names(value):
    if isinstance(value, str):
        redacted = value

        for secret_name in [
            "FMP_API_KEY",
            "ALPACA_API_KEY",
            "ALPACA_SECRET_KEY",
            "ALPACA_BASE_URL",
            "ALPACA_DATA_BASE_URL",
        ]:
            redacted = redacted.replace(secret_name, "[redacted]")

        return redacted

    if isinstance(value, list):
        return [redact_secret_names(item) for item in value]

    if isinstance(value, dict):
        return {key: redact_secret_names(item) for key, item in value.items()}

    return value


def sanitize_result_payload(result: Optional[dict]) -> Optional[dict]:
    if not isinstance(result, dict):
        return result

    safe_result = redact_secret_names(dict(result))

    if isinstance(safe_result.get("message"), str):
        safe_result["message"] = sanitize_error_message(safe_result["message"])

    for key in ["errors", "failures"]:
        if isinstance(safe_result.get(key), list):
            safe_result[key] = [
                {
                    **item,
                    "message": sanitize_error_message(item.get("message")),
                }
                if isinstance(item, dict)
                else {"message": sanitize_error_message(str(item))}
                for item in safe_result[key]
            ]

    return safe_result
