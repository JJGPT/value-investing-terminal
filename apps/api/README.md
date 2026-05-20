# API

FastAPI backend for the Value Investing Terminal. The API owns provider credentials, normalized data contracts, SQLite persistence, refresh jobs, diagnostics, deterministic rankings, valuation workflows, and watchlist intelligence.

## Install

```bash
cd apps/api
python3 -m pip install -r requirements-dev.txt
```

## Run

From the repository root:

```bash
npm run dev:api
```

Directly from this folder:

```bash
python3 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Environment

Use `infra/.env.example` as the safe template.

Core local settings:

```env
APP_ENV="development"
CORS_ORIGINS="http://localhost:3000"
VALUE_TERMINAL_DB_PATH="apps/api/data/value_terminal.db"
SNAPSHOT_STALE_AFTER_SECONDS="86400"
```

Optional backend-only provider keys:

```env
ALPACA_API_KEY=""
ALPACA_SECRET_KEY=""
FMP_API_KEY=""
```

Provider keys must never be sent to the frontend or prefixed with `NEXT_PUBLIC_`.

## SQLite

Create the local data directory before running the API in a clean checkout:

```bash
npm run init:db
```

The API creates tables lazily through repository classes when snapshots, rankings, valuation scenarios, refresh jobs, policies, or watchlists are written.

The local SQLite database is for development only. Production should move to PostgreSQL or Supabase before multi-user or hosted scheduled refresh workflows.

## Health And Diagnostics

```text
GET /health
GET /api/status
GET /api/diagnostics/market-data
GET /api/diagnostics/fundamentals
GET /api/diagnostics/rankings
GET /api/diagnostics/watchlists
GET /api/diagnostics/valuation?ticker=AAPL
```

`/health` only confirms the API process is running. `/api/status` and `/api/diagnostics/*` expose safe operational readiness, missing environment variables, provider states, cache settings, stale snapshots, job health, and repository health.

## Tests

```bash
npm run test:api
```

Tests use mocked providers only. They should not call Alpaca or FMP.

## Boundaries

- Alpaca is market data only. No trading routes exist.
- FMP is a fundamentals source. Platform metrics are calculated from normalized statements.
- Valuation is deterministic, transparent, editable, and auditable.
- Rankings and alerts are informational screens, not recommendations.
- AI/RAG, autonomous agents, notifications, portfolio optimization, and trading are outside the current scope.
