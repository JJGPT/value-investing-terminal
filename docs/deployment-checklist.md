# Deployment Checklist

Use this checklist before any preview or production deployment. Phase 5D does not deploy the app; it prepares the app to be deployed deliberately.

## Local Verification

- Install Node dependencies with `npm install`.
- Install API dependencies with `cd apps/api` then `python3 -m pip install -r requirements-dev.txt`.
- Create the local SQLite directory with `npm run init:db`.
- Run the API with `npm run dev:api`.
- Run the frontend with `npm run dev:web`.
- Confirm `http://localhost:8000/health` returns `status: ok`.
- Confirm `http://localhost:8000/api/status` returns safe provider states.
- Confirm `http://localhost:3000/diagnostics` renders API, provider, cache, repository, job, ranking, valuation, and watchlist readiness.

## Test Commands

```bash
npm run test:api
npm run typecheck
npm run build
```

`npm run check` runs the same core local verification sequence.

## Frontend Deployment

- Host `apps/web` on Netlify using the root `netlify.toml`.
- Keep the repository root as the Netlify base directory.
- Use `npm run build` as the build command.
- Use `apps/web/.next` as the publish directory.
- Set `NEXT_PUBLIC_API_BASE_URL` to the deployed FastAPI backend URL.
- Do not set Alpaca or FMP credentials as `NEXT_PUBLIC_*` values.
- Verify production build output with `npm run build`.
- Confirm frontend routes render graceful states when the backend is offline.

## Backend Deployment

- Host `apps/api` on a Python runtime that supports long-running FastAPI services.
- Use this run command:

```bash
python3 -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
```

- Set `APP_ENV="staging"` for staging deployments.
- Set `CORS_ORIGINS` to the Netlify site origin. Use comma-separated origins for multiple staging deploy URLs.
- Set `VALUE_TERMINAL_DB_PATH` to a persistent volume path if SQLite is used.
- Confirm `/health`, `/api/status`, and `/docs` are reachable.

Suggested hosted options are Render, Fly.io, and Railway. See `docs/staging-deployment.md` for exact manual settings.

## Provider Keys

Backend-only:

```env
ALPACA_API_KEY=""
ALPACA_SECRET_KEY=""
ALPACA_BASE_URL="https://paper-api.alpaca.markets"
ALPACA_DATA_BASE_URL="https://data.alpaca.markets"
FMP_API_KEY=""
FMP_BASE_URL="https://financialmodelingprep.com/stable"
```

Security reminders:

- Do not expose provider keys in the browser.
- Do not use `NEXT_PUBLIC_` for secrets.
- Rotate any key that was accidentally logged or committed.
- Confirm diagnostics show only present/missing status, never credential values.

## Data Refresh Steps

- Refresh fundamentals and screener snapshots before relying on rankings.
- Refresh rankings after snapshot refresh.
- Review `/diagnostics` for stale snapshot warnings.
- Review ranking refresh jobs and failed job counts.
- Run watchlist refreshes for active watchlists when using watchlist intelligence.

## Staging Diagnostics Checklist

Backend URLs:

- `/health`
- `/api/status`
- `/api/diagnostics/market-data`
- `/api/diagnostics/fundamentals`
- `/api/diagnostics/rankings`
- `/api/diagnostics/watchlists`

Frontend URL:

- `/diagnostics`

Confirm all diagnostics expose provider states, readiness, and stale/missing data without exposing Alpaca or FMP key values.

## SQLite Limitations

SQLite is suitable for local development and single-user previews only.

Before production usage, plan migration to PostgreSQL or Supabase for:

- multi-user workflows;
- durable refresh history;
- concurrent job workers;
- larger securities universes;
- long-term valuation and audit history.

## Known Limitations

- No AI/RAG research workflows yet.
- No autonomous analyst agents.
- No trading or order execution.
- No notifications.
- No portfolio optimization.
- No production-grade global universe coverage.
- Refresh orchestration is lightweight and local-first, not a distributed queue.

## Go/No-Go

Proceed to preview deploy only when:

- backend tests pass;
- TypeScript typecheck passes;
- frontend build passes;
- provider keys are backend-only;
- diagnostics show expected provider states;
- SQLite persistence behavior is acceptable for the preview audience;
- users understand rankings, alerts, and valuation gaps are informational, not recommendations.
