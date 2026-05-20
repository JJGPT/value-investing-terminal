# Frontend Architecture

## Purpose

The frontend is the analyst workstation for the platform. It should feel like an institutional research terminal: dense, fast, keyboard-friendly, data-rich, and visually premium without becoming decorative or gamer-like.

## Target Stack

- Next.js 15 with App Router.
- React and TypeScript.
- Tailwind CSS and shadcn/ui.
- Framer Motion for restrained transitions.
- Recharts for financial charts.
- Three.js/React Three Fiber only where it supports the premium landing/brand experience, not core data screens.

## UX Principles

- Prioritize scanning, comparison, and repeated workflows.
- Use dense but organized layouts, not marketing cards.
- Keep controls familiar: tabs, split panes, tables, filters, command palette, keyboard shortcuts, tooltips.
- Show data provenance and last-updated state wherever metrics appear.
- Never present AI output as fact without citations or supporting evidence.

## Application Shell

The terminal shell should include:

- Left navigation for Screener, Companies, Watchlists, Research, Valuation, Filings, News.
- Global ticker/company search.
- Command palette for fast navigation and actions.
- Workspace tabs for open companies and saved research tasks.
- Right-side context panel for notes, alerts, citations, or agent activity.
- Status bar for market state, data freshness, sync jobs, and API health.

## Main Views

- Landing: premium first impression, 3D sphere/neural aesthetic, direct entry into the terminal.
- Screener: global filters, saved screens, sortable financial metrics, exportable result sets.
- Company dashboard: overview, business summary, price chart, key metrics, valuation summary, latest filings/news.
- Financial statements: income statement, balance sheet, cash flow, normalized metrics, period comparison.
- Valuation workbench: DCF assumptions, WACC, scenarios, sensitivity tables, narrative-to-numbers notes.
- Research notebook: analyst notes, evidence clips, thesis sections, generated memo drafts.
- Agent console: future view for queued/running/completed agent workflows.

## Suggested App Organization

```text
apps/web/
  app/
    (terminal)/
      screener/
      company/[ticker]/
      valuation/[ticker]/
      research/
    api/                # thin BFF routes only when needed
  components/
    terminal/
    screener/
    company/
    financials/
    valuation/
    research/
  lib/
    api/
    formatters/
    hooks/
    charts/
  styles/
```

## Data Loading

- Use server components for stable page-level data where practical.
- Use client components for interactive tables, filters, charts, valuation inputs, and streaming job state.
- Use React Query or a similar client cache for frequently refreshed data.
- Keep provider-specific details out of the frontend; call backend domain endpoints.
- Prefer typed DTOs generated or shared from `packages/types`.
- Render explicit backend-offline, provider-missing, degraded, stale, and unavailable states instead of throwing or inventing values.

## State Model

- URL state for filters, selected ticker, tabs, and comparison modes.
- Client state for panel layout, unsaved valuation assumptions, and workspace UI preferences.
- Server state for watchlists, saved screens, notes, valuation scenarios, and research artifacts.

## Components

- Data grids must support sorting, pinned columns, density controls, column visibility, and filter chips.
- Charts must support crosshair inspection, period switching, and source/frequency labels.
- Valuation controls should use explicit numeric inputs, sliders for scenario ranges, and formula/tooltips for derived fields.
- AI panels should show evidence, citations, assumptions, and limitations, not just prose.

## Phase 1 Frontend Scope

Build:

- Terminal shell.
- Ticker search.
- Watchlist skeleton.
- Screener table with realistic filters.
- Company overview page.
- Basic market chart and key metrics.
- Data freshness and loading/error states.

Defer:

- Full 3D dashboard interiors.
- Complex multi-agent console.
- Memo generation UI.
- Monte Carlo and advanced valuation visualization.
- Portfolio-level workflows.

## Current Implemented Views

- Terminal shell and premium landing route.
- Provider diagnostics route.
- Fundamentals-backed company page with statement audit.
- Snapshot-backed screener route with filters, sorting, pagination, and provider states.
- Rankings route at `/rankings` with strategy selector, Magic Formula table, formula explanation, score components, quality flags, missing input states, and snapshot freshness markers.
- Watchlist route at `/watchlist` with saved watchlist sidebar, saved views, deterministic filter/sort controls, column visibility controls, create/update/archive/restore lifecycle controls, add ticker workflow, notes/tags/target price/status/priority/workflow-state fields, deterministic intelligence columns, staleness badges, stale/provider warnings, watchlist refresh controls, refresh history, alert inbox, and acknowledgement/dismissal history.
- DCF workbench route at `/valuation/[ticker]` with editable assumptions, scenario naming, immutable version saving, saved scenario reopening, saved case comparison, side-by-side scenario diffs, scenario lifecycle controls, assumption import/export, immutable analyst notes, version history, audit event history, valuation warnings, model metadata, reproducibility metadata, FCFF projection table, WACC inputs, enterprise-value bridge, heatmap-style sensitivity matrices, formulas, quality flags, and assumption provenance.
- Diagnostics route includes valuation engine readiness, scenario persistence status, repository health, orphaned version detection, stale valuation detection, reproducibility completeness, assumption validation bounds, ranking refresh health, and watchlist store/alert readiness.
- App-level `error.tsx` and `not-found.tsx` pages provide graceful fallback surfaces for backend failures, missing routes, or unexpected rendering errors.

The valuation workbench is intentionally analytical and transparent. It does not display buy/sell language, AI-generated assumptions, or hidden scoring.

The watchlist workspace is intentionally deterministic. Alert labels describe data conditions and analyst-entered thresholds; saved views preserve local analyst workflow state; refresh controls operate through auditable local jobs; alert acknowledgement history is local audit metadata. None of these surfaces use buy/sell language, notifications, or automated recommendations.
