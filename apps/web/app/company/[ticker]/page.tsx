import Link from "next/link";

import type {
  BalanceSheet,
  CashFlowStatement,
  ComputedMetrics,
  FundamentalsPeriod,
  IncomeStatement,
  KeyMetrics,
  ProviderConnectionStatus,
} from "@value-terminal/types";

import { ApiState } from "../../../components/data-status/api-state";
import { TerminalShell } from "../../../components/shell/terminal-shell";
import { PlaceholderCard } from "../../../components/ui/placeholder-card";
import { StatusList } from "../../../components/ui/status-list";
import {
  getBalanceSheet,
  getCashFlowStatement,
  getCompanyOverview,
  getComputedMetrics,
  getFundamentalsProfile,
  getIncomeStatement,
  getKeyMetrics,
  getMarketSnapshot,
} from "../../../lib/api/client";

type CompanyPageProps = {
  params: Promise<{
    ticker: string;
  }>;
  searchParams?: Promise<{
    period?: string | string[];
  }>;
};

const periods: FundamentalsPeriod[] = ["annual", "quarter", "ttm"];

function getQueryValue(value: string | string[] | undefined) {
  if (Array.isArray(value)) {
    return value[0] ?? "";
  }

  return value ?? "";
}

function normalizePeriod(
  value: string | string[] | undefined,
): FundamentalsPeriod {
  const period = getQueryValue(value).toLowerCase();

  if (periods.includes(period as FundamentalsPeriod)) {
    return period as FundamentalsPeriod;
  }

  return "annual";
}

function formatNumber(value: number | null | undefined) {
  if (value === null || value === undefined) {
    return "Unavailable";
  }

  return new Intl.NumberFormat("en-US", {
    maximumFractionDigits: 2,
    notation: Math.abs(value) >= 1_000_000 ? "compact" : "standard",
  }).format(value);
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

function formatText(value: string | null | undefined) {
  return value ?? "Unavailable";
}

function providerTitle(label: string, provider: ProviderConnectionStatus) {
  if (provider.state === "connected") {
    return `${label} connected`;
  }

  if (provider.state === "not_implemented") {
    return `${label} not implemented`;
  }

  if (provider.state === "degraded") {
    return `${label} degraded`;
  }

  return `${label} not connected`;
}

function latest<T>(rows: T[]) {
  return rows[0] ?? null;
}

function latestRows<T>(rows: T[], limit = 3) {
  return rows.slice(0, limit);
}

function sourceItems(
  row:
    | IncomeStatement
    | BalanceSheet
    | CashFlowStatement
    | KeyMetrics
    | ComputedMetrics
    | null,
) {
  if (!row) {
    return [];
  }

  return [
    { label: "Source", status: row.provider },
    { label: "Fetched", status: row.fetchedAt },
    { label: "Fiscal year", status: formatText(row.fiscalYear) },
    { label: "Fiscal period", status: formatText(row.fiscalPeriod) },
    {
      label: "Quality flags",
      status: row.qualityFlags.length ? row.qualityFlags.join(", ") : "none",
    },
  ];
}

function rowTitle(row: IncomeStatement | BalanceSheet | CashFlowStatement) {
  return (
    [row.fiscalYear, row.fiscalPeriod].filter(Boolean).join(" ") || "Period"
  );
}

function auditSourceItems(
  row: IncomeStatement | BalanceSheet | CashFlowStatement,
) {
  return [
    { label: "Source", status: row.provider },
    { label: "Currency", status: formatText(row.currency) },
    { label: "Fetched", status: row.fetchedAt },
    {
      label: "Quality flags",
      status: row.qualityFlags.length ? row.qualityFlags.join(", ") : "none",
    },
  ];
}

function StatementAuditGroup({
  title,
  rows,
  lineItems,
}: {
  title: string;
  rows: Array<IncomeStatement | BalanceSheet | CashFlowStatement>;
  lineItems: (
    row: IncomeStatement | BalanceSheet | CashFlowStatement,
  ) => Array<{ label: string; status: string }>;
}) {
  return (
    <div>
      <p className="text-accent font-mono text-[11px] uppercase">{title}</p>
      <div className="mt-3 space-y-3">
        {rows.length ? (
          rows.map((row) => (
            <div
              key={`${title}-${row.fiscalYear}-${row.fiscalPeriod}-${row.date}`}
              className="border-line border-t pt-3"
            >
              <p className="text-ink font-mono text-[11px] uppercase">
                {rowTitle(row)}
              </p>
              <StatusList
                items={[...lineItems(row), ...auditSourceItems(row)]}
              />
            </div>
          ))
        ) : (
          <p className="text-muted text-sm leading-6">
            No statement rows available.
          </p>
        )}
      </div>
    </div>
  );
}

export default async function CompanyPage({
  params,
  searchParams,
}: CompanyPageProps) {
  const { ticker } = await params;
  const query = searchParams ? await searchParams : {};
  const normalizedTicker = ticker.toUpperCase();
  const period = normalizePeriod(query.period);
  const [
    overviewResult,
    snapshotResult,
    profileResult,
    incomeResult,
    balanceResult,
    cashFlowResult,
    metricsResult,
    computedMetricsResult,
  ] = await Promise.all([
    getCompanyOverview(normalizedTicker),
    getMarketSnapshot(normalizedTicker),
    getFundamentalsProfile(normalizedTicker),
    getIncomeStatement(normalizedTicker, period),
    getBalanceSheet(normalizedTicker, period),
    getCashFlowStatement(normalizedTicker, period),
    getKeyMetrics(normalizedTicker, period),
    getComputedMetrics(normalizedTicker, period),
  ]);

  const income = incomeResult.ok
    ? latest(incomeResult.data.incomeStatements)
    : null;
  const incomeRows = incomeResult.ok
    ? latestRows(incomeResult.data.incomeStatements)
    : [];
  const balance = balanceResult.ok
    ? latest(balanceResult.data.balanceSheets)
    : null;
  const balanceRows = balanceResult.ok
    ? latestRows(balanceResult.data.balanceSheets)
    : [];
  const cashFlow = cashFlowResult.ok
    ? latest(cashFlowResult.data.cashFlowStatements)
    : null;
  const cashFlowRows = cashFlowResult.ok
    ? latestRows(cashFlowResult.data.cashFlowStatements)
    : [];
  const metrics = metricsResult.ok ? latest(metricsResult.data.metrics) : null;
  const computedMetrics = computedMetricsResult.ok
    ? latest(computedMetricsResult.data.computedMetrics)
    : null;

  return (
    <TerminalShell
      eyebrow={`Company / ${normalizedTicker}`}
      title="Company research dashboard."
      description="A structured company workspace for market data, canonical fundamentals, and future source-backed research."
    >
      <section className="mb-4 flex flex-wrap gap-2">
        {periods.map((item) => (
          <Link
            key={item}
            href={`/company/${normalizedTicker}?period=${item}`}
            className={`border-line border px-3 py-2 font-mono text-[11px] uppercase transition ${
              period === item
                ? "text-accent bg-accent/10"
                : "text-muted hover:text-accent"
            }`}
          >
            {item}
          </Link>
        ))}
      </section>

      <section className="grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
        <PlaceholderCard
          label="Company profile"
          title={`${normalizedTicker} reference canvas`}
          description="Market data comes from Alpaca. Fundamentals come from FMP when configured."
        >
          <div className="space-y-4">
            {overviewResult.ok ? (
              <ApiState
                title={providerTitle(
                  "Market reference",
                  overviewResult.data.provider,
                )}
                message={overviewResult.data.message}
                provider={overviewResult.data.provider}
                endpoint={`/api/securities/${normalizedTicker}`}
              />
            ) : (
              <ApiState
                title="Company API unavailable"
                message={overviewResult.error.message}
                endpoint={overviewResult.error.endpoint}
              />
            )}

            {profileResult.ok ? (
              <>
                <ApiState
                  title={providerTitle(
                    "FMP profile",
                    profileResult.data.provider,
                  )}
                  message={profileResult.data.message}
                  provider={profileResult.data.provider}
                  endpoint={`/api/fundamentals/${normalizedTicker}/profile`}
                />
                {profileResult.data.profile ? (
                  <StatusList
                    items={[
                      {
                        label: "Name",
                        status: formatText(profileResult.data.profile.name),
                      },
                      {
                        label: "Sector",
                        status: formatText(profileResult.data.profile.sector),
                      },
                      {
                        label: "Industry",
                        status: formatText(profileResult.data.profile.industry),
                      },
                      {
                        label: "Market cap",
                        status: formatNumber(
                          profileResult.data.profile.marketCap,
                        ),
                      },
                      {
                        label: "Currency",
                        status: formatText(profileResult.data.profile.currency),
                      },
                    ]}
                  />
                ) : null}
              </>
            ) : (
              <ApiState
                title="Profile API unavailable"
                message={profileResult.error.message}
                endpoint={profileResult.error.endpoint}
              />
            )}
          </div>
        </PlaceholderCard>

        <PlaceholderCard
          label="Market snapshot"
          title="Live market data status"
          description="Snapshot fields stay unavailable unless Alpaca returns real values."
        >
          {snapshotResult.ok ? (
            <div className="space-y-4">
              <ApiState
                title={providerTitle(
                  "Market snapshot",
                  snapshotResult.data.provider,
                )}
                message={snapshotResult.data.message}
                provider={snapshotResult.data.provider}
                endpoint={`/api/securities/${normalizedTicker}/snapshot`}
                asOf={snapshotResult.data.asOf}
              />
              {snapshotResult.data.provider.state === "connected" ? (
                <StatusList
                  items={[
                    {
                      label: "Last trade price",
                      status:
                        snapshotResult.data.price === null
                          ? "Unavailable"
                          : `${snapshotResult.data.price} ${snapshotResult.data.currency ?? ""}`.trim(),
                    },
                    {
                      label: "Volume",
                      status: formatNumber(snapshotResult.data.volume),
                    },
                    {
                      label: "As of",
                      status: snapshotResult.data.asOf ?? "Unavailable",
                    },
                  ]}
                />
              ) : null}
            </div>
          ) : (
            <ApiState
              title="Snapshot API unavailable"
              message={snapshotResult.error.message}
              endpoint={snapshotResult.error.endpoint}
            />
          )}
        </PlaceholderCard>

        <PlaceholderCard
          label="Income statement"
          title={`${period} income statement`}
          description="Canonical income statement fields normalized from FMP."
        >
          {incomeResult.ok ? (
            <div className="space-y-4">
              <ApiState
                title={providerTitle(
                  "Income statement",
                  incomeResult.data.provider,
                )}
                message={incomeResult.data.message}
                provider={incomeResult.data.provider}
                endpoint={`/api/fundamentals/${normalizedTicker}/income-statement?period=${period}&limit=5`}
              />
              {income ? (
                <StatusList
                  items={[
                    { label: "Revenue", status: formatNumber(income.revenue) },
                    {
                      label: "Gross profit",
                      status: formatNumber(income.grossProfit),
                    },
                    {
                      label: "Operating income",
                      status: formatNumber(income.operatingIncome),
                    },
                    { label: "EBITDA", status: formatNumber(income.ebitda) },
                    {
                      label: "Net income",
                      status: formatNumber(income.netIncome),
                    },
                    {
                      label: "Diluted EPS",
                      status: formatNumber(income.epsDiluted),
                    },
                    ...sourceItems(income),
                  ]}
                />
              ) : null}
            </div>
          ) : (
            <ApiState
              title="Income statement API unavailable"
              message={incomeResult.error.message}
              endpoint={incomeResult.error.endpoint}
            />
          )}
        </PlaceholderCard>

        <PlaceholderCard
          label="Balance sheet"
          title={`${period} balance sheet`}
          description="Canonical balance sheet fields normalized from FMP."
        >
          {balanceResult.ok ? (
            <div className="space-y-4">
              <ApiState
                title={providerTitle(
                  "Balance sheet",
                  balanceResult.data.provider,
                )}
                message={balanceResult.data.message}
                provider={balanceResult.data.provider}
                endpoint={`/api/fundamentals/${normalizedTicker}/balance-sheet?period=${period}&limit=5`}
              />
              {balance ? (
                <StatusList
                  items={[
                    {
                      label: "Cash and equivalents",
                      status: formatNumber(balance.cashAndEquivalents),
                    },
                    {
                      label: "Total assets",
                      status: formatNumber(balance.totalAssets),
                    },
                    {
                      label: "Total liabilities",
                      status: formatNumber(balance.totalLiabilities),
                    },
                    {
                      label: "Total debt",
                      status: formatNumber(balance.totalDebt),
                    },
                    {
                      label: "Shareholders equity",
                      status: formatNumber(balance.shareholdersEquity),
                    },
                    ...sourceItems(balance),
                  ]}
                />
              ) : null}
            </div>
          ) : (
            <ApiState
              title="Balance sheet API unavailable"
              message={balanceResult.error.message}
              endpoint={balanceResult.error.endpoint}
            />
          )}
        </PlaceholderCard>

        <PlaceholderCard
          label="Cash flow"
          title={`${period} cash flow statement`}
          description="Canonical cash flow fields normalized from FMP."
        >
          {cashFlowResult.ok ? (
            <div className="space-y-4">
              <ApiState
                title={providerTitle("Cash flow", cashFlowResult.data.provider)}
                message={cashFlowResult.data.message}
                provider={cashFlowResult.data.provider}
                endpoint={`/api/fundamentals/${normalizedTicker}/cash-flow?period=${period}&limit=5`}
              />
              {cashFlow ? (
                <StatusList
                  items={[
                    {
                      label: "Operating cash flow",
                      status: formatNumber(cashFlow.operatingCashFlow),
                    },
                    {
                      label: "Capital expenditures",
                      status: formatNumber(cashFlow.capitalExpenditures),
                    },
                    {
                      label: "Free cash flow",
                      status: formatNumber(cashFlow.freeCashFlow),
                    },
                    {
                      label: "Dividends paid",
                      status: formatNumber(cashFlow.dividendsPaid),
                    },
                    {
                      label: "Share repurchases",
                      status: formatNumber(cashFlow.shareRepurchases),
                    },
                    ...sourceItems(cashFlow),
                  ]}
                />
              ) : null}
            </div>
          ) : (
            <ApiState
              title="Cash flow API unavailable"
              message={cashFlowResult.error.message}
              endpoint={cashFlowResult.error.endpoint}
            />
          )}
        </PlaceholderCard>

        <PlaceholderCard
          label="Statement audit"
          title={`${period} canonical statement audit`}
          description="Compact audit view of normalized statement rows, source metadata, and quality flags before valuation or screening logic."
        >
          <div className="mb-4 flex flex-wrap gap-2">
            {(["annual", "quarter"] as FundamentalsPeriod[]).map((item) => (
              <Link
                key={`audit-${item}`}
                href={`/company/${normalizedTicker}?period=${item}`}
                className={`border-line border px-3 py-2 font-mono text-[11px] uppercase transition ${
                  period === item
                    ? "text-accent bg-accent/10"
                    : "text-muted hover:text-accent"
                }`}
              >
                {item}
              </Link>
            ))}
          </div>
          <div className="grid gap-3 2xl:grid-cols-3">
            <StatementAuditGroup
              title="Income statement"
              rows={incomeRows}
              lineItems={(row) => {
                const incomeRow = row as IncomeStatement;

                return [
                  {
                    label: "Revenue",
                    status: formatNumber(incomeRow.revenue),
                  },
                  {
                    label: "Gross profit",
                    status: formatNumber(incomeRow.grossProfit),
                  },
                  {
                    label: "Operating income",
                    status: formatNumber(incomeRow.operatingIncome),
                  },
                  {
                    label: "Net income",
                    status: formatNumber(incomeRow.netIncome),
                  },
                  {
                    label: "Diluted shares",
                    status: formatNumber(incomeRow.sharesDiluted),
                  },
                ];
              }}
            />
            <StatementAuditGroup
              title="Balance sheet"
              rows={balanceRows}
              lineItems={(row) => {
                const balanceRow = row as BalanceSheet;

                return [
                  {
                    label: "Cash",
                    status: formatNumber(balanceRow.cashAndEquivalents),
                  },
                  {
                    label: "Total assets",
                    status: formatNumber(balanceRow.totalAssets),
                  },
                  {
                    label: "Current assets",
                    status: formatNumber(balanceRow.currentAssets),
                  },
                  {
                    label: "Total debt",
                    status: formatNumber(balanceRow.totalDebt),
                  },
                  {
                    label: "Equity",
                    status: formatNumber(balanceRow.shareholdersEquity),
                  },
                ];
              }}
            />
            <StatementAuditGroup
              title="Cash flow"
              rows={cashFlowRows}
              lineItems={(row) => {
                const cashFlowRow = row as CashFlowStatement;

                return [
                  {
                    label: "Operating cash flow",
                    status: formatNumber(cashFlowRow.operatingCashFlow),
                  },
                  {
                    label: "Capital expenditures",
                    status: formatNumber(cashFlowRow.capitalExpenditures),
                  },
                  {
                    label: "Free cash flow",
                    status: formatNumber(cashFlowRow.freeCashFlow),
                  },
                  {
                    label: "Dividends paid",
                    status: formatNumber(cashFlowRow.dividendsPaid),
                  },
                  {
                    label: "Share repurchases",
                    status: formatNumber(cashFlowRow.shareRepurchases),
                  },
                ];
              }}
            />
          </div>
        </PlaceholderCard>

        <PlaceholderCard
          label="Computed metrics"
          title={`${period} platform-calculated metrics`}
          description="Platform-owned metrics calculated from canonical income statement, balance sheet, and cash flow data."
        >
          {computedMetricsResult.ok ? (
            <div className="space-y-4">
              <ApiState
                title={providerTitle(
                  "Computed metrics",
                  computedMetricsResult.data.provider,
                )}
                message={computedMetricsResult.data.message}
                provider={computedMetricsResult.data.provider}
                endpoint={`/api/fundamentals/${normalizedTicker}/computed-metrics?period=${period}&limit=5`}
              />
              {computedMetrics ? (
                <StatusList
                  items={[
                    {
                      label: "Gross margin",
                      status: formatPercent(computedMetrics.grossMargin),
                    },
                    {
                      label: "Operating margin",
                      status: formatPercent(computedMetrics.operatingMargin),
                    },
                    {
                      label: "Net margin",
                      status: formatPercent(computedMetrics.netMargin),
                    },
                    {
                      label: "FCF margin",
                      status: formatPercent(computedMetrics.freeCashFlowMargin),
                    },
                    {
                      label: "Revenue growth YoY",
                      status: formatPercent(computedMetrics.revenueGrowthYoY),
                    },
                    {
                      label: "ROE",
                      status: formatPercent(computedMetrics.returnOnEquity),
                    },
                    {
                      label: "Debt to equity",
                      status: formatNumber(computedMetrics.debtToEquity),
                    },
                    {
                      label: "Current ratio",
                      status: formatNumber(computedMetrics.currentRatio),
                    },
                    {
                      label: "FCF per share",
                      status: formatNumber(
                        computedMetrics.freeCashFlowPerShare,
                      ),
                    },
                    {
                      label: "Book value per share",
                      status: formatNumber(computedMetrics.bookValuePerShare),
                    },
                    {
                      label: "ROIC",
                      status: formatPercent(
                        computedMetrics.returnOnInvestedCapital,
                      ),
                    },
                    ...sourceItems(computedMetrics),
                  ]}
                />
              ) : null}
            </div>
          ) : (
            <ApiState
              title="Computed metrics API unavailable"
              message={computedMetricsResult.error.message}
              endpoint={computedMetricsResult.error.endpoint}
            />
          )}
        </PlaceholderCard>

        <PlaceholderCard
          label="Key metrics"
          title={`${period} provider metrics`}
          description="FMP key metrics are provisional provider data and are not treated as final platform truth."
        >
          {metricsResult.ok ? (
            <div className="space-y-4">
              <ApiState
                title={providerTitle(
                  "Key metrics",
                  metricsResult.data.provider,
                )}
                message={metricsResult.data.message}
                provider={metricsResult.data.provider}
                endpoint={`/api/fundamentals/${normalizedTicker}/metrics?period=${period}&limit=5`}
              />
              {metrics ? (
                <StatusList
                  items={[
                    {
                      label: "Revenue per share",
                      status: formatNumber(metrics.revenuePerShare),
                    },
                    {
                      label: "FCF per share",
                      status: formatNumber(metrics.freeCashFlowPerShare),
                    },
                    {
                      label: "ROIC",
                      status: formatNumber(metrics.returnOnInvestedCapital),
                    },
                    {
                      label: "ROE",
                      status: formatNumber(metrics.returnOnEquity),
                    },
                    {
                      label: "Debt to equity",
                      status: formatNumber(metrics.debtToEquity),
                    },
                    {
                      label: "P/E",
                      status: formatNumber(metrics.priceToEarnings),
                    },
                    {
                      label: "EV/EBITDA",
                      status: formatNumber(metrics.enterpriseValueToEbitda),
                    },
                    ...sourceItems(metrics),
                  ]}
                />
              ) : null}
            </div>
          ) : (
            <ApiState
              title="Metrics API unavailable"
              message={metricsResult.error.message}
              endpoint={metricsResult.error.endpoint}
            />
          )}
        </PlaceholderCard>
      </section>
    </TerminalShell>
  );
}
