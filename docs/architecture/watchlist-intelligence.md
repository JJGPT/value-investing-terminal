# Watchlist Intelligence

## Purpose

Phase 5C turns watchlists into deterministic research workspaces with saved views, auditable filters, alert acknowledgement history, staleness classification, and watchlist-scoped refresh jobs. A watchlist item can carry analyst-entered context while the backend aggregates source-backed data already produced by the platform.

This is not a recommendation engine. It does not trade, optimize portfolios, or infer buy/sell actions.

## Data Sources

Per ticker, the watchlist intelligence service reads:

- latest market snapshot from the `MarketDataProvider`;
- latest annual screener row snapshot;
- latest annual computed metrics snapshot;
- latest Magic Formula ranking run row;
- prior Magic Formula ranking run for change detection;
- latest saved DCF scenario summary;
- watchlist item notes, tags, target price, thesis status, priority, and workflow state.

Missing inputs remain `null` or unavailable. The service does not fabricate prices, rankings, fundamentals, valuation outputs, or qualitative analysis.

## Persistence

SQLite tables:

- `watchlists`: lifecycle metadata and JSON payload.
- `watchlist_items`: ticker rows with analyst-entered metadata and JSON payload.
- `watchlist_views`: saved filters, sorting, visible columns, lifecycle metadata, and JSON payload.
- `watchlist_alert_events`: deterministic alert history with acknowledgement/dismissal metadata and JSON payload.
- `refresh_jobs` / `refresh_job_events`: watchlist-scoped refresh jobs and append-only execution events.

Lifecycle states:

- `active`
- `archived`
- `deleted`

Delete is a soft-delete of the watchlist metadata. Item removal deletes the active item row from the watchlist.

Saved view delete is also a soft lifecycle state. Alert dismissal does not delete the alert event; it only hides it from the active inbox.

## Intelligence Output

`GET /api/watchlists/{watchlistId}/intelligence` returns:

- watchlist metadata;
- one intelligence item per ticker;
- market snapshot;
- fundamentals snapshot freshness;
- computed metrics snapshot summary;
- ranking summary and Magic Formula eligibility;
- valuation scenario summary;
- price versus intrinsic value gap;
- quality flags;
- deterministic alerts.

The intelligence endpoint accepts optional deterministic query state:

- `filters`: JSON array of saved-view-compatible filters.
- `sort`: JSON sort object.
- `viewId`: saved view id.

Supported filters cover ticker, tags, thesis status, priority, valuation gap, ranking status, alert type, stale snapshot state, missing critical data, and provider degraded state.

Phase 5C also supports filtering by workflow state, including a `needs_review` workspace lens.

Supported sorting covers ticker, priority, valuation gap, latest rank, alert count, snapshot freshness, and added date.

Saved views persist:

- view id and watchlist id;
- name;
- filters;
- sorting;
- visible columns;
- lifecycle timestamps;
- schema version.

## Alert Logic

Alert records are generated on read:

- `priceAboveTarget`: market price is above analyst-entered target.
- `priceBelowTarget`: market price is below analyst-entered target.
- `valuationGapAboveThreshold`: intrinsic value gap is at least 25%.
- `rankingStatusChanged`: latest ranking row changed versus the prior run.
- `snapshotStale`: fundamentals snapshot is stale or missing.
- `providerDegraded`: market data provider is degraded or not connected.
- `missingCriticalData`: price, fundamentals snapshot, computed metrics, ranking, or valuation is missing.

Alerts are informational research records only. No notification delivery, advice, or trading action is attached.

Alert lifecycle:

- `acknowledge`: records `acknowledgedAt` and placeholder `acknowledgedBy`.
- `dismiss`: records `dismissedAt` and removes the alert from the active inbox.
- `restore`: clears `dismissedAt` and returns the alert to active or acknowledged state.
- `history`: returns active, acknowledged, and dismissed alert records.

There are no push notifications, delivery preferences, escalation rules, or multi-user ownership semantics in Phase 5B.

## Staleness Model

`GET /api/watchlists/{watchlistId}/staleness` classifies each item across:

- fundamentals snapshot freshness;
- computed metrics snapshot freshness;
- ranking row freshness;
- valuation scenario freshness when available;
- market data freshness/provider state when available.

Item states:

- `fresh`: all tracked dependencies are present and current.
- `stale`: one or more dependencies is older than the stale threshold.
- `missing`: one or more dependencies is unavailable.
- `degraded`: a required provider dependency is degraded or not connected.

The response includes stale reasons, missing dependencies, last refreshed timestamp, max age, component details, and counts. Missing values are not invented.

## Workflow States

Each watchlist item has a manual deterministic workflow state:

- `not_started`
- `monitoring`
- `needs_review`
- `under_review`
- `thesis_ready`
- `archived`

Workflow state is analyst-entered process metadata. It is never inferred as a buy/sell recommendation.

## Watchlist Refresh

`POST /api/watchlists/{watchlistId}/refresh` creates a `watchlist_refresh` job through the existing local job store. The job scope contains:

- `watchlistId`;
- watchlist tickers;
- period;
- ranking strategy;
- `staleOnly`;
- schema version.

The job currently runs synchronously inside the API request. It reuses screener snapshot refresh for normalized fundamentals/computed metrics and ranking refresh for the watchlist ticker subset.

`staleOnly=true` refreshes stale, missing, or degraded items and skips fresh items. Job metadata records classification, skipped/fresh counts, refreshed tickers, and result summaries.

This is local-first orchestration only. Future phases can move the same contract to scheduled jobs, async workers, priority queues, or managed infrastructure.

## Diagnostics

`GET /api/diagnostics/watchlists` reports:

- watchlist store readiness;
- watchlist count;
- item count;
- alert count;
- saved view count;
- active, acknowledged, and dismissed alert counts;
- stale watchlist item count;
- watchlist refresh readiness and job counts;
- failed watchlist refresh count;
- alert store readiness;
- endpoint readiness.

## Limitations

- Alerts are still generated from deterministic rules; persisted history records acknowledgement and dismissal state only.
- Intelligence uses annual snapshots in Phase 5A.
- The service reads the latest Magic Formula ranking only.
- No multi-user ownership, permissions, notifications, or collaboration model exists yet.
- Valuation gaps are informational and depend on saved DCF scenarios plus available market prices.
