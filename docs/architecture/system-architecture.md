# System Architecture

## Purpose

Value Investing Terminal is an institutional-grade research platform for value investors. It should combine global stock screening, company research, valuation systems, financial intelligence, RAG, and eventually multi-agent workflows.

The product should feel closer to Bloomberg, TIKR, Koyfin, and institutional research terminals than a retail investing app.

## Architecture Principles

- Keep financial logic explicit, testable, and source-backed.
- Separate frontend presentation, backend domain logic, data ingestion, valuation, and AI orchestration.
- Preserve provenance for every metric, filing excerpt, valuation assumption, and AI output.
- Build incrementally: Phase 1 should create the terminal foundation before advanced AI systems.
- Prefer modular services and shared typed contracts over large monolithic prompts or page-level data hacks.

## Recommended Monorepo

```text
apps/
  web/                  # Next.js terminal UI
  api/                  # FastAPI domain API
  workers/              # ingestion, embeddings, filings, news, agent jobs
packages/
  ui/                   # reusable UI primitives and terminal components
  types/                # shared TypeScript/Python-compatible API contracts
  domain/               # financial domain constants, formulas, taxonomy
  valuation-engine/     # DCF, WACC, multiples, scenario logic
  rag-core/             # extraction, chunking, retrieval contracts
  data-connectors/      # Alpaca, SEC, fundamentals, news integrations
  agent-contracts/      # agent inputs, outputs, artifacts, guardrails
infra/
  migrations/           # database migrations
  netlify/              # Netlify config and deployment notes
  observability/        # logging, tracing, dashboards
docs/
  architecture/
  roadmap.md
  mvp-scope.md
```

This structure is a target architecture. Do not scaffold all packages until the implementation phase requires them.

## Runtime Topology

- Netlify hosts the web application, deploy previews, CDN, SSR, and edge-safe auth/session behavior.
- FastAPI provides financial domain APIs, valuation APIs, RAG APIs, and agent orchestration endpoints.
- Workers run ingestion, filings parsing, embedding jobs, news processing, and long-running research tasks.
- PostgreSQL/Supabase stores canonical data, normalized financials, user research, and audit trails.
- Redis handles caching, queues, deduplication locks, and short-lived market snapshots.
- Object storage stores raw filings, source PDFs, extracted text, provider payloads, and generated artifacts.

## Core Subsystems

- Terminal UI: workspace shell, ticker search, screener, company dashboard, financial statements, valuation workbench, research notebook.
- Data platform: securities master, market data, fundamentals, filings, news, macro data, knowledge documents.
- Valuation engine: WACC, FCFF, FCFE, DCF scenarios, terminal value, sensitivity analysis, multiples, quality scores.
- RAG system: document extraction, chunking, metadata, embeddings, hybrid retrieval, citations, evidence packets.
- Agent system: specialist workflows for quantitative, qualitative, valuation, news, screener, and research memo generation.

## Key Data Flows

1. Universe sync: data providers update securities, listings, exchanges, identifiers, and tradability.
2. Market data: Alpaca updates prices, bars, snapshots, calendar, and market status for supported assets.
3. Fundamentals: provider statements and metrics are normalized into canonical periods and line items.
4. Filings: SEC filings are downloaded, sectioned, indexed, and linked to companies and periods.
5. Knowledge base: local books, spreadsheets, letters, checklists, and sample analyses are extracted into reusable frameworks.
6. Research workflow: analysts query companies, retrieve evidence, run valuation scenarios, and generate source-backed memo sections.

## Cross-Cutting Requirements

- Authentication and authorization should be designed before user-specific watchlists, research notes, or saved valuations.
- API contracts must be typed and versioned.
- Long-running jobs must be idempotent and resumable.
- Logs, traces, and audit records must include provider, source, job id, and data version.
- AI outputs must include evidence references and confidence/limitation notes.
- Avoid direct provider calls from the browser; provider credentials stay server-side.

## Phase 1 System Boundary

Phase 1 should deliver a usable research terminal foundation:

- Next.js terminal shell.
- Ticker search and watchlists.
- Company profile and basic market data.
- Screener against a limited normalized universe.
- Basic company dashboard and charts.
- Backend service contracts and database schema foundations.

Advanced RAG, multi-agent orchestration, full global coverage, and probabilistic valuation should remain later phases.
