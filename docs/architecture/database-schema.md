# Database Schema

## Purpose

The database must support institutional research workflows: canonical securities, normalized financials, screeners, valuation scenarios, filings, news, RAG, agent runs, and user research artifacts.

PostgreSQL/Supabase should be the primary system of record. Redis should be used for queues, cache, locks, and short-lived market state.

## Schema Principles

- Store raw source payloads separately from normalized domain tables.
- Track provenance for reported and derived values.
- Version formulas, extraction logic, and provider mappings.
- Partition high-volume time-series tables.
- Make screener queries fast through materialized views or denormalized metric snapshots.
- Keep AI outputs auditable by linking them to evidence and source chunks.

## Core Tables

## Phase 2E Local SQLite Snapshot Store

Phase 2E uses SQLite for local development only. It is intentionally lightweight and should be replaced by PostgreSQL/Supabase through the repository interface when durable ingestion matures.

Local tables:

- `securities_universe`: controlled universe ticker membership.
- `fundamentals_snapshots`: versioned JSON payloads for profiles, statements, and provider key metrics.
- `computed_metric_snapshots`: versioned JSON payloads for platform-owned computed metrics.
- `screener_row_snapshots`: versioned JSON payloads for screener-ready rows.
- `snapshot_refresh_runs`: synchronous refresh audit metadata.
- `valuation_scenarios`: versioned JSON payloads for saved DCF scenarios and outputs.
- `valuation_scenario_versions`: immutable JSON payloads for every saved DCF scenario version.
- `valuation_audit_events`: append-only valuation audit events.
- `valuation_notes`: immutable analyst notes attached to scenario versions, assumptions, or warnings.
- `ranking_runs`: immutable ranking run metadata and full JSON result payloads.
- `ranking_row_snapshots`: one ranking row snapshot per ticker per persisted run.
- `ranking_saved_screens`: reusable deterministic ranking screen definitions.
- `ranking_refresh_runs`: ranking refresh workflow execution metadata.
- `refresh_jobs`: local refresh job records with JSON scope, payload, result metadata, warnings, and errors.
- `refresh_job_events`: append-only local refresh job event log.
- `refresh_policies`: local ranking/screener refresh policy definitions and scheduling hints.
- `watchlists`: persisted research workspace metadata with lifecycle status.
- `watchlist_items`: ticker-level analyst notes, tags, target prices, thesis status, priority, and workflow state.

All persisted payloads include `schemaVersion = 1` and explicit provenance: provider, provider version, fetched timestamp, and source symbol. Computed metric and screener row snapshots also include source fiscal period metadata in `computedFrom` and a `computedAt` timestamp.

Valuation scenarios are persisted separately from fundamentals and screener snapshots. A saved DCF payload includes:

- `schemaVersion`
- `scenario.id`, assumptions, timestamps, and assumption quality flags
- projection rows
- sensitivity grids
- sensitivity visualization metadata
- reproducibility metadata: statement references, metric references, market data reference, engine versions, sensitivity configuration, and timestamp chain
- base financial inputs
- enterprise value, equity value, terminal value, and intrinsic value per share
- formula strings and provider state

Phase 3B reads this table for:

- latest scenario retrieval;
- saved scenario list views;
- specific scenario loading by id;
- saved case comparison.

Phase 3C treats `valuation_scenarios` as the latest pointer and lifecycle row. It adds immutable version storage and audit events so scenario edits do not overwrite prior assumptions or results.

Phase 3D adds immutable notes and repository diagnostics for valuation reproducibility. Diagnostics inspect scenario counts, version counts, audit event counts, note counts, orphaned version rows, stale scenarios, model version distribution, and reproducibility completeness.

Phase 4B adds ranking persistence. Ranking runs store:

- `run_id`
- strategy and period
- `schema_version`
- `ranking_engine_version`
- `computed_at`
- universe JSON
- eligibility settings JSON
- full ranking payload JSON

Ranking row snapshots store:

- `run_id`
- ticker
- strategy and period
- rank
- eligibility status
- score
- `computed_at`
- row payload JSON with eligibility reasons, input values, formula components, snapshot metadata, and quality flags

Rankings remain append-only in Phase 4B. A refresh creates a new run rather than overwriting prior ranking outputs. Change history compares a run with the prior run for the same strategy and period.

Phase 4C adds saved ranking screens and refresh workflow metadata. Saved screens store screen id, lifecycle status, name, strategy, period, limit, schema version, timestamps, and full JSON payloads containing filters, sorting, and eligibility settings. Refresh runs store refresh id, state/status, strategy, period, scope JSON, timestamps, duration, warnings, errors, and full workflow payloads.

Refresh states are `queued`, `running`, `completed`, and `failed`.

Phase 4D adds the lighter-weight job runner schema. `refresh_jobs` stores `job_id`, `job_type`, status, schema version, scope JSON, payload JSON, timestamps, duration, warnings JSON, errors JSON, result metadata JSON, and the full job payload. `refresh_job_events` stores event id, job id, sequence number, event type, status, timestamp, message, and event payload JSON. Events are append-only so refresh execution can be audited even while execution remains synchronous.

Job states are `queued`, `running`, `completed`, `failed`, and `cancelled`. Cancellation is best-effort and only applies to queued jobs in Phase 4D. This is not yet a distributed queue, scheduler, or worker system; later PostgreSQL/Supabase work can keep the same repository boundary while moving execution to Redis/Celery, a worker service, scheduled tasks, or priority queues.

Phase 4E adds `refresh_policies`. Policies store policy id, name, target, strategy, period, scope JSON, stale threshold, enabled flag, schedule hint, last run timestamp, next run hint, schema version, timestamps, and the full JSON payload. Schedule hints are local advisory values, not production cron records. Policy-triggered jobs are still persisted in `refresh_jobs` and `refresh_job_events`.

Phase 5A adds SQLite-backed watchlists. `watchlists` stores watchlist id, status, name, description, schema version, created/updated timestamps, archive/delete timestamps, and full JSON metadata payload. `watchlist_items` stores watchlist id, ticker, company name when known, added/updated timestamps, notes, tags JSON, optional target price, thesis status, priority, workflow state, and item JSON payload.

Phase 5B adds `watchlist_views` and `watchlist_alert_events`. `watchlist_views` stores per-watchlist saved filters, sorting, visible columns, lifecycle status, parent view provenance for duplicates, timestamps, schema version, and the full JSON payload. `watchlist_alert_events` stores deterministic alert ids, watchlist id, ticker, alert type, severity, lifecycle status, created/acknowledged/dismissed timestamps, placeholder acknowledgement user, schema version, and full JSON payload.

Watchlist alerts remain deterministic research records, but acknowledgement and dismissal history is now persisted locally. The system does not send notifications, create recommendations, or trigger trading actions.

Phase 5C stores watchlist refresh executions in the existing `refresh_jobs` and `refresh_job_events` tables using `job_type = watchlist_refresh`. The job scope and payload JSON include `watchlistId`, tickers, period, ranking strategy, stale-only flag, and schema version. No separate watchlist refresh table is introduced yet.

Lifecycle fields:

- `status`: `active`, `archived`, or `deleted`
- `parent_scenario_id`
- `latest_version_id`
- `latest_version_number`
- `archived_at`
- `deleted_at`

Version rows store version id, scenario id, ticker, version number, schema version, model version, parent scenario id, prior version id, created timestamp, and JSON payload.

Audit rows store event id, scenario id, ticker, version id, version number, change type, field path, previous value JSON, new value JSON, created timestamp, and full JSON payload.

Note rows store note id, scenario id, ticker, version id, version number, attachment type, field path, warning code, created timestamp, and full JSON payload. Notes are append-only in Phase 3D.

This remains JSON payload persistence. Later PostgreSQL/Supabase work should split scenarios, assumptions, projections, sensitivity grids, audit events, notes, and reproducibility references into relational tables once workflow requirements settle.

This local schema deliberately avoids SQLAlchemy, complex migrations, event sourcing, and full relational statement normalization.

### Securities

- `securities`: canonical company/security identity.
- `listings`: ticker, exchange, currency, country, active status.
- `exchanges`: market metadata, timezone, mic, region.
- `security_identifiers`: CIK, ISIN, FIGI, CUSIP, provider ids.
- `corporate_actions`: splits, dividends, symbol changes, mergers.

### Market Data

- `price_bars_eod`: daily OHLCV bars.
- `price_bars_intraday`: intraday OHLCV bars, partitioned by date.
- `market_snapshots`: latest quote/trade/day snapshot cache mirror.
- `market_calendar`: trading sessions, open/close times, holidays.

### Fundamentals

- `financial_statements`: statement header by security, period, form, currency.
- `statement_line_items`: normalized line items and source labels.
- `financial_metrics`: derived metrics such as ROIC, ROE, margins, FCF yield.
- `metric_snapshots`: screener-ready latest metrics by security.
- `formula_versions`: metric and valuation formula definitions.

### Valuation

- `valuation_models`: saved model type and metadata.
- `valuation_scenarios`: base, bull, bear, custom scenario assumptions.
- `dcf_outputs`: calculated intrinsic value, upside, terminal value, WACC, sensitivity references.
- `valuation_assumptions`: growth, margin, reinvestment, discount rate, terminal assumptions.

### Filings And News

- `filings`: SEC filing metadata and storage pointer.
- `filing_sections`: parsed sections with text offsets.
- `xbrl_facts`: company facts, units, taxonomy tags, fiscal periods.
- `news_articles`: source, headline, body pointer, tickers, published time.
- `news_events`: materiality classification, event type, linked securities.

### Knowledge And RAG

- `documents`: source metadata for books, PDFs, spreadsheets, checklists, memos, filings.
- `document_chunks`: extracted chunks with source offsets and metadata.
- `embeddings`: vector records linked to chunks.
- `evidence_packets`: retrieved evidence bundles used in AI runs.
- `citations`: links from generated outputs to source chunks.

### Research And Agents

- `research_notes`: user-authored notes and thesis fragments.
- `research_memos`: generated or drafted memo artifacts.
- `agent_runs`: workflow state, requested task, status, model config.
- `agent_steps`: specialist steps, tool calls, errors, outputs.
- `agent_artifacts`: structured outputs such as findings, risks, assumptions, memos.

### Users And Workspaces

- `users`
- `workspaces`
- `watchlists`
- `watchlist_items`
- `saved_screens`
- `alerts`

## Important Indexes

- `listings(ticker, exchange)`
- `security_identifiers(identifier_type, identifier_value)`
- `financial_metrics(security_id, period_end, metric_key)`
- `metric_snapshots(metric_key, metric_value)`
- `filings(security_id, filing_type, filed_at)`
- `news_articles(published_at)`
- vector index on `embeddings.embedding`
- full-text index on `document_chunks.content`

## MVP Schema

Start with:

- securities, listings, identifiers;
- price bars and snapshots;
- watchlists;
- metric snapshots;
- screener saved queries;
- valuation scenarios;
- job/audit tables.

Add filings, RAG, and agent tables after the core terminal and data foundation are stable.
