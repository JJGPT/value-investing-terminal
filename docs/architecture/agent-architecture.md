# Agent Architecture

## Purpose

Agents should support institutional research workflows by producing source-backed findings, valuation assumptions, risks, and memo sections. They should not replace the core data platform or invent financial logic.

Advanced agents are a later phase. Phase 1 should make the system agent-ready through clean data contracts, provenance, and research artifacts.

## Orchestration Recommendation

Use a graph-based orchestrator such as LangGraph in Python when multi-step workflows begin. The orchestrator should persist state, support specialist handoffs, expose run status, and make tool usage auditable.

The OpenAI Responses API can power individual model calls. Agent workflows should call platform tools, not directly scrape or bypass backend services.

## Agent Principles

- One agent, one responsibility.
- Typed inputs and structured outputs.
- Explicit allowed tools per agent.
- Evidence required for qualitative claims.
- Formula/source required for quantitative claims.
- Human review before investment memo finalization.
- No autonomous trading or portfolio actions.

## Planned Specialist Agents

### Screener Agent

- Converts investor criteria into screener filters.
- Explains why companies match or fail criteria.
- Suggests comparable companies and peer sets.

### Quantitative Agent

- Analyzes statements and derived metrics.
- Detects deterioration, dilution, leverage, margin changes, and reinvestment quality.
- Produces metric-backed findings.

### Qualitative Agent

- Uses filings, checklists, fund-letter principles, and sample analyses.
- Assesses moat, business model, market size, competition, management, and risks.
- Produces evidence-backed qualitative findings.

### Valuation Agent

- Converts narrative assumptions into DCF scenarios.
- Uses Damodaran-style WACC, FCFF/FCFE, terminal value, and sensitivity logic.
- Produces assumption sets, not unsupported price targets.

### News And Macro Agent

- Monitors news, earnings, filings, insider activity, and macro events.
- Links events to companies and watchlists.
- Classifies materiality and likely thesis impact.

### Research Editor Agent

- Assembles memo drafts from structured findings.
- Preserves citations, assumptions, and open questions.
- Does not create unsupported analysis.

## Shared Artifacts

Agents should communicate through persisted artifacts:

- `EvidencePacket`
- `MetricFinding`
- `QualitativeFinding`
- `RiskItem`
- `AssumptionSet`
- `ValuationScenario`
- `NewsEvent`
- `ResearchMemoSection`
- `OpenQuestion`

Each artifact should include source ids, confidence, created_by, created_at, and validation status.

## Workflow Pattern

1. User starts a research task.
2. Orchestrator creates an `agent_run`.
3. Specialist agents fetch data through backend tools.
4. Retrieval service returns evidence packets.
5. Agents produce structured artifacts.
6. Validation checks citations, required fields, and numeric consistency.
7. Research editor assembles memo sections.
8. User reviews, edits, and approves.

## Guardrails

- Reject unsupported valuation conclusions.
- Mark stale or missing data.
- Require source citations for claims about filings, management, moat, or risk.
- Require formula version and input assumptions for valuation outputs.
- Preserve raw evidence and final generated text separately.

## Phase 1 Scope

Build no autonomous multi-agent workflows in Phase 1.

Prepare:

- agent run schema;
- artifact contracts;
- evidence packet design;
- backend tool boundaries;
- UI placeholders for future research jobs.

Implement simple AI/RAG only after reliable data and valuation systems exist.
