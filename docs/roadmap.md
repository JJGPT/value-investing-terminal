# Roadmap

## Guiding Rule

Build the terminal foundation before advanced AI. The platform must first have trustworthy data, clear UX, valuation logic, and provenance.

## Phase 0: Architecture And Foundations

Goal: make implementation decisions explicit before scaffolding.

Deliverables:

- Architecture docs.
- MVP scope.
- Initial database design.
- Provider selection notes.
- API contract conventions.
- CI/testing strategy.

Exit criteria:

- Project structure approved.
- Phase 1 scope frozen.
- Data provider assumptions documented.

## Phase 1: Core Terminal

Goal: create a usable analyst workstation with real market data and basic screening.

Deliverables:

- Next.js terminal shell.
- Ticker/company search.
- Watchlists.
- Alpaca market data integration.
- Securities master.
- Basic company overview.
- Screener with initial filters.
- Price chart and key market metrics.
- Backend API, database migrations, job logging.

Exit criteria:

- User can search a company, open a dashboard, view current/historical market data, and run a simple screen.
- Data freshness and source information are visible.

## Phase 2: Fundamentals And Valuation

Goal: make the platform useful for value investing analysis.

Deliverables:

- Fundamentals provider integration.
- Financial statements view.
- Normalized metrics: ROIC, ROE, margins, leverage, growth, FCF yield.
- DCF engine.
- WACC model.
- Scenario and sensitivity views.
- Magic Formula and quality scoring.

Exit criteria:

- User can evaluate a company using financial statements, metrics, and a source-backed valuation scenario.

## Phase 3: Knowledge And RAG

Goal: bring the knowledge base into research workflows.

Deliverables:

- Knowledge extraction pipeline.
- Document/chunk/embedding schema.
- Hybrid retrieval.
- Evidence packets.
- RAG question answering with citations.
- Qualitative checklist workflow.

Exit criteria:

- User can ask research questions and receive cited answers grounded in filings and curated knowledge.

## Phase 4: Agent Workflows

Goal: add specialist AI workflows that create structured research artifacts.

Deliverables:

- Agent run orchestration.
- Quantitative agent.
- Qualitative agent.
- Valuation agent.
- News/macro agent.
- Research memo assembly.
- Human review flow.

Exit criteria:

- User can start a company research workflow and review structured, cited findings.

## Phase 5: Advanced Intelligence

Goal: expand into portfolio intelligence and advanced analytical workflows.

Deliverables:

- Alerts and thesis monitoring.
- Portfolio/watchlist intelligence.
- Advanced news/event impact.
- Probabilistic valuation.
- Monte Carlo.
- Expanded global coverage.
- Agent evaluations and continuous quality loops.

Exit criteria:

- Platform supports repeatable institutional research workflows across watchlists and portfolios.

## Recommended Implementation Order

1. Documentation and architecture decisions.
2. Monorepo scaffolding.
3. Database migrations and shared types.
4. FastAPI skeleton and health checks.
5. Next.js terminal shell.
6. Alpaca connector and securities master.
7. Screener and company overview.
8. Fundamentals and financial statements.
9. Valuation engine.
10. Knowledge/RAG.
11. Agents.
