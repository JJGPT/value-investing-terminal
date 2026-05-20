# MVP Scope

## MVP Definition

The MVP is not the full AI-powered research terminal. It is the core platform foundation that proves the product can operate like an institutional research workspace with trustworthy data, clean architecture, and room for valuation and AI systems.

## MVP Goals

- Establish the terminal UX foundation.
- Prove secure backend data access.
- Integrate real market data through Alpaca.
- Create a securities master and company search.
- Build the first screener and company dashboard.
- Store data with provenance and freshness.
- Prepare the system for fundamentals, valuation, and RAG.

## In Scope

### Frontend

- Landing page with premium institutional positioning.
- Terminal shell.
- Global ticker/company search.
- Watchlist view.
- Screener table with initial filters.
- Company overview page.
- Basic price chart.
- Loading, empty, error, and stale-data states.

### Backend

- FastAPI service skeleton.
- Health and version endpoints.
- Securities and listings API.
- Alpaca market data adapter.
- Screener query endpoint.
- Company overview endpoint.
- Job status and audit logging foundation.

### Data

- Minimal securities master.
- Alpaca assets, market calendar, bars, snapshots.
- Basic metric snapshot table.
- Watchlist persistence.
- Provider provenance fields.

### Infrastructure

- Netlify deployment plan for frontend.
- Backend deployment target selected but not overbuilt.
- PostgreSQL/Supabase.
- Redis for cache/queue planning.
- Environment variable strategy.
- Basic observability plan.

## Out Of Scope For MVP

- Autonomous multi-agent workflows.
- Full RAG pipeline.
- Full SEC filing parser.
- Full global fundamentals coverage.
- Advanced valuation models beyond planning.
- Monte Carlo or probabilistic valuation.
- Trading/order execution.
- Portfolio management.
- Alerts.
- Mobile app.
- Complex options analytics.
- Fully polished investment memo generation.

## MVP Data Provider Assumptions

- Alpaca provides Phase 1 market data, assets, calendar, bars, and snapshots.
- A separate fundamentals provider must be selected before Phase 2.
- SEC, news, and knowledge ingestion are designed in Phase 1 but implemented later.

## MVP Acceptance Criteria

- A user can open the terminal and search for a supported ticker.
- A user can view a company overview with market data.
- A user can run a basic screener against the supported universe.
- A user can save or view a watchlist.
- The UI clearly shows loading, stale, and error states.
- Backend responses include source and freshness metadata.
- No provider credentials are exposed to the browser.
- The schema can support later fundamentals, valuation, RAG, and agents without major rewrites.

## What Comes Immediately After MVP

1. Fundamentals provider integration.
2. Financial statements view.
3. Derived value-investing metrics.
4. DCF and WACC engine.
5. Knowledge extraction and RAG.
6. Specialist agent workflows.
