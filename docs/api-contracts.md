# API Contracts

External data access stays behind backend provider abstractions. Alpaca remains the market data provider. Financial Modeling Prep (FMP) is the fundamentals provider for company profiles, financial statements, provisional key metrics, and the fundamentals-backed screener slice. The valuation API is platform-owned and calculates transparent DCF outputs from normalized fundamentals, computed metrics, and market data.

Credentials stay backend-only. The frontend talks only to FastAPI contracts and renders `connected`, `degraded`, `not_connected`, or `not_implemented` provider states.

## Base Routes

| Method   | Route                                                                                | Purpose                      | Current State                                                                           |
| -------- | ------------------------------------------------------------------------------------ | ---------------------------- | --------------------------------------------------------------------------------------- |
| `GET`    | `/health`                                                                            | API liveness check           | Returns service metadata                                                                |
| `GET`    | `/api/status`                                                                        | Contract and provider status | Returns provider state for Alpaca, FMP, SEC, and news                                   |
| `GET`    | `/api/diagnostics/market-data`                                                       | Market data diagnostics      | Safe Alpaca readiness, cache TTL, endpoint readiness, and last error/success metadata   |
| `GET`    | `/api/diagnostics/market-data/probe?ticker=AAPL`                                     | Market data smoke test       | Calls market data provider methods through the backend abstraction                      |
| `GET`    | `/api/diagnostics/fundamentals`                                                      | Fundamentals diagnostics     | Safe FMP readiness, period support, endpoint readiness, and last error/success metadata |
| `GET`    | `/api/diagnostics/valuation?ticker=AAPL`                                             | Valuation diagnostics        | DCF engine readiness, scenario persistence status, and assumption validation bounds     |
| `GET`    | `/api/diagnostics/watchlists`                                                        | Watchlist diagnostics        | Watchlist store readiness, item counts, alert counts, and stale item visibility         |
| `GET`    | `/api/securities/search?q=`                                                          | Security search              | Uses Alpaca assets when configured; otherwise empty `not_connected` response            |
| `GET`    | `/api/securities/{ticker}`                                                           | Company overview             | Uses Alpaca asset reference data when configured                                        |
| `GET`    | `/api/securities/{ticker}/snapshot`                                                  | Market snapshot              | Uses Alpaca stock snapshots when configured                                             |
| `GET`    | `/api/fundamentals/{ticker}/profile`                                                 | Company profile              | Uses FMP profile when configured                                                        |
| `GET`    | `/api/fundamentals/{ticker}/income-statement?period=annual&limit=5`                  | Income statement             | Uses canonical annual/quarter rows from FMP                                             |
| `GET`    | `/api/fundamentals/{ticker}/balance-sheet?period=annual&limit=5`                     | Balance sheet                | Uses canonical annual/quarter rows from FMP                                             |
| `GET`    | `/api/fundamentals/{ticker}/cash-flow?period=annual&limit=5`                         | Cash flow statement          | Uses canonical annual/quarter rows from FMP                                             |
| `GET`    | `/api/fundamentals/{ticker}/metrics?period=annual&limit=5`                           | Provider key metrics         | Ingests normalized FMP metrics as provisional provider data                             |
| `GET`    | `/api/fundamentals/{ticker}/computed-metrics?period=annual&limit=5`                  | Computed metrics             | Calculates platform-owned metrics from canonical statements                             |
| `GET`    | `/api/screener?period=annual&limit=25&page=1`                                        | Fundamentals screener        | Reads durable snapshots first, then falls back to provider-backed rows                  |
| `POST`   | `/api/screener/refresh?period=annual`                                                | Screener snapshot refresh    | Synchronously refreshes SQLite snapshots for the controlled universe                    |
| `GET`    | `/api/rankings/magic-formula?period=annual&limit=50`                                 | Magic Formula ranking        | Greenblatt-style ranking using canonical EBIT, enterprise value, and invested capital   |
| `GET`    | `/api/rankings?strategy=magic_formula&period=annual&limit=50&includeIneligible=true` | Strategy ranking             | Deterministic ranking with eligibility status, exclusion reasons, and audit metadata    |
| `POST`   | `/api/rankings/refresh?strategy=magic_formula&period=annual`                         | Ranking refresh workflow     | Creates and executes a local refresh job, then stores run plus workflow metadata        |
| `GET`    | `/api/rankings/refresh-runs?strategy=magic_formula&period=annual`                    | Ranking refresh history      | Recent refresh workflow executions and status metadata                                  |
| `POST`   | `/api/jobs/ranking-refresh?strategy=magic_formula&period=annual`                     | Ranking refresh job          | Creates a SQLite-backed local job and runs it synchronously by default                  |
| `GET`    | `/api/jobs?jobType=ranking_refresh`                                                  | Refresh job list             | Recent local job records with status, scope, timestamps, warnings, and errors           |
| `GET`    | `/api/jobs/{jobId}`                                                                  | Refresh job detail           | One persisted job payload                                                               |
| `GET`    | `/api/jobs/{jobId}/events`                                                           | Refresh job events           | Append-only job event log                                                               |
| `POST`   | `/api/jobs/{jobId}/cancel`                                                           | Cancel refresh job           | Best-effort cancellation for queued jobs only                                           |
| `GET`    | `/api/refresh-policies`                                                              | Refresh policies             | Local policy definitions for ranking/screener refresh orchestration                     |
| `POST`   | `/api/refresh-policies`                                                              | Create refresh policy        | Persists a local-first refresh policy                                                   |
| `GET`    | `/api/refresh-policies/{policyId}`                                                   | Refresh policy detail        | One persisted refresh policy                                                            |
| `PATCH`  | `/api/refresh-policies/{policyId}`                                                   | Update refresh policy        | Updates policy metadata, scope, schedule hint, and stale threshold                      |
| `POST`   | `/api/refresh-policies/{policyId}/enable`                                            | Enable refresh policy        | Marks policy enabled and recalculates next-run hint                                     |
| `POST`   | `/api/refresh-policies/{policyId}/disable`                                           | Disable refresh policy       | Disables policy without deleting history                                                |
| `POST`   | `/api/refresh-policies/{policyId}/run-now`                                           | Run refresh policy now       | Runs one policy through the local job foundation                                        |
| `POST`   | `/api/jobs/run-due-refresh-policies`                                                 | Run due policies             | Manual scheduler simulation for enabled due policies                                    |
| `GET`    | `/api/rankings/runs?strategy=magic_formula&period=annual`                            | Ranking run list             | Recent persisted ranking run summaries                                                  |
| `GET`    | `/api/rankings/runs/{runId}`                                                         | Ranking run detail           | Full persisted ranking run payload                                                      |
| `GET`    | `/api/rankings/runs/{runId}/changes`                                                 | Ranking run changes          | Latest run compared with the prior run for the same strategy and period                 |
| `GET`    | `/api/rankings/screens`                                                              | Saved ranking screens        | Saved deterministic screen definitions                                                  |
| `POST`   | `/api/rankings/screens`                                                              | Create ranking screen        | Persists screen name, strategy, filters, eligibility, sorting, period, and limit        |
| `GET`    | `/api/rankings/screens/{screenId}`                                                   | Ranking screen detail        | One saved ranking screen                                                                |
| `PATCH`  | `/api/rankings/screens/{screenId}`                                                   | Update ranking screen        | Rename or update deterministic screen settings                                          |
| `POST`   | `/api/rankings/screens/{screenId}/duplicate`                                         | Duplicate ranking screen     | Creates an active copy                                                                  |
| `POST`   | `/api/rankings/screens/{screenId}/archive`                                           | Archive ranking screen       | Archives without deleting history                                                       |
| `POST`   | `/api/rankings/screens/{screenId}/restore`                                           | Restore ranking screen       | Restores archived screen                                                                |
| `DELETE` | `/api/rankings/screens/{screenId}`                                                   | Soft delete ranking screen   | Marks screen deleted without hard deletion                                              |
| `GET`    | `/api/diagnostics/rankings`                                                          | Ranking diagnostics          | Ranking readiness, saved screens, refresh workflow, persisted runs, and staleness       |
| `GET`    | `/api/valuation/dcf/{ticker}`                                                        | Latest DCF scenario          | Reads the latest saved scenario or builds a fresh non-persisted scenario                |
| `POST`   | `/api/valuation/dcf/{ticker}`                                                        | Create DCF scenario          | Runs deterministic FCFF DCF with optional user-edited assumptions and persists result   |
| `GET`    | `/api/valuation/dcf/{ticker}/sensitivity`                                            | DCF sensitivity              | Returns WACC, terminal growth, and margin sensitivity grids                             |
| `GET`    | `/api/valuation/dcf/{ticker}/scenarios?limit=10`                                     | Saved DCF scenarios          | Lists saved scenarios newest first                                                      |
| `GET`    | `/api/valuation/dcf/{ticker}/scenarios/{scenarioId}`                                 | Saved DCF scenario           | Returns one persisted scenario or `404`                                                 |
| `POST`   | `/api/valuation/dcf/{ticker}/scenarios/{scenarioId}/versions`                        | New immutable DCF version    | Recalculates a saved scenario and appends a new immutable version                       |
| `PATCH`  | `/api/valuation/dcf/{ticker}/scenarios/{scenarioId}/rename`                          | Rename scenario              | Renames through a new version and audit event                                           |
| `POST`   | `/api/valuation/dcf/{ticker}/scenarios/{scenarioId}/duplicate`                       | Duplicate scenario           | Creates a new child scenario linked to the source scenario                              |
| `POST`   | `/api/valuation/dcf/{ticker}/scenarios/{scenarioId}/archive`                         | Archive scenario             | Soft-archives without deleting history                                                  |
| `POST`   | `/api/valuation/dcf/{ticker}/scenarios/{scenarioId}/restore`                         | Restore scenario             | Restores an archived/deleted scenario to active status                                  |
| `DELETE` | `/api/valuation/dcf/{ticker}/scenarios/{scenarioId}`                                 | Soft delete scenario         | Marks scenario deleted without destroying versions or audit events                      |
| `GET`    | `/api/valuation/dcf/{ticker}/scenarios/{scenarioId}/history`                         | Scenario audit history       | Returns immutable versions and audit events                                             |
| `GET`    | `/api/valuation/dcf/{ticker}/scenarios/{scenarioId}/notes`                           | Scenario notes               | Returns immutable analyst notes attached to scenario versions, assumptions, or warnings |
| `POST`   | `/api/valuation/dcf/{ticker}/scenarios/{scenarioId}/notes`                           | Add scenario note            | Appends an immutable markdown/plain-text note                                           |
| `GET`    | `/api/valuation/dcf/{ticker}/comparison?limit=5`                                     | DCF scenario comparison      | Compares saved scenarios on valuation output and primary assumptions                    |
| `GET`    | `/api/valuation/dcf/{ticker}/compare?leftScenarioId=&rightScenarioId=`               | DCF scenario diff            | Returns side-by-side assumption, output, warning, and valuation delta diffs             |
| `GET`    | `/api/valuation/dcf/{ticker}/export/{scenarioId}`                                    | Export DCF assumptions       | Exports schema/model-versioned editable assumptions as JSON                             |
| `POST`   | `/api/valuation/dcf/{ticker}/import`                                                 | Import DCF assumptions       | Validates schema/model-versioned JSON and creates a new saved scenario                  |
| `GET`    | `/api/watchlists`                                                                    | Watchlist collection         | Lists SQLite-backed active watchlists                                                   |
| `POST`   | `/api/watchlists`                                                                    | Create watchlist             | Persists a named research workspace                                                     |
| `GET`    | `/api/watchlists/{watchlistId}`                                                      | Watchlist detail             | Returns one persisted watchlist and items                                               |
| `PATCH`  | `/api/watchlists/{watchlistId}`                                                      | Update watchlist             | Renames or updates description                                                          |
| `POST`   | `/api/watchlists/{watchlistId}/archive`                                              | Archive watchlist            | Archives without hard deletion                                                          |
| `POST`   | `/api/watchlists/{watchlistId}/restore`                                              | Restore watchlist            | Restores archived/deleted watchlist to active                                           |
| `DELETE` | `/api/watchlists/{watchlistId}`                                                      | Soft delete watchlist        | Marks watchlist deleted without destroying metadata                                     |
| `POST`   | `/api/watchlists/{watchlistId}/items`                                                | Add ticker to watchlist      | Persists ticker, notes, tags, target price, status, priority, and workflow state        |
| `PATCH`  | `/api/watchlists/{watchlistId}/items/{ticker}`                                       | Update watchlist item        | Updates analyst-entered item metadata and workflow state                                |
| `DELETE` | `/api/watchlists/{watchlistId}/items/{ticker}`                                       | Remove ticker from watchlist | Removes the ticker from the active item set                                             |
| `GET`    | `/api/watchlists/{watchlistId}/intelligence?filters=&sort=&viewId=`                 | Watchlist intelligence       | Aggregates market, snapshot, ranking, valuation, and quality context                    |
| `POST`   | `/api/watchlists/{watchlistId}/refresh?period=annual&staleOnly=true`                | Watchlist refresh            | Creates and runs a local watchlist-scoped refresh job                                   |
| `GET`    | `/api/watchlists/{watchlistId}/refresh-history`                                     | Watchlist refresh history    | Lists local refresh jobs scoped to one watchlist                                        |
| `GET`    | `/api/watchlists/{watchlistId}/staleness`                                           | Watchlist staleness          | Returns item-level freshness, missing dependencies, and stale reasons                   |
| `GET`    | `/api/watchlists/{watchlistId}/views`                                               | Saved watchlist views        | Lists saved deterministic filters, sorting, and visible columns                         |
| `POST`   | `/api/watchlists/{watchlistId}/views`                                               | Create watchlist view        | Persists a reusable watchlist view                                                      |
| `GET`    | `/api/watchlists/{watchlistId}/views/{viewId}`                                      | Watchlist view detail        | Returns one saved view                                                                  |
| `PATCH`  | `/api/watchlists/{watchlistId}/views/{viewId}`                                      | Update watchlist view        | Updates name, filters, sorting, or visible columns                                      |
| `POST`   | `/api/watchlists/{watchlistId}/views/{viewId}/duplicate`                            | Duplicate watchlist view     | Copies a saved view and preserves parent provenance                                     |
| `POST`   | `/api/watchlists/{watchlistId}/views/{viewId}/archive`                              | Archive watchlist view       | Archives a view without hard deletion                                                   |
| `POST`   | `/api/watchlists/{watchlistId}/views/{viewId}/restore`                              | Restore watchlist view       | Restores archived/deleted view to active                                                |
| `DELETE` | `/api/watchlists/{watchlistId}/views/{viewId}`                                      | Soft delete watchlist view   | Marks a view deleted without destroying metadata                                        |
| `GET`    | `/api/watchlists/{watchlistId}/alerts?includeDismissed=false`                       | Watchlist alerts             | Returns active and acknowledged deterministic alert records                             |
| `GET`    | `/api/watchlists/{watchlistId}/alerts/history`                                      | Watchlist alert history      | Returns active, acknowledged, and dismissed alert records                               |
| `POST`   | `/api/watchlists/{watchlistId}/alerts/{alertId}/acknowledge`                        | Acknowledge alert            | Stamps `acknowledgedAt` and placeholder `acknowledgedBy`                                |
| `POST`   | `/api/watchlists/{watchlistId}/alerts/{alertId}/dismiss`                            | Dismiss alert                | Hides an alert from the active inbox while retaining history                            |
| `POST`   | `/api/watchlists/{watchlistId}/alerts/{alertId}/restore`                            | Restore alert                | Restores a dismissed alert to active or acknowledged state                              |

## Shared Types

The frontend consumes shared TypeScript contracts from `packages/types`.

Core provider/system types:

- `ApiStatus`
- `ProviderConnectionStatus`
- `MarketDataDiagnostics`
- `MarketDataProbe`
- `FundamentalsDiagnostics`

Market data types:

- `Security`
- `SecuritySearchResult`
- `CompanyOverview`
- `MarketSnapshot`

Fundamentals types:

- `FundamentalsPeriod = annual | quarter | ttm`
- `CompanyProfile`
- `IncomeStatement`
- `BalanceSheet`
- `CashFlowStatement`
- `KeyMetrics`
- `ComputedMetrics`

Screener types:

- `ScreenerQuery`
- `ScreenerFilter`
- `ScreenerSort`
- `ScreenerResultRow`
- `ScreenerResponse`
- `SnapshotMetadata`
- `ScreenerRefreshResult`

Ranking types:

- `RankingStrategy`
- `RankingInput`
- `RankingResultRow`
- `RankingResponse`
- `RankingQualityFlags`
- `MagicFormulaInputs`
- `MagicFormulaResult`
- `RankingDiagnostics`
- `RankingEligibilitySettings`
- `RankingRun`
- `RankingRunSummary`
- `RankingRunChanges`
- `SavedRankingScreen`
- `RankingRefreshRun`
- `RefreshJob`
- `RefreshJobEvent`
- `RefreshJobStoreDiagnostics`
- `RefreshPolicy`
- `RefreshPolicyRunResult`
- `DueRefreshPolicyRunResult`
- `RefreshPolicyStoreDiagnostics`

Valuation types:

- `ValuationScenario`
- `DiscountRateAssumptions`
- `GrowthAssumptions`
- `MarginAssumptions`
- `ReinvestmentAssumptions`
- `ShareCountAssumptions`
- `NetDebtAssumptions`
- `TerminalValueAssumptions`
- `DCFProjectionYear`
- `DCFResult`
- `SensitivityGrid`
- `ValuationQualityFlags`
- `ValuationWarning`
- `ValuationModelMetadata`
- `ValuationScenarioSummary`
- `ValuationScenarioCollection`
- `ValuationScenarioComparison`
- `ValuationScenarioDiff`
- `ValuationScenarioHistory`
- `ValuationAuditEvent`
- `ValuationNote`
- `ValuationNotesResult`
- `ValuationAssumptionExport`
- `ValuationReproducibility`
- `SensitivityVisualization`
- `ValuationDiagnostics`

Watchlist types:

- `Watchlist`
- `WatchlistItem`
- `WatchlistCollection`
- `WatchlistIntelligence`
- `WatchlistIntelligenceItem`
- `WatchlistFilter`
- `WatchlistSort`
- `WatchlistWorkflowState`
- `WatchlistItemStaleness`
- `WatchlistStalenessResult`
- `WatchlistRefreshHistory`
- `SavedWatchlistView`
- `SavedWatchlistViewCollection`
- `WatchlistAlert`
- `WatchlistAlertsResult`
- `WatchlistAlertHistory`
- `WatchlistDiagnostics`
- `WatchlistStoreDiagnostics`

Provider status uses:

- `connected`
- `not_connected`
- `degraded`
- `not_implemented`

## Fundamentals Contracts

Statement and metric routes accept:

- `period`: `annual`, `quarter`, or `ttm`; default `annual`
- `limit`: `1` to `20`; default `5`

Phase 2A supports `annual` and `quarter` through FMP. `ttm` is contract-ready and returns `provider.state = "not_implemented"` until a future phase wires a normalized TTM calculation or source endpoint.

Every normalized profile/financial row includes source metadata:

- `provider`
- `fetchedAt`
- `sourceSymbol`
- `currency`
- `fiscalYear`
- `fiscalPeriod`
- `qualityFlags`

Canonical field names are used internally. Raw FMP field names such as `weightedAverageShsOutDil`, `totalStockholdersEquity`, `capitalExpenditure`, `roic`, and `peRatio` should not be exposed to frontend contracts.

Examples of canonical names:

- Income statement: `revenue`, `grossProfit`, `operatingIncome`, `ebitda`, `netIncome`, `epsDiluted`, `sharesDiluted`
- Balance sheet: `cashAndEquivalents`, `totalAssets`, `totalLiabilities`, `totalDebt`, `shareholdersEquity`
- Cash flow: `operatingCashFlow`, `capitalExpenditures`, `freeCashFlow`, `dividendsPaid`, `shareRepurchases`
- Metrics: `revenuePerShare`, `freeCashFlowPerShare`, `returnOnInvestedCapital`, `debtToEquity`, `enterpriseValueToEbitda`

`qualityFlags` carries normalization and calculation audit hints. It is not an investment conclusion.

## Fundamentals Cache

Phase 2C adds backend-only in-memory TTL caching for successful fundamentals responses. Provider errors and degraded responses are not cached.

Cache keys are normalized by endpoint, ticker, period, and limit where applicable:

- company profile: ticker
- income statement: ticker, period, limit
- balance sheet: ticker, period, limit
- cash flow: ticker, period, limit
- key metrics: ticker, period, limit
- computed metrics: ticker, period, limit

TTL environment variables:

- `FUNDAMENTALS_PROFILE_CACHE_TTL_SECONDS`, default `3600`
- `FUNDAMENTALS_INCOME_STATEMENT_CACHE_TTL_SECONDS`, default `3600`
- `FUNDAMENTALS_BALANCE_SHEET_CACHE_TTL_SECONDS`, default `3600`
- `FUNDAMENTALS_CASH_FLOW_CACHE_TTL_SECONDS`, default `3600`
- `FUNDAMENTALS_KEY_METRICS_CACHE_TTL_SECONDS`, default `3600`
- `COMPUTED_METRICS_CACHE_TTL_SECONDS`, default `900`

Setting a TTL to `0` disables that cache. This is not durable persistence and should be replaced or supplemented by Redis/PostgreSQL in later ingestion phases.

## Quality Flags

Current flags include:

- `missing_core_field:{field}` for absent canonical statement fields.
- `currency_missing` when a statement row lacks currency.
- `fiscal_year_missing` when fiscal year cannot be normalized.
- `shares_missing` when diluted shares are unavailable for per-share metrics.
- `zero_denominator:{metric}` when a metric cannot be divided safely.
- `negative_denominator:{metric}` when a ratio is computed over a negative denominator.
- `missing_input:{metric}` when a computed metric lacks required inputs.
- `missing_prior_period:{metric}` when growth cannot be computed.
- `zero_prior_period:{metric}` and `negative_prior_period:{metric}` for growth denominators.
- `currency_mismatch` when statements feeding a computed row disagree on currency.
- `invested_capital_unavailable` when invested capital cannot be calculated.
- `negative_invested_capital` when the invested capital proxy is negative.
- `stale_provider_response` when source fetched timestamps are detectably stale.
- `provider_anomaly:{reason}` for malformed provider-normalized rows.

## Provider Adapter Design

Market data access is isolated behind `apps/api/app/services/market_data/provider.py`.

The `MarketDataProvider` protocol defines:

- `search_securities(query)`
- `get_security(ticker)`
- `get_market_snapshot(ticker)`

Fundamentals access is isolated behind `apps/api/app/services/fundamentals/provider.py`.

The `FundamentalsProvider` protocol defines:

- `provider_status()`
- `get_company_profile(ticker)`
- `get_income_statement(ticker, period, limit)`
- `get_balance_sheet(ticker, period, limit)`
- `get_cash_flow_statement(ticker, period, limit)`
- `get_key_metrics(ticker, period, limit)`

Routes depend on provider factories rather than constructing provider-shaped responses inline. This keeps contracts stable while providers move from not connected, to live integration, to durable ingestion later.

## Alpaca Behavior

`AlpacaMarketDataProvider` is selected only when both backend env vars are present:

- `ALPACA_API_KEY`
- `ALPACA_SECRET_KEY`

Optional backend-only URL overrides:

- `ALPACA_BASE_URL`, default `https://paper-api.alpaca.markets`
- `ALPACA_DATA_BASE_URL`, default `https://data.alpaca.markets`

Alpaca is used for active US equity asset lookup and stock snapshots. It is not used for trading, fundamentals, SEC filings, valuation, AI/RAG, or persistence.

## FMP Behavior

`FinancialModelingPrepProvider` is selected only when `FMP_API_KEY` is present.

Optional backend-only URL override:

- `FMP_BASE_URL`, default `https://financialmodelingprep.com/stable`

Phase 2A uses FMP stable endpoints:

- `/profile?symbol={ticker}`
- `/income-statement?symbol={ticker}&period={annual|quarter}&limit={limit}`
- `/balance-sheet-statement?symbol={ticker}&period={annual|quarter}&limit={limit}`
- `/cash-flow-statement?symbol={ticker}&period={annual|quarter}&limit={limit}`
- `/key-metrics?symbol={ticker}&period={annual|quarter}&limit={limit}`

FMP key metrics are ingested as provisional provider metrics only. They are not the platform's final truth. Platform-owned metrics are calculated from canonical statements and tagged with a calculation engine version.

## Watchlist Intelligence Contracts

Phase 5B makes watchlists persistent local research workspaces with saved views and auditable alert lifecycle history. Watchlists, views, and alert events are stored in SQLite through the repository abstraction and remain separate from provider credentials.

Watchlist item analyst inputs:

- ticker;
- company name when manually provided or discoverable from persisted snapshots;
- notes;
- tags;
- target price;
- thesis status;
- priority;
- deterministic research workflow state: `not_started`, `monitoring`, `needs_review`, `under_review`, `thesis_ready`, or `archived`.

`GET /api/watchlists/{watchlistId}/intelligence` aggregates deterministic context per ticker and accepts optional JSON query params:

- `filters`: array of `WatchlistFilter`.
- `sort`: one `WatchlistSort`.
- `viewId`: saved view id; saved view filters/sorting/visible columns are used when explicit filters or sort are not supplied.

Supported filter fields are `ticker`, `tags`, `thesisStatus`, `priority`, `workflowState`, `valuationGap`, `rankingStatus`, `alertType`, `staleSnapshot`, `missingCriticalData`, and `providerDegraded`.

Supported sort fields are `ticker`, `priority`, `valuationGap`, `latestRank`, `alertCount`, `snapshotFreshness`, and `addedAt`.

The intelligence payload includes:

- latest market snapshot from the backend market data provider;
- annual fundamentals and screener snapshot freshness;
- latest computed metrics snapshot when present;
- latest Magic Formula ranking row and eligibility state when a ranking run exists;
- latest saved DCF scenario summary when present;
- item staleness summary;
- price versus intrinsic value gap when both price and intrinsic value are available;
- quality flags and rule-based alerts.

Missing data stays `null` or `unavailable`. The API does not fabricate prices, rankings, valuation outputs, or financial analysis.

Alert types:

- `priceAboveTarget`
- `priceBelowTarget`
- `valuationGapAboveThreshold`
- `rankingStatusChanged`
- `snapshotStale`
- `providerDegraded`
- `missingCriticalData`

Alerts are deterministic research records only. They are not push notifications, recommendations, portfolio instructions, or trading signals.

Alert lifecycle:

- Generated alerts are upserted into local alert history using deterministic alert ids.
- `acknowledge` records `acknowledgedAt` and a placeholder `acknowledgedBy`.
- `dismiss` records `dismissedAt` and removes the alert from the active inbox.
- `restore` clears `dismissedAt` and returns the alert to active or acknowledged status.
- No notification delivery exists in Phase 5B.

Saved view lifecycle:

- Views persist `name`, `filters`, `sorting`, `visibleColumns`, `createdAt`, `updatedAt`, `archivedAt`, `deletedAt`, and `schemaVersion`.
- Archive and delete are soft lifecycle states for local auditability.
- Duplicated views carry `parentViewId`.

Watchlist staleness:

- `fundamentals`: screener/fundamentals snapshot freshness.
- `computedMetrics`: computed metric snapshot freshness.
- `ranking`: latest ranking row freshness.
- `valuation`: latest saved valuation scenario freshness when available.
- `marketData`: market snapshot provider/as-of freshness when available.

Item state is `degraded` if a provider dependency is degraded or not connected, `missing` if any required dependency is unavailable, `stale` if any dependency exceeds the stale threshold, and `fresh` only when all tracked dependencies are current.

Watchlist refresh:

- `POST /api/watchlists/{watchlistId}/refresh` creates a `watchlist_refresh` job in the existing `refresh_jobs` table.
- The job scope stores `watchlistId`, watchlist tickers, period, strategy, `staleOnly`, and `schemaVersion`.
- The current implementation runs synchronously inside the API process, then stores job events and compact result metadata.
- Refresh reuses screener snapshot refresh and ranking refresh logic for the watchlist ticker set.
- `staleOnly=true` refreshes only items classified as stale, missing, or degraded; fresh items are skipped.
- This is not a notification system, recommendation engine, or trading workflow.

## Platform-Owned Computed Metrics

`GET /api/fundamentals/{ticker}/computed-metrics` computes metrics from normalized canonical statements. It does not use raw FMP field names and does not trust FMP key metrics as final truth.

Inputs:

- `IncomeStatement`
- `BalanceSheet`
- `CashFlowStatement`

Implemented formula definitions:

- `grossMargin = grossProfit / revenue`
- `operatingMargin = operatingIncome / revenue`
- `netMargin = netIncome / revenue`
- `freeCashFlowMargin = freeCashFlow / revenue`
- `revenueGrowthYoY = (currentRevenue - priorRevenue) / abs(priorRevenue)`
- `netIncomeGrowthYoY = (currentNetIncome - priorNetIncome) / abs(priorNetIncome)`
- `operatingIncomeGrowthYoY = (currentOperatingIncome - priorOperatingIncome) / abs(priorOperatingIncome)`
- `freeCashFlowGrowthYoY = (currentFreeCashFlow - priorFreeCashFlow) / abs(priorFreeCashFlow)`
- `returnOnEquity = netIncome / shareholdersEquity`
- `debtToEquity = totalDebt / shareholdersEquity`
- `currentRatio = currentAssets / currentLiabilities`
- `freeCashFlowPerShare = freeCashFlow / sharesDiluted`
- `bookValuePerShare = shareholdersEquity / sharesDiluted`
- `earningsPerShareDiluted = netIncome / sharesDiluted`
- `investedCapital = totalDebt + shareholdersEquity - cashAndEquivalents`
- `returnOnInvestedCapital = operatingIncome / investedCapital`

Safe calculation rules:

- Missing inputs return `null`.
- Division by zero returns `null`.
- Negative denominators can still produce a value, but add a quality flag.
- Annual growth compares with the prior annual row.
- Quarterly growth compares with the matching prior-year fiscal quarter when available.
- TTM returns `not_implemented` until a future TTM layer is added.

Known limitations:

- ROE uses ending-period shareholders' equity, not average equity.
- ROIC uses operating income as a conservative operating proxy until tax/NOPAT normalization is implemented.
- Computed rows include `calculationEngine = platform-normalized-metrics-v1`.

## Ranking Engine

`GET /api/rankings/magic-formula?period=annual&limit=50` returns a deterministic Magic Formula ranking.

`GET /api/rankings?strategy=magic_formula|quality|value|growth|profitability&period=annual|quarter&limit=50&includeIneligible=true` returns deterministic strategy rankings.

Supported strategies:

- `magic_formula`
- `quality`
- `value`
- `growth`
- `profitability`

Magic Formula methodology:

- `earningsYield = EBIT / enterpriseValue`
- `returnOnCapital = EBIT / investedCapital`
- `combinedRankScore = earningsYieldRank + returnOnCapitalRank`

Canonical inputs:

- `EBIT` uses normalized `operatingIncome`.
- `enterpriseValue` uses market data enterprise value when available, otherwise `marketCap + totalDebt - cashAndEquivalents`.
- `investedCapital` uses platform-owned computed metrics when available, otherwise `totalDebt + shareholdersEquity - cashAndEquivalents`.

Missing data behavior:

- Missing EBIT, market cap, balance sheet, enterprise value, or invested capital returns `null` for affected formulas.
- Rows with missing Magic Formula inputs remain in the response with `rank = null`.
- Missing input reasons are exposed in `qualityFlags`; no placeholder values are invented.

Eligibility behavior:

- Rows are classified as `eligible`, `ineligible`, or `unranked_missing_data`.
- Default rules require positive enterprise value, positive invested capital, positive EBIT for Magic Formula, and no missing critical inputs.
- Configurable rule fields include minimum market cap, minimum price, optional minimum volume, and transparent sector exclusions for financials/utilities.
- Ineligible or missing-data rows are never silently discarded. They remain in responses when `includeIneligible=true` with `eligibilityReasons`.
- Ranking row audit metadata exposes input values used, formula components, snapshot metadata, `computedAt`, and `rankingEngineVersion`.

Basic strategy methodology:

- `quality`: transparent composite of ROIC, ROE, and FCF margin.
- `value`: inverse P/E, P/B, and P/S provider-reference ratios.
- `growth`: revenue growth YoY.
- `profitability`: gross, operating, net, and FCF margins.

Rankings are not recommendations. They are deterministic research screens over the controlled universe and should not be interpreted as buy/sell signals.

Ranking persistence:

- `POST /api/rankings/refresh` now creates a local `ranking_refresh` job and executes it synchronously in Phase 4D. The response is job-shaped and includes the legacy refresh workflow result under `result` plus compact ids under `resultMetadata`.
- `POST /api/jobs/ranking-refresh` exposes the same job runner directly. Passing `run=false` creates a queued job without executing it.
- Persisted run payloads include `schemaVersion`, strategy, period, universe, eligibility settings, ranking results, `computedAt`, and `rankingEngineVersion`.
- `ranking_runs` stores run-level metadata and full run payloads.
- `ranking_row_snapshots` stores one row snapshot per ticker per run.
- `ranking_refresh_runs` stores refresh execution metadata including `queued`, `running`, `completed`, or `failed` status, timestamps, duration, scope, warnings, and errors.
- `refresh_jobs` stores local job records with `jobId`, `jobType`, status, scope, payload, timestamps, duration, warnings, errors, result metadata, and `schemaVersion`.
- `refresh_job_events` stores append-only events such as `job_created`, `job_started`, `ranking_refresh_completed`, `job_completed`, `job_failed`, and `job_cancelled`.
- `GET /api/rankings/runs/{runId}/changes` compares a run with the immediately prior run for the same strategy and period, exposing rank change, score change, eligibility change, new entrants, and dropped rows.
- The Phase 4D runner is not a distributed queue. Execution remains synchronous inside the API process, but the API is job-shaped so later phases can move execution to a worker, scheduler, Redis/Celery-style queue, or another worker service without changing ranking contracts.

Refresh job model:

- Status values are `queued`, `running`, `completed`, `failed`, and `cancelled`.
- Job payloads and scopes are stored as JSON for local-first development.
- Events are append-only; prior events are never edited.
- Cancellation is best-effort and currently only applies before a queued job starts running.

Refresh policies:

- `refresh_policies` stores local orchestration policies for ranking and screener refresh.
- Policy fields include `policyId`, name, target, strategy, period, scope, `staleAfterSeconds`, enabled state, `scheduleHint`, `lastRunAt`, `nextRunHint`, timestamps, and `schemaVersion`.
- Schedule hints are advisory: `manual`, `stale_only`, `hourly`, `daily`, `weekly`, and `always`.
- `POST /api/jobs/run-due-refresh-policies` is a manual scheduler simulation. It inspects enabled policies, checks `nextRunHint`/`lastRunAt`/`staleAfterSeconds`, creates jobs for due policies, and runs them synchronously.
- Stale-only refresh classifies tickers as `fresh`, `stale`, or `missing` from screener row snapshot freshness. Fresh rows are skipped. Stale and missing rows are refreshed/re-ranked through the job runner.
- Policy-triggered jobs store classification metadata in `resultMetadata.staleOnly`, including fresh, stale, missing, skipped, and refreshed counts.
- This is local-first orchestration, not a production scheduler. Future phases should move the same contracts to cron, worker, Redis/Celery, or Supabase scheduled jobs.

Saved ranking screens:

- `ranking_saved_screens` stores reusable deterministic screen definitions.
- Saved screens include name, strategy, filters, eligibility settings, sorting, period, limit, status, `createdAt`, `updatedAt`, and `schemaVersion`.
- Lifecycle states are `active`, `archived`, and `deleted`.
- Archive, restore, duplicate, and soft delete preserve history and avoid hard deletion in Phase 4C.

## Statement Audit UI

The company page includes a compact statement audit section for annual and quarterly periods. It shows only core canonical line items, source metadata, and quality flags for the latest normalized income statement, balance sheet, and cash flow rows.

The audit section exists to make statement normalization inspectable before DCF, Magic Formula, or screening logic depends on the data.

## Snapshot Persistence

Phase 2E adds lightweight local persistence for the controlled screener universe and normalized snapshots.

Configuration:

- `VALUE_TERMINAL_DB_PATH`, default `apps/api/data/value_terminal.db`
- `SNAPSHOT_STALE_AFTER_SECONDS`, default `86400`

The implementation intentionally uses Python stdlib `sqlite3`, a repository abstraction, and JSON payloads. It does not use SQLAlchemy, a heavy ORM, event sourcing, a distributed async job system, or a migration framework.

Persisted snapshot payloads must include:

- `schemaVersion`, currently `1`
- `provenance.provider`
- `provenance.providerVersion`
- `provenance.fetchedAt`
- `provenance.sourceSymbol`

Computed metric and screener row snapshots also include:

- `computedFrom`, with source fiscal years and fiscal periods for income statement, balance sheet, cash flow, and key metrics where available
- `computedAt`

SQLite tables:

- `securities_universe`
- `fundamentals_snapshots`
- `computed_metric_snapshots`
- `screener_row_snapshots`
- `snapshot_refresh_runs`
- `valuation_scenarios`
- `ranking_runs`
- `ranking_row_snapshots`
- `ranking_saved_screens`
- `ranking_refresh_runs`
- `refresh_jobs`
- `refresh_job_events`
- `refresh_policies`

## Fundamentals Screener

`GET /api/screener` is deterministic, backend-only, and does not use AI ranking, Magic Formula, valuation ranking, or a global security master.

Query parameters:

- `period`: `annual` or `quarter`; default `annual`
- `filters`: JSON object or array of `ScreenerFilter`
- `sort`: JSON object or `field:direction` shorthand
- `page`: default `1`
- `limit`: default `25`, maximum `100`

Supported filter operators:

- `gt`
- `gte`
- `lt`
- `lte`
- `eq`
- `between`

Supported metric fields:

- `marketCap`
- `revenue`
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
- `price`
- `peRatio`
- `pbRatio`
- `psRatio`

Rows include `ticker`, `companyName`, `currency`, `metrics`, `source`, `provider`, `snapshot`, and `qualityFlags`. Missing metrics remain `null` and do not pass metric filters. Sorting places missing values last.

Snapshot behavior:

- Persisted rows are read first.
- Stale persisted rows are still used and marked with `snapshot.isStale = true`.
- Missing rows fall back to provider-backed fetches when the provider is connected.
- Provider fallback rows are not persisted by `GET /api/screener`.
- Durable writes happen through `POST /api/screener/refresh`.

Phase 2D universe:

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

Metric source policy:

- Margins, growth, ROE, ROIC, current ratio, debt/equity, FCF/share, and book value/share come from platform-owned computed metrics.
- `marketCap`, `price`, and `revenue` come from normalized profile or statement rows.
- `peRatio`, `pbRatio`, and `psRatio` currently use normalized FMP key metrics as provider reference metrics and are flagged with `provider_reference_metric:{field}`. They are not final platform truth.

Refresh behavior:

- `POST /api/screener/refresh?period=annual|quarter` refreshes the controlled universe synchronously.
- It writes universe rows, normalized fundamentals snapshots, computed metric snapshots, screener row snapshots, and refresh-run metadata.
- Screener refresh remains synchronous. Ranking refresh has a Phase 4D job-shaped API, but still executes synchronously inside the API process. Future phases should move both toward async refresh workers, scheduled refreshes, incremental refreshes, priority refreshes, and queue-based ingestion.

Known limitations:

- This is not a production-grade global screener.
- SQLite is a local development snapshot store, not the future production database.
- There is no ranking model, Magic Formula calculation, or intrinsic-value-backed screener ranking.
- Provider fallback is still request-time for missing rows only.

## DCF Valuation

`GET /api/valuation/dcf/{ticker}` returns the latest saved DCF scenario when one exists. If no scenario has been saved, it builds a fresh non-persisted base case from current normalized inputs.

`POST /api/valuation/dcf/{ticker}` accepts optional assumption overrides and persists the resulting scenario:

```json
{
  "scenarioName": "Base case",
  "discountRate": {
    "wacc": 0.09,
    "taxRate": 0.25
  },
  "growth": {
    "revenueGrowthRate": 0.05
  },
  "margin": {
    "operatingMargin": 0.25
  },
  "reinvestment": {
    "reinvestmentRate": 0.1
  },
  "terminalValue": {
    "terminalGrowthRate": 0.025
  }
}
```

The response is a `DCFResult` with:

- `schemaVersion`
- saved `scenario` assumptions and assumption quality flags
- immutable scenario metadata: `versionNumber`, `versionId`, `priorVersionId`, `parentScenarioId`, `status`, and `modelVersion`
- `modelMetadata`: `dcfEngineVersion`, `valuationMethodologyVersion`, `modelVersion`, and `computationTimestamp`
- `reproducibility`: statement references, computed metric references, market data references, engine versions, sensitivity configuration, and timestamp chain
- explicit `projections`
- `sensitivity` grids
- `sensitivityVisualization` heatmap metadata for frontend rendering
- `baseFinancials`
- `terminalValue`, `enterpriseValue`, `equityValue`, and `intrinsicValuePerShare`
- `warnings`
- formula strings
- provider state and valuation quality flags

DCF formulas:

- `revenue[t] = revenue[t-1] * (1 + revenueGrowthRate)`
- `operatingIncome[t] = revenue[t] * operatingMargin`
- `nopat[t] = operatingIncome[t] * (1 - taxRate)`
- `reinvestment[t] = max(revenue[t] - revenue[t-1], 0) * reinvestmentRate`
- `fcff[t] = nopat[t] - reinvestment[t]`
- `sharesDiluted[t] = sharesDiluted[t-1] * (1 + dilutedShareGrowthRate + stockBasedCompensationDilutionRate - buybackRate)`
- `presentValueFcff[t] = fcff[t] / (1 + wacc)^t`
- `terminalValue = fcff[final] * (1 + terminalGrowthRate) / (wacc - terminalGrowthRate)`
- `enterpriseValue = sum(presentValueFcff) + presentValueTerminalValue`
- `netDebt = totalDebt + leaseDebt + preferredEquity + minorityInterest - excessCash`
- `equityValue = enterpriseValue - netDebt`
- `intrinsicValuePerShare = equityValue / projectedSharesDiluted`

Assumption policy:

- No AI-generated assumptions.
- Historical assumptions are derived from normalized computed metrics or canonical statements when possible.
- Macro inputs such as risk-free rate, equity risk premium, and debt cost start as editable manual defaults and carry `manual_review_required` quality flags.
- User overrides are preserved as `source = "user_override"`.

Sensitivity:

- WACC versus terminal growth.
- Operating margin versus WACC.
- Operating margin versus terminal growth.

This valuation API is not a trading system, recommendation engine, or automatic buy/sell signal.

Scenario management:

- `GET /api/valuation/dcf/{ticker}/scenarios` lists active saved scenarios newest first. `includeArchived=true` and `includeDeleted=true` expose soft-archived records.
- `GET /api/valuation/dcf/{ticker}/scenarios/{scenarioId}` loads a specific persisted scenario.
- `POST /api/valuation/dcf/{ticker}/scenarios/{scenarioId}/versions` creates a new immutable version for an existing scenario.
- `PATCH /api/valuation/dcf/{ticker}/scenarios/{scenarioId}/rename` renames through a new immutable version.
- `POST /api/valuation/dcf/{ticker}/scenarios/{scenarioId}/duplicate` creates a child scenario with `parentScenarioId`.
- `POST /api/valuation/dcf/{ticker}/scenarios/{scenarioId}/archive`, `POST /restore`, and `DELETE /scenarios/{scenarioId}` change lifecycle status without deleting history.
- `GET /api/valuation/dcf/{ticker}/scenarios/{scenarioId}/history` returns immutable versions and audit events.
- `GET /api/valuation/dcf/{ticker}/scenarios/{scenarioId}/notes` returns immutable analyst notes.
- `POST /api/valuation/dcf/{ticker}/scenarios/{scenarioId}/notes` appends an immutable note attached to the current scenario version, an assumption path, or a warning code.
- `GET /api/valuation/dcf/{ticker}/comparison` returns a compact comparison of saved scenarios by intrinsic value/share, enterprise value, equity value, revenue growth, operating margin, WACC, tax rate, reinvestment rate, terminal growth, and quality flags.
- `GET /api/valuation/dcf/{ticker}/compare?leftScenarioId=&rightScenarioId=` returns arbitrary scenario or version diffs. Optional `leftVersionId` and `rightVersionId` compare immutable historical versions instead of latest scenario payloads.
- `GET /api/valuation/dcf/{ticker}/export/{scenarioId}` returns editable assumptions with `schemaVersion`, `modelVersion`, source scenario summary, warnings, and export timestamp.
- `POST /api/valuation/dcf/{ticker}/import` accepts the same export shape, validates `schemaVersion = 1` and a present `modelVersion`, and creates a new saved DCF scenario.
- Scenario names are analyst labels only; labels do not change calculations.

Scenario diff semantics:

- `assumptionDiffs` compare editable assumption paths such as `growth.revenueGrowthRate`.
- `outputDiffs` compare valuation outputs such as `intrinsicValuePerShare`, `enterpriseValue`, `equityValue`, `netDebt`, and projected shares.
- `warningDiffs` returns warnings added, removed, and shared on the right scenario versus the left scenario.
- `valuationDelta` summarizes output deltas and percent deltas. It is descriptive only and is not a ranking signal.

Import/export safety:

- Exports do not contain provider credentials.
- Imports create a new scenario instead of mutating an existing one.
- Unsupported schema versions are rejected.
- Imported values still pass through the normal deterministic DCF engine, assumption validation, quality flags, warnings, and persistence.

Reproducibility metadata:

- `statementSnapshotReferences` records the latest normalized income statement, balance sheet, and cash flow references used by the model.
- `metricSnapshotsUsed` records platform-computed metrics used for historical assumption derivation.
- `marketDataSnapshotReference` records the backend market snapshot reference.
- `valuationEngineVersions` records DCF and methodology versions.
- `sensitivityConfiguration` records row/column variables and values used to generate matrices.
- `calculationTimestampChain` records materials load, assumption build, and valuation calculation timestamps.

Analyst notes:

- Notes are append-only payloads in `valuation_notes`.
- Notes attach to a scenario version, an assumption path, or a warning code.
- Notes are immutable historical attachments; editing/deleting notes is intentionally out of scope for Phase 3D.

Immutable versioning:

- Every persisted scenario starts at `versionNumber = 1`.
- Every scenario edit, rename, archive, restore, or soft delete appends a new row in `valuation_scenario_versions`.
- The current `valuation_scenarios` row is only the latest pointer and workflow state.
- Prior version payloads are not overwritten.
- Audit events record `changeType`, `fieldPath`, `previousValue`, `newValue`, timestamp, version id, and version number.

DCF hardening:

- Assumption values are checked against explicit bounds.
- Out-of-range assumptions add quality flags such as `out_of_range:revenueGrowthRate`.
- Invalid terminal spreads add `invalid_terminal_spread:wacc_lte_terminal_growth` and return `null` terminal value.
- Debt/equity weight mismatches add `capital_weight_sum_mismatch`.
- Warnings cover terminal value dominance, terminal growth above GDP proxy, WACC/terminal spread issues, unrealistic operating margins, negative reinvestment, ROIC/WACC inconsistency, projection instability, and missing diluted share assumptions.
- Scenario diagnostics expose configured bounds, warning rules, repository health, orphaned version count, model version distribution, stale scenario count, note count, and reproducibility completeness through `/api/diagnostics/valuation`.

## Error And Fallback Behavior

Missing credentials select safe not-connected providers. Provider HTTP errors, timeouts, malformed payloads, or JSON errors return degraded provider metadata without crashing routes.

Responses keep the same contract shape and include:

- `provider.state`
- `provider.message`
- `provider.requiredEnvironmentVariables`
- `provider.lastSuccessfulCallAt`
- `provider.lastErrorMessage`

Secrets must never appear in API responses, diagnostics, or frontend-rendered error text.

## Frontend Handling

The web app uses `apps/web/lib/api/client.ts` as the typed API boundary. It returns either:

- `{ ok: true, data, provider? }`
- `{ ok: false, error }`

Pages render loading, API failure, provider status, empty, not-connected, degraded, and not-implemented states without inventing financial values.

## Credential Boundary

No provider key may use `NEXT_PUBLIC_*`. Browser code must not call Alpaca or FMP directly. FastAPI owns credentials, provider selection, normalization, error handling, and observability.

## Non-Goals For Current Scope

- No trading or order execution.
- No AI, RAG, or agents.
- No AI-generated valuation assumptions.
- No automatic buy/sell recommendations.
- No SEC filing parser.
- No production distributed queue or notification delivery.
- No SQLAlchemy, heavy ORM, or migration framework.
- No production-grade global screener coverage.
