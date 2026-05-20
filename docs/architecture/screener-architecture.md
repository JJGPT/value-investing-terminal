# Screener Architecture

## Purpose

Phase 2E makes the first screener slice snapshot-backed. It screens a small controlled ticker universe using durable normalized snapshots, canonical fundamentals, and platform-owned computed metrics.

This is not yet a production global screener. It is an auditable backend service boundary that can later be backed by PostgreSQL/Supabase, scheduled ingestion, and saved screens.

## Current Universe

The Phase 2D development universe is fixed in code:

- `AAPL`
- `MSFT`
- `GOOGL`
- `AMZN`
- `META`
- `BRK.B`
- `TPL`
- `KO`
- `COST`
- `NVDA`
- `UPWK`
- `GCT`

The universe module is intentionally small and replaceable. Later phases should move universe selection into a securities database and materialized screener snapshot table.

## Backend Flow

`GET /api/screener` runs through `apps/api/app/services/screener/engine.py`.

The engine:

1. Normalizes query parameters.
2. Iterates over the controlled universe.
3. Reads persisted screener row snapshots from the SQLite repository.
4. Uses stale snapshots when present and marks them as stale.
5. Fetches provider-backed rows only when snapshots are missing.
6. Extracts canonical screener fields.
7. Adds missing metric and source quality flags.
8. Applies deterministic filters.
9. Applies deterministic sort with null values last.
10. Applies pagination.
11. Returns provider state, source metadata, snapshot metadata, quality flags, and pagination metadata.

There is no heavy ORM, AI scoring, DCF, intrinsic value, or autonomous workflow in this phase. The ranking engine consumes this screener foundation without changing screener filtering semantics.

## Snapshot Store

Phase 2E uses Python stdlib `sqlite3` through a repository abstraction. JSON payloads are stored in:

- `securities_universe`
- `fundamentals_snapshots`
- `computed_metric_snapshots`
- `screener_row_snapshots`
- `snapshot_refresh_runs`

Every persisted payload includes:

- `schemaVersion: 1`
- `provenance.provider`
- `provenance.providerVersion`
- `provenance.fetchedAt`
- `provenance.sourceSymbol`

Computed metric and screener row snapshots also include:

- `computedFrom`
- `computedAt`

Local configuration:

- `VALUE_TERMINAL_DB_PATH`
- `SNAPSHOT_STALE_AFTER_SECONDS`

## Metric Sources

Platform-owned fields:

- `revenueGrowthYoY`
- `grossMargin`
- `operatingMargin`
- `netMargin`
- `freeCashFlowMargin`
- `returnOnEquity`
- `returnOnInvestedCapital`
- `debtToEquity`
- `currentRatio`
- `freeCashFlowPerShare`
- `bookValuePerShare`

Canonical provider-normalized fields:

- `marketCap`
- `price`
- `revenue`

Temporary provider reference fields:

- `peRatio`
- `pbRatio`
- `psRatio`

The price ratio fields currently use normalized FMP key metrics and are tagged with `provider_reference_metric:{field}`. They should eventually move into the platform-owned metrics engine.

## Filters And Sorting

Supported operators:

- `gt`
- `gte`
- `lt`
- `lte`
- `eq`
- `between`

Missing metric values:

- Render as `null` in API contracts.
- Do not pass metric filters.
- Sort last for both ascending and descending sorts.
- Add `missing_metric:{field}` quality flags.

## Frontend

`/screener` is a compact institutional table interface. It calls only the backend API client and never contacts FMP directly.

The page shows:

- period selector;
- single metric filter;
- sort selector;
- provider status;
- universe size;
- pagination metadata;
- snapshot state and stale markers;
- real screener rows when the backend can produce them;
- not-connected or degraded states without fake values.

## Diagnostics

`/api/diagnostics/fundamentals` includes a `screener` block with:

- readiness;
- universe name and size;
- persisted universe size;
- FMP provider dependency state;
- SQLite snapshot store state;
- annual/quarter snapshot freshness;
- cache-backed status;
- fundamentals cache TTLs;
- screener endpoint readiness.

`/api/diagnostics/rankings` adds ranking-specific readiness:

- available deterministic strategies;
- ranking engine version;
- controlled universe size;
- eligible Magic Formula rows;
- ineligible and missing-data row counts;
- ranking store readiness;
- latest ranking run metadata;
- saved screen counts;
- refresh workflow status distribution;
- local refresh job counts and status distribution;
- refresh policy counts and due-policy counts;
- latest refresh metadata;
- latest refresh job metadata;
- failed refresh count;
- stale ranking run count;
- engine version distribution;
- endpoint readiness for `/api/rankings`, `/api/rankings/magic-formula`, `/api/rankings/refresh`, `/api/jobs/ranking-refresh`, and `/api/rankings/runs`.

## Ranking Engine Relationship

Rankings read the same controlled universe and prefer persisted snapshots. When snapshots are missing and providers are connected, rankings can fall back to provider-backed normalized fundamentals.

Magic Formula ranking uses canonical statement fields:

- `EBIT = operatingIncome`
- `enterpriseValue = marketData.enterpriseValue` when available, otherwise `marketCap + totalDebt - cashAndEquivalents`
- `returnOnCapital = EBIT / investedCapital`

Rows with missing ranking inputs remain visible with `rank = null` and explanatory quality flags.

Phase 4B adds deterministic eligibility classification and ranking run persistence:

- rows are classified as `eligible`, `ineligible`, or `unranked_missing_data`;
- every exclusion includes `eligibilityReasons`;
- persisted ranking runs are stored in SQLite JSON payloads;
- row snapshots include input values, formula components, eligibility settings, and engine version;
- rank-change history compares the latest persisted run with the prior run for the same strategy and period.

Phase 4C adds saved ranking screens and refresh workflow records:

- saved screens persist strategy, filters, eligibility settings, sorting, period, and limit;
- screen lifecycle supports active, archived, and deleted states;
- refresh workflow records queued/running/completed/failed transitions;
- refresh scopes are ready for future per-ticker, stale-only, partial, and scheduled refreshes, while execution remains synchronous.

Phase 4D adds a SQLite-backed local job runner around ranking refresh. Jobs store queue-shaped status, scope, payload, result metadata, warnings, sanitized errors, and append-only events in `refresh_jobs` and `refresh_job_events`. Execution remains synchronous inside the API request, but `/api/jobs/ranking-refresh` and related job history endpoints prepare the contract for a later worker or scheduler.

Phase 4E adds refresh policies for both ranking and screener refresh. Stale-only policy execution classifies screener row snapshots as fresh, stale, or missing. Fresh rows are skipped; stale and missing rows are refreshed or re-ranked. `/api/jobs/run-due-refresh-policies` manually simulates a scheduler by evaluating enabled policies and running due jobs synchronously.

## Phase 2D Limitations

- SQLite is local-development persistence, not the final production database.
- No global coverage.
- No saved screens.
- Ranking is limited to deterministic methods; no AI summaries.
- No intrinsic value or DCF-based ranking.
- Refresh jobs still run synchronously in Phase 4E and should become async, scheduled, incremental, priority-aware, and queue-backed later.

## Next Evolution

The next useful step is to move the job-shaped refresh runner into scheduled or background execution and add durable PostgreSQL/Supabase repositories behind the same storage abstraction.
