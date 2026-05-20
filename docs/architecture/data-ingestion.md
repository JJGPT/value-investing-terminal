# Data Ingestion Architecture

## Purpose

Data ingestion turns provider data, filings, news, and knowledge assets into clean, source-backed platform data. It must be reliable before advanced screeners, valuation, or AI workflows can be trusted.

## Provider Roles

- Alpaca: backend-only market data source for US equity asset reference data and stock snapshots. It is not used for trading, order execution, fundamentals, filings, valuation, or AI workflows.
- Financial Modeling Prep (FMP): Phase 2A backend-only fundamentals source for company profiles, annual/quarterly financial statements, and provisional key metrics.
- SEC: future source for filings, XBRL company facts, 10-K/10-Q/8-K text, and filing sections.
- News provider: future source for financial news, press releases, earnings headlines, and macro events.
- Local knowledge base: Damodaran material, valuation spreadsheets, fund letters, checklists, and sample analyses.

## Pipeline Pattern

Every ingestion pipeline should follow this shape:

1. Discover work.
2. Fetch raw payload.
3. Store raw source artifact.
4. Normalize into canonical schema.
5. Validate quality and completeness.
6. Persist normalized records.
7. Update derived metrics or search indexes.
8. Record job status, logs, and provenance.

Current provider requests are still synchronous API calls behind backend adapter interfaces. Process-local caches reduce repeated provider calls, and SQLite snapshots provide local durable screener/fundamentals reads until async ingestion jobs are introduced.

## Job Requirements

- Idempotent by source id, symbol, period, date, and provider version.
- Retryable with exponential backoff.
- Rate-limit aware.
- Observable through job status and logs.
- Able to resume after partial failure.
- Should never silently overwrite reported data without source/version tracking.

## Current Provider Adapters

### Alpaca Market Data

The market data adapter is defined by `MarketDataProvider`:

- `search_securities(query)`
- `get_security(ticker)`
- `get_market_snapshot(ticker)`

`AlpacaMarketDataProvider` is selected when `ALPACA_API_KEY` and `ALPACA_SECRET_KEY` are configured. Otherwise the API uses `NotConnectedProvider`.

Backend-only environment variables:

- `ALPACA_API_KEY`
- `ALPACA_SECRET_KEY`
- `ALPACA_BASE_URL`, default `https://paper-api.alpaca.markets`
- `ALPACA_DATA_BASE_URL`, default `https://data.alpaca.markets`

The Alpaca provider has a backend-only in-memory cache for successful normalized responses:

- `SECURITY_SEARCH_CACHE_TTL_SECONDS`, default `300`
- `SECURITY_LOOKUP_CACHE_TTL_SECONDS`, default `900`
- `MARKET_SNAPSHOT_CACHE_TTL_SECONDS`, default `30`

Provider errors are returned as degraded states and are not cached.

### FMP Fundamentals

The fundamentals adapter is defined by `FundamentalsProvider`:

- `provider_status()`
- `get_company_profile(ticker)`
- `get_income_statement(ticker, period, limit)`
- `get_balance_sheet(ticker, period, limit)`
- `get_cash_flow_statement(ticker, period, limit)`
- `get_key_metrics(ticker, period, limit)`

`FinancialModelingPrepProvider` is selected when `FMP_API_KEY` is configured. Otherwise the API uses `NotConnectedFundamentalsProvider`.

Backend-only environment variables:

- `FMP_API_KEY`
- `FMP_BASE_URL`, default `https://financialmodelingprep.com/stable`

Phase 2A uses FMP stable endpoints:

- `/profile`
- `/income-statement`
- `/balance-sheet-statement`
- `/cash-flow-statement`
- `/key-metrics`

Supported periods:

- `annual`: default and provider-backed in Phase 2A
- `quarter`: provider-backed in Phase 2A
- `ttm`: contract-ready; returns `not_implemented` until a future TTM layer is added

FMP key metrics are provider data, not final platform truth. The platform-owned metrics engine computes ratios from canonical statements and versions the calculation engine as `platform-normalized-metrics-v1`.

The FMP provider has a backend-only in-memory cache for successful normalized responses:

- `FUNDAMENTALS_PROFILE_CACHE_TTL_SECONDS`, default `3600`
- `FUNDAMENTALS_INCOME_STATEMENT_CACHE_TTL_SECONDS`, default `3600`
- `FUNDAMENTALS_BALANCE_SHEET_CACHE_TTL_SECONDS`, default `3600`
- `FUNDAMENTALS_CASH_FLOW_CACHE_TTL_SECONDS`, default `3600`
- `FUNDAMENTALS_KEY_METRICS_CACHE_TTL_SECONDS`, default `3600`
- `COMPUTED_METRICS_CACHE_TTL_SECONDS`, default `900`

Cache keys are normalized by endpoint, ticker, period, and limit where applicable. Provider errors are returned as degraded states and are not cached.

## Canonical Financial Models

Provider payloads must be normalized before reaching internal contracts or the frontend. Do not expose raw FMP field names as platform fields.

Canonical fields include:

- Income statement: `revenue`, `grossProfit`, `operatingIncome`, `ebitda`, `netIncome`, `epsDiluted`, `sharesDiluted`
- Balance sheet: `cashAndEquivalents`, `totalAssets`, `totalLiabilities`, `totalDebt`, `shareholdersEquity`
- Cash flow: `operatingCashFlow`, `capitalExpenditures`, `freeCashFlow`, `dividendsPaid`, `shareRepurchases`
- Metrics: `revenuePerShare`, `freeCashFlowPerShare`, `returnOnInvestedCapital`, `debtToEquity`, `enterpriseValueToEbitda`

Every normalized profile/financial row should carry source metadata:

- `provider`
- `fetchedAt`
- `sourceSymbol`
- `currency`
- `fiscalYear`
- `fiscalPeriod`
- `qualityFlags`

`qualityFlags` carries normalization and calculation audit hints. Current flags include missing core fields, missing currency, missing fiscal year, missing shares, currency mismatch, stale provider response when detectable, provider anomalies, missing computed inputs, zero or negative denominators, unavailable invested capital, and negative invested capital.

## Platform-Owned Metrics

Computed metrics use normalized statement data only:

- Income statement rows for revenue, gross profit, operating income, net income, and diluted shares.
- Balance sheet rows for current assets, current liabilities, debt, cash, and shareholders' equity.
- Cash flow rows for free cash flow.

The first metric engine calculates:

- Margins: gross, operating, net, and free cash flow margin.
- Growth: revenue, operating income, net income, and free cash flow year over year.
- Balance-sheet ratios: return on equity, debt to equity, and current ratio.
- Per-share metrics: free cash flow per share, book value per share, and diluted EPS.
- Capital metrics: invested capital and return on invested capital.

Safe calculation rules:

- Missing inputs return `null`.
- Zero denominators return `null`.
- Negative denominators return a value with a quality flag.
- Annual growth uses the previous annual row.
- Quarterly growth uses the matching prior-year fiscal quarter when present.
- TTM remains `not_implemented` until a normalized TTM layer is added.

Limitations:

- ROE currently uses ending equity rather than average equity.
- ROIC currently uses operating income over invested capital, not tax-adjusted NOPAT.
- FMP key metrics may be displayed as provider reference data, but they must not overwrite platform-owned calculations.

## Ranking Inputs

Phase 4 rankings consume the same normalized and snapshot-backed data:

- screener row snapshots for company identity, market cap, ratios, computed metrics, source metadata, and snapshot freshness;
- fundamentals snapshots for income statement EBIT, balance sheet debt, cash, and shareholders' equity;
- computed metric snapshots for invested capital where available;
- backend market data snapshots for enterprise value when available.

Magic Formula ranking uses canonical values only. Missing ranking inputs remain `null` and add quality flags rather than being filled with estimates. Phase 4B adds persisted ranking runs, row-level eligibility status, exclusion reasons, input audit metadata, and rank-change history. Phase 4C adds saved screen definitions and refresh workflow metadata. Phase 4D wraps ranking refresh in SQLite-backed local jobs with append-only events. Phase 4E adds refresh policies, stale-only ticker classification, and a manual due-policy runner so refresh can later move from synchronous execution into async, scheduled, stale-only, and per-ticker ingestion jobs.

## Valuation Inputs

Phase 3A adds a platform-owned FCFF DCF engine. The valuation layer consumes normalized data; it does not fetch raw provider-shaped payloads and does not call AI systems for assumptions.

DCF inputs:

- latest normalized income statement for revenue, operating income, diluted shares, fiscal period, and currency;
- latest normalized balance sheet for debt, cash, and capital-structure inputs;
- latest normalized cash flow statement for free cash flow context;
- platform-owned computed metrics for historical growth and margin derivation;
- market data snapshot or profile price for market reference only.

Assumption derivation:

- revenue growth and operating margin use historical normalized computed metrics when available;
- tax rate uses a conservative historical proxy from normalized income statement rows;
- reinvestment uses a statement-derived NOPAT-minus-FCF proxy where available;
- WACC inputs stay editable and source-labelled;
- macro assumptions start as manual defaults with `manual_review_required` flags.

Valuation outputs are stored in `valuation_scenarios`, separate from fundamentals snapshots. A saved scenario keeps assumptions, projections, formulas, quality flags, and sensitivity grids so the calculation can be audited later.

Phase 3B adds saved scenario list/load/compare behavior on top of the same persisted payloads. Scenario comparison is intentionally descriptive and limited to saved cases; it is not a screening rank, investment score, or recommendation layer.

Assumption validation bounds are exposed through valuation diagnostics so analysts can see what the engine considers suspicious before relying on outputs.

Phase 3C adds immutable valuation history. Every persisted edit creates a new valuation version, and audit events record changed assumptions or lifecycle actions. Current scenario rows are latest pointers; prior versions and audit records remain available through history routes.

DCF inputs now include incremental support for projected diluted share count and a refined net debt bridge. Missing lease debt, preferred equity, minority interest, and share-count details remain nullable rather than invented.

The valuation layer is intentionally not a trading system, automated recommendation engine, or AI-generated assumptions engine.

## Statement Audit UI

The company page includes a statement audit section before valuation or screening logic exists. It shows compact canonical line items, source metadata, and quality flags for the latest normalized income statement, balance sheet, and cash flow rows.

The audit view is intentionally not a raw data dump. It exists so the user can inspect whether statement normalization and computed metrics are trustworthy before DCF, Magic Formula, or screeners depend on them.

## Phase 2E Screener Snapshots

The screener now reads durable SQLite snapshots before using provider fallback. It stores:

- controlled universe tickers;
- normalized fundamentals snapshots;
- platform-owned computed metric snapshots;
- screener row snapshots.

Snapshots are JSON payloads persisted through a repository abstraction. Every payload includes `schemaVersion = 1` and explicit provenance: provider, provider version, fetched timestamp, and source symbol.

Computed metric and screener row snapshots also include `computedFrom` source fiscal periods and `computedAt`. Stale snapshots are still read and marked stale. Missing snapshots fall back to provider-backed request-time construction when the provider is connected.

DCF scenarios are stored in the same SQLite database, but in a separate `valuation_scenarios` table. They are not used as screener snapshots and should evolve into a dedicated valuation persistence model when PostgreSQL/Supabase replaces local SQLite.

`POST /api/screener/refresh` is synchronous and intentionally temporary. Ranking and policy-triggered screener refresh now use job-shaped APIs and SQLite job/event records, but execution still occurs synchronously inside the request in Phase 4E. Future ingestion should move toward async refresh workers, scheduled refreshes, incremental refreshes, priority refreshes, and queue-based ingestion.

## Provider Observability

Provider status is exposed through:

- `/api/status`
- `/api/diagnostics/market-data`
- `/api/diagnostics/market-data/probe?ticker=AAPL`
- `/api/diagnostics/fundamentals`
- `/api/screener`
- `/api/screener/refresh`
- individual provider-backed endpoint payloads

Safe metadata includes:

- `connected`, `degraded`, `not_connected`, or `not_implemented`
- required environment variables
- sanitized last error message
- last successful provider call timestamp

Provider errors must never leak API keys, secret keys, or raw credential-bearing URLs.

## Future Durable Ingestion Pipelines

### Universe Sync

- Pull active Alpaca assets and listing metadata.
- Map tickers to canonical securities.
- Store exchange, currency, country, status, and identifiers.
- Detect ticker changes and inactive securities.

### Market Data

- Pull EOD bars for supported symbols.
- Pull intraday bars only for watchlisted or actively viewed symbols.
- Use Alpaca stock snapshots/latest market data for dashboard freshness.
- Cache latest values in Redis; persist historical bars in PostgreSQL.

### Fundamentals

- Pull income statements, balance sheets, cash flows, profiles, shares, and provider metrics.
- Normalize periods, currencies, line items, and restatements.
- Compute derived metrics through versioned formulas.
- Populate screener metric snapshots.

### SEC Filings

- Map ticker to CIK.
- Download 10-K, 10-Q, 8-K, and company facts.
- Parse key sections: business, risk factors, MD&A, financial statements, notes.
- Store filing text chunks with page/section/source offsets.
- Link XBRL facts to financial periods.

### News

- Fetch articles by ticker, market, sector, and watchlist.
- Deduplicate by URL, title similarity, source, and timestamp.
- Entity-link articles to securities.
- Classify event type and materiality.
- Store article source and extracted summary separately.

### Knowledge Base

- Extract PDFs, DOCX, and spreadsheets.
- Convert valuation spreadsheets into documented model references before rewriting them in code.
- Tag material by method, author, source type, topic, and intended use.
- Build RAG chunks only after extraction quality is verified.

## Data Quality Checks

- Missing period detection.
- Currency mismatch detection.
- Outlier checks for margins, growth rates, shares, and debt.
- Duplicate filing/news checks.
- Provider disagreement flags.
- Formula output regression tests.

## Deferred From Phase 2D

- Full database-backed ingestion.
- Redis-backed provider cache.
- Distributed async, scheduled, incremental, priority, or queue-based refresh jobs.
- SEC filing parsing.
- News materiality classification.
- Knowledge embedding pipeline.
- Real-time streaming.
- Valuation formulas and Magic Formula ranking.
- Production-grade global screener coverage and saved screens.
