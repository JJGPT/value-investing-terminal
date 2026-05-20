# Backend Architecture

## Purpose

The backend owns financial domain logic, provider integrations, valuation calculations, RAG retrieval, AI orchestration, persistence, and auditability. The frontend should not contain provider credentials, valuation formulas, or data normalization rules.

## Target Stack

- FastAPI for domain APIs.
- PostgreSQL/Supabase for canonical data.
- Redis for cache, queues, locks, and ephemeral market data.
- Object storage for raw filings, provider payloads, extracted documents, and generated research artifacts.
- Worker processes for ingestion, filings, embeddings, and agent jobs.

## Service Boundaries

```text
apps/api/
  app/
    routers/
      securities.py
      screener.py
      companies.py
      financials.py
      valuation.py
      filings.py
      news.py
      research.py
      agents.py
    services/
      securities/
      market_data/
      fundamentals/
      valuation/
      filings/
      news/
      rag/
      agents/
    models/
    schemas/
    jobs/
```

## Core Backend Services

- Securities service: canonical company/listing/identifier model.
- Market data service: Alpaca bars, snapshots, calendar, market status, and cache policy.
- Fundamentals service: normalized financial statements, periods, currencies, restatements, derived metrics.
- Screener service: filterable metrics, saved screens, ranking formulas.
- Valuation service: DCF, WACC, FCFF/FCFE, multiples, scenarios, sensitivity.
- Watchlist service: persistent research workspaces, item metadata, workflow states, saved views, deterministic intelligence aggregation, staleness classification, watchlist-scoped refresh jobs, rule-based alerts, and alert lifecycle history.
- Filings service: SEC ingestion, section extraction, XBRL facts, filing citations.
- News service: provider ingestion, deduplication, entity linking, materiality classification.
- RAG service: retrieval, evidence packets, citations, document metadata.
- Agent service: job creation, state transitions, tool execution, artifact persistence.

## API Design

- Use resource-oriented REST endpoints first.
- Keep API responses typed, paginated, and versionable.
- Return provenance metadata with financial values where possible.
- Avoid provider-shaped responses; normalize to platform DTOs.
- Expose `/health` for process liveness and `/api/status` plus `/api/diagnostics/*` for safe provider, cache, repository, job, and environment readiness.
- Configure CORS through `CORS_ORIGINS` so deployed frontends can call the API without exposing backend secrets.
- Current provider-backed contracts are documented in [`../api-contracts.md`](../api-contracts.md).

Example endpoint families:

- `GET /api/securities/search?q=`
- `GET /api/securities/{ticker}`
- `GET /api/securities/{ticker}/snapshot`
- `GET /api/watchlists`
- `POST /api/watchlists`
- `GET /api/watchlists/{watchlistId}`
- `PATCH /api/watchlists/{watchlistId}`
- `POST /api/watchlists/{watchlistId}/archive`
- `POST /api/watchlists/{watchlistId}/restore`
- `DELETE /api/watchlists/{watchlistId}`
- `POST /api/watchlists/{watchlistId}/items`
- `PATCH /api/watchlists/{watchlistId}/items/{ticker}`
- `DELETE /api/watchlists/{watchlistId}/items/{ticker}`
- `GET /api/watchlists/{watchlistId}/intelligence`
- `POST /api/watchlists/{watchlistId}/refresh`
- `GET /api/watchlists/{watchlistId}/refresh-history`
- `GET /api/watchlists/{watchlistId}/staleness`
- `GET /api/watchlists/{watchlistId}/views`
- `POST /api/watchlists/{watchlistId}/views`
- `PATCH /api/watchlists/{watchlistId}/views/{viewId}`
- `GET /api/watchlists/{watchlistId}/alerts`
- `GET /api/watchlists/{watchlistId}/alerts/history`
- `POST /api/watchlists/{watchlistId}/alerts/{alertId}/acknowledge`
- `POST /api/watchlists/{watchlistId}/alerts/{alertId}/dismiss`
- `POST /api/watchlists/{watchlistId}/alerts/{alertId}/restore`
- `GET /api/fundamentals/{ticker}/profile`
- `GET /api/fundamentals/{ticker}/income-statement?period=annual&limit=5`
- `GET /api/fundamentals/{ticker}/balance-sheet?period=annual&limit=5`
- `GET /api/fundamentals/{ticker}/cash-flow?period=annual&limit=5`
- `GET /api/fundamentals/{ticker}/metrics?period=annual&limit=5`
- `GET /api/fundamentals/{ticker}/computed-metrics?period=annual&limit=5`
- `GET /api/screener?period=annual&limit=25&page=1`
- `GET /api/rankings/magic-formula?period=annual&limit=50`
- `GET /api/rankings?strategy=magic_formula&period=annual&limit=50&includeIneligible=true`
- `POST /api/rankings/refresh?strategy=magic_formula&period=annual`
- `GET /api/rankings/refresh-runs?strategy=magic_formula&period=annual`
- `POST /api/jobs/ranking-refresh?strategy=magic_formula&period=annual`
- `GET /api/jobs?jobType=ranking_refresh`
- `GET /api/jobs/{jobId}`
- `GET /api/jobs/{jobId}/events`
- `POST /api/jobs/{jobId}/cancel`
- `GET /api/refresh-policies`
- `POST /api/refresh-policies`
- `GET /api/refresh-policies/{policyId}`
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
- `GET /api/diagnostics/watchlists`
- `GET /api/valuation/dcf/{ticker}`
- `POST /api/valuation/dcf/{ticker}`
- `GET /api/valuation/dcf/{ticker}/sensitivity`
- `GET /api/valuation/dcf/{ticker}/scenarios?limit=10`
- `GET /api/valuation/dcf/{ticker}/scenarios/{scenarioId}`
- `POST /api/valuation/dcf/{ticker}/scenarios/{scenarioId}/versions`
- `PATCH /api/valuation/dcf/{ticker}/scenarios/{scenarioId}/rename`
- `POST /api/valuation/dcf/{ticker}/scenarios/{scenarioId}/duplicate`
- `POST /api/valuation/dcf/{ticker}/scenarios/{scenarioId}/archive`
- `POST /api/valuation/dcf/{ticker}/scenarios/{scenarioId}/restore`
- `DELETE /api/valuation/dcf/{ticker}/scenarios/{scenarioId}`
- `GET /api/valuation/dcf/{ticker}/scenarios/{scenarioId}/history`
- `GET /api/valuation/dcf/{ticker}/scenarios/{scenarioId}/notes`
- `POST /api/valuation/dcf/{ticker}/scenarios/{scenarioId}/notes`
- `GET /api/valuation/dcf/{ticker}/comparison?limit=5`
- `GET /api/valuation/dcf/{ticker}/compare?leftScenarioId=&rightScenarioId=`
- `GET /api/valuation/dcf/{ticker}/export/{scenarioId}`
- `POST /api/valuation/dcf/{ticker}/import`
- `GET /api/diagnostics/valuation?ticker=AAPL`
- `GET /companies/{ticker}/filings`
- `POST /research/query`
- `POST /agents/runs`
- `GET /agents/runs/{id}`

## Job Architecture

Use workers for:

- Universe sync.
- Market data backfills.
- Fundamentals refresh.
- SEC filing download and parsing.
- News ingestion and classification.
- Knowledge document extraction.
- Embedding generation.
- Agent research runs.

Phase 4D introduces a local refresh job foundation for ranking refreshes. The current runner still executes synchronously inside the API request, but it persists a job record and append-only event log first. This creates the API shape needed for later scheduled workers without introducing Celery, Redis, or a distributed queue yet.

Phase 4E adds refresh policies and a manual scheduler simulation. Policies are local SQLite records with schedule hints and stale thresholds. The scheduler endpoint inspects enabled due policies and runs them through the same synchronous job foundation.

Phase 5A adds persistent watchlists and deterministic watchlist intelligence. The watchlist service reads from the SQLite repository, market data provider, screener snapshots, computed metric snapshots, ranking runs, and saved valuation scenarios.

Phase 5B adds saved watchlist views, deterministic filter/sort execution, column visibility state, and alert acknowledgement/dismissal history. Alert records are still rule-based and generated from deterministic conditions, but their lifecycle state is persisted locally for auditability. The backend still does not send notifications or create investment conclusions.

Phase 5C adds watchlist-scoped refresh jobs and item-level staleness classification. Watchlist refresh jobs use `job_type = watchlist_refresh` in the existing job store and reuse screener snapshot refresh plus ranking refresh for the watchlist ticker set. Workflow states are manual item metadata and are never interpreted as recommendations.

Jobs should record:

- job type;
- scope and JSON payload;
- status: `queued`, `running`, `completed`, `failed`, or `cancelled`;
- started/completed timestamps;
- warnings and sanitized errors;
- result metadata such as refresh id and ranking run id;
- append-only events.

## Caching

- Phase 2C uses process-local TTL caches for successful Alpaca and FMP provider responses. This is intentionally lightweight and not durable persistence.
- Fundamentals cache keys are normalized by endpoint, ticker, period, and limit. Provider errors are not cached.
- Phase 2E adds a local SQLite snapshot repository for the controlled universe, normalized fundamentals snapshots, computed metric snapshots, and screener row snapshots.
- Screener requests read durable snapshots first, use stale snapshots with explicit metadata, and only fall back to provider-backed fetches for missing rows.
- Redis for short-lived market snapshots, provider rate-limit state, and active job progress.
- Database materialized views for screener metrics and expensive derived aggregates.
- CDN caching only for public/static frontend assets and explicitly cacheable read endpoints.

## Validation And Provenance

Every financial metric should carry:

- source provider or filing;
- fiscal period;
- currency;
- formula version;
- update timestamp;
- whether it is reported, normalized, or derived.
- quality flags for missing core fields, missing currency, missing fiscal year, missing shares, stale provider timestamps, currency mismatch, zero or negative denominators, unavailable invested capital, and provider anomalies.

AI-facing APIs should return evidence identifiers, not raw unsupported text blobs.

## Testing Strategy

- Unit tests for formulas and normalization.
- Golden tests for DCF and WACC models against known spreadsheet outputs.
- Integration tests for provider adapters with recorded fixtures.
- API contract tests between frontend DTOs and backend schemas.
- Ingestion idempotency tests.

## Current Backend Scope

Build:

- Alpaca market data adapter behind `MarketDataProvider`.
- FMP fundamentals adapter behind `FundamentalsProvider`.
- Not-connected fallback providers for missing credentials.
- Canonical company profile, statement, and provider-metric contracts.
- Annual and quarterly FMP fundamentals requests.
- TTM-ready contracts returning `not_implemented`.
- Platform-owned computed metrics from canonical statements.
- Process-local fundamentals and computed metrics cache.
- SQLite-backed snapshot repository using versioned JSON payloads and explicit provenance.
- Statement audit UI for source metadata and quality flags.
- Fundamentals-backed screener slice over a controlled 12-ticker universe.
- Deterministic screener filtering, sorting, pagination, missing metric handling, and quality flag propagation.
- Manual synchronous screener snapshot refresh endpoint.
- Platform-owned deterministic ranking engine over screener snapshots and canonical fundamentals.
- Magic Formula ranking using EBIT, enterprise value, and invested capital inputs.
- Basic transparent quality, value, growth, and profitability ranking strategies.
- Platform-owned FCFF DCF engine using canonical normalized statements, computed metrics, and market data.
- Editable deterministic valuation assumptions with source, rationale, and quality flags.
- SQLite-backed valuation scenario persistence separate from fundamentals and screener snapshots.
- Saved DCF scenario list/load/compare routes.
- Scenario diff, assumption import/export, and immutable analyst notes routes.
- Scenario lifecycle actions for rename, duplicate, archive, restore, and soft delete.
- Immutable scenario versions and audit event history.
- Model metadata and reproducibility references persisted with each DCF result.
- Incremental share-count projection and refined net debt assumptions.
- Valuation warning system for terminal value dominance, terminal growth, WACC spread, margins, reinvestment, ROIC/WACC consistency, projection instability, and missing shares.
- Valuation diagnostics for route readiness, repository state, engine version, saved scenario count, assumption validation bounds, orphaned versions, model version distribution, stale scenarios, notes, and reproducibility completeness.
- DCF sensitivity grids and heatmap visualization metadata for WACC, terminal growth, and operating margin.
- Valuation workbench UI at `/valuation/[ticker]`.
- Ranking run persistence, saved ranking screens, refresh jobs, refresh policies, stale-only orchestration, and manual due-policy execution.
- Persistent watchlists with saved views, deterministic alerts, alert lifecycle history, intelligence aggregation, item staleness, watchlist-scoped refresh jobs, and manual workflow states.
- Provider diagnostics for market data and fundamentals.
- Mocked provider and route contract tests.

Defer:

- PostgreSQL/Supabase persistence and durable ingestion jobs.
- Intrinsic-value-backed screener ranking and portfolio-level optimization.
- AI-generated valuation assumptions, autonomous valuation agents, and automatic buy/sell recommendations.
- Production valuation workflow controls such as approvals, audit locks, model ownership, and change history.
- Full global fundamentals normalization beyond current contracts.
- Production-grade global screener coverage, saved screens, materialized metric views, and ranking models.
- Full SEC parsing pipeline.
- Agent orchestration.
- Production RAG.
- Portfolio intelligence.
