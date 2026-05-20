# Staging Deployment Guide

This guide prepares a controlled staging deployment with Netlify for the frontend and a hosted FastAPI service for the backend. It does not deploy the app or require real secrets in the repository.

## Staging Topology

```text
Netlify frontend
  NEXT_PUBLIC_API_BASE_URL=https://your-fastapi-staging-host.example.com
        |
        v
Hosted FastAPI backend
  CORS_ORIGINS=https://your-netlify-staging-site.netlify.app
  ALPACA_API_KEY / ALPACA_SECRET_KEY / FMP_API_KEY kept backend-only
        |
        v
SQLite staging file on persistent disk, or temporary file for throwaway preview
```

The frontend must never call Alpaca or FMP directly. The browser receives only the public API base URL and safe provider status metadata.

## Netlify Frontend

The repository includes a root [netlify.toml](/Users/jjgonzalezramirez/Documents/App%20de%20inversiones/value-investing-terminal/netlify.toml) configured for the `apps/web` workspace:

```toml
[build]
  command = "npm run build"
  publish = "apps/web/.next"
```

Netlify automatically detects Next.js and uses the Netlify Next runtime for App Router pages.

Manual Netlify steps:

1. Create a new Netlify site from the GitHub repository.
2. Keep the repository root as the base directory.
3. Use the committed `netlify.toml` settings.
4. Set `NEXT_PUBLIC_API_BASE_URL` to the hosted FastAPI staging URL.
5. Do not add `ALPACA_API_KEY`, `ALPACA_SECRET_KEY`, `FMP_API_KEY`, or future provider secrets to the frontend environment.
6. Deploy a branch deploy or deploy preview first.
7. Open `/diagnostics` after the backend is live.

Frontend staging env:

```env
NEXT_PUBLIC_API_BASE_URL="https://your-fastapi-staging-host.example.com"
```

Optional server-side fallback for Netlify SSR:

```env
API_BASE_URL="https://your-fastapi-staging-host.example.com"
```

## Backend Hosting Options

All options run the same FastAPI app from `apps/api`.

### Render

Suggested Render Web Service settings:

```text
Runtime: Python
Root directory: apps/api
Build command: python3 -m pip install -r requirements.txt
Start command: python3 -m uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

If using SQLite beyond a throwaway preview, add a Render persistent disk and set:

```env
VALUE_TERMINAL_DB_PATH="/data/value_terminal.db"
```

### Fly.io

Suggested Fly shape:

```text
App root: apps/api
Install: python3 -m pip install -r requirements.txt
Start: python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8080
Internal port: 8080
```

Use a Fly volume for SQLite staging persistence and set `VALUE_TERMINAL_DB_PATH` to the mounted path.

### Railway

Suggested Railway service settings:

```text
Root directory: apps/api
Install command: python3 -m pip install -r requirements.txt
Start command: python3 -m uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Railway storage can be ephemeral depending on the service configuration. Use a volume if staging data must survive restarts.

## Backend Environment Variables

Required for staging:

```env
APP_ENV="staging"
CORS_ORIGINS="https://your-netlify-staging-site.netlify.app"
VALUE_TERMINAL_DB_PATH="/data/value_terminal.db"
SNAPSHOT_STALE_AFTER_SECONDS="86400"
```

Backend-only provider keys:

```env
ALPACA_API_KEY=""
ALPACA_SECRET_KEY=""
ALPACA_BASE_URL="https://paper-api.alpaca.markets"
ALPACA_DATA_BASE_URL="https://data.alpaca.markets"
FMP_API_KEY=""
FMP_BASE_URL="https://financialmodelingprep.com/stable"
```

Cache TTLs:

```env
SECURITY_SEARCH_CACHE_TTL_SECONDS="300"
SECURITY_LOOKUP_CACHE_TTL_SECONDS="900"
MARKET_SNAPSHOT_CACHE_TTL_SECONDS="30"
FUNDAMENTALS_PROFILE_CACHE_TTL_SECONDS="3600"
FUNDAMENTALS_INCOME_STATEMENT_CACHE_TTL_SECONDS="3600"
FUNDAMENTALS_BALANCE_SHEET_CACHE_TTL_SECONDS="3600"
FUNDAMENTALS_CASH_FLOW_CACHE_TTL_SECONDS="3600"
FUNDAMENTALS_KEY_METRICS_CACHE_TTL_SECONDS="3600"
COMPUTED_METRICS_CACHE_TTL_SECONDS="900"
```

Do not set backend provider keys in Netlify unless a future server-side Netlify backend owns those calls. In the current staging architecture, FastAPI owns them.

## CORS

Set `CORS_ORIGINS` on the backend to the exact Netlify staging origin:

```env
CORS_ORIGINS="https://your-netlify-staging-site.netlify.app"
```

For multiple staging URLs, use comma-separated origins:

```env
CORS_ORIGINS="https://main--value-terminal.netlify.app,https://deploy-preview-12--value-terminal.netlify.app"
```

Avoid `*` because credentials and provider boundaries should stay explicit.

## SQLite In Hosted Staging

SQLite is acceptable for a controlled single-user staging preview, but hosted environments need care:

- ephemeral disks lose watchlists, valuations, rankings, jobs, policies, and snapshots on restart;
- concurrent refreshes are not designed for distributed workers;
- SQLite is not the long-term production database;
- persistent disks must be backed up if staging data matters.

Before broader usage, migrate persistence to PostgreSQL or Supabase.

## Manual Deployment Sequence

1. Run local verification:

```bash
npm run test:api
npm run typecheck
npm run build
```

2. Create the FastAPI backend service on Render, Fly.io, or Railway.
3. Set backend environment variables, including `CORS_ORIGINS` and backend-only Alpaca/FMP keys.
4. Deploy the backend.
5. Validate backend liveness:

```text
https://your-fastapi-staging-host.example.com/health
https://your-fastapi-staging-host.example.com/api/status
```

6. Create the Netlify frontend site from the repository.
7. Set `NEXT_PUBLIC_API_BASE_URL` to the backend URL.
8. Deploy the Netlify site.
9. Open the Netlify `/diagnostics` page.
10. Run the staging diagnostics checklist below.

## Staging Diagnostics Checklist

Backend:

- `GET /health` returns `status: ok`.
- `GET /api/status` returns safe provider state metadata.
- `GET /api/diagnostics/market-data` reports Alpaca readiness without key values.
- `GET /api/diagnostics/fundamentals` reports FMP readiness without key values.
- `GET /api/diagnostics/rankings` reports ranking store/readiness.
- `GET /api/diagnostics/watchlists` reports watchlist store/readiness.

Frontend:

- `/diagnostics` renders the backend connection panel.
- `/diagnostics` shows provider states without secrets.
- `/screener`, `/rankings`, `/company/AAPL`, `/valuation/AAPL`, and `/watchlist` render unavailable/degraded/stale states instead of white screens.

## Staging Go/No-Go

Go only when:

- build and tests pass locally;
- backend `/health` is reachable;
- CORS allows the Netlify staging origin;
- `NEXT_PUBLIC_API_BASE_URL` points to the hosted backend;
- provider keys exist only in the backend host;
- diagnostics show expected connected, degraded, or not-connected states;
- SQLite persistence behavior is acceptable for the staging audience.
