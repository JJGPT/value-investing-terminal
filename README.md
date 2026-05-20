# Value Investing Terminal

Institutional-grade value investing research terminal for deterministic screening, rankings, valuation workflows, watchlists, diagnostics, and provider-backed financial data.

The current product is intentionally pre-AI and pre-trading. It uses backend-only provider integrations, SQLite snapshots for local development, auditable valuation scenarios, deterministic ranking logic, and explicit degraded/not-connected states instead of synthetic financial analysis.

## Monorepo

```text
apps/
  web/       Next.js 15 App Router UI
  api/       FastAPI backend and local SQLite persistence
packages/
  types/     Shared TypeScript contracts
  domain/    Domain package placeholder
  valuation-engine/ Platform-owned metrics and valuation engine
  data-connectors/ Provider connector package placeholder
  agent-contracts/ Future agent contract package placeholder
docs/         Architecture, roadmap, API, ranking, valuation, and deployment docs
infra/        Environment template and deployment notes
knowledge/    Research knowledge base and investing references
```

## Local Setup

Install Node dependencies:

```bash
npm install
```

Install Python API dependencies:

```bash
cd apps/api
python3 -m pip install -r requirements-dev.txt
```

Create the local SQLite folder:

```bash
npm run init:db
```

SQLite is initialized lazily when the API first writes snapshots, rankings, valuation scenarios, watchlists, jobs, or policies. The local database path defaults to:

```text
apps/api/data/value_terminal.db
```

## Environment

Copy the safe template from [infra/.env.example](/Users/jjgonzalezramirez/Documents/App%20de%20inversiones/value-investing-terminal/infra/.env.example) into your local environment manager, shell profile, or app-specific `.env.local` files.

Minimum web setting:

```env
NEXT_PUBLIC_API_BASE_URL="http://localhost:8000"
```

Optional backend-only provider keys:

```env
ALPACA_API_KEY=""
ALPACA_SECRET_KEY=""
FMP_API_KEY=""
```

Never prefix provider secrets with `NEXT_PUBLIC_`. The frontend must only call the FastAPI backend.

## Running Locally

Run the backend:

```bash
npm run dev:api
```

Run the frontend in a second terminal:

```bash
npm run dev:web
```

Open:

```text
http://localhost:3000
```

Useful backend checks:

```text
http://localhost:8000/health
http://localhost:8000/api/status
http://localhost:8000/docs
```

Use the UI diagnostics workspace at:

```text
http://localhost:3000/diagnostics
```

## Provider Configuration

Alpaca is used only for market data. It does not enable trading or order execution.

```env
ALPACA_API_KEY="your_backend_only_key"
ALPACA_SECRET_KEY="your_backend_only_secret"
ALPACA_BASE_URL="https://paper-api.alpaca.markets"
ALPACA_DATA_BASE_URL="https://data.alpaca.markets"
```

Financial Modeling Prep is used for fundamentals. Platform-owned computed metrics are derived from normalized statements, not trusted raw provider ratios.

```env
FMP_API_KEY="your_backend_only_key"
FMP_BASE_URL="https://financialmodelingprep.com/stable"
```

Missing credentials are safe: providers fall back to explicit not-connected states and the UI renders unavailable values.

## Testing And Build

Backend tests:

```bash
npm run test:api
```

Typecheck:

```bash
npm run typecheck
```

Frontend production build:

```bash
npm run build
```

Full local check:

```bash
npm run check
```

## Current Scope

Implemented:

- Terminal UI shell and diagnostics workspace.
- Alpaca market data provider abstraction with safe fallback.
- FMP fundamentals provider abstraction with normalized canonical statements.
- Platform-owned computed metrics engine.
- SQLite snapshot persistence for fundamentals, screener rows, rankings, valuation scenarios, jobs, policies, and watchlists.
- Deterministic screener and ranking engines, including Magic Formula support.
- Transparent DCF workbench with scenario history, audit events, comparison, import/export, notes, and warnings.
- Watchlist workspaces with saved views, deterministic alerts, staleness, and refresh integration.

Not implemented:

- AI/RAG research workflows.
- Autonomous analyst agents.
- Trading or order execution.
- Portfolio optimization.
- Notifications.
- Production-grade global data coverage.

## Deployment

See [infra/README.md](/Users/jjgonzalezramirez/Documents/App%20de%20inversiones/value-investing-terminal/infra/README.md), [docs/staging-deployment.md](/Users/jjgonzalezramirez/Documents/App%20de%20inversiones/value-investing-terminal/docs/staging-deployment.md), and [docs/deployment-checklist.md](/Users/jjgonzalezramirez/Documents/App%20de%20inversiones/value-investing-terminal/docs/deployment-checklist.md).
