import Link from "next/link";

import type {
  DCFProjectionYear,
  DCFResult,
  SensitivityMatrix,
  ValuationAssumption,
  ValuationAssumptionExport,
  ValuationAuditEvent,
  ValuationScenarioCollection,
  ValuationScenarioComparison,
  ValuationScenarioComparisonAssumptions,
  ValuationScenarioDiff,
  ValuationScenarioHistory,
  ValuationNotesResult,
  ValuationWarning,
} from "@value-terminal/types";

import { ApiState } from "../../../components/data-status/api-state";
import { TerminalShell } from "../../../components/shell/terminal-shell";
import { PlaceholderCard } from "../../../components/ui/placeholder-card";
import { StatusList } from "../../../components/ui/status-list";
import {
  addDcfNote,
  createDcfScenarioVersion,
  duplicateDcfScenario,
  exportDcfAssumptions,
  getDcfComparison,
  getDcfScenario,
  getDcfScenarioDiff,
  getDcfScenarioHistory,
  getDcfValuation,
  importDcfAssumptions,
  listDcfNotes,
  listDcfScenarios,
  renameDcfScenario,
  runDcfValuation,
  setDcfScenarioLifecycle,
} from "../../../lib/api/client";

type ValuationPageProps = {
  params: Promise<{
    ticker: string;
  }>;
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
};

type AssumptionInputProps = {
  label: string;
  name: string;
  assumption: ValuationAssumption;
  step?: string;
};

function getQueryValue(value: string | string[] | undefined) {
  if (Array.isArray(value)) {
    return value[0] ?? "";
  }

  return value ?? "";
}

function parseDecimal(value: string | string[] | undefined) {
  const parsed = Number(getQueryValue(value));

  return Number.isFinite(parsed) ? parsed : null;
}

function buildOverrides(params: Record<string, string | string[] | undefined>) {
  if (getQueryValue(params.run) !== "1") {
    return null;
  }

  const discountRate = compactObject({
    riskFreeRate: parseDecimal(params.riskFreeRate),
    equityRiskPremium: parseDecimal(params.equityRiskPremium),
    beta: parseDecimal(params.beta),
    preTaxCostOfDebt: parseDecimal(params.preTaxCostOfDebt),
    taxRate: parseDecimal(params.taxRate),
    debtWeight: parseDecimal(params.debtWeight),
    equityWeight: parseDecimal(params.equityWeight),
    wacc: parseDecimal(params.wacc),
  });
  const growth = compactObject({
    revenueGrowthRate: parseDecimal(params.revenueGrowthRate),
  });
  const margin = compactObject({
    operatingMargin: parseDecimal(params.operatingMargin),
  });
  const reinvestment = compactObject({
    reinvestmentRate: parseDecimal(params.reinvestmentRate),
  });
  const shareCount = compactObject({
    dilutedShareGrowthRate: parseDecimal(params.dilutedShareGrowthRate),
    stockBasedCompensationDilutionRate: parseDecimal(
      params.stockBasedCompensationDilutionRate,
    ),
    buybackRate: parseDecimal(params.buybackRate),
  });
  const netDebt = compactObject({
    operatingCashPercentOfRevenue: parseDecimal(
      params.operatingCashPercentOfRevenue,
    ),
    leaseDebt: parseDecimal(params.leaseDebt),
    preferredEquity: parseDecimal(params.preferredEquity),
    minorityInterest: parseDecimal(params.minorityInterest),
  });
  const terminalValue = compactObject({
    terminalGrowthRate: parseDecimal(params.terminalGrowthRate),
  });
  const scenarioName = getQueryValue(params.scenarioName);

  return compactObject({
    scenarioName: scenarioName || null,
    discountRate,
    growth,
    margin,
    reinvestment,
    shareCount,
    netDebt,
    terminalValue,
  });
}

function compactObject(values: Record<string, unknown>) {
  return Object.fromEntries(
    Object.entries(values).filter(([, value]) => {
      if (value === null || value === undefined) {
        return false;
      }

      if (typeof value === "object" && !Array.isArray(value)) {
        return Object.keys(value).length > 0;
      }

      return true;
    }),
  );
}

function providerTitle(result: DCFResult) {
  if (result.provider.state === "connected") {
    return "Valuation inputs connected";
  }

  if (result.provider.state === "degraded") {
    return "Valuation inputs degraded";
  }

  if (result.provider.state === "not_implemented") {
    return "Valuation inputs not implemented";
  }

  return "Valuation inputs not connected";
}

function formatText(value: string | null | undefined) {
  return value ?? "Unavailable";
}

function formatNumber(value: number | null | undefined) {
  if (value === null || value === undefined) {
    return "Unavailable";
  }

  return new Intl.NumberFormat("en-US", {
    maximumFractionDigits: 2,
  }).format(value);
}

function formatMoney(
  value: number | null | undefined,
  currency: string | null | undefined,
  compact = true,
) {
  if (value === null || value === undefined) {
    return "Unavailable";
  }

  const formatted = new Intl.NumberFormat("en-US", {
    maximumFractionDigits: 2,
    notation: compact && Math.abs(value) >= 1_000_000 ? "compact" : "standard",
  }).format(value);

  return currency ? `${formatted} ${currency}` : formatted;
}

function formatPercent(value: number | null | undefined) {
  if (value === null || value === undefined) {
    return "Unavailable";
  }

  return new Intl.NumberFormat("en-US", {
    maximumFractionDigits: 2,
    style: "percent",
  }).format(value);
}

function inputValue(assumption: ValuationAssumption) {
  return assumption.value === null ? "" : String(assumption.value);
}

function assumptionFlags(assumption: ValuationAssumption) {
  return assumption.qualityFlags.length
    ? assumption.qualityFlags.join(", ")
    : "none";
}

function AssumptionInput({
  label,
  name,
  assumption,
  step = "0.001",
}: AssumptionInputProps) {
  return (
    <label className="border-line bg-graphite2/60 block border p-4">
      <span className="text-ink block text-sm">{label}</span>
      <input
        className="border-line bg-obsidian text-ink mt-3 w-full border px-3 py-2 font-mono text-sm focus:outline-none focus:ring-1 focus:ring-accent"
        defaultValue={inputValue(assumption)}
        inputMode="decimal"
        name={name}
        step={step}
        type="number"
      />
      <span className="text-muted mt-3 block font-mono text-[11px] uppercase">
        {assumption.source} | {assumption.unit}
      </span>
      <span className="text-muted mt-2 block text-xs leading-5">
        {assumption.rationale}
      </span>
      <span className="text-muted mt-2 block font-mono text-[11px] uppercase">
        Flags: {assumptionFlags(assumption)}
      </span>
    </label>
  );
}

function ProjectionTable({
  projections,
  currency,
}: {
  projections: DCFProjectionYear[];
  currency: string | null;
}) {
  return (
    <div className="border-line overflow-hidden border">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[940px] border-collapse text-left text-sm">
          <thead className="bg-graphite2 text-muted font-mono text-[11px] uppercase">
            <tr>
              {[
                "Year",
                "Revenue",
                "Growth",
                "Operating income",
                "Tax",
                "NOPAT",
                "Reinvestment",
                "FCFF",
                "Discount factor",
                "PV FCFF",
              ].map((column) => (
                <th key={column} className="border-line border-b px-4 py-3">
                  {column}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-line divide-y">
            {projections.map((row) => (
              <tr key={row.year} className="bg-panel/60">
                <td className="text-ink px-4 py-3 font-mono text-xs">
                  {row.year}
                </td>
                <td className="text-ink px-4 py-3">
                  {formatMoney(row.revenue, currency)}
                </td>
                <td className="text-ink px-4 py-3">
                  {formatPercent(row.revenueGrowthRate)}
                </td>
                <td className="text-ink px-4 py-3">
                  {formatMoney(row.operatingIncome, currency)}
                </td>
                <td className="text-ink px-4 py-3">
                  {formatPercent(row.taxRate)}
                </td>
                <td className="text-ink px-4 py-3">
                  {formatMoney(row.nopat, currency)}
                </td>
                <td className="text-ink px-4 py-3">
                  {formatMoney(row.reinvestment, currency)}
                </td>
                <td className="text-ink px-4 py-3">
                  {formatMoney(row.fcff, currency)}
                </td>
                <td className="text-ink px-4 py-3">
                  {formatNumber(row.discountFactor)}
                </td>
                <td className="text-ink px-4 py-3">
                  {formatMoney(row.presentValueFcff, currency)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function sensitivityLabel(variable: SensitivityMatrix["rowVariable"]) {
  if (variable === "wacc") {
    return "WACC";
  }

  if (variable === "terminalGrowthRate") {
    return "Terminal growth";
  }

  return "Operating margin";
}

function SensitivityMatrixView({
  matrix,
  currency,
}: {
  matrix: SensitivityMatrix;
  currency: string | null;
}) {
  const numericValues = matrix.cells
    .flat()
    .map((cell) => cell.intrinsicValuePerShare)
    .filter((value): value is number => value !== null && value !== undefined);
  const minimum = numericValues.length ? Math.min(...numericValues) : null;
  const maximum = numericValues.length ? Math.max(...numericValues) : null;

  return (
    <div className="border-line overflow-hidden border">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[680px] border-collapse text-left text-sm">
          <thead className="bg-graphite2 text-muted font-mono text-[11px] uppercase">
            <tr>
              <th className="border-line border-b px-4 py-3">
                {sensitivityLabel(matrix.rowVariable)} /{" "}
                {sensitivityLabel(matrix.columnVariable)}
              </th>
              {matrix.columnValues.map((value) => (
                <th
                  key={`${matrix.columnVariable}-${value}`}
                  className="border-line border-b px-4 py-3"
                >
                  {formatPercent(value)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-line divide-y">
            {matrix.rowValues.map((rowValue, rowIndex) => (
              <tr
                key={`${matrix.rowVariable}-${rowValue}`}
                className="bg-panel/60"
              >
                <td className="text-ink px-4 py-3 font-mono text-xs">
                  {formatPercent(rowValue)}
                </td>
                {matrix.columnValues.map((columnValue, columnIndex) => {
                  const cell = matrix.cells[rowIndex]?.[columnIndex];

                  return (
                    <td
                      key={`${rowValue}-${columnValue}`}
                      className="text-ink border-line/60 px-4 py-3 transition"
                      style={sensitivityCellStyle(
                        cell?.intrinsicValuePerShare,
                        minimum,
                        maximum,
                      )}
                      title={`${sensitivityLabel(
                        matrix.rowVariable,
                      )}: ${formatPercent(rowValue)} | ${sensitivityLabel(
                        matrix.columnVariable,
                      )}: ${formatPercent(columnValue)}`}
                    >
                      {formatMoney(
                        cell?.intrinsicValuePerShare,
                        currency,
                        false,
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function sensitivityCellStyle(
  value: number | null | undefined,
  minimum: number | null,
  maximum: number | null,
) {
  if (value === null || value === undefined || minimum === null || maximum === null) {
    return undefined;
  }

  const intensity = maximum === minimum ? 0.5 : (value - minimum) / (maximum - minimum);
  const alpha = 0.16 + intensity * 0.42;

  return {
    backgroundColor: `rgba(34, 211, 238, ${alpha.toFixed(3)})`,
  };
}

function qualityFlags(flags: string[]) {
  if (!flags.length) {
    return "none";
  }

  return flags.join(", ");
}

function assumptionProvenance(result: DCFResult) {
  return [
    {
      label: "Revenue growth",
      assumption: result.scenario.growth.revenueGrowthRate,
    },
    {
      label: "Operating margin",
      assumption: result.scenario.margin.operatingMargin,
    },
    {
      label: "Reinvestment rate",
      assumption: result.scenario.reinvestment.reinvestmentRate,
    },
    { label: "Tax rate", assumption: result.scenario.discountRate.taxRate },
    { label: "WACC", assumption: result.scenario.discountRate.wacc },
    {
      label: "Terminal growth",
      assumption: result.scenario.terminalValue.terminalGrowthRate,
    },
  ].map((item) => ({
    label: item.label,
    status: `${item.assumption.source} | flags: ${assumptionFlags(
      item.assumption,
    )}`,
  }));
}

function scenarioUrl(ticker: string, scenarioId: string | null) {
  if (!scenarioId) {
    return `/valuation/${ticker}`;
  }

  return `/valuation/${ticker}?scenario=${encodeURIComponent(scenarioId)}`;
}

function SavedScenarioList({
  ticker,
  activeScenarioId,
  collection,
}: {
  ticker: string;
  activeScenarioId: string | null;
  collection: ValuationScenarioCollection | null;
}) {
  const scenarios = collection?.scenarios ?? [];

  return (
    <div className="space-y-3">
      {scenarios.length ? (
        scenarios.map((scenario) => (
          <Link
            className={`border-line block border p-4 transition ${
              activeScenarioId === scenario.scenarioId
                ? "bg-accent/10 text-accent"
                : "bg-graphite2/60 text-muted hover:text-accent"
            }`}
            href={scenarioUrl(ticker, scenario.scenarioId)}
            key={scenario.scenarioId ?? scenario.updatedAt}
          >
            <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <p className="text-ink text-sm font-semibold">
                  {scenario.name}
                </p>
                <p className="text-muted mt-1 font-mono text-[11px] uppercase">
                  {scenario.updatedAt ?? "Unavailable"}
                </p>
              </div>
              <span className="font-mono text-[11px] uppercase">
                {formatMoney(
                  scenario.intrinsicValuePerShare,
                  scenario.currency,
                  false,
                )}
              </span>
            </div>
          </Link>
        ))
      ) : (
        <p className="text-muted text-sm leading-6">
          No saved DCF scenarios yet. Run and save the current case to create
          the first scenario.
        </p>
      )}
    </div>
  );
}

function ComparisonTable({
  comparison,
}: {
  comparison: ValuationScenarioComparison | null;
}) {
  const rows = comparison?.rows ?? [];

  if (!rows.length) {
    return (
      <p className="text-muted text-sm leading-6">
        Save at least one scenario to populate the comparison grid.
      </p>
    );
  }

  return (
    <div className="border-line overflow-hidden border">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[980px] border-collapse text-left text-sm">
          <thead className="bg-graphite2 text-muted font-mono text-[11px] uppercase">
            <tr>
              {[
                "Scenario",
                "Intrinsic / share",
                "Revenue growth",
                "Operating margin",
                "WACC",
                "Terminal growth",
                "Flags",
              ].map((column) => (
                <th className="border-line border-b px-4 py-3" key={column}>
                  {column}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-line divide-y">
            {rows.map((row) => (
              <tr className="bg-panel/60" key={row.scenarioId}>
                <td className="text-ink px-4 py-3">
                  <div>
                    <p>{row.name}</p>
                    <p className="text-muted mt-1 font-mono text-[11px] uppercase">
                      {row.updatedAt ?? "Unavailable"}
                    </p>
                  </div>
                </td>
                <td className="text-ink px-4 py-3">
                  {formatMoney(row.intrinsicValuePerShare, row.currency, false)}
                </td>
                <td className="text-ink px-4 py-3">
                  {formatComparisonPercent(
                    row.assumptions,
                    "revenueGrowthRate",
                  )}
                </td>
                <td className="text-ink px-4 py-3">
                  {formatComparisonPercent(row.assumptions, "operatingMargin")}
                </td>
                <td className="text-ink px-4 py-3">
                  {formatComparisonPercent(row.assumptions, "wacc")}
                </td>
                <td className="text-ink px-4 py-3">
                  {formatComparisonPercent(
                    row.assumptions,
                    "terminalGrowthRate",
                  )}
                </td>
                <td className="text-muted max-w-[220px] px-4 py-3 font-mono text-[11px] uppercase">
                  {qualityFlags(row.qualityFlags)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function formatComparisonPercent(
  assumptions: ValuationScenarioComparisonAssumptions,
  key: keyof ValuationScenarioComparisonAssumptions,
) {
  return formatPercent(assumptions[key]);
}

function WarningList({ warnings }: { warnings: ValuationWarning[] }) {
  if (!warnings.length) {
    return (
      <p className="text-muted text-sm leading-6">
        No valuation warnings on the current scenario.
      </p>
    );
  }

  return (
    <div className="border-line divide-line divide-y border">
      {warnings.map((warning) => (
        <div className="px-4 py-3" key={warning.code}>
          <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
            <p className="text-ink text-sm">{warning.code}</p>
            <span className="text-amber font-mono text-[11px] uppercase">
              {warning.severity}
            </span>
          </div>
          <p className="text-muted mt-2 text-sm leading-6">{warning.message}</p>
          <p className="text-muted mt-2 font-mono text-[11px] uppercase">
            Value: {formatNumber(warning.value)}
          </p>
        </div>
      ))}
    </div>
  );
}

function HistoryPanel({
  history,
}: {
  history: ValuationScenarioHistory | null;
}) {
  if (!history) {
    return (
      <p className="text-muted text-sm leading-6">
        Save the scenario to create immutable version history.
      </p>
    );
  }

  return (
    <div className="grid gap-4 2xl:grid-cols-2">
      <div>
        <p className="text-accent font-mono text-[11px] uppercase">Versions</p>
        <StatusList
          items={history.versions.slice(0, 6).map((version) => ({
            label: `v${version.versionNumber ?? "?"} ${version.name}`,
            status: version.updatedAt ?? "Unavailable",
          }))}
        />
      </div>
      <div>
        <p className="text-accent font-mono text-[11px] uppercase">
          Audit events
        </p>
        <div className="border-line divide-line divide-y border">
          {history.auditEvents.slice(0, 8).map((event) => (
            <AuditEventRow event={event} key={event.id} />
          ))}
        </div>
      </div>
    </div>
  );
}

function ScenarioDiffPanel({
  ticker,
  activeScenarioId,
  collection,
  diff,
}: {
  ticker: string;
  activeScenarioId: string;
  collection: ValuationScenarioCollection | null;
  diff: ValuationScenarioDiff | null;
}) {
  const scenarios = collection?.scenarios ?? [];

  return (
    <div className="space-y-4">
      <form className="grid gap-3 md:grid-cols-[1fr_1fr_auto]" method="GET">
        <label className="border-line bg-graphite2/60 block border p-3">
          <span className="text-muted font-mono text-[11px] uppercase">
            Left scenario
          </span>
          <select
            className="bg-obsidian border-line text-ink mt-2 w-full border px-3 py-2 text-sm"
            defaultValue={diff?.left.scenarioId ?? scenarios[1]?.scenarioId ?? activeScenarioId}
            name="leftScenario"
          >
            {scenarios.map((scenario) => (
              <option
                key={scenario.scenarioId ?? scenario.name}
                value={scenario.scenarioId ?? ""}
              >
                {scenario.name}
              </option>
            ))}
          </select>
        </label>
        <label className="border-line bg-graphite2/60 block border p-3">
          <span className="text-muted font-mono text-[11px] uppercase">
            Right scenario
          </span>
          <select
            className="bg-obsidian border-line text-ink mt-2 w-full border px-3 py-2 text-sm"
            defaultValue={diff?.right.scenarioId ?? activeScenarioId}
            name="rightScenario"
          >
            {scenarios.map((scenario) => (
              <option
                key={scenario.scenarioId ?? scenario.name}
                value={scenario.scenarioId ?? ""}
              >
                {scenario.name}
              </option>
            ))}
          </select>
        </label>
        <input name="scenario" type="hidden" value={activeScenarioId} />
        <button
          className="border-line text-muted hover:text-accent self-end border px-4 py-2 font-mono text-[11px] uppercase transition"
          type="submit"
        >
          Compare
        </button>
      </form>
      {diff ? (
        <>
          <StatusList
            items={[
              {
                label: "Left",
                status: `${diff.left.name} v${diff.left.versionNumber ?? "?"}`,
              },
              {
                label: "Right",
                status: `${diff.right.name} v${diff.right.versionNumber ?? "?"}`,
              },
              {
                label: "Value/share delta",
                status: formatNumber(
                  diff.valuationDelta.intrinsicValuePerShare?.delta,
                ),
              },
              {
                label: "Warnings added/removed",
                status: `${diff.warningDiffs.added.length}/${diff.warningDiffs.removed.length}`,
              },
            ]}
          />
          <DiffRows title="Assumption diffs" rows={diff.assumptionDiffs} />
          <DiffRows title="Output diffs" rows={diff.outputDiffs} />
        </>
      ) : (
        <p className="text-muted text-sm leading-6">
          Save at least two scenarios to enable side-by-side scenario diffing.
        </p>
      )}
      <Link
        className="text-muted hover:text-accent font-mono text-[11px] uppercase"
        href={`/valuation/${ticker}`}
      >
        Clear comparison
      </Link>
    </div>
  );
}

function DiffRows({
  title,
  rows,
}: {
  title: string;
  rows: ValuationScenarioDiff["assumptionDiffs"];
}) {
  if (!rows.length) {
    return (
      <p className="text-muted text-sm leading-6">
        {title}: no differences.
      </p>
    );
  }

  return (
    <div>
      <p className="text-accent mb-2 font-mono text-[11px] uppercase">
        {title}
      </p>
      <div className="border-line divide-line divide-y border">
        {rows.slice(0, 10).map((row) => (
          <div
            className="grid gap-2 px-4 py-3 text-sm md:grid-cols-[1.2fr_1fr_1fr_1fr]"
            key={row.fieldPath}
          >
            <span className="text-ink font-mono text-xs">{row.fieldPath}</span>
            <span className="text-muted">{String(row.leftValue ?? "null")}</span>
            <span className="text-muted">{String(row.rightValue ?? "null")}</span>
            <span className="text-ink">{formatNumber(row.delta)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function NotesPanel({ notes }: { notes: ValuationNotesResult | null }) {
  const rows = notes?.notes ?? [];

  if (!rows.length) {
    return (
      <p className="text-muted text-sm leading-6">
        No analyst notes attached to this scenario yet.
      </p>
    );
  }

  return (
    <div className="border-line divide-line divide-y border">
      {rows.slice(0, 8).map((note) => (
        <div className="px-4 py-3" key={note.id}>
          <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
            <p className="text-ink text-sm">{note.attachmentType}</p>
            <span className="text-muted font-mono text-[11px] uppercase">
              v{note.versionNumber ?? "?"}
            </span>
          </div>
          <p className="text-muted mt-2 text-sm leading-6 whitespace-pre-wrap">
            {note.text}
          </p>
          <p className="text-muted mt-2 font-mono text-[11px] uppercase">
            {note.fieldPath ?? note.warningCode ?? "scenario"} | {note.createdAt}
          </p>
        </div>
      ))}
    </div>
  );
}

function ImportExportPanel({
  exported,
}: {
  exported: ValuationAssumptionExport | null;
}) {
  return (
    <div className="space-y-4">
      {exported ? (
        <StatusList
          items={[
            { label: "Schema version", status: String(exported.schemaVersion) },
            { label: "Model version", status: exported.modelVersion },
            { label: "Exported", status: exported.exportedAt },
            {
              label: "Source scenario",
              status: exported.sourceScenario.name,
            },
          ]}
        />
      ) : (
        <p className="text-muted text-sm leading-6">
          Save the scenario before exporting assumptions.
        </p>
      )}
      <form className="space-y-3" method="GET">
        <input name="action" type="hidden" value="import" />
        <label className="block">
          <span className="text-muted font-mono text-[11px] uppercase">
            Import assumption JSON
          </span>
          <textarea
            className="border-line bg-obsidian text-ink mt-2 min-h-28 w-full border p-3 font-mono text-xs focus:outline-none focus:ring-1 focus:ring-accent"
            name="importPayload"
            placeholder='{"schemaVersion":1,"modelVersion":"platform-fcff-dcf-v1","assumptions":{...}}'
          />
        </label>
        <button
          className="border-line text-muted hover:text-accent border px-4 py-2 font-mono text-[11px] uppercase transition"
          type="submit"
        >
          Import as scenario
        </button>
      </form>
    </div>
  );
}

function ReproducibilityPanel({ result }: { result: DCFResult }) {
  const reproducibility = result.reproducibility;

  if (!reproducibility) {
    return (
      <p className="text-muted text-sm leading-6">
        Reproducibility metadata is unavailable for this historical payload.
      </p>
    );
  }

  return (
    <StatusList
      items={[
        {
          label: "Income statement",
          status:
            reproducibility.statementSnapshotReferences.incomeStatement
              ?.fiscalYear ?? "missing",
        },
        {
          label: "Balance sheet",
          status:
            reproducibility.statementSnapshotReferences.balanceSheet
              ?.fiscalYear ?? "missing",
        },
        {
          label: "Cash flow",
          status:
            reproducibility.statementSnapshotReferences.cashFlowStatement
              ?.fiscalYear ?? "missing",
        },
        {
          label: "Computed metrics used",
          status: String(reproducibility.metricSnapshotsUsed.length),
        },
        {
          label: "Market data as of",
          status: reproducibility.marketDataSnapshotReference.asOf ?? "missing",
        },
        {
          label: "Timestamp chain",
          status:
            reproducibility.calculationTimestampChain.valuationComputedAt,
        },
        {
          label: "Reproducibility flags",
          status: qualityFlags(reproducibility.qualityFlags),
        },
      ]}
    />
  );
}

function AuditEventRow({ event }: { event: ValuationAuditEvent }) {
  return (
    <div className="px-4 py-3">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <p className="text-ink text-sm">{event.changeType}</p>
        <span className="text-muted font-mono text-[11px] uppercase">
          v{event.versionNumber}
        </span>
      </div>
      <p className="text-muted mt-2 font-mono text-[11px] uppercase">
        {event.fieldPath ?? "scenario"}
      </p>
      <p className="text-muted mt-2 text-xs leading-5">
        {String(event.previousValue ?? "none")} {"->"}{" "}
        {String(event.newValue ?? "none")}
      </p>
    </div>
  );
}

function LifecycleLink({
  action,
  label,
  scenarioId,
}: {
  action: "archive" | "restore" | "delete";
  label: string;
  scenarioId: string;
}) {
  return (
    <Link
      className="border-line text-muted hover:text-accent border px-3 py-2 font-mono text-[11px] uppercase transition"
      href={`?action=${action}&scenario=${encodeURIComponent(scenarioId)}`}
    >
      {label}
    </Link>
  );
}

async function runLifecycleAction(
  ticker: string,
  params: Record<string, string | string[] | undefined>,
) {
  const action = getQueryValue(params.action);
  const scenarioId = getQueryValue(params.scenario);
  const scenarioName = getQueryValue(params.scenarioName);

  if (!action || !scenarioId) {
    return null;
  }

  if (action === "rename") {
    return renameDcfScenario(ticker, scenarioId, scenarioName);
  }

  if (action === "duplicate") {
    return duplicateDcfScenario(ticker, scenarioId, scenarioName);
  }

  if (action === "archive" || action === "restore" || action === "delete") {
    return setDcfScenarioLifecycle(ticker, scenarioId, action);
  }

  return null;
}

async function runImportAction(
  ticker: string,
  params: Record<string, string | string[] | undefined>,
) {
  if (getQueryValue(params.action) !== "import") {
    return null;
  }

  const rawPayload = getQueryValue(params.importPayload);

  if (!rawPayload.trim()) {
    return null;
  }

  try {
    return importDcfAssumptions(
      ticker,
      JSON.parse(rawPayload) as Record<string, unknown>,
    );
  } catch {
    return null;
  }
}

async function runNoteAction(
  ticker: string,
  params: Record<string, string | string[] | undefined>,
) {
  if (getQueryValue(params.action) !== "note") {
    return null;
  }

  const scenarioId = getQueryValue(params.scenario);
  const text = getQueryValue(params.noteText);

  if (!scenarioId || !text.trim()) {
    return null;
  }

  const attachmentType =
    (getQueryValue(params.attachmentType) as "scenario_version" | "assumption" | "warning") ||
    "scenario_version";
  const attachmentTarget = getQueryValue(params.fieldPath) || null;

  return addDcfNote(ticker, scenarioId, {
    attachmentType,
    fieldPath: attachmentType === "assumption" ? attachmentTarget : null,
    warningCode: attachmentType === "warning" ? attachmentTarget : null,
    text,
  });
}

export default async function ValuationPage({
  params,
  searchParams,
}: ValuationPageProps) {
  const { ticker } = await params;
  const query = searchParams ? await searchParams : {};
  const normalizedTicker = ticker.toUpperCase();
  const importResult = await runImportAction(normalizedTicker, query);
  const lifecycleResult = await runLifecycleAction(normalizedTicker, query);
  const overrides = buildOverrides(query);
  const scenarioId =
    importResult?.ok
      ? importResult.data.scenario.id
      : lifecycleResult?.ok && lifecycleResult.data.scenario.status !== "deleted"
        ? lifecycleResult.data.scenario.id
        : getQueryValue(query.scenario);
  const valuationResult = importResult?.ok
    ? importResult
    : overrides
    ? getQueryValue(query.action) === "version" && scenarioId
      ? await createDcfScenarioVersion(normalizedTicker, scenarioId, overrides)
      : await runDcfValuation(normalizedTicker, overrides)
    : scenarioId
      ? await getDcfScenario(normalizedTicker, scenarioId)
      : await getDcfValuation(normalizedTicker);
  const [scenarioCollectionResult, comparisonResult] = await Promise.all([
    listDcfScenarios(normalizedTicker, 10),
    getDcfComparison(normalizedTicker, 5),
  ]);
  const result = valuationResult.ok ? valuationResult.data : null;
  const noteResult = result ? await runNoteAction(normalizedTicker, query) : null;
  const historyResult = result
    ? await getDcfScenarioHistory(normalizedTicker, result.scenario.id)
    : null;
  const notesResult = result
    ? await listDcfNotes(normalizedTicker, result.scenario.id)
    : null;
  const exportResult = result
    ? await exportDcfAssumptions(normalizedTicker, result.scenario.id)
    : null;
  const currency = result?.baseFinancials.currency ?? null;
  const scenarioCollection = scenarioCollectionResult.ok
    ? scenarioCollectionResult.data
    : null;
  const comparison = comparisonResult.ok ? comparisonResult.data : null;
  const history = historyResult?.ok ? historyResult.data : null;
  const notes = notesResult?.ok ? notesResult.data : null;
  const exported = exportResult?.ok ? exportResult.data : null;
  const isPersistedScenario = Boolean(
    result &&
    scenarioCollection?.scenarios.some(
      (scenario) => scenario.scenarioId === result.scenario.id,
    ),
  );
  const leftScenarioId =
    getQueryValue(query.leftScenario) ||
    scenarioCollection?.scenarios.find(
      (scenario) => scenario.scenarioId !== result?.scenario.id,
    )?.scenarioId ||
    "";
  const rightScenarioId = getQueryValue(query.rightScenario) || result?.scenario.id || "";
  const diffResult =
    leftScenarioId && rightScenarioId && leftScenarioId !== rightScenarioId
      ? await getDcfScenarioDiff(
          normalizedTicker,
          leftScenarioId,
          rightScenarioId,
        )
      : null;
  const scenarioDiff = diffResult?.ok ? diffResult.data : null;

  return (
    <TerminalShell
      eyebrow={`Valuation / ${normalizedTicker}`}
      title="DCF valuation workbench."
      description="Transparent FCFF valuation using normalized financial statements, platform-owned metrics, editable assumptions, and explicit quality flags."
    >
      <section className="mb-4 flex flex-wrap gap-2">
        <Link
          className="border-line text-muted hover:text-accent border px-3 py-2 font-mono text-[11px] uppercase transition"
          href={`/company/${normalizedTicker}`}
        >
          Company
        </Link>
        <Link
          className="border-line text-muted hover:text-accent border px-3 py-2 font-mono text-[11px] uppercase transition"
          href={`/screener`}
        >
          Screener
        </Link>
      </section>

      {noteResult ? (
        <div className="mb-4">
          <ApiState
            title={noteResult.ok ? "Analyst note saved" : "Analyst note failed"}
            message={
              noteResult.ok
                ? "Immutable note attached to the current scenario version."
                : noteResult.error.message
            }
            endpoint={
              noteResult.ok
                ? `/api/valuation/dcf/${normalizedTicker}/scenarios/${noteResult.data.scenarioId}/notes`
                : noteResult.error.endpoint
            }
          />
        </div>
      ) : null}

      {!valuationResult.ok ? (
        <PlaceholderCard
          label="Valuation API"
          title="DCF service unavailable"
          description="The valuation workbench could not reach the backend valuation route."
        >
          <ApiState
            title="Valuation API unavailable"
            message={valuationResult.error.message}
            endpoint={valuationResult.error.endpoint}
          />
        </PlaceholderCard>
      ) : null}

      {result ? (
        <section className="grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
          <PlaceholderCard
            label="Model state"
            title="Input readiness"
            description="Provider status reflects the normalized statements, computed metrics, and market snapshot used by the DCF engine."
          >
            <ApiState
              title={providerTitle(result)}
              message={result.message}
              provider={result.provider}
              endpoint={`/api/valuation/dcf/${normalizedTicker}`}
            />
          </PlaceholderCard>

          <PlaceholderCard
            label="Output"
            title="Intrinsic value per share"
            description="Platform-calculated value output from the current editable scenario."
          >
            <div className="border-line bg-graphite2/70 border p-5">
              <p className="text-accent font-mono text-[11px] uppercase">
                Intrinsic value / share
              </p>
              <p className="text-ink mt-3 font-mono text-3xl font-semibold">
                {formatMoney(result.intrinsicValuePerShare, currency, false)}
              </p>
              <p className="text-muted mt-3 text-sm leading-6">
                This is not a buy/sell recommendation.
              </p>
            </div>
          </PlaceholderCard>

          <PlaceholderCard
            label="Warnings"
            title="Valuation warning review"
            description="Warnings identify assumptions or outputs that need analyst review before the model is relied on."
          >
            <WarningList warnings={result.warnings} />
          </PlaceholderCard>

          <PlaceholderCard
            label="Model provenance"
            title="Model metadata"
            description="Engine and methodology versions are persisted with each immutable scenario version."
          >
            <StatusList
              items={[
                {
                  label: "DCF engine",
                  status: result.modelMetadata.dcfEngineVersion,
                },
                {
                  label: "Methodology",
                  status: result.modelMetadata.valuationMethodologyVersion,
                },
                {
                  label: "Computation timestamp",
                  status: result.modelMetadata.computationTimestamp,
                },
                {
                  label: "Scenario status",
                  status: result.scenario.status,
                },
                {
                  label: "Scenario version",
                  status: `v${result.scenario.versionNumber ?? "unsaved"}`,
                },
                {
                  label: "Prior version",
                  status: result.scenario.priorVersionId ?? "none",
                },
              ]}
            />
          </PlaceholderCard>

          <PlaceholderCard
            label="Reproducibility"
            title="Snapshot references"
            description="Historical valuations carry statement, metric, market data, sensitivity, and timestamp references for future replay."
          >
            <ReproducibilityPanel result={result} />
          </PlaceholderCard>

          <PlaceholderCard
            label="Assumptions"
            title="Editable base case"
            description="Assumptions are deterministic and source-labelled. Submitting the form persists a new scenario."
          >
            <form className="space-y-4" method="GET">
              <input name="run" type="hidden" value="1" />
              <input
                name="action"
                type="hidden"
                value={isPersistedScenario ? "version" : "create"}
              />
              {isPersistedScenario ? (
                <input
                  name="scenario"
                  type="hidden"
                  value={result.scenario.id}
                />
              ) : null}
              <label className="border-line bg-graphite2/60 block border p-4">
                <span className="text-ink block text-sm">Scenario name</span>
                <input
                  className="border-line bg-obsidian text-ink mt-3 w-full border px-3 py-2 font-mono text-sm focus:outline-none focus:ring-1 focus:ring-accent"
                  defaultValue={result.scenario.name}
                  maxLength={80}
                  name="scenarioName"
                  type="text"
                />
                <span className="text-muted mt-2 block text-xs leading-5">
                  Use names like Base, Upside, Downside, or Analyst case. The
                  label does not change the calculation.
                </span>
              </label>
              <div className="grid gap-3 lg:grid-cols-2 2xl:grid-cols-3">
                <AssumptionInput
                  assumption={result.scenario.growth.revenueGrowthRate}
                  label="Revenue growth"
                  name="revenueGrowthRate"
                />
                <AssumptionInput
                  assumption={result.scenario.margin.operatingMargin}
                  label="Operating margin"
                  name="operatingMargin"
                />
                <AssumptionInput
                  assumption={result.scenario.reinvestment.reinvestmentRate}
                  label="Reinvestment rate"
                  name="reinvestmentRate"
                />
                <AssumptionInput
                  assumption={result.scenario.discountRate.taxRate}
                  label="Tax rate"
                  name="taxRate"
                />
                <AssumptionInput
                  assumption={result.scenario.discountRate.wacc}
                  label="WACC"
                  name="wacc"
                />
                <AssumptionInput
                  assumption={result.scenario.terminalValue.terminalGrowthRate}
                  label="Terminal growth"
                  name="terminalGrowthRate"
                />
                <AssumptionInput
                  assumption={result.scenario.shareCount.dilutedShareGrowthRate}
                  label="Diluted share growth"
                  name="dilutedShareGrowthRate"
                />
                <AssumptionInput
                  assumption={
                    result.scenario.shareCount
                      .stockBasedCompensationDilutionRate
                  }
                  label="SBC dilution"
                  name="stockBasedCompensationDilutionRate"
                />
                <AssumptionInput
                  assumption={result.scenario.shareCount.buybackRate}
                  label="Buyback rate"
                  name="buybackRate"
                />
                <AssumptionInput
                  assumption={
                    result.scenario.netDebt.operatingCashPercentOfRevenue
                  }
                  label="Operating cash % revenue"
                  name="operatingCashPercentOfRevenue"
                />
              </div>
              <div className="flex flex-wrap gap-3">
                <button
                  className="border-accent text-accent hover:bg-accent hover:text-obsidian border px-4 py-2 font-mono text-[11px] uppercase transition"
                  type="submit"
                >
                  {isPersistedScenario
                    ? "Save immutable version"
                    : "Run and save scenario"}
                </button>
                <Link
                  className="border-line text-muted hover:text-accent border px-4 py-2 font-mono text-[11px] uppercase transition"
                  href={`/valuation/${normalizedTicker}`}
                >
                  Reset inputs
                </Link>
              </div>
            </form>
          </PlaceholderCard>

          <PlaceholderCard
            label="Lifecycle"
            title="Scenario workflow controls"
            description="Lifecycle actions create audit records and preserve history. They do not permanently destroy valuation records."
          >
            <div className="grid gap-3 lg:grid-cols-2">
              <form
                className="border-line bg-graphite2/60 border p-4"
                method="GET"
              >
                <input name="action" type="hidden" value="rename" />
                <input
                  name="scenario"
                  type="hidden"
                  value={result.scenario.id}
                />
                <label className="text-ink block text-sm">
                  Rename scenario
                </label>
                <input
                  className="border-line bg-obsidian text-ink mt-3 w-full border px-3 py-2 font-mono text-sm focus:outline-none focus:ring-1 focus:ring-accent"
                  defaultValue={result.scenario.name}
                  maxLength={80}
                  name="scenarioName"
                  type="text"
                />
                <button
                  className="border-line text-muted hover:text-accent mt-3 border px-3 py-2 font-mono text-[11px] uppercase transition"
                  type="submit"
                >
                  Rename
                </button>
              </form>
              <form
                className="border-line bg-graphite2/60 border p-4"
                method="GET"
              >
                <input name="action" type="hidden" value="duplicate" />
                <input
                  name="scenario"
                  type="hidden"
                  value={result.scenario.id}
                />
                <label className="text-ink block text-sm">
                  Duplicate as base/bull/bear
                </label>
                <input
                  className="border-line bg-obsidian text-ink mt-3 w-full border px-3 py-2 font-mono text-sm focus:outline-none focus:ring-1 focus:ring-accent"
                  defaultValue={`${result.scenario.name} Copy`}
                  maxLength={80}
                  name="scenarioName"
                  type="text"
                />
                <div className="mt-3 flex flex-wrap gap-2">
                  {["Base", "Bull", "Bear"].map((label) => (
                    <button
                      className="border-line text-muted hover:text-accent border px-3 py-2 font-mono text-[11px] uppercase transition"
                      key={label}
                      name="scenarioName"
                      type="submit"
                      value={`${label} case`}
                    >
                      {label}
                    </button>
                  ))}
                  <button
                    className="border-line text-muted hover:text-accent border px-3 py-2 font-mono text-[11px] uppercase transition"
                    type="submit"
                  >
                    Duplicate
                  </button>
                </div>
              </form>
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              {result.scenario.status === "archived" ? (
                <LifecycleLink
                  action="restore"
                  label="Restore"
                  scenarioId={result.scenario.id}
                />
              ) : (
                <LifecycleLink
                  action="archive"
                  label="Archive"
                  scenarioId={result.scenario.id}
                />
              )}
              <LifecycleLink
                action="delete"
                label="Soft delete"
                scenarioId={result.scenario.id}
              />
            </div>
          </PlaceholderCard>

          <PlaceholderCard
            label="Import / export"
            title="Assumption portability"
            description="Exported assumptions preserve schema and model versions. Imported JSON is validated before it creates a saved scenario."
          >
            <ImportExportPanel exported={exported} />
          </PlaceholderCard>

          <PlaceholderCard
            label="Scenario library"
            title="Saved DCF scenarios"
            description="Saved scenarios can be reopened without recalculating fresh provider inputs."
          >
            <SavedScenarioList
              activeScenarioId={result.scenario.id}
              collection={scenarioCollection}
              ticker={normalizedTicker}
            />
          </PlaceholderCard>

          <PlaceholderCard
            label="Scenario comparison"
            title="Saved case comparison"
            description="Compares saved DCF cases on key assumptions and valuation output. No ranking or recommendation is implied."
          >
            <ComparisonTable comparison={comparison} />
          </PlaceholderCard>

          <PlaceholderCard
            label="Scenario diff"
            title="Side-by-side scenario diff"
            description="Compare base, bull, bear, or arbitrary saved scenario versions across assumptions, outputs, and warnings."
          >
            <ScenarioDiffPanel
              activeScenarioId={result.scenario.id}
              collection={scenarioCollection}
              diff={scenarioDiff}
              ticker={normalizedTicker}
            />
          </PlaceholderCard>

          <PlaceholderCard
            label="Audit trail"
            title="Immutable version history"
            description="Each scenario edit creates a new immutable version with audit events for changed assumptions or lifecycle actions."
          >
            <HistoryPanel history={history} />
          </PlaceholderCard>

          <PlaceholderCard
            label="Analyst notes"
            title="Immutable notes"
            description="Attach markdown/plain text notes to this scenario version, an assumption path, or a warning code."
          >
            <form className="mb-4 space-y-3" method="GET">
              <input name="action" type="hidden" value="note" />
              <input name="scenario" type="hidden" value={result.scenario.id} />
              <div className="grid gap-3 md:grid-cols-[1fr_1fr]">
                <label className="block">
                  <span className="text-muted font-mono text-[11px] uppercase">
                    Attachment
                  </span>
                  <select
                    className="bg-obsidian border-line text-ink mt-2 w-full border px-3 py-2 text-sm"
                    name="attachmentType"
                  >
                    <option value="scenario_version">Scenario version</option>
                    <option value="assumption">Assumption</option>
                    <option value="warning">Warning</option>
                  </select>
                </label>
                <label className="block">
                  <span className="text-muted font-mono text-[11px] uppercase">
                    Field path / warning
                  </span>
                  <input
                    className="border-line bg-obsidian text-ink mt-2 w-full border px-3 py-2 font-mono text-sm focus:outline-none focus:ring-1 focus:ring-accent"
                    name="fieldPath"
                    placeholder="growth.revenueGrowthRate"
                    type="text"
                  />
                </label>
              </div>
              <label className="block">
                <span className="text-muted font-mono text-[11px] uppercase">
                  Note
                </span>
                <textarea
                  className="border-line bg-obsidian text-ink mt-2 min-h-24 w-full border p-3 text-sm focus:outline-none focus:ring-1 focus:ring-accent"
                  name="noteText"
                />
              </label>
              <button
                className="border-line text-muted hover:text-accent border px-4 py-2 font-mono text-[11px] uppercase transition"
                type="submit"
              >
                Attach note
              </button>
            </form>
            <NotesPanel notes={notes} />
          </PlaceholderCard>

          <PlaceholderCard
            label="Discount rate"
            title="WACC inputs"
            description="Discount-rate assumptions remain visible so the valuation does not become a black box."
          >
            <StatusList
              items={[
                {
                  label: "Risk-free rate",
                  status: formatPercent(
                    result.scenario.discountRate.riskFreeRate.value,
                  ),
                },
                {
                  label: "Equity risk premium",
                  status: formatPercent(
                    result.scenario.discountRate.equityRiskPremium.value,
                  ),
                },
                {
                  label: "Beta",
                  status: formatNumber(result.scenario.discountRate.beta.value),
                },
                {
                  label: "Cost of equity",
                  status: formatPercent(
                    result.scenario.discountRate.costOfEquity.value,
                  ),
                },
                {
                  label: "Pre-tax cost of debt",
                  status: formatPercent(
                    result.scenario.discountRate.preTaxCostOfDebt.value,
                  ),
                },
                {
                  label: "After-tax cost of debt",
                  status: formatPercent(
                    result.scenario.discountRate.afterTaxCostOfDebt.value,
                  ),
                },
                {
                  label: "Debt weight",
                  status: formatPercent(
                    result.scenario.discountRate.debtWeight.value,
                  ),
                },
                {
                  label: "Equity weight",
                  status: formatPercent(
                    result.scenario.discountRate.equityWeight.value,
                  ),
                },
              ]}
            />
          </PlaceholderCard>

          <PlaceholderCard
            label="Base financials"
            title="Normalized source inputs"
            description="Core statement inputs used by the FCFF projection engine."
          >
            <StatusList
              items={[
                {
                  label: "Revenue",
                  status: formatMoney(result.baseFinancials.revenue, currency),
                },
                {
                  label: "Operating income",
                  status: formatMoney(
                    result.baseFinancials.operatingIncome,
                    currency,
                  ),
                },
                {
                  label: "Free cash flow",
                  status: formatMoney(
                    result.baseFinancials.freeCashFlow,
                    currency,
                  ),
                },
                {
                  label: "Cash and equivalents",
                  status: formatMoney(
                    result.baseFinancials.cashAndEquivalents,
                    currency,
                  ),
                },
                {
                  label: "Operating cash",
                  status: formatMoney(
                    result.baseFinancials.operatingCash,
                    currency,
                  ),
                },
                {
                  label: "Excess cash",
                  status: formatMoney(
                    result.baseFinancials.excessCash,
                    currency,
                  ),
                },
                {
                  label: "Total debt",
                  status: formatMoney(
                    result.baseFinancials.totalDebt,
                    currency,
                  ),
                },
                {
                  label: "Lease debt",
                  status: formatMoney(
                    result.baseFinancials.leaseDebt,
                    currency,
                  ),
                },
                {
                  label: "Preferred equity",
                  status: formatMoney(
                    result.baseFinancials.preferredEquity,
                    currency,
                  ),
                },
                {
                  label: "Minority interest",
                  status: formatMoney(
                    result.baseFinancials.minorityInterest,
                    currency,
                  ),
                },
                {
                  label: "Diluted shares",
                  status: formatNumber(result.baseFinancials.sharesDiluted),
                },
                {
                  label: "Projected diluted shares",
                  status: formatNumber(result.projectedSharesDiluted),
                },
                {
                  label: "Fiscal year",
                  status: formatText(result.baseFinancials.fiscalYear),
                },
                {
                  label: "Fiscal period",
                  status: formatText(result.baseFinancials.fiscalPeriod),
                },
              ]}
            />
          </PlaceholderCard>

          <PlaceholderCard
            label="Projection"
            title="FCFF projection table"
            description="Explicit projection years show revenue, operating income, NOPAT, reinvestment, FCFF, and discounted FCFF."
          >
            <ProjectionTable
              currency={currency}
              projections={result.projections}
            />
          </PlaceholderCard>

          <PlaceholderCard
            label="Terminal value"
            title="Enterprise value bridge"
            description="The bridge from projected FCFF to equity value remains visible and auditable."
          >
            <StatusList
              items={[
                {
                  label: "Terminal value",
                  status: formatMoney(result.terminalValue, currency),
                },
                {
                  label: "PV terminal value",
                  status: formatMoney(
                    result.presentValueTerminalValue,
                    currency,
                  ),
                },
                {
                  label: "Enterprise value",
                  status: formatMoney(result.enterpriseValue, currency),
                },
                {
                  label: "Net debt",
                  status: formatMoney(result.netDebt, currency),
                },
                {
                  label: "Equity value",
                  status: formatMoney(result.equityValue, currency),
                },
              ]}
            />
          </PlaceholderCard>

          <PlaceholderCard
            label="Sensitivity"
            title="WACC and terminal growth matrix"
            description="Sensitivity cells show intrinsic value per share under deterministic assumption changes."
          >
            <SensitivityMatrixView
              currency={currency}
              matrix={result.sensitivity.waccTerminalGrowth}
            />
          </PlaceholderCard>

          <PlaceholderCard
            label="Sensitivity"
            title="Margin and WACC matrix"
            description="Margin sensitivity keeps operating assumptions separate from discount-rate assumptions."
          >
            <SensitivityMatrixView
              currency={currency}
              matrix={result.sensitivity.marginWacc}
            />
          </PlaceholderCard>

          <PlaceholderCard
            label="Audit"
            title="Quality flags and formulas"
            description="Formula definitions and quality flags are returned with every DCF result."
          >
            <div className="space-y-4">
              <StatusList
                items={[
                  {
                    label: "Scenario id",
                    status: result.scenario.id,
                  },
                  {
                    label: "Schema version",
                    status: String(result.schemaVersion),
                  },
                  {
                    label: "Updated",
                    status: result.updatedAt,
                  },
                  {
                    label: "Quality flags",
                    status: qualityFlags(result.qualityFlags),
                  },
                ]}
              />
              <div className="border-line divide-line divide-y border">
                {result.formulas.map((formula) => (
                  <p
                    className="text-muted px-4 py-3 font-mono text-[11px]"
                    key={formula}
                  >
                    {formula}
                  </p>
                ))}
              </div>
            </div>
          </PlaceholderCard>

          <PlaceholderCard
            label="Provenance"
            title="Assumption provenance"
            description="Each primary assumption carries source, rationale, editability, and quality flags."
          >
            <StatusList items={assumptionProvenance(result)} />
          </PlaceholderCard>
        </section>
      ) : null}
    </TerminalShell>
  );
}
