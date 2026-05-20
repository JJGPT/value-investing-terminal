export type HealthResponse = {
  status: "ok";
  service: string;
  version: string;
  environment: string;
  message: string;
  apiStatusPath: string;
  diagnosticsPath: string;
  docsPath: string;
};

export type ProviderConnectionState =
  | "connected"
  | "not_connected"
  | "degraded"
  | "not_implemented";

export type ProviderConnectionStatus = {
  provider: string;
  state: ProviderConnectionState;
  message: string;
  requiredEnvironmentVariables?: string[];
  lastCheckedAt: string | null;
  lastSuccessfulCallAt?: string | null;
  lastErrorMessage?: string | null;
};

export type ApiStatus = {
  status: "ok" | "degraded";
  service: string;
  version: string;
  environment: string;
  message: string;
  providers: ProviderConnectionStatus[];
};

export type EnvironmentVariableStatus = {
  name: string;
  present: boolean;
  required: boolean;
};

export type CacheTtlSettings = {
  securitySearchSeconds: number;
  securityLookupSeconds: number;
  marketSnapshotSeconds: number;
};

export type EndpointReadinessState =
  | "ready"
  | "degraded"
  | "blocked"
  | "not_implemented";

export type EndpointReadiness = {
  name: string;
  method: string;
  path: string;
  state: EndpointReadinessState;
  message: string;
};

export type MarketDataDiagnostics = {
  provider: ProviderConnectionStatus;
  environment: EnvironmentVariableStatus[];
  cacheTtls: CacheTtlSettings;
  endpointReadiness: EndpointReadiness[];
  message: string;
};

export type FundamentalsPeriod = "annual" | "quarter" | "ttm";

export type FundamentalsCacheTtlSettings = {
  companyProfileSeconds: number;
  incomeStatementSeconds: number;
  balanceSheetSeconds: number;
  cashFlowSeconds: number;
  keyMetricsSeconds: number;
  computedMetricsSeconds: number;
};

export type SnapshotState = "persisted" | "provider_fallback" | "missing";

export type SnapshotProvenance = {
  provider: string;
  providerVersion: string;
  fetchedAt: string;
  sourceSymbol: string;
};

export type SnapshotComputedFrom = {
  statementPeriod: Extract<FundamentalsPeriod, "annual" | "quarter">;
  incomeStatementFiscalYear: string | null;
  incomeStatementFiscalPeriod: string | null;
  balanceSheetFiscalYear: string | null;
  balanceSheetFiscalPeriod: string | null;
  cashFlowFiscalYear: string | null;
  cashFlowFiscalPeriod: string | null;
  keyMetricsFiscalYear: string | null;
  keyMetricsFiscalPeriod: string | null;
};

export type SnapshotMetadata = {
  state: SnapshotState;
  schemaVersion: number;
  refreshedAt: string | null;
  isStale: boolean;
  ageSeconds: number | null;
  provenance: SnapshotProvenance | null;
  computedFrom: SnapshotComputedFrom | null;
  computedAt: string | null;
};

export type SnapshotFreshnessSummary = {
  period: Extract<FundamentalsPeriod, "annual" | "quarter">;
  universeSize: number;
  persistedCount: number;
  freshCount: number;
  staleCount: number;
  missingCount: number;
  oldestRefreshedAt: string | null;
  newestRefreshedAt: string | null;
  maxAgeSeconds: number | null;
  staleAfterSeconds: number;
};

export type SnapshotStoreStatus = {
  provider: string;
  state: "connected" | "degraded";
  message: string;
  path: string;
};

export type FundamentalsDiagnostics = {
  provider: ProviderConnectionStatus;
  environment: EnvironmentVariableStatus[];
  cacheTtls: FundamentalsCacheTtlSettings;
  endpointReadiness: EndpointReadiness[];
  supportedPeriods: FundamentalsPeriod[];
  defaultPeriod: FundamentalsPeriod;
  screener?: ScreenerDiagnostics;
  message: string;
};

export type ProbeLatency = {
  securityLookup: number | null;
  marketSnapshot: number | null;
  total: number;
};

export type Security = {
  ticker: string;
  name: string;
  exchange: string | null;
  region: string | null;
  currency: string | null;
  assetType: "equity" | "fund" | "adr" | "unknown";
  provider: string | null;
  providerState: ProviderConnectionState;
};

export type SecuritySearchResult = {
  query: string;
  results: Security[];
  provider: ProviderConnectionStatus;
  message: string;
};

export type CompanyOverview = {
  ticker: string;
  security: Security | null;
  businessSummary: string | null;
  sector: string | null;
  industry: string | null;
  domicile: string | null;
  fiscalYearEnd: string | null;
  provider: ProviderConnectionStatus;
  message: string;
};

export type MarketSnapshot = {
  ticker: string;
  price: number | null;
  currency: string | null;
  marketCap: number | null;
  enterpriseValue: number | null;
  volume: number | null;
  asOf: string | null;
  provider: ProviderConnectionStatus;
  message: string;
};

export type MarketDataProbe = {
  ticker: string;
  provider: ProviderConnectionStatus;
  securityLookup: CompanyOverview | null;
  marketSnapshot: MarketSnapshot | null;
  latencyMs: ProbeLatency;
  error: string | null;
  message: string;
};

export type QualityFlag = string;

export type FinancialSourceMetadata = {
  provider: string;
  fetchedAt: string;
  sourceSymbol: string;
  currency: string | null;
  fiscalYear: string | null;
  fiscalPeriod: string | null;
  qualityFlags: QualityFlag[];
};

export type CompanyProfile = FinancialSourceMetadata & {
  ticker: string;
  name: string | null;
  exchange: string | null;
  sector: string | null;
  industry: string | null;
  country: string | null;
  website: string | null;
  marketCap: number | null;
  beta: number | null;
  price: number | null;
  description: string | null;
};

export type IncomeStatement = FinancialSourceMetadata & {
  date: string | null;
  revenue: number | null;
  grossProfit: number | null;
  operatingIncome: number | null;
  ebitda: number | null;
  netIncome: number | null;
  eps: number | null;
  epsDiluted: number | null;
  sharesDiluted: number | null;
};

export type BalanceSheet = FinancialSourceMetadata & {
  date: string | null;
  cashAndEquivalents: number | null;
  totalAssets: number | null;
  currentAssets: number | null;
  totalLiabilities: number | null;
  currentLiabilities: number | null;
  totalDebt: number | null;
  shareholdersEquity: number | null;
  retainedEarnings: number | null;
};

export type CashFlowStatement = FinancialSourceMetadata & {
  date: string | null;
  operatingCashFlow: number | null;
  capitalExpenditures: number | null;
  freeCashFlow: number | null;
  dividendsPaid: number | null;
  shareRepurchases: number | null;
  debtRepayment: number | null;
  debtIssuance: number | null;
  netChangeInCash: number | null;
};

export type KeyMetrics = FinancialSourceMetadata & {
  date: string | null;
  revenuePerShare: number | null;
  netIncomePerShare: number | null;
  freeCashFlowPerShare: number | null;
  bookValuePerShare: number | null;
  returnOnInvestedCapital: number | null;
  returnOnEquity: number | null;
  debtToEquity: number | null;
  currentRatio: number | null;
  priceToEarnings: number | null;
  priceToBook: number | null;
  priceToSales: number | null;
  enterpriseValueToEbitda: number | null;
};

export type ComputedMetrics = FinancialSourceMetadata & {
  date: string | null;
  period: FundamentalsPeriod;
  sourceProviders: string[];
  calculationEngine: string;
  grossMargin: number | null;
  operatingMargin: number | null;
  netMargin: number | null;
  freeCashFlowMargin: number | null;
  revenueGrowthYoY: number | null;
  netIncomeGrowthYoY: number | null;
  operatingIncomeGrowthYoY: number | null;
  freeCashFlowGrowthYoY: number | null;
  returnOnEquity: number | null;
  debtToEquity: number | null;
  currentRatio: number | null;
  freeCashFlowPerShare: number | null;
  bookValuePerShare: number | null;
  earningsPerShareDiluted: number | null;
  investedCapital: number | null;
  returnOnInvestedCapital: number | null;
};

export type CompanyProfileResult = {
  ticker: string;
  profile: CompanyProfile | null;
  provider: ProviderConnectionStatus;
  message: string;
};

export type IncomeStatementResult = {
  ticker: string;
  period: FundamentalsPeriod;
  limit: number;
  incomeStatements: IncomeStatement[];
  provider: ProviderConnectionStatus;
  message: string;
};

export type BalanceSheetResult = {
  ticker: string;
  period: FundamentalsPeriod;
  limit: number;
  balanceSheets: BalanceSheet[];
  provider: ProviderConnectionStatus;
  message: string;
};

export type CashFlowStatementResult = {
  ticker: string;
  period: FundamentalsPeriod;
  limit: number;
  cashFlowStatements: CashFlowStatement[];
  provider: ProviderConnectionStatus;
  message: string;
};

export type KeyMetricsResult = {
  ticker: string;
  period: FundamentalsPeriod;
  limit: number;
  metrics: KeyMetrics[];
  provider: ProviderConnectionStatus;
  message: string;
};

export type ComputedMetricsResult = {
  ticker: string;
  period: FundamentalsPeriod;
  limit: number;
  computedMetrics: ComputedMetrics[];
  provider: ProviderConnectionStatus;
  message: string;
};

export type ScreenerMetricField =
  | "marketCap"
  | "revenue"
  | "revenueGrowthYoY"
  | "grossMargin"
  | "operatingMargin"
  | "netMargin"
  | "freeCashFlowMargin"
  | "returnOnEquity"
  | "returnOnInvestedCapital"
  | "debtToEquity"
  | "currentRatio"
  | "freeCashFlowPerShare"
  | "bookValuePerShare"
  | "price"
  | "peRatio"
  | "pbRatio"
  | "psRatio";

export type ScreenerFilterOperator =
  | "gt"
  | "gte"
  | "lt"
  | "lte"
  | "eq"
  | "between";

export type ScreenerFilter = {
  field: ScreenerMetricField;
  operator: ScreenerFilterOperator;
  value: number | [number, number];
};

export type ScreenerSort = {
  field: ScreenerMetricField;
  direction: "asc" | "desc";
};

export type ScreenerQuery = {
  filters: ScreenerFilter[];
  sort: ScreenerSort | null;
  period: Extract<FundamentalsPeriod, "annual" | "quarter">;
  page: number;
  limit: number;
};

export type ScreenerMetrics = Record<ScreenerMetricField, number | null>;

export type ScreenerSourceMetadata = {
  provider: string;
  fetchedAt: string | null;
  sourceSymbol: string;
  currency: string | null;
  fiscalYear: string | null;
  fiscalPeriod: string | null;
  sourceProviders: string[];
};

export type ScreenerResultRow = {
  ticker: string;
  companyName: string | null;
  currency: string | null;
  period: Extract<FundamentalsPeriod, "annual" | "quarter">;
  metrics: ScreenerMetrics;
  qualityFlags: QualityFlag[];
  provider: ProviderConnectionStatus;
  source: ScreenerSourceMetadata;
  snapshot?: SnapshotMetadata;
  message: string;
};

export type ScreenerPagination = {
  page: number;
  limit: number;
  total: number;
  totalPages: number;
  hasNextPage: boolean;
  hasPreviousPage: boolean;
};

export type ScreenerUniverse = {
  name: string;
  size: number;
  tickers: string[];
};

export type ScreenerResponse = {
  query: ScreenerQuery;
  rows: ScreenerResultRow[];
  provider: ProviderConnectionStatus;
  pagination: ScreenerPagination;
  universe: ScreenerUniverse;
  message: string;
};

export type ScreenerDiagnostics = {
  readiness: EndpointReadinessState;
  universeName: string;
  universeSize: number;
  persistedUniverseSize: number;
  providerDependency: ProviderConnectionStatus;
  snapshotStore: SnapshotStoreStatus;
  snapshotFreshness: SnapshotFreshnessSummary[];
  cacheBacked: boolean;
  cacheTtls: FundamentalsCacheTtlSettings;
  endpointReadiness: EndpointReadiness[];
  message: string;
};

export type ScreenerRefreshFailure = {
  ticker: string;
  message: string;
};

export type ScreenerRefreshResult = {
  period: Extract<FundamentalsPeriod, "annual" | "quarter">;
  universe: ScreenerUniverse;
  status: "completed" | "partial" | "failed";
  refreshedCount: number;
  failedCount: number;
  failures: ScreenerRefreshFailure[];
  provider: ProviderConnectionStatus;
  repository: SnapshotStoreStatus;
  startedAt: string;
  completedAt: string;
  message: string;
};

export type RankingStrategy =
  | "magic_formula"
  | "quality"
  | "value"
  | "growth"
  | "profitability";

export type RankingQualityFlag = string;
export type RankingQualityFlags = RankingQualityFlag[];
export type RankingEligibilityStatus =
  | "eligible"
  | "ineligible"
  | "unranked_missing_data";

export type RankingEligibilitySettings = {
  minimumMarketCap: number;
  minimumPrice: number;
  minimumVolume: number | null;
  excludeFinancials: boolean;
  excludeUtilities: boolean;
  requirePositiveEnterpriseValue: boolean;
  requirePositiveInvestedCapital: boolean;
  requirePositiveEbit: boolean;
};

export type RankingFilterOperator = ScreenerFilterOperator;

export type RankingFilter = {
  field:
    | "rank"
    | "score"
    | "earningsYield"
    | "returnOnCapital"
    | "enterpriseValue"
    | "investedCapital"
    | "ebit"
    | "marketCap"
    | "price";
  operator: RankingFilterOperator;
  value: number | [number, number];
};

export type RankingSort = {
  field: RankingFilter["field"];
  direction: "asc" | "desc";
};

export type SavedRankingScreenStatus = "active" | "archived" | "deleted";

export type SavedRankingScreen = {
  screenId: string;
  schemaVersion: number;
  name: string;
  strategy: RankingStrategy;
  filters: RankingFilter[];
  eligibilitySettings: RankingEligibilitySettings;
  sorting: RankingSort | null;
  period: Extract<FundamentalsPeriod, "annual" | "quarter">;
  limit: number;
  status: SavedRankingScreenStatus;
  parentScreenId?: string | null;
  createdAt: string;
  updatedAt: string;
  archivedAt: string | null;
  deletedAt: string | null;
  message: string;
};

export type SavedRankingScreenCollection = {
  screens: SavedRankingScreen[];
  message: string;
};

export type MagicFormulaInputs = {
  ticker: string;
  ebit: number | null;
  enterpriseValue: number | null;
  marketCap: number | null;
  totalDebt: number | null;
  cashAndEquivalents: number | null;
  investedCapital: number | null;
  tangibleCapital: number | null;
  price?: number | null;
  volume?: number | null;
  sector?: string | null;
  industry?: string | null;
  currency: string | null;
  qualityFlags: RankingQualityFlags;
};

export type MagicFormulaResult = {
  inputs: MagicFormulaInputs;
  earningsYield: number | null;
  returnOnCapital: number | null;
  earningsYieldRank: number | null;
  returnOnCapitalRank: number | null;
  combinedRankScore: number | null;
  qualityFlags: RankingQualityFlags;
  methodology: string;
};

export type RankingInput = {
  ticker: string;
  period: Extract<FundamentalsPeriod, "annual" | "quarter">;
  screenerMetrics: Partial<ScreenerMetrics>;
  magicFormula: MagicFormulaResult;
  qualityFlags: RankingQualityFlags;
};

export type RankingResultRow = {
  rank: number | null;
  ticker: string;
  companyName: string | null;
  currency: string | null;
  strategy: RankingStrategy;
  score: number | null;
  scoreComponents: Record<string, number | null>;
  magicFormula: MagicFormulaResult;
  eligibilityStatus: RankingEligibilityStatus;
  eligibilityReasons: string[];
  qualityFlags: RankingQualityFlags;
  provider: ProviderConnectionStatus;
  source: ScreenerSourceMetadata & {
    snapshotState?: SnapshotState;
    snapshot?: SnapshotMetadata;
  };
  computedAt: string;
  rankingEngineVersion: string;
  audit: {
    eligibilityStatus: RankingEligibilityStatus;
    eligibilityReasons: string[];
    eligibilitySettings: RankingEligibilitySettings;
    inputValues: MagicFormulaInputs;
    formulaComponents: Record<string, number | null>;
    snapshotMetadata?: SnapshotMetadata | null;
    computedAt: string;
    rankingEngineVersion: string;
  };
  message: string;
};

export type RankingDiagnosticsSummary = {
  availableStrategies: RankingStrategy[];
  eligibleRows: number;
  ineligibleRows: number;
  unrankedMissingDataRows: number;
  excludedRows: number;
  engineVersion: string;
};

export type RankingRunSummary = {
  runId: string;
  strategy: RankingStrategy;
  period: Extract<FundamentalsPeriod, "annual" | "quarter">;
  schemaVersion: number;
  rankingEngineVersion: string;
  computedAt: string;
  universe: ScreenerUniverse;
  eligibilitySettings: RankingEligibilitySettings;
  filters?: RankingFilter[];
  sorting?: RankingSort | null;
  summary: RankingDiagnosticsSummary & {
    totalRows?: number;
  };
};

export type RankingRun = RankingRunSummary & {
  provider: ProviderConnectionStatus;
  rows: RankingResultRow[];
  savedScreen?: Pick<
    SavedRankingScreen,
    "screenId" | "name" | "status" | "strategy" | "period" | "limit"
  > | null;
  message: string;
};

export type RankingRunCollection = {
  runs: RankingRunSummary[];
  message: string;
};

export type RankingChangeType =
  | "new_entrant"
  | "dropped"
  | "eligibility_changed"
  | "unchanged";

export type RankingChangeRow = {
  ticker: string;
  currentRank: number | null;
  previousRank: number | null;
  rankChange: number | null;
  currentScore: number | null;
  previousScore: number | null;
  scoreChange: number | null;
  currentEligibilityStatus: RankingEligibilityStatus | null;
  previousEligibilityStatus: RankingEligibilityStatus | null;
  eligibilityChange: string;
  changeType: RankingChangeType;
};

export type RankingRunChanges = {
  runId: string;
  run: RankingRunSummary;
  previousRun: RankingRunSummary | null;
  changes: RankingChangeRow[];
  summary: {
    newEntrants: number;
    dropped: number;
    changedEligibility: number;
    unchanged: number;
  };
  message: string;
};

export type RankingRefreshState = "queued" | "running" | "completed" | "failed";

export type RankingRefreshScope = {
  type: "universe" | "tickers" | "stale_only" | "scheduled";
  tickers: string[];
  staleOnly: boolean;
  screenId?: string | null;
  refreshScopeVersion: string;
};

export type RankingRefreshWarning = {
  code: string;
  message: string;
};

export type RankingRefreshError = {
  message: string;
};

export type RankingRefreshTransition = {
  state: RankingRefreshState;
  at: string;
  message: string;
};

export type RankingRefreshRun = {
  refreshId: string;
  schemaVersion: number;
  status: RankingRefreshState;
  state: RankingRefreshState;
  strategy: RankingStrategy;
  period: Extract<FundamentalsPeriod, "annual" | "quarter">;
  scope: RankingRefreshScope;
  startedAt: string | null;
  completedAt: string | null;
  failedAt: string | null;
  durationMs: number | null;
  warnings: RankingRefreshWarning[];
  errors: RankingRefreshError[];
  stateTransitions: RankingRefreshTransition[];
  metadata: {
    synchronous: boolean;
    supportsPerTickerRefresh: boolean;
    supportsPartialRefresh: boolean;
    supportsStaleOnlyRefresh: boolean;
    supportsScheduledRefresh: boolean;
  };
  runId: string | null;
  run: RankingRun | null;
  message: string;
};

export type RankingRefreshRunCollection = {
  refreshRuns: RankingRefreshRun[];
  message: string;
};

export type RefreshJobStatus =
  | "queued"
  | "running"
  | "completed"
  | "failed"
  | "cancelled";

export type RefreshJobScope = {
  type: "universe" | "tickers" | "stale_only" | "scheduled" | string;
  tickers: string[];
  staleOnly: boolean;
  screenId?: string | null;
  watchlistId?: string | null;
  period?: Extract<FundamentalsPeriod, "annual" | "quarter"> | string | null;
  strategy?: RankingStrategy | string | null;
  requestedTickers?: string[];
  scopeVersion?: string;
  schemaVersion?: number;
};

export type RefreshJobResultMetadata = {
  refreshId?: string | null;
  runId?: string | null;
  strategy?: RankingStrategy | string | null;
  period?: Extract<FundamentalsPeriod, "annual" | "quarter"> | string | null;
  status?: RankingRefreshState | string | null;
  scope?: RankingRefreshScope | RefreshJobScope | null;
  startedAt?: string | null;
  completedAt?: string | null;
  failedAt?: string | null;
  cancelled?: boolean;
  refreshedCount?: number | null;
  skippedFreshCount?: number | null;
  freshCount?: number | null;
  staleCount?: number | null;
  missingCount?: number | null;
  staleOnly?: {
    enabled?: boolean;
    staleAfterSeconds?: number;
    universeSize?: number;
    freshCount?: number;
    staleCount?: number;
    missingCount?: number;
    degradedCount?: number;
    refreshedCount?: number;
    skippedFreshCount?: number;
    refreshTickers?: string[];
    skippedTickers?: string[];
    classification?: Array<{
      ticker: string;
      state: "fresh" | "stale" | "missing" | "degraded" | string;
      ageSeconds: number | null;
      refreshed: boolean;
      reasons?: string[];
    }>;
  };
};

export type RefreshJob = {
  jobId: string;
  jobType: "ranking_refresh" | "screener_refresh" | string;
  status: RefreshJobStatus;
  scope: RefreshJobScope;
  payload: Record<string, unknown>;
  schemaVersion: number;
  createdAt: string;
  startedAt: string | null;
  completedAt: string | null;
  failedAt: string | null;
  durationMs: number | null;
  warnings: RankingRefreshWarning[];
  errors: RankingRefreshError[];
  resultMetadata: RefreshJobResultMetadata;
  result: RankingRefreshRun | Record<string, unknown> | null;
  message: string;
  cancelled?: boolean;
};

export type RefreshJobSummary = Omit<
  RefreshJob,
  "payload" | "result" | "message"
>;

export type RefreshJobEvent = {
  eventId: string;
  jobId: string;
  sequence: number;
  eventType: string;
  status: RefreshJobStatus | RankingRefreshState | string;
  message?: string | null;
  createdAt: string;
  payload: Record<string, unknown>;
};

export type RefreshJobCollection = {
  jobs: RefreshJob[];
  message: string;
};

export type RefreshJobEventCollection = {
  jobId: string;
  events: RefreshJobEvent[];
  message: string;
};

export type RefreshJobStoreDiagnostics = {
  repository: SnapshotStoreStatus;
  jobCount: number;
  eventCount: number;
  statusCounts: Partial<Record<RefreshJobStatus, number>>;
  jobTypeDistribution: Array<{
    jobType: string;
    count: number;
  }>;
  queuedCount: number;
  runningCount: number;
  failedCount: number;
  latestJob: RefreshJobSummary | null;
  staleAfterSeconds: number;
};

export type RefreshPolicyTarget = "ranking" | "screener";

export type RefreshPolicyScheduleHint =
  | "manual"
  | "stale_only"
  | "hourly"
  | "daily"
  | "weekly"
  | "always";

export type RefreshPolicy = {
  policyId: string;
  schemaVersion: number;
  name: string;
  target: RefreshPolicyTarget;
  strategy: RankingStrategy | "screener" | string;
  period: Extract<FundamentalsPeriod, "annual" | "quarter">;
  scope: RefreshJobScope;
  staleAfterSeconds: number;
  enabled: boolean;
  scheduleHint: RefreshPolicyScheduleHint;
  lastRunAt: string | null;
  nextRunHint: string | null;
  createdAt: string;
  updatedAt: string;
};

export type RefreshPolicyCollection = {
  policies: RefreshPolicy[];
  message: string;
};

export type RefreshPolicyRunResult = {
  policy: RefreshPolicy;
  job: RefreshJob;
  message: string;
};

export type DueRefreshPolicyRunResult = {
  schemaVersion: number;
  policiesInspected: number;
  duePolicies: number;
  skippedPolicies: Array<{
    policyId: string;
    name: string;
    target: RefreshPolicyTarget | string;
    strategy: string;
    period: string;
    scheduleHint: string;
    nextRunHint: string | null;
    reason: string;
  }>;
  jobs: Array<{
    policy: RefreshPolicy;
    job: RefreshJob;
  }>;
  ranAt: string;
  message: string;
};

export type RefreshPolicyStoreDiagnostics = {
  repository: SnapshotStoreStatus;
  policyCount: number;
  enabledPolicyCount: number;
  duePolicyCount: number;
  targetDistribution: Array<{
    target: RefreshPolicyTarget | string;
    count: number;
  }>;
  latestPolicyTriggeredJobs: RefreshJobSummary[];
  staleOnlyRefreshReady: boolean;
  staleAfterSeconds: number;
};

export type RankingStoreDiagnostics = {
  repository: SnapshotStoreStatus;
  runCount: number;
  rowSnapshotCount: number;
  savedScreenCounts: Partial<Record<SavedRankingScreenStatus, number>>;
  refreshRunCount: number;
  workflowStatusDistribution: Array<{
    status: RankingRefreshState;
    count: number;
  }>;
  failedRefreshCount: number;
  latestRefreshes: RankingRefreshRun[];
  latestRefreshByStrategy: Record<string, RankingRefreshRun>;
  latestRuns: RankingRunSummary[];
  latestRunByStrategy: Record<string, RankingRunSummary>;
  engineVersionDistribution: Array<{
    rankingEngineVersion: string;
    count: number;
  }>;
  staleRunCount: number;
  staleAfterSeconds: number;
};

export type RankingResponse = {
  strategy: RankingStrategy;
  period: Extract<FundamentalsPeriod, "annual" | "quarter">;
  limit: number;
  includeIneligible: boolean;
  filters: RankingFilter[];
  sorting: RankingSort | null;
  rows: RankingResultRow[];
  provider: ProviderConnectionStatus;
  universe: ScreenerUniverse;
  diagnostics: RankingDiagnosticsSummary;
  eligibilitySettings: RankingEligibilitySettings;
  latestRun: RankingRunSummary | null;
  message: string;
};

export type RankingDiagnostics = {
  provider: ProviderConnectionStatus;
  engineVersion: string;
  availableStrategies: RankingStrategy[];
  defaultStrategy: RankingStrategy;
  defaultPeriod: Extract<FundamentalsPeriod, "annual" | "quarter">;
  universe: ScreenerUniverse;
  eligibleRows: number;
  excludedRows: number;
  ineligibleRows: number;
  unrankedMissingDataRows: number;
  rankingStore: RankingStoreDiagnostics;
  jobStore: RefreshJobStoreDiagnostics;
  policyStore: RefreshPolicyStoreDiagnostics;
  endpointReadiness: EndpointReadiness[];
  message: string;
};

export type ValuationQualityFlag = string;
export type ValuationQualityFlags = ValuationQualityFlag[];

export type ValuationAssumption = {
  value: number | null;
  source: string;
  rationale: string;
  editable: boolean;
  unit: "decimal" | "years" | "currency" | "multiple";
  qualityFlags: ValuationQualityFlags;
};

export type DiscountRateAssumptions = {
  riskFreeRate: ValuationAssumption;
  equityRiskPremium: ValuationAssumption;
  beta: ValuationAssumption;
  costOfEquity: ValuationAssumption;
  preTaxCostOfDebt: ValuationAssumption;
  taxRate: ValuationAssumption;
  afterTaxCostOfDebt: ValuationAssumption;
  debtWeight: ValuationAssumption;
  equityWeight: ValuationAssumption;
  wacc: ValuationAssumption;
};

export type GrowthAssumptions = {
  projectionYears: ValuationAssumption;
  revenueGrowthRate: ValuationAssumption;
};

export type MarginAssumptions = {
  operatingMargin: ValuationAssumption;
};

export type ReinvestmentAssumptions = {
  reinvestmentRate: ValuationAssumption;
};

export type ShareCountAssumptions = {
  dilutedShareGrowthRate: ValuationAssumption;
  stockBasedCompensationDilutionRate: ValuationAssumption;
  buybackRate: ValuationAssumption;
};

export type NetDebtAssumptions = {
  operatingCashPercentOfRevenue: ValuationAssumption;
  leaseDebt: ValuationAssumption;
  preferredEquity: ValuationAssumption;
  minorityInterest: ValuationAssumption;
};

export type TerminalValueAssumptions = {
  terminalGrowthRate: ValuationAssumption;
};

export type ValuationWarning = {
  code: string;
  severity: "low" | "medium" | "high";
  message: string;
  value: number | null;
};

export type ValuationModelMetadata = {
  dcfEngineVersion: string;
  valuationMethodologyVersion: string;
  modelVersion: string;
  computationTimestamp: string;
};

export type ValuationScenario = {
  id: string;
  ticker: string;
  name: string;
  schemaVersion: number;
  modelVersion: string;
  versionNumber: number | null;
  versionId: string | null;
  priorVersionId: string | null;
  parentScenarioId: string | null;
  status: "active" | "archived" | "deleted";
  archivedAt: string | null;
  deletedAt: string | null;
  createdAt: string;
  updatedAt: string;
  discountRate: DiscountRateAssumptions;
  growth: GrowthAssumptions;
  margin: MarginAssumptions;
  reinvestment: ReinvestmentAssumptions;
  shareCount: ShareCountAssumptions;
  netDebt: NetDebtAssumptions;
  terminalValue: TerminalValueAssumptions;
  qualityFlags: ValuationQualityFlags;
};

export type ValuationScenarioSummary = {
  scenarioId: string | null;
  ticker: string | null;
  name: string;
  schemaVersion: number | null;
  modelVersion: string | null;
  versionNumber: number | null;
  versionId: string | null;
  priorVersionId: string | null;
  parentScenarioId: string | null;
  status: "active" | "archived" | "deleted";
  archivedAt: string | null;
  deletedAt: string | null;
  createdAt: string | null;
  updatedAt: string | null;
  intrinsicValuePerShare: number | null;
  equityValue: number | null;
  enterpriseValue: number | null;
  currency: string | null;
  providerState: ProviderConnectionState | null;
  qualityFlags: ValuationQualityFlags;
  warnings: ValuationWarning[];
};

export type ValuationScenarioCollection = {
  ticker: string;
  scenarios: ValuationScenarioSummary[];
  latestScenarioId: string | null;
  count: number;
  message: string;
};

export type ValuationScenarioComparisonAssumptions = {
  revenueGrowthRate: number | null;
  operatingMargin: number | null;
  reinvestmentRate: number | null;
  taxRate: number | null;
  wacc: number | null;
  terminalGrowthRate: number | null;
};

export type ValuationScenarioComparisonRow = ValuationScenarioSummary & {
  assumptions: ValuationScenarioComparisonAssumptions;
};

export type ValuationScenarioComparison = {
  ticker: string;
  rows: ValuationScenarioComparisonRow[];
  count: number;
  message: string;
};

export type ValuationDiffValue = {
  delta: number | null;
  percentDelta: number | null;
};

export type ValuationDiffRow = ValuationDiffValue & {
  fieldPath: string;
  leftValue: unknown;
  rightValue: unknown;
};

export type ValuationScenarioDiff = {
  ticker: string;
  left: ValuationScenarioSummary;
  right: ValuationScenarioSummary;
  valuationDelta: Record<string, ValuationDiffValue>;
  assumptionDiffs: ValuationDiffRow[];
  outputDiffs: ValuationDiffRow[];
  warningDiffs: {
    added: ValuationWarning[];
    removed: ValuationWarning[];
    shared: ValuationWarning[];
  };
  message: string;
};

export type ValuationAuditEvent = {
  id: string;
  scenarioId: string;
  ticker: string;
  versionId: string;
  versionNumber: number;
  changeType: string;
  fieldPath: string | null;
  previousValue: unknown;
  newValue: unknown;
  createdAt: string;
  message?: string | null;
};

export type ValuationNote = {
  id: string;
  ticker: string;
  scenarioId: string;
  schemaVersion: number;
  attachmentType: "scenario_version" | "assumption" | "warning";
  versionId: string | null;
  versionNumber: number | null;
  fieldPath: string | null;
  warningCode: string | null;
  text: string;
  createdAt: string;
  immutable: boolean;
};

export type ValuationScenarioHistory = {
  ticker: string;
  scenarioId: string;
  scenario: ValuationScenarioSummary;
  versions: Array<
    ValuationScenarioSummary & { modelMetadata?: ValuationModelMetadata }
  >;
  auditEvents: ValuationAuditEvent[];
  message: string;
};

export type ValuationNotesResult = {
  ticker: string;
  scenarioId: string;
  scenario: ValuationScenarioSummary;
  notes: ValuationNote[];
  message: string;
};

export type ValuationAssumptionExport = {
  schemaVersion: number;
  modelVersion: string;
  exportedAt: string;
  ticker: string;
  sourceScenario: ValuationScenarioSummary;
  assumptions: Record<string, Record<string, number | null>>;
  warnings: ValuationWarning[];
  message: string;
};

export type ValuationAssumptionLimit = {
  group: string;
  name: string;
  minimum: number;
  maximum: number;
};

export type ValuationRepositoryHealth = {
  scenarioCount: number;
  versionCount: number;
  auditEventCount: number;
  noteCount: number;
  orphanedScenarioVersionCount: number;
  modelVersionDistribution: Array<{
    modelVersion: string;
    count: number;
  }>;
  staleScenarioCount: number;
  staleAfterSeconds: number;
  reproducibility: {
    completeScenarioCount: number;
    incompleteScenarioCount: number;
  };
};

export type ValuationDiagnostics = {
  provider: ProviderConnectionStatus;
  engineVersion: string;
  valuationMethodologyVersion: string;
  schemaVersion: number;
  repository: SnapshotStoreStatus;
  repositoryHealth: ValuationRepositoryHealth;
  ticker: string;
  savedScenarioCount: number;
  latestScenario: ValuationScenarioSummary | null;
  assumptionLimits: ValuationAssumptionLimit[];
  warningRules: Array<{
    code: string;
    message: string;
  }>;
  endpointReadiness: EndpointReadiness[];
  message: string;
};

export type DCFProjectionYear = {
  year: number;
  revenue: number | null;
  revenueGrowthRate: number | null;
  operatingIncome: number | null;
  taxRate: number | null;
  nopat: number | null;
  reinvestment: number | null;
  fcff: number | null;
  discountFactor: number | null;
  presentValueFcff: number | null;
  sharesDiluted: number | null;
  shareCountGrowthRate: number | null;
};

export type SensitivityCell = {
  rowValue: number;
  columnValue: number;
  intrinsicValuePerShare: number | null;
  qualityFlags: ValuationQualityFlags;
};

export type SensitivityHeatmapCell = SensitivityCell & {
  intensity: number | null;
  tone: "low" | "mid" | "high" | "unavailable";
};

export type SensitivityHeatmap = {
  rowVariable: SensitivityMatrix["rowVariable"];
  columnVariable: SensitivityMatrix["columnVariable"];
  minimumIntrinsicValuePerShare: number | null;
  maximumIntrinsicValuePerShare: number | null;
  cells: SensitivityHeatmapCell[][];
};

export type SensitivityVisualization = {
  currency: string | null;
  heatmaps: Record<string, SensitivityHeatmap>;
  message: string;
};

export type SensitivityMatrix = {
  rowVariable: "wacc" | "terminalGrowthRate" | "operatingMargin";
  columnVariable: "wacc" | "terminalGrowthRate" | "operatingMargin";
  rowValues: number[];
  columnValues: number[];
  cells: SensitivityCell[][];
};

export type SensitivityGrid = {
  waccTerminalGrowth: SensitivityMatrix;
  marginWacc: SensitivityMatrix;
  marginTerminalGrowth: SensitivityMatrix;
};

export type ReproducibilityReference = {
  provider: string | null;
  providerVersion?: string | null;
  providerState?: ProviderConnectionState | null;
  fetchedAt: string | null;
  sourceSymbol: string | null;
  currency: string | null;
  fiscalYear?: string | null;
  fiscalPeriod?: string | null;
  asOf?: string | null;
  qualityFlags: ValuationQualityFlags;
};

export type ValuationReproducibility = {
  schemaVersion: number;
  statementSnapshotReferences: {
    incomeStatement: ReproducibilityReference | null;
    balanceSheet: ReproducibilityReference | null;
    cashFlowStatement: ReproducibilityReference | null;
  };
  metricSnapshotsUsed: ReproducibilityReference[];
  marketDataSnapshotReference: ReproducibilityReference;
  valuationEngineVersions: {
    dcfEngineVersion: string;
    valuationMethodologyVersion: string;
    modelVersion: string;
  };
  sensitivityConfiguration: Record<
    string,
    {
      rowVariable: string;
      columnVariable: string;
      rowValues: number[];
      columnValues: number[];
    }
  >;
  calculationTimestampChain: {
    materialsLoadedAt: string;
    assumptionsBuiltAt: string;
    valuationComputedAt: string;
  };
  completeness: Record<string, boolean>;
  qualityFlags: ValuationQualityFlags;
};

export type DCFResult = {
  ticker: string;
  schemaVersion: number;
  scenario: ValuationScenario;
  projections: DCFProjectionYear[];
  sensitivity: SensitivityGrid;
  sensitivityVisualization?: SensitivityVisualization;
  baseFinancials: {
    revenue: number | null;
    operatingIncome: number | null;
    freeCashFlow: number | null;
    cashAndEquivalents: number | null;
    operatingCash: number | null;
    excessCash: number | null;
    totalDebt: number | null;
    leaseDebt: number | null;
    preferredEquity: number | null;
    minorityInterest: number | null;
    sharesDiluted: number | null;
    marketPrice: number | null;
    currency: string | null;
    fiscalYear: string | null;
    fiscalPeriod: string | null;
  };
  modelMetadata: ValuationModelMetadata;
  reproducibility?: ValuationReproducibility;
  terminalValue: number | null;
  presentValueTerminalValue: number | null;
  enterpriseValue: number | null;
  netDebt: number | null;
  projectedSharesDiluted: number | null;
  equityValue: number | null;
  intrinsicValuePerShare: number | null;
  formulas: string[];
  provider: ProviderConnectionStatus;
  warnings: ValuationWarning[];
  qualityFlags: ValuationQualityFlags;
  createdAt: string;
  updatedAt: string;
  message: string;
};

export type WatchlistStatus = "active" | "archived" | "deleted";

export type WatchlistItemPriority = "low" | "medium" | "high" | string;

export type WatchlistWorkflowState =
  | "not_started"
  | "monitoring"
  | "needs_review"
  | "under_review"
  | "thesis_ready"
  | "archived"
  | string;

export type WatchlistThesisStatus =
  | "watching"
  | "researching"
  | "under_review"
  | "passed"
  | "owned"
  | string;

export type WatchlistItem = {
  ticker: string;
  companyName: string | null;
  addedAt: string;
  updatedAt: string;
  notes: string | null;
  tags: string[];
  targetPrice: number | null;
  thesisStatus: WatchlistThesisStatus | null;
  priority: WatchlistItemPriority | null;
  workflowState: WatchlistWorkflowState;
};

export type Watchlist = {
  watchlistId: string;
  id: string;
  schemaVersion: number;
  name: string;
  description: string | null;
  status: WatchlistStatus;
  items: WatchlistItem[];
  createdAt: string;
  updatedAt: string;
  archivedAt: string | null;
  deletedAt: string | null;
  provider: ProviderConnectionStatus;
  message: string;
};

export type WatchlistCollection = {
  watchlists: Watchlist[];
  provider: ProviderConnectionStatus;
  message: string;
};

export type WatchlistFilterField =
  | "ticker"
  | "tags"
  | "thesisStatus"
  | "priority"
  | "workflowState"
  | "valuationGap"
  | "rankingStatus"
  | "alertType"
  | "staleSnapshot"
  | "missingCriticalData"
  | "providerDegraded";

export type WatchlistFilter = {
  field: WatchlistFilterField;
  operator:
    | "eq"
    | "contains"
    | "gt"
    | "gte"
    | "lt"
    | "lte"
    | "between";
  value: string | number | boolean | [number, number] | string[];
};

export type WatchlistSortField =
  | "ticker"
  | "priority"
  | "valuationGap"
  | "latestRank"
  | "alertCount"
  | "snapshotFreshness"
  | "addedAt";

export type WatchlistSort = {
  field: WatchlistSortField;
  direction: "asc" | "desc";
};

export type WatchlistVisibleColumn =
  | "ticker"
  | "company"
  | "price"
  | "target"
  | "valuationGap"
  | "rank"
  | "eligibility"
  | "freshness"
  | "staleness"
  | "provider"
  | "status"
  | "workflowState"
  | "priority"
  | "alerts"
  | "flags"
  | "notes"
  | string;

export type SavedWatchlistView = {
  viewId: string;
  watchlistId: string;
  schemaVersion: number;
  name: string;
  filters: WatchlistFilter[];
  sorting: WatchlistSort | null;
  visibleColumns: WatchlistVisibleColumn[];
  status: WatchlistStatus;
  parentViewId?: string | null;
  createdAt: string;
  updatedAt: string;
  archivedAt: string | null;
  deletedAt: string | null;
  message: string;
};

export type SavedWatchlistViewCollection = {
  watchlistId: string;
  views: SavedWatchlistView[];
  message: string;
};

export type WatchlistFundamentalsFreshness = {
  period: Extract<FundamentalsPeriod, "annual" | "quarter"> | string;
  state: "fresh" | "stale" | "missing";
  refreshedAt: string | null;
  ageSeconds: number | null;
  isStale: boolean;
  metadata: SnapshotMetadata | null;
};

export type WatchlistComputedMetricsSnapshot = {
  state: SnapshotState;
  refreshedAt: string | null;
  computedAt: string | null;
  metrics: Partial<
    Pick<
      ComputedMetrics,
      | "grossMargin"
      | "operatingMargin"
      | "netMargin"
      | "freeCashFlowMargin"
      | "returnOnEquity"
      | "returnOnInvestedCapital"
      | "debtToEquity"
    >
  >;
  qualityFlags: QualityFlag[];
} | null;

export type WatchlistRankingSummary = {
  runId: string | null;
  strategy: RankingStrategy | string;
  period: Extract<FundamentalsPeriod, "annual" | "quarter"> | string;
  rank: number | null;
  score: number | null;
  companyName: string | null;
  eligibilityStatus: RankingEligibilityStatus;
  eligibilityReasons: string[];
  qualityFlags: RankingQualityFlags;
  computedAt: string | null;
  rankChange: RankingChangeRow | null;
  magicFormula: MagicFormulaResult | null;
} | null;

export type WatchlistValuationGap = {
  price: number | null;
  intrinsicValuePerShare: number | null;
  gapPercent: number | null;
  state: "available" | "unavailable";
  message: string;
};

export type WatchlistStalenessState =
  | "fresh"
  | "stale"
  | "missing"
  | "degraded";

export type WatchlistStalenessComponent = {
  dependency: string;
  state: WatchlistStalenessState;
  lastRefreshedAt: string | null;
  ageSeconds: number | null;
  reasons: string[];
};

export type WatchlistItemStaleness = {
  ticker: string;
  state: WatchlistStalenessState;
  staleReasons: string[];
  missingDependencies: string[];
  lastRefreshedAt: string | null;
  maxAgeSeconds: number | null;
  components: Record<string, WatchlistStalenessComponent>;
  schemaVersion: number;
};

export type WatchlistAlertType =
  | "priceAboveTarget"
  | "priceBelowTarget"
  | "valuationGapAboveThreshold"
  | "rankingStatusChanged"
  | "snapshotStale"
  | "providerDegraded"
  | "missingCriticalData";

export type WatchlistAlert = {
  alertId: string;
  watchlistId: string;
  ticker: string;
  type: WatchlistAlertType;
  severity: "low" | "medium" | "high";
  message: string;
  createdAt: string;
  acknowledgedAt: string | null;
  acknowledgedBy: string | null;
  dismissedAt: string | null;
  status: "active" | "acknowledged" | "dismissed";
  schemaVersion: number;
  metadata: Record<string, unknown>;
};

export type WatchlistIntelligenceItem = {
  ticker: string;
  companyName: string | null;
  item: WatchlistItem;
  marketSnapshot: MarketSnapshot;
  fundamentalsSnapshot: WatchlistFundamentalsFreshness;
  computedMetricsSnapshot: WatchlistComputedMetricsSnapshot;
  ranking: WatchlistRankingSummary;
  magicFormulaEligibility: {
    status: RankingEligibilityStatus | string;
    reasons: string[];
  };
  valuation: ValuationScenarioSummary | null;
  staleness: WatchlistItemStaleness;
  valuationGap: WatchlistValuationGap;
  qualityFlags: QualityFlag[];
  alerts: WatchlistAlert[];
};

export type WatchlistIntelligence = {
  watchlist: Watchlist;
  items: WatchlistIntelligenceItem[];
  allItemCount: number;
  provider: ProviderConnectionStatus;
  alertCount: number;
  activeAlertCount: number;
  view: SavedWatchlistView | null;
  query: {
    filters: WatchlistFilter[];
    sorting: WatchlistSort | null;
    visibleColumns: WatchlistVisibleColumn[];
  };
  message: string;
};

export type WatchlistAlertsResult = {
  watchlist: Watchlist;
  alerts: WatchlistAlert[];
  provider: ProviderConnectionStatus;
  message: string;
};

export type WatchlistAlertHistory = WatchlistAlertsResult;

export type WatchlistStalenessResult = {
  watchlist: Watchlist;
  items: Array<
    WatchlistItemStaleness & {
      companyName: string | null;
      workflowState: WatchlistWorkflowState;
    }
  >;
  counts: Record<WatchlistStalenessState | "total", number>;
  provider: ProviderConnectionStatus;
  staleAfterSeconds: number;
  message: string;
};

export type WatchlistRefreshHistory = {
  watchlist: Watchlist;
  jobs: RefreshJob[];
  provider: ProviderConnectionStatus;
  message: string;
};

export type WatchlistStoreDiagnostics = {
  repository: SnapshotStoreStatus;
  watchlistCount: number;
  activeWatchlistCount: number;
  archivedWatchlistCount: number;
  itemCount: number;
  staleWatchlistItemCount: number;
  savedViewCount: number;
  activeAlertCount: number;
  acknowledgedAlertCount: number;
  dismissedAlertCount: number;
  staleAfterSeconds: number;
};

export type WatchlistDiagnostics = {
  provider: ProviderConnectionStatus;
  watchlistStore: WatchlistStoreDiagnostics;
  watchlistCount: number;
  watchlistItemCount: number;
  alertCount: number;
  staleWatchlistItemCount: number;
  savedWatchlistViewCount: number;
  activeAlertCount: number;
  acknowledgedAlertCount: number;
  dismissedAlertCount: number;
  watchlistRefresh: {
    ready: boolean;
    jobType: string;
    jobCount: number;
    failedJobCount: number;
    latestJob: RefreshJobSummary | null;
  };
  staleness: {
    counts: Record<WatchlistStalenessState | "total", number>;
    staleItemCount: number;
  };
  alertStore: {
    repository: SnapshotStoreStatus;
    activeAlertCount: number;
    acknowledgedAlertCount: number;
    dismissedAlertCount: number;
  };
  endpointReadiness: EndpointReadiness[];
  message: string;
};
