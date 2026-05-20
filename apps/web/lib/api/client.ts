import type {
  ApiStatus,
  BalanceSheetResult,
  CashFlowStatementResult,
  CompanyOverview,
  CompanyProfileResult,
  ComputedMetricsResult,
  DCFResult,
  FundamentalsDiagnostics,
  FundamentalsPeriod,
  IncomeStatementResult,
  KeyMetricsResult,
  MarketDataDiagnostics,
  MarketDataProbe,
  MarketSnapshot,
  ProviderConnectionStatus,
  RankingDiagnostics,
  RankingFilter,
  RefreshJob,
  RefreshJobCollection,
  RefreshJobEventCollection,
  RefreshJobStatus,
  DueRefreshPolicyRunResult,
  RankingRefreshRun,
  RankingRefreshRunCollection,
  RankingResponse,
  RankingRunChanges,
  RankingRunCollection,
  RankingSort,
  RankingStrategy,
  RefreshPolicy,
  RefreshPolicyCollection,
  RefreshPolicyRunResult,
  SavedRankingScreen,
  SavedRankingScreenCollection,
  SavedWatchlistView,
  SavedWatchlistViewCollection,
  SecuritySearchResult,
  ScreenerFilter,
  ScreenerResponse,
  ScreenerRefreshResult,
  ScreenerSort,
  SensitivityGrid,
  ValuationAssumptionExport,
  ValuationDiagnostics,
  ValuationScenarioCollection,
  ValuationScenarioComparison,
  ValuationScenarioDiff,
  ValuationScenarioHistory,
  ValuationNotesResult,
  ValuationNote,
  Watchlist,
  WatchlistAlertHistory,
  WatchlistAlertsResult,
  WatchlistCollection,
  WatchlistDiagnostics,
  WatchlistFilter,
  WatchlistIntelligence,
  WatchlistRefreshHistory,
  WatchlistSort,
  WatchlistStalenessResult,
  WatchlistVisibleColumn,
} from "@value-terminal/types";

import { hasProviderConnectionStatus } from "./guards";

type ApiClientError = {
  endpoint: string;
  status: number | null;
  message: string;
};

export type ApiResult<T> =
  | {
      ok: true;
      data: T;
      provider?: ProviderConnectionStatus;
    }
  | {
      ok: false;
      error: ApiClientError;
    };

export type CreateWatchlistPayload = {
  name: string;
  description?: string | null;
};

export type UpdateWatchlistPayload = Partial<CreateWatchlistPayload>;

export type AddWatchlistItemPayload = {
  ticker: string;
  companyName?: string | null;
  notes?: string | null;
  tags?: string[];
  targetPrice?: number | null;
  thesisStatus?: string | null;
  priority?: string | null;
  workflowState?: string | null;
};

export type UpdateWatchlistItemPayload = Partial<
  Omit<AddWatchlistItemPayload, "ticker">
>;

export type WatchlistViewPayload = {
  name?: string | null;
  filters?: WatchlistFilter[];
  sorting?: WatchlistSort | null;
  visibleColumns?: WatchlistVisibleColumn[];
};

const DEFAULT_API_BASE_URL = "http://localhost:8000";

function getApiBaseUrl() {
  const baseUrl =
    process.env.NEXT_PUBLIC_API_BASE_URL ||
    process.env.API_BASE_URL ||
    DEFAULT_API_BASE_URL;

  return baseUrl.replace(/\/$/, "");
}

function endpointUrl(endpoint: string) {
  return `${getApiBaseUrl()}${endpoint}`;
}

function providerFromPayload<T>(
  payload: T,
): ProviderConnectionStatus | undefined {
  if (hasProviderConnectionStatus(payload)) {
    return payload.provider;
  }

  return undefined;
}

export function isProviderNotConnected(provider?: ProviderConnectionStatus) {
  return provider?.state === "not_connected";
}

export async function apiRequest<T>(
  endpoint: string,
  init?: RequestInit,
): Promise<ApiResult<T>> {
  try {
    const response = await fetch(endpointUrl(endpoint), {
      ...init,
      cache: "no-store",
      headers: {
        "Content-Type": "application/json",
        ...init?.headers,
      },
    });

    if (!response.ok) {
      return {
        ok: false,
        error: {
          endpoint,
          status: response.status,
          message: `API request failed with status ${response.status}.`,
        },
      };
    }

    const data = (await response.json()) as T;

    return {
      ok: true,
      data,
      provider: providerFromPayload(data),
    };
  } catch (error) {
    return {
      ok: false,
      error: {
        endpoint,
        status: null,
        message:
          error instanceof Error
            ? error.message
            : "Unable to reach the API service.",
      },
    };
  }
}

export function getApiStatus() {
  return apiRequest<ApiStatus>("/api/status");
}

export function getMarketDataDiagnostics() {
  return apiRequest<MarketDataDiagnostics>("/api/diagnostics/market-data");
}

export function getFundamentalsDiagnostics() {
  return apiRequest<FundamentalsDiagnostics>("/api/diagnostics/fundamentals");
}

export function getRankingDiagnostics() {
  return apiRequest<RankingDiagnostics>("/api/diagnostics/rankings");
}

export function getWatchlistDiagnostics() {
  return apiRequest<WatchlistDiagnostics>("/api/diagnostics/watchlists");
}

export function getValuationDiagnostics(ticker = "AAPL") {
  const search = new URLSearchParams({ ticker });

  return apiRequest<ValuationDiagnostics>(
    `/api/diagnostics/valuation?${search}`,
  );
}

export function getMarketDataProbe(ticker: string) {
  const search = new URLSearchParams({ ticker });

  return apiRequest<MarketDataProbe>(
    `/api/diagnostics/market-data/probe?${search}`,
  );
}

export function searchSecurities(query: string) {
  const search = new URLSearchParams({ q: query });

  return apiRequest<SecuritySearchResult>(`/api/securities/search?${search}`);
}

export function getCompanyOverview(ticker: string) {
  return apiRequest<CompanyOverview>(
    `/api/securities/${encodeURIComponent(ticker)}`,
  );
}

export function getMarketSnapshot(ticker: string) {
  return apiRequest<MarketSnapshot>(
    `/api/securities/${encodeURIComponent(ticker)}/snapshot`,
  );
}

function fundamentalsParams(period: FundamentalsPeriod, limit: number) {
  return new URLSearchParams({
    period,
    limit: String(limit),
  });
}

export function getFundamentalsProfile(ticker: string) {
  return apiRequest<CompanyProfileResult>(
    `/api/fundamentals/${encodeURIComponent(ticker)}/profile`,
  );
}

export function getIncomeStatement(
  ticker: string,
  period: FundamentalsPeriod,
  limit = 5,
) {
  return apiRequest<IncomeStatementResult>(
    `/api/fundamentals/${encodeURIComponent(
      ticker,
    )}/income-statement?${fundamentalsParams(period, limit)}`,
  );
}

export function getBalanceSheet(
  ticker: string,
  period: FundamentalsPeriod,
  limit = 5,
) {
  return apiRequest<BalanceSheetResult>(
    `/api/fundamentals/${encodeURIComponent(
      ticker,
    )}/balance-sheet?${fundamentalsParams(period, limit)}`,
  );
}

export function getCashFlowStatement(
  ticker: string,
  period: FundamentalsPeriod,
  limit = 5,
) {
  return apiRequest<CashFlowStatementResult>(
    `/api/fundamentals/${encodeURIComponent(
      ticker,
    )}/cash-flow?${fundamentalsParams(period, limit)}`,
  );
}

export function getKeyMetrics(
  ticker: string,
  period: FundamentalsPeriod,
  limit = 5,
) {
  return apiRequest<KeyMetricsResult>(
    `/api/fundamentals/${encodeURIComponent(
      ticker,
    )}/metrics?${fundamentalsParams(period, limit)}`,
  );
}

export function getComputedMetrics(
  ticker: string,
  period: FundamentalsPeriod,
  limit = 5,
) {
  return apiRequest<ComputedMetricsResult>(
    `/api/fundamentals/${encodeURIComponent(
      ticker,
    )}/computed-metrics?${fundamentalsParams(period, limit)}`,
  );
}

type ScreenerRequestParams = {
  filters?: ScreenerFilter[];
  sort?: ScreenerSort | null;
  period?: "annual" | "quarter";
  page?: number;
  limit?: number;
};

export function getScreener({
  filters = [],
  sort = null,
  period = "annual",
  page = 1,
  limit = 25,
}: ScreenerRequestParams = {}) {
  const search = new URLSearchParams({
    period,
    page: String(page),
    limit: String(limit),
  });

  if (filters.length) {
    search.set("filters", JSON.stringify(filters));
  }

  if (sort) {
    search.set("sort", JSON.stringify(sort));
  }

  return apiRequest<ScreenerResponse>(`/api/screener?${search}`);
}

export function refreshScreener(period: "annual" | "quarter" = "annual") {
  const search = new URLSearchParams({ period });

  return apiRequest<ScreenerRefreshResult>(`/api/screener/refresh?${search}`, {
    method: "POST",
  });
}

export function getRankings({
  strategy = "magic_formula",
  period = "annual",
  limit = 50,
  includeIneligible = true,
  filters = [],
  sort = null,
  screenId = null,
}: {
  strategy?: RankingStrategy;
  period?: "annual" | "quarter";
  limit?: number;
  includeIneligible?: boolean;
  filters?: RankingFilter[];
  sort?: RankingSort | null;
  screenId?: string | null;
} = {}) {
  const search = new URLSearchParams({
    strategy,
    period,
    limit: String(limit),
    includeIneligible: String(includeIneligible),
  });

  if (filters.length) {
    search.set("filters", JSON.stringify(filters));
  }

  if (sort) {
    search.set("sort", JSON.stringify(sort));
  }

  if (screenId) {
    search.set("screenId", screenId);
  }

  return apiRequest<RankingResponse>(`/api/rankings?${search}`);
}

export function refreshRankings({
  strategy = "magic_formula",
  period = "annual",
  screenId = null,
  scope = "universe",
  tickers = [],
  staleOnly = false,
}: {
  strategy?: RankingStrategy;
  period?: "annual" | "quarter";
  screenId?: string | null;
  scope?: "universe" | "tickers" | "stale_only" | "scheduled";
  tickers?: string[];
  staleOnly?: boolean;
} = {}) {
  const search = new URLSearchParams({
    strategy,
    period,
    scope,
    staleOnly: String(staleOnly),
  });

  if (screenId) {
    search.set("screenId", screenId);
  }

  if (tickers.length) {
    search.set("tickers", tickers.join(","));
  }

  return apiRequest<RefreshJob>(`/api/rankings/refresh?${search}`, {
    method: "POST",
  });
}

export function createRankingRefreshJob({
  strategy = "magic_formula",
  period = "annual",
  screenId = null,
  scope = "universe",
  tickers = [],
  staleOnly = false,
  run = true,
}: {
  strategy?: RankingStrategy;
  period?: "annual" | "quarter";
  screenId?: string | null;
  scope?: "universe" | "tickers" | "stale_only" | "scheduled";
  tickers?: string[];
  staleOnly?: boolean;
  run?: boolean;
} = {}) {
  const search = new URLSearchParams({
    strategy,
    period,
    scope,
    staleOnly: String(staleOnly),
    run: String(run),
  });

  if (screenId) {
    search.set("screenId", screenId);
  }

  if (tickers.length) {
    search.set("tickers", tickers.join(","));
  }

  return apiRequest<RefreshJob>(`/api/jobs/ranking-refresh?${search}`, {
    method: "POST",
  });
}

export function listRefreshJobs({
  jobType = "ranking_refresh",
  status,
  limit = 5,
}: {
  jobType?: string;
  status?: RefreshJobStatus;
  limit?: number;
} = {}) {
  const search = new URLSearchParams({
    jobType,
    limit: String(limit),
  });

  if (status) {
    search.set("status", status);
  }

  return apiRequest<RefreshJobCollection>(`/api/jobs?${search}`);
}

export function getRefreshJob(jobId: string) {
  return apiRequest<RefreshJob>(`/api/jobs/${jobId}`);
}

export function getRefreshJobEvents(jobId: string) {
  return apiRequest<RefreshJobEventCollection>(`/api/jobs/${jobId}/events`);
}

export function cancelRefreshJob(jobId: string) {
  return apiRequest<RefreshJob>(`/api/jobs/${jobId}/cancel`, {
    method: "POST",
  });
}

export function listRefreshPolicies({
  includeDisabled = true,
  limit = 50,
}: {
  includeDisabled?: boolean;
  limit?: number;
} = {}) {
  const search = new URLSearchParams({
    includeDisabled: String(includeDisabled),
    limit: String(limit),
  });

  return apiRequest<RefreshPolicyCollection>(`/api/refresh-policies?${search}`);
}

export function createRefreshPolicy(payload: Partial<RefreshPolicy>) {
  return apiRequest<RefreshPolicy>("/api/refresh-policies", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateRefreshPolicy(
  policyId: string,
  payload: Partial<RefreshPolicy>,
) {
  return apiRequest<RefreshPolicy>(`/api/refresh-policies/${policyId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function setRefreshPolicyEnabled(policyId: string, enabled: boolean) {
  return apiRequest<RefreshPolicy>(
    `/api/refresh-policies/${policyId}/${enabled ? "enable" : "disable"}`,
    {
      method: "POST",
    },
  );
}

export function runRefreshPolicyNow(policyId: string) {
  return apiRequest<RefreshPolicyRunResult>(
    `/api/refresh-policies/${policyId}/run-now`,
    {
      method: "POST",
    },
  );
}

export function runDueRefreshPolicies() {
  return apiRequest<DueRefreshPolicyRunResult>(
    "/api/jobs/run-due-refresh-policies",
    {
      method: "POST",
    },
  );
}

export function listRankingRefreshRuns({
  strategy = "magic_formula",
  period = "annual",
  limit = 5,
}: {
  strategy?: RankingStrategy;
  period?: "annual" | "quarter";
  limit?: number;
} = {}) {
  const search = new URLSearchParams({
    strategy,
    period,
    limit: String(limit),
  });

  return apiRequest<RankingRefreshRunCollection>(
    `/api/rankings/refresh-runs?${search}`,
  );
}

export function listRankingRuns({
  strategy = "magic_formula",
  period = "annual",
  limit = 5,
}: {
  strategy?: RankingStrategy;
  period?: "annual" | "quarter";
  limit?: number;
} = {}) {
  const search = new URLSearchParams({
    strategy,
    period,
    limit: String(limit),
  });

  return apiRequest<RankingRunCollection>(`/api/rankings/runs?${search}`);
}

export function getRankingRunChanges(runId: string) {
  return apiRequest<RankingRunChanges>(
    `/api/rankings/runs/${encodeURIComponent(runId)}/changes`,
  );
}

export function listRankingScreens({
  includeArchived = false,
  includeDeleted = false,
  limit = 25,
}: {
  includeArchived?: boolean;
  includeDeleted?: boolean;
  limit?: number;
} = {}) {
  const search = new URLSearchParams({
    includeArchived: String(includeArchived),
    includeDeleted: String(includeDeleted),
    limit: String(limit),
  });

  return apiRequest<SavedRankingScreenCollection>(
    `/api/rankings/screens?${search}`,
  );
}

export function getRankingScreen(screenId: string) {
  return apiRequest<SavedRankingScreen>(
    `/api/rankings/screens/${encodeURIComponent(screenId)}`,
  );
}

export function createRankingScreen(payload: Partial<SavedRankingScreen>) {
  return apiRequest<SavedRankingScreen>("/api/rankings/screens", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateRankingScreen(
  screenId: string,
  payload: Partial<SavedRankingScreen>,
) {
  return apiRequest<SavedRankingScreen>(
    `/api/rankings/screens/${encodeURIComponent(screenId)}`,
    {
      method: "PATCH",
      body: JSON.stringify(payload),
    },
  );
}

export function duplicateRankingScreen(screenId: string, name?: string) {
  return apiRequest<SavedRankingScreen>(
    `/api/rankings/screens/${encodeURIComponent(screenId)}/duplicate`,
    {
      method: "POST",
      body: JSON.stringify({ name }),
    },
  );
}

export function setRankingScreenLifecycle(
  screenId: string,
  action: "archive" | "restore" | "delete",
) {
  const encodedScreenId = encodeURIComponent(screenId);

  if (action === "delete") {
    return apiRequest<SavedRankingScreen>(
      `/api/rankings/screens/${encodedScreenId}`,
      { method: "DELETE" },
    );
  }

  return apiRequest<SavedRankingScreen>(
    `/api/rankings/screens/${encodedScreenId}/${action}`,
    { method: "POST" },
  );
}

export function getMagicFormulaRanking({
  period = "annual",
  limit = 50,
}: {
  period?: "annual" | "quarter";
  limit?: number;
} = {}) {
  const search = new URLSearchParams({
    period,
    limit: String(limit),
  });

  return apiRequest<RankingResponse>(`/api/rankings/magic-formula?${search}`);
}

export function getDcfValuation(ticker: string) {
  return apiRequest<DCFResult>(
    `/api/valuation/dcf/${encodeURIComponent(ticker)}`,
  );
}

export function getDcfScenario(ticker: string, scenarioId: string) {
  return apiRequest<DCFResult>(
    `/api/valuation/dcf/${encodeURIComponent(
      ticker,
    )}/scenarios/${encodeURIComponent(scenarioId)}`,
  );
}

export function listDcfScenarios(ticker: string, limit = 10) {
  const search = new URLSearchParams({ limit: String(limit) });

  return apiRequest<ValuationScenarioCollection>(
    `/api/valuation/dcf/${encodeURIComponent(ticker)}/scenarios?${search}`,
  );
}

export function getDcfComparison(ticker: string, limit = 5) {
  const search = new URLSearchParams({ limit: String(limit) });

  return apiRequest<ValuationScenarioComparison>(
    `/api/valuation/dcf/${encodeURIComponent(ticker)}/comparison?${search}`,
  );
}

export function getDcfScenarioDiff(
  ticker: string,
  leftScenarioId: string,
  rightScenarioId: string,
  options: {
    leftVersionId?: string | null;
    rightVersionId?: string | null;
  } = {},
) {
  const search = new URLSearchParams({
    leftScenarioId,
    rightScenarioId,
  });

  if (options.leftVersionId) {
    search.set("leftVersionId", options.leftVersionId);
  }

  if (options.rightVersionId) {
    search.set("rightVersionId", options.rightVersionId);
  }

  return apiRequest<ValuationScenarioDiff>(
    `/api/valuation/dcf/${encodeURIComponent(ticker)}/compare?${search}`,
  );
}

export function exportDcfAssumptions(ticker: string, scenarioId: string) {
  return apiRequest<ValuationAssumptionExport>(
    `/api/valuation/dcf/${encodeURIComponent(
      ticker,
    )}/export/${encodeURIComponent(scenarioId)}`,
  );
}

export function importDcfAssumptions(
  ticker: string,
  payload: Record<string, unknown>,
) {
  return apiRequest<DCFResult>(
    `/api/valuation/dcf/${encodeURIComponent(ticker)}/import`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );
}

export function runDcfValuation(
  ticker: string,
  payload: Record<string, unknown>,
) {
  return apiRequest<DCFResult>(
    `/api/valuation/dcf/${encodeURIComponent(ticker)}`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );
}

export function createDcfScenarioVersion(
  ticker: string,
  scenarioId: string,
  payload: Record<string, unknown>,
) {
  return apiRequest<DCFResult>(
    `/api/valuation/dcf/${encodeURIComponent(
      ticker,
    )}/scenarios/${encodeURIComponent(scenarioId)}/versions`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );
}

export function renameDcfScenario(
  ticker: string,
  scenarioId: string,
  name: string,
) {
  return apiRequest<DCFResult>(
    `/api/valuation/dcf/${encodeURIComponent(
      ticker,
    )}/scenarios/${encodeURIComponent(scenarioId)}/rename`,
    {
      method: "PATCH",
      body: JSON.stringify({ name }),
    },
  );
}

export function duplicateDcfScenario(
  ticker: string,
  scenarioId: string,
  name?: string,
) {
  return apiRequest<DCFResult>(
    `/api/valuation/dcf/${encodeURIComponent(
      ticker,
    )}/scenarios/${encodeURIComponent(scenarioId)}/duplicate`,
    {
      method: "POST",
      body: JSON.stringify({ name }),
    },
  );
}

export function setDcfScenarioLifecycle(
  ticker: string,
  scenarioId: string,
  action: "archive" | "restore" | "delete",
) {
  const encodedTicker = encodeURIComponent(ticker);
  const encodedScenarioId = encodeURIComponent(scenarioId);

  if (action === "delete") {
    return apiRequest<DCFResult>(
      `/api/valuation/dcf/${encodedTicker}/scenarios/${encodedScenarioId}`,
      { method: "DELETE" },
    );
  }

  return apiRequest<DCFResult>(
    `/api/valuation/dcf/${encodedTicker}/scenarios/${encodedScenarioId}/${action}`,
    { method: "POST" },
  );
}

export function getDcfScenarioHistory(ticker: string, scenarioId: string) {
  return apiRequest<ValuationScenarioHistory>(
    `/api/valuation/dcf/${encodeURIComponent(
      ticker,
    )}/scenarios/${encodeURIComponent(scenarioId)}/history`,
  );
}

export function listDcfNotes(ticker: string, scenarioId: string) {
  return apiRequest<ValuationNotesResult>(
    `/api/valuation/dcf/${encodeURIComponent(
      ticker,
    )}/scenarios/${encodeURIComponent(scenarioId)}/notes`,
  );
}

export function addDcfNote(
  ticker: string,
  scenarioId: string,
  payload: {
    text: string;
    attachmentType?: ValuationNote["attachmentType"];
    fieldPath?: string | null;
    warningCode?: string | null;
  },
) {
  return apiRequest<ValuationNote>(
    `/api/valuation/dcf/${encodeURIComponent(
      ticker,
    )}/scenarios/${encodeURIComponent(scenarioId)}/notes`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );
}

export function getDcfSensitivity(ticker: string) {
  return apiRequest<SensitivityGrid>(
    `/api/valuation/dcf/${encodeURIComponent(ticker)}/sensitivity`,
  );
}

export function listWatchlists({
  includeArchived = false,
  includeDeleted = false,
  limit = 50,
}: {
  includeArchived?: boolean;
  includeDeleted?: boolean;
  limit?: number;
} = {}) {
  const search = new URLSearchParams({
    includeArchived: String(includeArchived),
    includeDeleted: String(includeDeleted),
    limit: String(limit),
  });

  return apiRequest<WatchlistCollection>(`/api/watchlists?${search}`);
}

export function createWatchlist(payload: CreateWatchlistPayload) {
  return apiRequest<Watchlist>("/api/watchlists", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getWatchlist(watchlistId: string) {
  return apiRequest<Watchlist>(
    `/api/watchlists/${encodeURIComponent(watchlistId)}`,
  );
}

export function updateWatchlist(
  watchlistId: string,
  payload: UpdateWatchlistPayload,
) {
  return apiRequest<Watchlist>(
    `/api/watchlists/${encodeURIComponent(watchlistId)}`,
    {
      method: "PATCH",
      body: JSON.stringify(payload),
    },
  );
}

export function setWatchlistLifecycle(
  watchlistId: string,
  action: "archive" | "restore" | "delete",
) {
  const encodedWatchlistId = encodeURIComponent(watchlistId);

  if (action === "delete") {
    return apiRequest<Watchlist>(`/api/watchlists/${encodedWatchlistId}`, {
      method: "DELETE",
    });
  }

  return apiRequest<Watchlist>(
    `/api/watchlists/${encodedWatchlistId}/${action}`,
    {
      method: "POST",
    },
  );
}

export function addWatchlistItem(
  watchlistId: string,
  payload: AddWatchlistItemPayload,
) {
  return apiRequest<Watchlist>(
    `/api/watchlists/${encodeURIComponent(watchlistId)}/items`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );
}

export function updateWatchlistItem(
  watchlistId: string,
  ticker: string,
  payload: UpdateWatchlistItemPayload,
) {
  const encodedWatchlistId = encodeURIComponent(watchlistId);
  const encodedTicker = encodeURIComponent(ticker);

  return apiRequest<Watchlist>(
    `/api/watchlists/${encodedWatchlistId}/items/${encodedTicker}`,
    {
      method: "PATCH",
      body: JSON.stringify(payload),
    },
  );
}

export function removeWatchlistItem(watchlistId: string, ticker: string) {
  const encodedWatchlistId = encodeURIComponent(watchlistId);
  const encodedTicker = encodeURIComponent(ticker);

  return apiRequest<Watchlist>(
    `/api/watchlists/${encodedWatchlistId}/items/${encodedTicker}`,
    {
      method: "DELETE",
    },
  );
}

export function listWatchlistViews(
  watchlistId: string,
  {
    includeArchived = false,
    includeDeleted = false,
    limit = 50,
  }: {
    includeArchived?: boolean;
    includeDeleted?: boolean;
    limit?: number;
  } = {},
) {
  const search = new URLSearchParams({
    includeArchived: String(includeArchived),
    includeDeleted: String(includeDeleted),
    limit: String(limit),
  });

  return apiRequest<SavedWatchlistViewCollection>(
    `/api/watchlists/${encodeURIComponent(watchlistId)}/views?${search}`,
  );
}

export function getWatchlistView(watchlistId: string, viewId: string) {
  return apiRequest<SavedWatchlistView>(
    `/api/watchlists/${encodeURIComponent(
      watchlistId,
    )}/views/${encodeURIComponent(viewId)}`,
  );
}

export function createWatchlistView(
  watchlistId: string,
  payload: WatchlistViewPayload,
) {
  return apiRequest<SavedWatchlistView>(
    `/api/watchlists/${encodeURIComponent(watchlistId)}/views`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );
}

export function updateWatchlistView(
  watchlistId: string,
  viewId: string,
  payload: WatchlistViewPayload,
) {
  return apiRequest<SavedWatchlistView>(
    `/api/watchlists/${encodeURIComponent(
      watchlistId,
    )}/views/${encodeURIComponent(viewId)}`,
    {
      method: "PATCH",
      body: JSON.stringify(payload),
    },
  );
}

export function duplicateWatchlistView(
  watchlistId: string,
  viewId: string,
  name?: string,
) {
  return apiRequest<SavedWatchlistView>(
    `/api/watchlists/${encodeURIComponent(
      watchlistId,
    )}/views/${encodeURIComponent(viewId)}/duplicate`,
    {
      method: "POST",
      body: JSON.stringify({ name }),
    },
  );
}

export function setWatchlistViewLifecycle(
  watchlistId: string,
  viewId: string,
  action: "archive" | "restore" | "delete",
) {
  const encodedWatchlistId = encodeURIComponent(watchlistId);
  const encodedViewId = encodeURIComponent(viewId);

  if (action === "delete") {
    return apiRequest<SavedWatchlistView>(
      `/api/watchlists/${encodedWatchlistId}/views/${encodedViewId}`,
      { method: "DELETE" },
    );
  }

  return apiRequest<SavedWatchlistView>(
    `/api/watchlists/${encodedWatchlistId}/views/${encodedViewId}/${action}`,
    { method: "POST" },
  );
}

export function getWatchlistIntelligence(
  watchlistId: string,
  {
    filters = [],
    sort = null,
    viewId = null,
  }: {
    filters?: WatchlistFilter[];
    sort?: WatchlistSort | null;
    viewId?: string | null;
  } = {},
) {
  const search = new URLSearchParams();

  if (filters.length) {
    search.set("filters", JSON.stringify(filters));
  }

  if (sort) {
    search.set("sort", JSON.stringify(sort));
  }

  if (viewId) {
    search.set("viewId", viewId);
  }

  const suffix = search.toString() ? `?${search}` : "";

  return apiRequest<WatchlistIntelligence>(
    `/api/watchlists/${encodeURIComponent(watchlistId)}/intelligence${suffix}`,
  );
}

export function refreshWatchlist({
  watchlistId,
  period = "annual",
  staleOnly = true,
  strategy = "magic_formula",
}: {
  watchlistId: string;
  period?: "annual" | "quarter";
  staleOnly?: boolean;
  strategy?: RankingStrategy;
}) {
  const search = new URLSearchParams({
    period,
    staleOnly: String(staleOnly),
    strategy,
  });

  return apiRequest<RefreshJob>(
    `/api/watchlists/${encodeURIComponent(watchlistId)}/refresh?${search}`,
    { method: "POST" },
  );
}

export function getWatchlistRefreshHistory(watchlistId: string, limit = 25) {
  const search = new URLSearchParams({ limit: String(limit) });

  return apiRequest<WatchlistRefreshHistory>(
    `/api/watchlists/${encodeURIComponent(
      watchlistId,
    )}/refresh-history?${search}`,
  );
}

export function getWatchlistStaleness(watchlistId: string) {
  return apiRequest<WatchlistStalenessResult>(
    `/api/watchlists/${encodeURIComponent(watchlistId)}/staleness`,
  );
}

export function getWatchlistAlerts(
  watchlistId: string,
  { includeDismissed = false }: { includeDismissed?: boolean } = {},
) {
  const search = new URLSearchParams({
    includeDismissed: String(includeDismissed),
  });

  return apiRequest<WatchlistAlertsResult>(
    `/api/watchlists/${encodeURIComponent(watchlistId)}/alerts?${search}`,
  );
}

export function getWatchlistAlertHistory(watchlistId: string) {
  return apiRequest<WatchlistAlertHistory>(
    `/api/watchlists/${encodeURIComponent(watchlistId)}/alerts/history`,
  );
}

export function acknowledgeWatchlistAlert(
  watchlistId: string,
  alertId: string,
  acknowledgedBy = "local-user",
) {
  return apiRequest<WatchlistAlertsResult["alerts"][number]>(
    `/api/watchlists/${encodeURIComponent(
      watchlistId,
    )}/alerts/${encodeURIComponent(alertId)}/acknowledge`,
    {
      method: "POST",
      body: JSON.stringify({ acknowledgedBy }),
    },
  );
}

export function dismissWatchlistAlert(watchlistId: string, alertId: string) {
  return apiRequest<WatchlistAlertsResult["alerts"][number]>(
    `/api/watchlists/${encodeURIComponent(
      watchlistId,
    )}/alerts/${encodeURIComponent(alertId)}/dismiss`,
    { method: "POST" },
  );
}

export function restoreWatchlistAlert(watchlistId: string, alertId: string) {
  return apiRequest<WatchlistAlertsResult["alerts"][number]>(
    `/api/watchlists/${encodeURIComponent(
      watchlistId,
    )}/alerts/${encodeURIComponent(alertId)}/restore`,
    { method: "POST" },
  );
}
