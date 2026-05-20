# Refresh Workflows

## Purpose

Refresh workflows move expensive provider-backed work out of read paths. Phase 4D introduces a lightweight local job foundation for ranking refresh while preserving deterministic execution and SQLite auditability.

This is not a distributed queue yet. There is no Celery, Redis worker, scheduler, retry worker, or background process in Phase 4D.

## Current Job Model

Refresh jobs persist:

- `jobId`
- `jobType`
- `status`: `queued`, `running`, `completed`, `failed`, or `cancelled`
- scope JSON
- payload JSON
- `createdAt`, `startedAt`, `completedAt`, `failedAt`
- duration
- warnings
- sanitized errors
- result metadata
- `schemaVersion`

Job events are append-only and record lifecycle milestones such as job creation, start, ranking refresh completion, job completion, failure, or cancellation.

## Ranking Refresh Flow

1. The API creates a `ranking_refresh` job in `refresh_jobs`.
2. The API appends a `job_created` event.
3. If `run=true`, the API marks the job `running` and appends `job_started`.
4. The existing deterministic ranking refresh workflow computes and persists the ranking run.
5. The job stores compact result metadata, including refresh id and ranking run id.
6. The API appends completion or failure events and returns the job payload.

`POST /api/rankings/refresh` routes through the same job foundation. `POST /api/jobs/ranking-refresh` exposes the job API directly and supports `run=false` for queued-only creation.

## Cancellation

Cancellation is best-effort in Phase 4D. Only queued jobs can be cancelled. Running jobs execute synchronously inside the API process and are not interrupted.

## Future Migration Path

Later phases should move execution behind the same repository and API contracts:

- scheduled refreshes;
- stale-only refreshes;
- per-ticker and partial refreshes;
- retry policies;
- priority queues;
- a worker service backed by Redis, Celery, or managed queue infrastructure;
- PostgreSQL/Supabase persistence for production job history.

## Refresh Policies

Phase 4E adds local refresh policies for ranking and screener refresh orchestration.

A policy stores:

- `policyId`
- name
- target: `ranking` or `screener`
- strategy
- period
- scope
- stale threshold
- enabled flag
- schedule hint
- last run timestamp
- next run hint
- timestamps and `schemaVersion`

Schedule hints are intentionally simple: `manual`, `stale_only`, `hourly`, `daily`, `weekly`, and `always`. They are not cron expressions and do not run automatically.

## Manual Scheduler Simulation

`POST /api/jobs/run-due-refresh-policies` manually evaluates enabled policies. A policy is due when its next-run hint is at or before the current time. Due policies create jobs and run through the same local job runner.

This endpoint exists to test orchestration semantics before introducing a real scheduler. It is not a production background scheduler.

## Stale-Only Semantics

Stale-only refresh uses screener row snapshot freshness as the classification source:

- `fresh`: snapshot exists and is newer than `staleAfterSeconds`;
- `stale`: snapshot exists but is older than `staleAfterSeconds`;
- `missing`: no snapshot exists for the ticker/period.

Fresh tickers are skipped. Stale and missing tickers are refreshed or re-ranked. Job metadata records fresh, stale, missing, skipped, and refreshed counts plus per-ticker classification.

## Watchlist Refresh

Phase 5C adds `watchlist_refresh` jobs on top of the same local job foundation.

`POST /api/watchlists/{watchlistId}/refresh` creates a job whose scope stores:

- `watchlistId`;
- ticker list from watchlist items;
- period;
- ranking strategy;
- `staleOnly`;
- `schemaVersion`.

Execution remains synchronous for now. The watchlist job reuses existing snapshot refresh logic for fundamentals/computed metrics and existing ranking refresh logic for the watchlist ticker subset.

Watchlist stale-only mode uses the watchlist staleness model rather than only screener row freshness. Items classified as `stale`, `missing`, or `degraded` are refreshed; `fresh` items are skipped. Result metadata records stale/fresh/missing/degraded counts, refreshed tickers, skipped tickers, and per-ticker classification.

This does not send notifications, infer recommendations, trade, or optimize portfolios. It is a local deterministic research workflow that can later move to scheduled or async workers.
