# Valuation Architecture

## Purpose

Phase 3A introduces a transparent, platform-owned FCFF DCF workbench. The system calculates valuation outputs from canonical normalized fundamentals, platform-owned computed metrics, and backend market data. It does not generate assumptions with AI, issue recommendations, or execute trades.

## Inputs

The DCF engine uses:

- normalized income statement rows for `revenue`, `operatingIncome`, `netIncome`, and `sharesDiluted`;
- normalized balance sheet rows for `cashAndEquivalents`, `totalDebt`, and capital-structure context;
- normalized cash flow rows for `freeCashFlow`;
- platform-owned computed metrics for historical growth and margin derivation;
- market snapshot/profile data for price reference and market capitalization where available.

Missing inputs remain `null` and add quality flags. The engine should not invent unavailable source values.

## Assumptions

Every assumption includes:

- `value`
- `source`
- `rationale`
- `editable`
- `unit`
- `qualityFlags`

Default assumptions are deterministic:

- Revenue growth: median available platform-owned historical revenue growth; otherwise editable manual default.
- Operating margin: median available platform-owned operating margin; otherwise latest normalized operating-income margin where possible.
- Tax rate: statement-derived proxy using normalized net income and operating income; otherwise editable manual default.
- Reinvestment rate: statement-derived NOPAT-minus-FCF proxy as a percentage of revenue; otherwise editable manual default.
- WACC: derived from risk-free rate, equity risk premium, beta, debt cost, tax rate, debt weight, and equity weight.
- Terminal growth: half of explicit revenue growth, capped at 3%, and flagged for manual review.

User edits are preserved as `source = "user_override"`.

## FCFF Methodology

Implemented formulas:

- `revenue[t] = revenue[t-1] * (1 + revenueGrowthRate)`
- `operatingIncome[t] = revenue[t] * operatingMargin`
- `nopat[t] = operatingIncome[t] * (1 - taxRate)`
- `reinvestment[t] = max(revenue[t] - revenue[t-1], 0) * reinvestmentRate`
- `fcff[t] = nopat[t] - reinvestment[t]`
- `presentValueFcff[t] = fcff[t] / (1 + wacc)^t`

Terminal value uses the Gordon growth method:

- `terminalValue = fcff[final] * (1 + terminalGrowthRate) / (wacc - terminalGrowthRate)`
- `enterpriseValue = sum(presentValueFcff) + presentValueTerminalValue`
- `equityValue = enterpriseValue - (totalDebt - cashAndEquivalents)`
- `intrinsicValuePerShare = equityValue / sharesDiluted`

If `wacc <= terminalGrowthRate`, terminal value returns `null` and adds a quality flag.

## Sensitivity

The engine produces three deterministic sensitivity matrices:

- WACC versus terminal growth.
- Operating margin versus WACC.
- Operating margin versus terminal growth.

Cells return intrinsic value per share or `null` with quality flags.

Phase 3D adds `sensitivityVisualization` metadata derived from the same deterministic cells. It includes min/max values, per-cell intensity, and tone labels for heatmap rendering. The visualization layer does not alter valuation calculations.

## Persistence

DCF scenarios are persisted in local SQLite table `valuation_scenarios`, separate from fundamentals snapshots and screener row snapshots. Each saved payload includes:

- `schemaVersion`
- scenario assumptions and timestamps
- projection rows
- base financials
- terminal value, enterprise value, equity value, and intrinsic value per share
- sensitivity grids
- formulas
- provider state and quality flags

SQLite remains a local development persistence layer. PostgreSQL/Supabase should replace it through the repository abstraction in later phases.

Phase 3C extends local persistence:

- `valuation_scenarios`: latest pointer and lifecycle state for each scenario.
- `valuation_scenario_versions`: immutable version payloads for every persisted scenario edit.
- `valuation_audit_events`: append-only audit events describing changes.

The latest pointer can change, but historical version payloads and audit events are preserved.

Phase 3D adds:

- `valuation_notes`: immutable analyst notes attached to scenario versions, assumption paths, or warning codes;
- richer reproducibility metadata inside each DCF payload;
- schema/model-versioned assumption import/export payloads.

## Scenario Management

Phase 3C supports a fuller scenario lifecycle:

- list saved scenarios newest first;
- load one saved scenario by id;
- compare saved scenarios on intrinsic value/share and primary assumptions;
- save analyst-provided scenario names without changing calculation behavior;
- rename scenarios;
- duplicate scenarios with `parentScenarioId`;
- archive, restore, and soft delete scenarios without permanently destroying history.
- compare any two saved scenarios or immutable scenario versions;
- export and import editable assumption JSON;
- attach immutable analyst notes.

Routes:

- `GET /api/valuation/dcf/{ticker}/scenarios?limit=10`
- `GET /api/valuation/dcf/{ticker}/scenarios/{scenarioId}`
- `POST /api/valuation/dcf/{ticker}/scenarios/{scenarioId}/versions`
- `PATCH /api/valuation/dcf/{ticker}/scenarios/{scenarioId}/rename`
- `POST /api/valuation/dcf/{ticker}/scenarios/{scenarioId}/duplicate`
- `POST /api/valuation/dcf/{ticker}/scenarios/{scenarioId}/archive`
- `POST /api/valuation/dcf/{ticker}/scenarios/{scenarioId}/restore`
- `DELETE /api/valuation/dcf/{ticker}/scenarios/{scenarioId}`
- `GET /api/valuation/dcf/{ticker}/scenarios/{scenarioId}/history`
- `GET /api/valuation/dcf/{ticker}/comparison?limit=5`
- `GET /api/valuation/dcf/{ticker}/compare?leftScenarioId=&rightScenarioId=`
- `GET /api/valuation/dcf/{ticker}/export/{scenarioId}`
- `POST /api/valuation/dcf/{ticker}/import`
- `GET /api/valuation/dcf/{ticker}/scenarios/{scenarioId}/notes`
- `POST /api/valuation/dcf/{ticker}/scenarios/{scenarioId}/notes`

Scenario comparison is descriptive only. It must not rank securities, recommend actions, or imply buy/sell decisions.

The diff route returns assumption diffs, output diffs, warning diffs, and valuation delta summaries. Optional version id query parameters compare historical immutable versions instead of latest scenario pointers.

## Immutable Versions

Every persisted scenario has immutable versions:

- `versionNumber`
- `versionId`
- `priorVersionId`
- `parentScenarioId`
- `schemaVersion`
- `modelVersion`
- `createdAt`

Every scenario edit appends a new version. Prior versions are not overwritten. The current scenario row stores only the latest payload and workflow status.

## Audit Trail

Audit events record:

- change type;
- field path;
- previous value;
- new value;
- timestamp;
- scenario version id and number.

Examples include `create`, `assumption_update`, `rename`, `duplicate`, `status:archived`, `status:active`, and `status:deleted`.

## Import, Export, And Notes

Assumption export returns:

- `schemaVersion`
- `modelVersion`
- source scenario summary
- editable assumption values
- warnings
- `exportedAt`

Assumption import validates schema and model metadata before building a new saved scenario. Imports do not mutate existing scenarios and do not bypass valuation warnings or quality flags.

Analyst notes are immutable. A note stores text, timestamp, attachment type, scenario id, version id, version number, optional assumption field path, and optional warning code. Phase 3D intentionally omits collaborative editing, identity, permissions, and note deletion.

## Reproducibility Metadata

Each DCF result records a `reproducibility` block:

- statement snapshot references for income statement, balance sheet, and cash flow;
- computed metric references used for historical assumption derivation;
- market data snapshot reference;
- DCF engine, methodology, and model versions;
- sensitivity configuration;
- calculation timestamp chain;
- completeness and quality flags.

This metadata is designed so future model changes can explain which inputs and engine versions produced a historical valuation. Exact replay still depends on durable storage of source snapshots and future migration to production persistence.

## Hardening

The DCF service validates assumption bounds and records issues as quality flags:

- out-of-range assumption values;
- non-integer projection year counts;
- invalid WACC versus terminal growth spread;
- debt/equity capital weight mismatch;
- missing source inputs and zero denominators.

The warning system adds explicit review items for:

- terminal value dominance above 75%;
- perpetual growth above the long-term GDP proxy;
- WACC less than or equal to terminal growth;
- unrealistic operating margins;
- negative reinvestment inconsistency;
- ROIC below WACC with positive growth;
- projection instability;
- missing diluted share assumptions.

Diagnostics are exposed through `GET /api/diagnostics/valuation?ticker=AAPL`, including engine version, methodology version, repository status, saved scenario count, route readiness, latest saved scenario summary, configured assumption bounds, warning rules, repository health, orphaned version count, model version distribution, stale scenario count, note count, and reproducibility completeness.

## Model Refinements

Phase 3C adds incremental support for:

- diluted share trajectory;
- stock-based compensation dilution;
- buyback assumptions;
- projected diluted share count;
- operating cash versus excess cash;
- nullable lease debt, preferred equity, and minority interest;
- refined net debt bridge.

This is not a full equity-compensation or capital-structure engine. Missing values remain nullable and visible.

## Frontend Workbench

`/valuation/[ticker]` renders:

- provider readiness;
- intrinsic value per share;
- editable assumptions;
- scenario naming;
- saved scenario library;
- saved case comparison grid;
- side-by-side scenario diff workflow;
- assumption import/export panel;
- immutable analyst notes panel;
- scenario version history;
- audit event history;
- base/bull/bear duplication controls;
- archive, restore, and soft-delete controls;
- valuation warning section;
- model metadata section;
- WACC inputs;
- base financials;
- FCFF projection table;
- enterprise value bridge;
- sensitivity matrices;
- heatmap-style sensitivity rendering;
- reproducibility metadata;
- formulas and quality flags;
- assumption provenance.

The UI must keep formulas, limitations, missing data, and assumption sources visible.

## Limitations

- No AI/RAG or autonomous valuation agents.
- No trading or order execution.
- No buy/sell recommendation logic.
- Ranking is handled by the separate deterministic Phase 4A ranking engine, not by DCF outputs.
- No FCFE or multi-stage margin fade yet.
- No collaboration, analyst identity, approvals, or note editing yet.
- Macro assumptions require analyst review before investment use.
