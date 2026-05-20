import type {
  BalanceSheet,
  CashFlowStatement,
  ComputedMetrics,
  FundamentalsPeriod,
  IncomeStatement,
} from "@value-terminal/types";

export type MetricsEngineInput = {
  ticker: string;
  period: Exclude<FundamentalsPeriod, "ttm">;
  incomeStatements: IncomeStatement[];
  balanceSheets: BalanceSheet[];
  cashFlowStatements: CashFlowStatement[];
  limit?: number;
};

export function computeNormalizedMetrics({
  ticker,
  period,
  incomeStatements,
  balanceSheets,
  cashFlowStatements,
  limit = 5,
}: MetricsEngineInput): ComputedMetrics[] {
  return incomeStatements.slice(0, limit).map((income, index) => {
    const balance = findMatchingRow(income, balanceSheets, index);
    const cashFlow = findMatchingRow(income, cashFlowStatements, index);
    const previousIncome = findPriorRow(
      income,
      incomeStatements,
      index,
      period,
    );
    const previousCashFlow = cashFlow.row
      ? findPriorRow(cashFlow.row, cashFlowStatements, cashFlow.index, period)
      : null;
    const qualityFlags = sourceQualityFlags(income, balance.row, cashFlow.row);

    return {
      provider: "platform",
      fetchedAt: new Date().toISOString(),
      sourceSymbol: income.sourceSymbol || ticker.toUpperCase(),
      currency:
        income.currency ??
        balance.row?.currency ??
        cashFlow.row?.currency ??
        null,
      fiscalYear: income.fiscalYear,
      fiscalPeriod: income.fiscalPeriod,
      date: income.date,
      period,
      sourceProviders: sourceProviders(income, balance.row, cashFlow.row),
      calculationEngine: "platform-normalized-metrics-v1",
      ...calculateMetrics(
        income,
        balance.row,
        cashFlow.row,
        previousIncome,
        previousCashFlow,
        qualityFlags,
      ),
    };
  });
}

function calculateMetrics(
  income: IncomeStatement,
  balance: BalanceSheet | null,
  cashFlow: CashFlowStatement | null,
  previousIncome: IncomeStatement | null,
  previousCashFlow: CashFlowStatement | null,
  qualityFlags: string[],
) {
  const investedCapital = calculateInvestedCapital(
    balance?.totalDebt ?? null,
    balance?.shareholdersEquity ?? null,
    balance?.cashAndEquivalents ?? null,
    qualityFlags,
  );

  if (income.sharesDiluted === null) {
    qualityFlags.push("shares_missing");
  }

  return {
    grossMargin: ratio(
      income.grossProfit,
      income.revenue,
      "grossMargin",
      qualityFlags,
    ),
    operatingMargin: ratio(
      income.operatingIncome,
      income.revenue,
      "operatingMargin",
      qualityFlags,
    ),
    netMargin: ratio(
      income.netIncome,
      income.revenue,
      "netMargin",
      qualityFlags,
    ),
    freeCashFlowMargin: ratio(
      cashFlow?.freeCashFlow ?? null,
      income.revenue,
      "freeCashFlowMargin",
      qualityFlags,
    ),
    revenueGrowthYoY: growth(
      income.revenue,
      previousIncome?.revenue ?? null,
      "revenueGrowthYoY",
      qualityFlags,
    ),
    netIncomeGrowthYoY: growth(
      income.netIncome,
      previousIncome?.netIncome ?? null,
      "netIncomeGrowthYoY",
      qualityFlags,
    ),
    operatingIncomeGrowthYoY: growth(
      income.operatingIncome,
      previousIncome?.operatingIncome ?? null,
      "operatingIncomeGrowthYoY",
      qualityFlags,
    ),
    freeCashFlowGrowthYoY: growth(
      cashFlow?.freeCashFlow ?? null,
      previousCashFlow?.freeCashFlow ?? null,
      "freeCashFlowGrowthYoY",
      qualityFlags,
    ),
    returnOnEquity: ratio(
      income.netIncome,
      balance?.shareholdersEquity ?? null,
      "returnOnEquity",
      qualityFlags,
    ),
    debtToEquity: ratio(
      balance?.totalDebt ?? null,
      balance?.shareholdersEquity ?? null,
      "debtToEquity",
      qualityFlags,
    ),
    currentRatio: ratio(
      balance?.currentAssets ?? null,
      balance?.currentLiabilities ?? null,
      "currentRatio",
      qualityFlags,
    ),
    freeCashFlowPerShare: ratio(
      cashFlow?.freeCashFlow ?? null,
      income.sharesDiluted,
      "freeCashFlowPerShare",
      qualityFlags,
    ),
    bookValuePerShare: ratio(
      balance?.shareholdersEquity ?? null,
      income.sharesDiluted,
      "bookValuePerShare",
      qualityFlags,
    ),
    earningsPerShareDiluted: ratio(
      income.netIncome,
      income.sharesDiluted,
      "earningsPerShareDiluted",
      qualityFlags,
    ),
    investedCapital,
    returnOnInvestedCapital: ratio(
      income.operatingIncome,
      investedCapital,
      "returnOnInvestedCapital",
      qualityFlags,
    ),
    qualityFlags: [...new Set(qualityFlags)],
  };
}

function ratio(
  numerator: number | null,
  denominator: number | null,
  metricName: string,
  qualityFlags: string[],
) {
  if (numerator === null || denominator === null) {
    qualityFlags.push(`missing_input:${metricName}`);
    return null;
  }

  if (denominator === 0) {
    qualityFlags.push(`zero_denominator:${metricName}`);
    return null;
  }

  if (denominator < 0) {
    qualityFlags.push(`negative_denominator:${metricName}`);
  }

  return numerator / denominator;
}

function growth(
  current: number | null,
  previous: number | null,
  metricName: string,
  qualityFlags: string[],
) {
  if (current === null || previous === null) {
    qualityFlags.push(`missing_prior_period:${metricName}`);
    return null;
  }

  if (previous === 0) {
    qualityFlags.push(`zero_prior_period:${metricName}`);
    return null;
  }

  if (previous < 0) {
    qualityFlags.push(`negative_prior_period:${metricName}`);
  }

  return (current - previous) / Math.abs(previous);
}

function calculateInvestedCapital(
  totalDebt: number | null,
  shareholdersEquity: number | null,
  cashAndEquivalents: number | null,
  qualityFlags: string[],
) {
  if (
    totalDebt === null ||
    shareholdersEquity === null ||
    cashAndEquivalents === null
  ) {
    qualityFlags.push("missing_input:investedCapital");
    qualityFlags.push("invested_capital_unavailable");
    return null;
  }

  const investedCapital = totalDebt + shareholdersEquity - cashAndEquivalents;

  if (investedCapital < 0) {
    qualityFlags.push("negative_invested_capital");
  }

  if (investedCapital === 0) {
    qualityFlags.push("invested_capital_unavailable");
  }

  return investedCapital;
}

function findMatchingRow<
  T extends {
    fiscalYear: string | null;
    fiscalPeriod: string | null;
    date: string | null;
  },
>(income: IncomeStatement, rows: T[], fallbackIndex: number) {
  const match = rows.findIndex((row) => rowKey(row) === rowKey(income));

  if (match >= 0) {
    return { row: rows[match], index: match };
  }

  return { row: rows[fallbackIndex] ?? null, index: fallbackIndex };
}

function findPriorRow<T extends { fiscalPeriod: string | null }>(
  current: T,
  rows: T[],
  currentIndex: number,
  period: Exclude<FundamentalsPeriod, "ttm">,
) {
  if (period === "quarter") {
    return (
      rows
        .slice(currentIndex + 1)
        .find((row) => row.fiscalPeriod === current.fiscalPeriod) ?? null
    );
  }

  return rows[currentIndex + 1] ?? null;
}

function rowKey(row: {
  fiscalYear: string | null;
  fiscalPeriod: string | null;
  date: string | null;
}) {
  return `${row.fiscalYear ?? ""}|${row.fiscalPeriod ?? ""}|${row.date ?? ""}`;
}

function sourceQualityFlags(
  income: IncomeStatement,
  balance: BalanceSheet | null,
  cashFlow: CashFlowStatement | null,
) {
  const flags = income.qualityFlags.map((flag) => `source:${flag}`);

  if (!income.currency) {
    flags.push("currency_missing");
  }

  if (!income.fiscalYear) {
    flags.push("fiscal_year_missing");
  }

  if (isStaleFetchedAt(income.fetchedAt)) {
    flags.push("stale_provider_response");
  }

  if (!balance) {
    flags.push("missing_statement:balance_sheet");
  } else {
    flags.push(...balance.qualityFlags.map((flag) => `source:${flag}`));

    if (isStaleFetchedAt(balance.fetchedAt)) {
      flags.push("stale_provider_response");
    }
  }

  if (!cashFlow) {
    flags.push("missing_statement:cash_flow");
  } else {
    flags.push(...cashFlow.qualityFlags.map((flag) => `source:${flag}`));

    if (isStaleFetchedAt(cashFlow.fetchedAt)) {
      flags.push("stale_provider_response");
    }
  }

  const currencies = new Set(
    [income.currency, balance?.currency, cashFlow?.currency].filter(Boolean),
  );

  if (currencies.size > 1) {
    flags.push("currency_mismatch");
  }

  return [...new Set(flags)];
}

function isStaleFetchedAt(value: string, maxAgeSeconds = 86400) {
  const fetchedAt = new Date(value).getTime();

  if (Number.isNaN(fetchedAt)) {
    return false;
  }

  return Date.now() - fetchedAt > maxAgeSeconds * 1000;
}

function sourceProviders(
  income: IncomeStatement,
  balance: BalanceSheet | null,
  cashFlow: CashFlowStatement | null,
) {
  return [
    ...new Set(
      [income.provider, balance?.provider, cashFlow?.provider].filter(Boolean),
    ),
  ] as string[];
}
