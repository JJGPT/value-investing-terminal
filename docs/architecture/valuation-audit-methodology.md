# Valuation Audit Methodology

## Philosophy

Valuation scenarios are analytical records, not disposable UI state. Once a scenario has been persisted, later edits must create new immutable versions instead of overwriting the prior assumptions, projections, warnings, or model outputs.

The latest scenario row is a convenience pointer. The durable audit record is the combination of immutable version payloads and audit events.

Phase 3D extends the audit record with side-by-side scenario diffs, schema/model-versioned assumption import/export, reproducibility metadata, and immutable analyst notes.

## Scenario Lifecycle

Supported lifecycle states:

- `active`: visible in default scenario lists and eligible for latest-scenario retrieval.
- `archived`: hidden by default but restorable.
- `deleted`: soft-deleted and hidden by default; history remains preserved.

Lifecycle actions:

- rename;
- duplicate;
- archive;
- restore;
- soft delete.

No lifecycle action permanently destroys valuation history.

## Immutable Versions

Each saved scenario version records:

- `versionNumber`
- `versionId`
- `priorVersionId`
- `parentScenarioId`
- `schemaVersion`
- `modelVersion`
- `createdAt`
- full DCF payload

New versions are created for assumption edits and lifecycle changes.

## Audit Events

Audit events record:

- `changeType`
- `fieldPath`
- `previousValue`
- `newValue`
- `createdAt`
- `versionId`
- `versionNumber`

Events are meant for analyst review and reproducibility, not compliance-grade legal audit. A later production database should add user identity, workspace id, request id, and approval state.

## Scenario Diff Methodology

The diff system compares two saved DCF payloads. Inputs can be latest scenario ids or explicit immutable version ids.

Diff output includes:

- assumption diffs by field path;
- output diffs for enterprise value, equity value, intrinsic value/share, net debt, terminal value, and projected shares;
- warning diffs grouped as added, removed, and shared;
- valuation delta summaries with absolute and percent deltas.

Diffs are descriptive workflow tools. They do not rank scenarios or produce investment recommendations.

## Model Provenance

Each DCF result stores:

- `dcfEngineVersion`
- `valuationMethodologyVersion`
- `modelVersion`
- `computationTimestamp`

Historical scenarios should be interpreted against the model metadata persisted with that version.

## Reproducibility Metadata

Each DCF result also stores:

- normalized statement references used by the model;
- computed metric references used for historical assumption derivation;
- market data snapshot reference;
- sensitivity configuration;
- calculation timestamp chain;
- completeness and quality flags.

This metadata makes the historical calculation explainable after future engine changes. Exact replay still requires durable storage of source snapshots in later production persistence.

## Import And Export

Assumption exports include `schemaVersion`, `modelVersion`, source scenario metadata, editable assumption values, warnings, and export timestamp.

Imports are validated before execution:

- unsupported schema versions are rejected;
- missing model version is rejected;
- imported assumptions create a new scenario instead of mutating existing history;
- imported values still pass through deterministic validation, warnings, and immutable persistence.

Exports and imports must never include provider credentials.

## Immutable Notes

Analyst notes attach to:

- a scenario version;
- an assumption field path;
- a warning code.

Notes are append-only and timestamped. Phase 3D does not support note editing, deletion, user identity, collaboration, or approvals.

## Warning Semantics

Warnings are review prompts. They are not investment conclusions.

Current warning categories:

- terminal value dominance;
- terminal growth above GDP proxy;
- WACC less than or equal to terminal growth;
- unrealistic operating margins;
- negative reinvestment inconsistency;
- ROIC below WACC with positive growth;
- projection instability;
- missing diluted share assumptions.

Warnings should remain visible in API responses and the valuation UI.

## Limitations

- No AI-generated audit interpretation.
- No autonomous valuation agent.
- No buy/sell recommendation.
- No permanent delete.
- No approval workflow, analyst identity, or collaborative notes yet.
- No full capital-structure or equity-compensation engine yet.
