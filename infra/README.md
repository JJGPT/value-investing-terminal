# Infrastructure And Deployment Notes

This project is deployment-ready enough for a controlled preview, but it is not yet production-ready for multi-user institutional usage. The current stack is local-first, deterministic, and intentionally lightweight.

## Recommended Preview Architecture

- Frontend: Netlify hosting for `apps/web`.
- Backend: a Python API host such as Render, Fly.io, Railway, Cloud Run, or ECS running `apps/api`.
- Persistence: SQLite for local development only. Move to PostgreSQL or Supabase before serious hosted usage.
- Secrets: provider keys stay in the backend runtime only.
- Refresh jobs: lightweight local job abstraction, currently not a distributed queue.

## Netlify Frontend

The root `netlify.toml` is configured for the web workspace:

```text
Base directory: repository root
Build command: npm run build
Publish directory: apps/web/.next
```

If configuring the site manually, keep the repository root as the base directory so npm workspaces and the root lockfile are available:

```bash
npm install
npm run build
```

Frontend environment:

```env
NEXT_PUBLIC_API_BASE_URL="https://your-api-host.example.com"
```

Only expose the API base URL to the browser. Do not configure Alpaca, FMP, or future AI provider secrets in Netlify unless they are used only by server-side backend code.

## Backend Hosting

Run command:

```bash
python3 -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
```

Backend environment:

```env
APP_ENV="staging"
CORS_ORIGINS="https://your-netlify-site.netlify.app"
VALUE_TERMINAL_DB_PATH="/data/value_terminal.db"
ALPACA_API_KEY=""
ALPACA_SECRET_KEY=""
FMP_API_KEY=""
```

For a hosted backend, the SQLite path must point to a persistent volume. If the host has ephemeral storage, snapshots, valuation scenarios, watchlists, jobs, and rankings will be lost on restart.

## SQLite Limitations

SQLite is acceptable for local development and single-user previews.

Do not rely on SQLite for:

- multi-user collaboration;
- concurrent hosted refresh workers;
- durable production refresh history;
- larger global universes;
- long-term audit storage.

Future migration target:

- PostgreSQL or Supabase for primary tables;
- object storage for large raw provider payloads and filings;
- Redis or a managed queue for distributed refresh orchestration.

## Deployment Boundary

The frontend calls only FastAPI. It must never call Alpaca or FMP directly.

Provider credentials must remain backend-only because:

- browser bundles expose `NEXT_PUBLIC_*` variables;
- market and fundamentals keys can be abused if leaked;
- backend routing centralizes provider fallback, degraded states, caching, and audit metadata.

## Pre-Deploy Checks

Run locally before deploying:

```bash
npm run test:api
npm run typecheck
npm run build
```

Then verify:

```text
/health
/api/status
/api/diagnostics/market-data
/api/diagnostics/fundamentals
/api/diagnostics/rankings
/api/diagnostics/watchlists
```

See `docs/deployment-checklist.md` for the full checklist.

For exact staging steps across Netlify, Render, Fly.io, and Railway, see `docs/staging-deployment.md`.
