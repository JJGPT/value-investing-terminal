# Ranking Methodology

## Purpose

Phase 4 introduces deterministic, platform-owned ranking screens. Rankings are research workflow tools, not recommendations, portfolio instructions, or trading signals.

The ranking engine uses canonical normalized fundamentals, platform-owned computed metrics, backend market data when available, and persisted screener snapshots where possible.

## Strategies

Supported strategies:

- `magic_formula`
- `quality`
- `value`
- `growth`
- `profitability`

## Magic Formula

The Magic Formula implementation follows a Greenblatt-style two-factor ranking:

- `earningsYield = EBIT / enterpriseValue`
- `returnOnCapital = EBIT / investedCapital`
- `combinedRankScore = earningsYieldRank + returnOnCapitalRank`

Rows are ranked by lowest combined rank score. Ties are resolved deterministically by earnings yield rank and ticker.

Canonical inputs:

- `EBIT`: normalized `operatingIncome`
- `enterpriseValue`: market-data enterprise value when available, otherwise `marketCap + totalDebt - cashAndEquivalents`
- `investedCapital`: platform-owned computed `investedCapital` when available, otherwise `totalDebt + shareholdersEquity - cashAndEquivalents`

## Other Strategies

Initial non-Magic strategies are intentionally simple:

- `quality`: ROIC, ROE, and FCF margin.
- `value`: inverse P/E, P/B, and P/S provider-reference ratios.
- `growth`: revenue growth YoY.
- `profitability`: gross, operating, net, and FCF margins.

These are transparent deterministic composites for workflow testing. They are not final institutional ranking models.

## Eligibility Layer

Phase 4B adds deterministic eligibility classification before ranking. Every row is classified as:

- `eligible`
- `ineligible`
- `unranked_missing_data`

Default eligibility settings:

- minimum market cap: `0`
- minimum price: `0`
- minimum volume: disabled until reliable liquidity data is available
- positive enterprise value required where EV is used
- positive invested capital required where return on capital is used
- positive EBIT required for Magic Formula ranking
- optional financials/utilities sector exclusions are supported but disabled by default

Rows are not silently removed. Ineligible and missing-data rows remain visible when `includeIneligible=true`, with explicit `eligibilityReasons`.

Example reasons:

- `missing_input:ebit`
- `missing_input:enterpriseValue`
- `non_positive:enterpriseValue`
- `below_minimum:marketCap`
- `excluded_sector:financials`

## Missing Data

Missing inputs return `null` and add quality flags. The engine does not invent values.

Examples:

- `missing_input:ebit`
- `missing_input:marketCap`
- `missing_input:earningsYield`
- `missing_input:returnOnCapital`
- `excluded_from_ranking:missing_magic_formula_inputs`

Rows with missing Magic Formula inputs stay in the response with `rank = null` so the analyst can audit coverage gaps.

## Ranking Audit Metadata

Every ranking row exposes:

- eligibility status and reasons
- input values used by the formula
- score/formula components
- snapshot metadata
- `computedAt`
- `rankingEngineVersion`

This metadata is intended to make every rank traceable back to canonical inputs and persisted snapshots.

## Ranking Runs And Change History

`POST /api/rankings/refresh` creates a local refresh job and persists an immutable ranking run in SQLite when the job completes.

Stored run metadata includes:

- `schemaVersion`
- strategy and period
- controlled universe
- eligibility settings
- ranking rows
- `computedAt`
- `rankingEngineVersion`

SQLite tables:

- `ranking_runs`
- `ranking_row_snapshots`

`GET /api/rankings/runs/{runId}/changes` compares the selected run with the prior run for the same strategy and period. Change rows include rank change, score change, eligibility change, new entrant/dropped/unchanged classification, and current/prior eligibility status.

The legacy refresh run remains stored in `ranking_refresh_runs`; Phase 4D also stores the surrounding job record in `refresh_jobs` and its append-only events in `refresh_job_events`.

## Saved Screens

Phase 4C adds reusable saved ranking screens. A screen stores:

- name
- strategy
- filters
- eligibility settings
- sorting
- period
- limit
- `schemaVersion`
- `createdAt` and `updatedAt`

Lifecycle states are `active`, `archived`, and `deleted`. Rename, duplicate, archive, restore, and soft delete are deterministic metadata operations. They do not alter historical ranking runs.

Saved screens are stored in `ranking_saved_screens` as JSON payloads with indexed status, strategy, period, and timestamps. This keeps the local implementation lightweight while preserving a clean path to PostgreSQL/Supabase later.

## Refresh Workflow Foundation

Phase 4C wraps ranking refresh in a reusable workflow model:

- refresh request
- refresh scope
- refresh state
- refresh result
- refresh metadata
- refresh timestamps

States:

- `queued`
- `running`
- `completed`
- `failed`

Refresh remains synchronous internally. Each refresh records state transitions, duration, strategy, period, scope, warnings, errors, and the produced ranking run id when successful.

Refresh scopes are contract-ready for:

- full universe refresh
- per-ticker refresh
- partial refresh
- stale-only refresh
- scheduled refresh

Phase 4D adds a lightweight local job runner around this workflow. A ranking refresh job stores:

- `jobId`
- `jobType = ranking_refresh`
- status: `queued`, `running`, `completed`, `failed`, or `cancelled`
- scope and payload JSON
- timestamps and duration
- warnings and sanitized errors
- result metadata, including refresh id and ranking run id
- append-only events

`POST /api/jobs/ranking-refresh` creates a job and runs it synchronously by default. Passing `run=false` creates only the queued job. `POST /api/jobs/{jobId}/cancel` can cancel a queued job before execution.

This is not yet a distributed queue. It intentionally avoids Celery, Redis, scheduler infrastructure, and worker processes in Phase 4D. The API is job-shaped so later phases can move execution to scheduled refreshes, incremental refreshes, priority refreshes, and a queue-backed worker without changing ranking contracts.

Phase 4E adds refresh policies and stale-only orchestration:

- ranking and screener policies persist target, strategy, period, scope, stale threshold, enabled state, schedule hint, and run hints;
- stale-only jobs classify tickers from screener row snapshot freshness;
- fresh rows are skipped;
- stale and missing rows are refreshed or re-ranked;
- policy-triggered jobs record classification counts and per-ticker states in job metadata;
- `POST /api/jobs/run-due-refresh-policies` is a manual scheduler simulation, not an automatic production scheduler.

## Snapshot Behavior

The engine prefers persisted SQLite snapshots:

- fundamentals snapshots
- computed metric snapshots
- screener row snapshots

If snapshots are missing and providers are connected, the engine may fall back to provider-backed normalized fundamentals. Provider fallback is explicit in row source metadata.

## API

- `GET /api/rankings/magic-formula?period=annual&limit=50`
- `GET /api/rankings?strategy=magic_formula|quality|value|growth|profitability&period=annual|quarter&limit=50&includeIneligible=true`
- `POST /api/rankings/refresh?strategy=magic_formula&period=annual`
- `GET /api/rankings/refresh-runs?strategy=magic_formula&period=annual`
- `POST /api/jobs/ranking-refresh?strategy=magic_formula&period=annual`
- `GET /api/jobs?jobType=ranking_refresh`
- `GET /api/jobs/{jobId}`
- `GET /api/jobs/{jobId}/events`
- `POST /api/jobs/{jobId}/cancel`
- `GET /api/refresh-policies`
- `POST /api/refresh-policies`
- `PATCH /api/refresh-policies/{policyId}`
- `POST /api/refresh-policies/{policyId}/enable`
- `POST /api/refresh-policies/{policyId}/disable`
- `POST /api/refresh-policies/{policyId}/run-now`
- `POST /api/jobs/run-due-refresh-policies`
- `GET /api/rankings/runs?strategy=magic_formula&period=annual`
- `GET /api/rankings/runs/{runId}`
- `GET /api/rankings/runs/{runId}/changes`
- `GET /api/rankings/screens`
- `POST /api/rankings/screens`
- `GET /api/rankings/screens/{screenId}`
- `PATCH /api/rankings/screens/{screenId}`
- `POST /api/rankings/screens/{screenId}/duplicate`
- `POST /api/rankings/screens/{screenId}/archive`
- `POST /api/rankings/screens/{screenId}/restore`
- `DELETE /api/rankings/screens/{screenId}`
- `GET /api/diagnostics/rankings`

Responses include ranked rows, formula inputs, score components, quality flags, provider state, source metadata, universe metadata, and eligibility diagnostics.

## Limitations

- Controlled universe only.
- No global production coverage.
- No buy/sell recommendation.
- No AI/RAG interpretation.
- No portfolio construction or optimization.
- No sector/industry neutral ranking yet.
- Liquidity eligibility is only active when volume data is available and a minimum is configured.
- Enterprise value is proxied when direct market data is unavailable.
- Invested capital is a conservative proxy until the normalized metrics engine matures.
- Ranking refresh jobs still execute synchronously inside the API process until a worker or queue exists.
- Refresh policies are advisory local records and not cron-backed production schedules.
- Saved screens are single-user/local metadata; no collaboration, sharing, or permissions model yet.
