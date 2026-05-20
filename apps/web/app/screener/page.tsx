import Link from "next/link";
import type {
  ScreenerFilter,
  ScreenerFilterOperator,
  ScreenerMetricField,
  ScreenerResultRow,
  ScreenerSort,
} from "@value-terminal/types";

import { ApiState } from "../../components/data-status/api-state";
import { TerminalShell } from "../../components/shell/terminal-shell";
import { PlaceholderCard } from "../../components/ui/placeholder-card";
import { StatusList } from "../../components/ui/status-list";
import { getScreener } from "../../lib/api/client";

type ScreenerPageProps = {
  searchParams?: Promise<{
    metric?: string | string[];
    operator?: string | string[];
    value?: string | string[];
    min?: string | string[];
    max?: string | string[];
    period?: string | string[];
    sortField?: string | string[];
    sortDirection?: string | string[];
    page?: string | string[];
  }>;
};

const metricOptions: Array<{ field: ScreenerMetricField; label: string }> = [
  { field: "marketCap", label: "Market cap" },
  { field: "revenue", label: "Revenue" },
  { field: "revenueGrowthYoY", label: "Revenue growth YoY" },
  { field: "grossMargin", label: "Gross margin" },
  { field: "operatingMargin", label: "Operating margin" },
  { field: "netMargin", label: "Net margin" },
  { field: "freeCashFlowMargin", label: "FCF margin" },
  { field: "returnOnEquity", label: "ROE" },
  { field: "returnOnInvestedCapital", label: "ROIC" },
  { field: "debtToEquity", label: "Debt / equity" },
  { field: "currentRatio", label: "Current ratio" },
  { field: "freeCashFlowPerShare", label: "FCF / share" },
  { field: "bookValuePerShare", label: "Book value / share" },
  { field: "price", label: "Price" },
  { field: "peRatio", label: "P/E" },
  { field: "pbRatio", label: "P/B" },
  { field: "psRatio", label: "P/S" },
];

const operatorOptions: Array<{ value: ScreenerFilterOperator; label: string }> =
  [
    { value: "gte", label: ">=" },
    { value: "gt", label: ">" },
    { value: "lte", label: "<=" },
    { value: "lt", label: "<" },
    { value: "eq", label: "=" },
    { value: "between", label: "Between" },
  ];

const percentageFields = new Set<ScreenerMetricField>([
  "revenueGrowthYoY",
  "grossMargin",
  "operatingMargin",
  "netMargin",
  "freeCashFlowMargin",
  "returnOnEquity",
  "returnOnInvestedCapital",
]);

const compactCurrencyFields = new Set<ScreenerMetricField>([
  "marketCap",
  "revenue",
]);

const ratioFields = new Set<ScreenerMetricField>([
  "debtToEquity",
  "currentRatio",
  "peRatio",
  "pbRatio",
  "psRatio",
]);

function getQueryValue(value: string | string[] | undefined) {
  if (Array.isArray(value)) {
    return value[0] ?? "";
  }

  return value ?? "";
}

function isMetricField(value: string): value is ScreenerMetricField {
  return metricOptions.some((option) => option.field === value);
}

function isOperator(value: string): value is ScreenerFilterOperator {
  return operatorOptions.some((option) => option.value === value);
}

function parseNumber(value: string) {
  const parsed = Number(value);

  return Number.isFinite(parsed) ? parsed : null;
}

function buildFilter(params: Record<string, string | string[] | undefined>) {
  const metric = getQueryValue(params.metric);
  const operator = getQueryValue(params.operator);

  if (!isMetricField(metric) || !isOperator(operator)) {
    return null;
  }

  if (operator === "between") {
    const min = parseNumber(getQueryValue(params.min));
    const max = parseNumber(getQueryValue(params.max));

    if (min === null || max === null) {
      return null;
    }

    return {
      field: metric,
      operator,
      value: [Math.min(min, max), Math.max(min, max)],
    } satisfies ScreenerFilter;
  }

  const value = parseNumber(getQueryValue(params.value));

  if (value === null) {
    return null;
  }

  return {
    field: metric,
    operator,
    value,
  } satisfies ScreenerFilter;
}

function buildSort(params: Record<string, string | string[] | undefined>) {
  const field = getQueryValue(params.sortField);
  const direction = getQueryValue(params.sortDirection);

  if (!isMetricField(field)) {
    return null;
  }

  return {
    field,
    direction: direction === "asc" ? "asc" : "desc",
  } satisfies ScreenerSort;
}

function normalizePeriod(value: string) {
  return value === "quarter" ? "quarter" : "annual";
}

function normalizePage(value: string) {
  const page = Number(value);

  return Number.isInteger(page) && page > 0 ? page : 1;
}

function labelForMetric(field: ScreenerMetricField) {
  return metricOptions.find((option) => option.field === field)?.label ?? field;
}

function formatMetric(
  field: ScreenerMetricField,
  value: number | null | undefined,
  currency: string | null,
) {
  if (value === null || value === undefined) {
    return "Unavailable";
  }

  if (percentageFields.has(field)) {
    return `${(value * 100).toFixed(1)}%`;
  }

  if (compactCurrencyFields.has(field)) {
    const formatted = Intl.NumberFormat("en-US", {
      notation: "compact",
      maximumFractionDigits: 1,
    }).format(value);

    return currency ? `${formatted} ${currency}` : formatted;
  }

  if (field === "price") {
    return currency ? `${value.toFixed(2)} ${currency}` : value.toFixed(2);
  }

  if (field === "freeCashFlowPerShare" || field === "bookValuePerShare") {
    return value.toFixed(2);
  }

  if (ratioFields.has(field)) {
    return `${value.toFixed(2)}x`;
  }

  return Intl.NumberFormat("en-US", {
    maximumFractionDigits: 2,
  }).format(value);
}

function qualityPreview(row: ScreenerResultRow) {
  if (!row.qualityFlags.length) {
    return "clean";
  }

  return row.qualityFlags.slice(0, 3).join(", ");
}

function nextPageUrl(
  params: Record<string, string | string[] | undefined>,
  page: number,
) {
  const search = new URLSearchParams();

  for (const [key, value] of Object.entries(params)) {
    const queryValue = getQueryValue(value);

    if (queryValue && key !== "page") {
      search.set(key, queryValue);
    }
  }

  search.set("page", String(page));

  return `/screener?${search}`;
}

export default async function ScreenerPage({
  searchParams,
}: ScreenerPageProps) {
  const params = searchParams ? await searchParams : {};
  const period = normalizePeriod(getQueryValue(params.period));
  const page = normalizePage(getQueryValue(params.page));
  const filter = buildFilter(params);
  const sort = buildSort(params);
  const screenerResult = await getScreener({
    filters: filter ? [filter] : [],
    sort,
    period,
    page,
    limit: 12,
  });
  const selectedMetric =
    getQueryValue(params.metric) || "returnOnInvestedCapital";
  const selectedOperator = getQueryValue(params.operator) || "gte";
  const selectedSortField = getQueryValue(params.sortField) || "marketCap";
  const selectedSortDirection = getQueryValue(params.sortDirection) || "desc";

  return (
    <TerminalShell
      eyebrow="Screener"
      title="Fundamentals-backed screening workspace."
      description="A compact institutional screener over the controlled development universe, using normalized statements, saved snapshots, and platform-calculated metrics."
    >
      <section className="grid gap-4 xl:grid-cols-[320px_1fr]">
        <PlaceholderCard
          label="Controls"
          title="Canonical metric filter"
          description="Filters run on backend-normalized screener rows. Missing values are excluded from metric filters."
        >
          <form className="space-y-4" action="/screener">
            <div className="grid gap-3">
              <label
                htmlFor="period"
                className="text-muted font-mono text-[11px] uppercase"
              >
                Period
              </label>
              <select
                id="period"
                name="period"
                defaultValue={period}
                className="border-line bg-obsidian text-ink min-h-11 border px-3 text-sm outline-none"
              >
                <option value="annual">Annual</option>
                <option value="quarter">Quarter</option>
              </select>
            </div>

            <div className="grid gap-3">
              <label
                htmlFor="metric"
                className="text-muted font-mono text-[11px] uppercase"
              >
                Metric
              </label>
              <select
                id="metric"
                name="metric"
                defaultValue={selectedMetric}
                className="border-line bg-obsidian text-ink min-h-11 border px-3 text-sm outline-none"
              >
                {metricOptions.map((option) => (
                  <option key={option.field} value={option.field}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>

            <div className="grid grid-cols-[0.8fr_1fr] gap-3">
              <div className="grid gap-3">
                <label
                  htmlFor="operator"
                  className="text-muted font-mono text-[11px] uppercase"
                >
                  Operator
                </label>
                <select
                  id="operator"
                  name="operator"
                  defaultValue={selectedOperator}
                  className="border-line bg-obsidian text-ink min-h-11 border px-3 text-sm outline-none"
                >
                  {operatorOptions.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </div>
              <div className="grid gap-3">
                <label
                  htmlFor="value"
                  className="text-muted font-mono text-[11px] uppercase"
                >
                  Value
                </label>
                <input
                  id="value"
                  name="value"
                  defaultValue={getQueryValue(params.value)}
                  placeholder="0.15"
                  className="border-line bg-obsidian text-ink placeholder:text-muted min-h-11 border px-3 text-sm outline-none"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <input
                name="min"
                defaultValue={getQueryValue(params.min)}
                placeholder="Between min"
                className="border-line bg-obsidian text-ink placeholder:text-muted min-h-11 border px-3 text-sm outline-none"
              />
              <input
                name="max"
                defaultValue={getQueryValue(params.max)}
                placeholder="Between max"
                className="border-line bg-obsidian text-ink placeholder:text-muted min-h-11 border px-3 text-sm outline-none"
              />
            </div>

            <div className="grid grid-cols-[1fr_0.7fr] gap-3">
              <select
                name="sortField"
                defaultValue={selectedSortField}
                className="border-line bg-obsidian text-ink min-h-11 border px-3 text-sm outline-none"
              >
                {metricOptions.map((option) => (
                  <option key={option.field} value={option.field}>
                    Sort: {option.label}
                  </option>
                ))}
              </select>
              <select
                name="sortDirection"
                defaultValue={selectedSortDirection}
                className="border-line bg-obsidian text-ink min-h-11 border px-3 text-sm outline-none"
              >
                <option value="desc">Desc</option>
                <option value="asc">Asc</option>
              </select>
            </div>

            <button
              type="submit"
              className="border-line text-muted hover:text-accent min-h-11 w-full border px-4 font-mono text-[11px] uppercase transition"
            >
              Run screen
            </button>
          </form>
        </PlaceholderCard>

        <PlaceholderCard
          label="Results"
          title="Canonical fundamentals screen"
          description="Rows are generated from the backend screener engine. Provider metrics are clearly flagged where used as temporary references."
        >
          {screenerResult.ok ? (
            <div className="space-y-4">
              <ApiState
                title={`Provider ${screenerResult.data.provider.state}`}
                message={screenerResult.data.message}
                provider={screenerResult.data.provider}
                endpoint="/api/screener"
              />

              <StatusList
                items={[
                  {
                    label: "Universe",
                    status: `${screenerResult.data.universe.size} controlled tickers`,
                  },
                  {
                    label: "Matched rows",
                    status: String(screenerResult.data.pagination.total),
                  },
                  {
                    label: "Period",
                    status: screenerResult.data.query.period,
                  },
                  {
                    label: "Sort",
                    status: screenerResult.data.query.sort
                      ? `${labelForMetric(
                          screenerResult.data.query.sort.field,
                        )} ${screenerResult.data.query.sort.direction}`
                      : "none",
                  },
                ]}
              />

              {screenerResult.data.rows.length ? (
                <div className="border-line overflow-hidden border">
                  <div className="overflow-x-auto">
                    <table className="w-full min-w-[1120px] border-collapse text-left text-sm">
                      <thead className="bg-graphite2 text-muted font-mono text-[11px] uppercase">
                        <tr>
                          {[
                            "Ticker",
                            "Company",
                            "Market cap",
                            "Revenue",
                            "Rev growth",
                            "Gross margin",
                            "Operating margin",
                            "Net margin",
                            "ROIC",
                            "Debt/equity",
                            "Current",
                            "P/E",
                            "Snapshot",
                            "Quality",
                          ].map((column) => (
                            <th
                              key={column}
                              className="border-line border-b px-4 py-3"
                            >
                              {column}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody className="divide-line divide-y">
                        {screenerResult.data.rows.map((row) => (
                          <tr key={row.ticker} className="bg-panel/60">
                            <td className="text-accent px-4 py-3 font-mono text-xs">
                              <Link href={`/company/${row.ticker}`}>
                                {row.ticker}
                              </Link>
                            </td>
                            <td className="text-ink max-w-[220px] px-4 py-3">
                              {row.companyName ?? "Unavailable"}
                            </td>
                            <td className="text-ink px-4 py-3">
                              {formatMetric(
                                "marketCap",
                                row.metrics.marketCap,
                                row.currency,
                              )}
                            </td>
                            <td className="text-ink px-4 py-3">
                              {formatMetric(
                                "revenue",
                                row.metrics.revenue,
                                row.currency,
                              )}
                            </td>
                            <td className="text-ink px-4 py-3">
                              {formatMetric(
                                "revenueGrowthYoY",
                                row.metrics.revenueGrowthYoY,
                                row.currency,
                              )}
                            </td>
                            <td className="text-ink px-4 py-3">
                              {formatMetric(
                                "grossMargin",
                                row.metrics.grossMargin,
                                row.currency,
                              )}
                            </td>
                            <td className="text-ink px-4 py-3">
                              {formatMetric(
                                "operatingMargin",
                                row.metrics.operatingMargin,
                                row.currency,
                              )}
                            </td>
                            <td className="text-ink px-4 py-3">
                              {formatMetric(
                                "netMargin",
                                row.metrics.netMargin,
                                row.currency,
                              )}
                            </td>
                            <td className="text-ink px-4 py-3">
                              {formatMetric(
                                "returnOnInvestedCapital",
                                row.metrics.returnOnInvestedCapital,
                                row.currency,
                              )}
                            </td>
                            <td className="text-ink px-4 py-3">
                              {formatMetric(
                                "debtToEquity",
                                row.metrics.debtToEquity,
                                row.currency,
                              )}
                            </td>
                            <td className="text-ink px-4 py-3">
                              {formatMetric(
                                "currentRatio",
                                row.metrics.currentRatio,
                                row.currency,
                              )}
                            </td>
                            <td className="text-ink px-4 py-3">
                              {formatMetric(
                                "peRatio",
                                row.metrics.peRatio,
                                row.currency,
                              )}
                            </td>
                            <td className="text-muted px-4 py-3 font-mono text-[11px] uppercase">
                              {row.snapshot
                                ? `${row.snapshot.state}${row.snapshot.isStale ? " stale" : ""}`
                                : "live"}
                            </td>
                            <td className="text-muted max-w-[260px] px-4 py-3 font-mono text-[11px]">
                              {qualityPreview(row)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              ) : (
                <ApiState
                  title="No screener rows returned"
                  message={
                    screenerResult.data.provider.state === "not_connected"
                      ? "FMP credentials are not configured, so the backend did not return fundamentals-backed rows."
                      : "The current filter removed all rows or provider data was unavailable for the controlled universe."
                  }
                  provider={screenerResult.data.provider}
                />
              )}

              {screenerResult.data.pagination.totalPages > 1 ? (
                <div className="flex flex-wrap items-center gap-3">
                  {screenerResult.data.pagination.hasPreviousPage ? (
                    <Link
                      href={nextPageUrl(params, page - 1)}
                      className="border-line text-muted hover:text-accent border px-3 py-2 font-mono text-[11px] uppercase transition"
                    >
                      Previous
                    </Link>
                  ) : null}
                  <span className="text-muted font-mono text-[11px] uppercase">
                    Page {screenerResult.data.pagination.page} of{" "}
                    {screenerResult.data.pagination.totalPages}
                  </span>
                  {screenerResult.data.pagination.hasNextPage ? (
                    <Link
                      href={nextPageUrl(params, page + 1)}
                      className="border-line text-muted hover:text-accent border px-3 py-2 font-mono text-[11px] uppercase transition"
                    >
                      Next
                    </Link>
                  ) : null}
                </div>
              ) : null}
            </div>
          ) : (
            <ApiState
              title="Screener API unavailable"
              message={screenerResult.error.message}
              endpoint={screenerResult.error.endpoint}
            />
          )}
        </PlaceholderCard>
      </section>
    </TerminalShell>
  );
}
