import { ApiState } from "../../components/data-status/api-state";
import { TerminalShell } from "../../components/shell/terminal-shell";
import { PlaceholderCard } from "../../components/ui/placeholder-card";
import { StatusList } from "../../components/ui/status-list";
import {
  getApiStatus,
  getFundamentalsDiagnostics,
  getMarketDataDiagnostics,
  getMarketDataProbe,
  getRankingDiagnostics,
  getValuationDiagnostics,
  getWatchlistDiagnostics,
} from "../../lib/api/client";

type DiagnosticsPageProps = {
  searchParams?: Promise<{
    ticker?: string | string[];
  }>;
};

function getQueryValue(value: string | string[] | undefined) {
  if (Array.isArray(value)) {
    return value[0] ?? "";
  }

  return value ?? "";
}

function formatOptionalNumber(value: number | null | undefined, suffix = "") {
  if (value === null || value === undefined) {
    return "Unavailable";
  }

  return `${value}${suffix}`;
}

export default async function DiagnosticsPage({
  searchParams,
}: DiagnosticsPageProps) {
  const params = searchParams ? await searchParams : {};
  const submittedTicker = getQueryValue(params.ticker).trim().toUpperCase();
  const probeTicker = submittedTicker || "AAPL";
  const [
    apiStatusResult,
    diagnosticsResult,
    fundamentalsDiagnosticsResult,
    valuationDiagnosticsResult,
    rankingDiagnosticsResult,
    watchlistDiagnosticsResult,
  ] = await Promise.all([
    getApiStatus(),
    getMarketDataDiagnostics(),
    getFundamentalsDiagnostics(),
    getValuationDiagnostics(probeTicker),
    getRankingDiagnostics(),
    getWatchlistDiagnostics(),
  ]);
  const probeResult = submittedTicker
    ? await getMarketDataProbe(probeTicker)
    : null;

  return (
    <TerminalShell
      eyebrow="Diagnostics"
      title="Data provider reliability workspace."
      description="A backend-only diagnostics view for API connectivity, provider health, endpoint readiness, cache settings, and safe configuration checks."
    >
      <section className="mb-4 grid gap-4 xl:grid-cols-[0.85fr_1.15fr]">
        <PlaceholderCard
          label="API"
          title="Backend connection"
          description="The web app reaches FastAPI through NEXT_PUBLIC_API_BASE_URL. Provider keys remain backend-only."
        >
          {apiStatusResult.ok ? (
            <StatusList
              items={[
                {
                  label: "Service",
                  status: apiStatusResult.data.service,
                },
                {
                  label: "Status",
                  status: apiStatusResult.data.status,
                },
                {
                  label: "Environment",
                  status: apiStatusResult.data.environment,
                },
                {
                  label: "Version",
                  status: apiStatusResult.data.version,
                },
              ]}
            />
          ) : (
            <>
              <ApiState
                title="Backend offline"
                message={apiStatusResult.error.message}
                endpoint={apiStatusResult.error.endpoint}
              />
              <p className="text-amber mt-4 text-sm leading-6">
                Start the API with npm run dev:api and confirm the frontend
                environment points to http://localhost:8000.
              </p>
            </>
          )}
        </PlaceholderCard>

        <PlaceholderCard
          label="Provider map"
          title="Configured backend providers"
          description="This is a safe overview of provider states exposed by /api/status; it never includes credential values."
        >
          {apiStatusResult.ok ? (
            <StatusList
              items={apiStatusResult.data.providers.map((provider) => ({
                label: provider.provider,
                status: provider.state,
              }))}
            />
          ) : (
            <p className="text-muted text-sm leading-6">
              Provider state is unavailable until the backend is reachable.
            </p>
          )}
        </PlaceholderCard>
      </section>

      {diagnosticsResult.ok ? (
        <section className="grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
          <PlaceholderCard
            label="Smoke test"
            title="Run market data probe"
            description="Probe calls the backend provider abstraction for one ticker. It never sends Alpaca keys to the browser."
          >
            <form
              className="flex flex-col gap-3 sm:flex-row"
              action="/diagnostics"
            >
              <div className="border-line bg-obsidian flex min-h-11 flex-1 items-center border px-3">
                <label
                  htmlFor="probe-ticker"
                  className="text-muted mr-3 font-mono text-[11px] uppercase"
                >
                  Ticker
                </label>
                <input
                  id="probe-ticker"
                  name="ticker"
                  defaultValue={probeTicker}
                  className="text-ink placeholder:text-muted min-w-0 flex-1 bg-transparent text-sm uppercase outline-none"
                />
              </div>
              <button
                type="submit"
                className="border-line text-muted hover:text-accent min-h-11 border px-4 font-mono text-[11px] uppercase transition"
              >
                Run probe
              </button>
            </form>
            {probeResult ? (
              <div className="mt-5 space-y-4">
                {probeResult.ok ? (
                  <>
                    <ApiState
                      title={`Probe ${probeResult.data.provider.state}`}
                      message={probeResult.data.message}
                      provider={probeResult.data.provider}
                      endpoint={`/api/diagnostics/market-data/probe?ticker=${probeTicker}`}
                    />
                    <StatusList
                      items={[
                        {
                          label: "Ticker",
                          status: probeResult.data.ticker,
                        },
                        {
                          label: "Security latency",
                          status: formatOptionalNumber(
                            probeResult.data.latencyMs.securityLookup,
                            "ms",
                          ),
                        },
                        {
                          label: "Snapshot latency",
                          status: formatOptionalNumber(
                            probeResult.data.latencyMs.marketSnapshot,
                            "ms",
                          ),
                        },
                        {
                          label: "Total latency",
                          status: formatOptionalNumber(
                            probeResult.data.latencyMs.total,
                            "ms",
                          ),
                        },
                        {
                          label: "Probe error",
                          status: probeResult.data.error ?? "none",
                        },
                      ]}
                    />
                  </>
                ) : (
                  <ApiState
                    title="Probe API unavailable"
                    message={probeResult.error.message}
                    endpoint={probeResult.error.endpoint}
                  />
                )}
              </div>
            ) : (
              <p className="text-muted mt-4 text-sm leading-6">
                Enter a ticker and run the probe to test the backend Alpaca
                path. AAPL is prefilled.
              </p>
            )}
          </PlaceholderCard>

          <PlaceholderCard
            label="Provider"
            title="Market data provider status"
            description="Provider credentials stay on the backend. This panel only shows safe operational metadata."
          >
            <ApiState
              title={`Provider ${diagnosticsResult.data.provider.state}`}
              message={diagnosticsResult.data.provider.message}
              provider={diagnosticsResult.data.provider}
              endpoint="/api/diagnostics/market-data"
            />
          </PlaceholderCard>

          <PlaceholderCard
            label="Configuration"
            title="Alpaca environment readiness"
            description="The API reports whether required variables are present, without exposing their values."
          >
            <StatusList
              items={diagnosticsResult.data.environment.map((variable) => ({
                label: variable.name,
                status: variable.present
                  ? "present"
                  : variable.required
                    ? "missing"
                    : "default",
              }))}
            />
            {diagnosticsResult.data.provider.state === "not_connected" ? (
              <p className="text-amber mt-4 text-sm leading-6">
                Alpaca keys are missing. Add backend environment variables to
                enable live market data.
              </p>
            ) : null}
          </PlaceholderCard>

          <PlaceholderCard
            label="Cache"
            title="In-memory TTL settings"
            description="These backend-only TTLs reduce repeated provider calls before a durable cache or database exists."
          >
            <StatusList
              items={[
                {
                  label: "Security search",
                  status: `${diagnosticsResult.data.cacheTtls.securitySearchSeconds}s`,
                },
                {
                  label: "Security lookup",
                  status: `${diagnosticsResult.data.cacheTtls.securityLookupSeconds}s`,
                },
                {
                  label: "Market snapshot",
                  status: `${diagnosticsResult.data.cacheTtls.marketSnapshotSeconds}s`,
                },
              ]}
            />
          </PlaceholderCard>

          <PlaceholderCard
            label="Readiness"
            title="Endpoint readiness"
            description="Readiness is derived from provider state and preserves the existing API contracts."
          >
            <StatusList
              items={diagnosticsResult.data.endpointReadiness.map(
                (endpoint) => ({
                  label: `${endpoint.method} ${endpoint.path}`,
                  status: endpoint.state,
                }),
              )}
            />
          </PlaceholderCard>

          <PlaceholderCard
            label="Provider history"
            title="Last success and error"
            description="Operational history is sanitized before reaching the browser."
          >
            <StatusList
              items={[
                {
                  label: "Last successful provider call",
                  status:
                    diagnosticsResult.data.provider.lastSuccessfulCallAt ??
                    "none",
                },
                {
                  label: "Last provider error",
                  status:
                    diagnosticsResult.data.provider.lastErrorMessage ?? "none",
                },
              ]}
            />
          </PlaceholderCard>

          {probeResult?.ok ? (
            <>
              <PlaceholderCard
                label="Probe security"
                title="Security lookup response"
                description="This is the normalized backend response from the security lookup contract."
              >
                <StatusList
                  items={[
                    {
                      label: "Ticker",
                      status:
                        probeResult.data.securityLookup?.ticker ??
                        "Unavailable",
                    },
                    {
                      label: "Security name",
                      status:
                        probeResult.data.securityLookup?.security?.name ??
                        "Unavailable",
                    },
                    {
                      label: "Exchange",
                      status:
                        probeResult.data.securityLookup?.security?.exchange ??
                        "Unavailable",
                    },
                    {
                      label: "Asset type",
                      status:
                        probeResult.data.securityLookup?.security?.assetType ??
                        "Unavailable",
                    },
                    {
                      label: "Provider state",
                      status:
                        probeResult.data.securityLookup?.provider.state ??
                        "Unavailable",
                    },
                  ]}
                />
              </PlaceholderCard>

              <PlaceholderCard
                label="Probe snapshot"
                title="Market snapshot response"
                description="Only real provider fields are shown. Missing values remain unavailable."
              >
                <StatusList
                  items={[
                    {
                      label: "Ticker",
                      status:
                        probeResult.data.marketSnapshot?.ticker ??
                        "Unavailable",
                    },
                    {
                      label: "Price",
                      status:
                        probeResult.data.marketSnapshot?.price === null ||
                        probeResult.data.marketSnapshot?.price === undefined
                          ? "Unavailable"
                          : `${probeResult.data.marketSnapshot.price} ${probeResult.data.marketSnapshot.currency ?? ""}`.trim(),
                    },
                    {
                      label: "Volume",
                      status: formatOptionalNumber(
                        probeResult.data.marketSnapshot?.volume,
                      ),
                    },
                    {
                      label: "As of",
                      status:
                        probeResult.data.marketSnapshot?.asOf ?? "Unavailable",
                    },
                    {
                      label: "Provider state",
                      status:
                        probeResult.data.marketSnapshot?.provider.state ??
                        "Unavailable",
                    },
                  ]}
                />
              </PlaceholderCard>
            </>
          ) : null}
        </section>
      ) : (
        <PlaceholderCard
          label="Diagnostics"
          title="Diagnostics API unavailable"
          description="The web app could not reach the backend diagnostics endpoint."
        >
          <ApiState
            title="API unavailable"
            message={diagnosticsResult.error.message}
            endpoint={diagnosticsResult.error.endpoint}
          />
        </PlaceholderCard>
      )}

      <section className="mt-4 grid gap-4 xl:grid-cols-[1fr_1fr]">
        {valuationDiagnosticsResult.ok ? (
          <>
            <PlaceholderCard
              label="Valuation engine"
              title="DCF route readiness"
              description="The valuation engine is platform-owned and uses saved scenario persistence separate from fundamentals snapshots."
            >
              <ApiState
                title={`Provider ${valuationDiagnosticsResult.data.provider.state}`}
                message={valuationDiagnosticsResult.data.provider.message}
                provider={valuationDiagnosticsResult.data.provider}
                endpoint={`/api/diagnostics/valuation?ticker=${probeTicker}`}
              />
            </PlaceholderCard>

            <PlaceholderCard
              label="Valuation scenarios"
              title="Scenario persistence"
              description="Saved DCF scenarios are stored as versioned SQLite payloads until a production database replaces local persistence."
            >
              <StatusList
                items={[
                  {
                    label: "Engine version",
                    status: valuationDiagnosticsResult.data.engineVersion,
                  },
                  {
                    label: "Repository",
                    status: valuationDiagnosticsResult.data.repository.state,
                  },
                  {
                    label: "Ticker",
                    status: valuationDiagnosticsResult.data.ticker,
                  },
                  {
                    label: "Saved scenarios",
                    status: String(
                      valuationDiagnosticsResult.data.savedScenarioCount,
                    ),
                  },
                  {
                    label: "Latest scenario",
                    status:
                      valuationDiagnosticsResult.data.latestScenario?.name ??
                      "none",
                  },
                ]}
              />
            </PlaceholderCard>

            <PlaceholderCard
              label="Valuation repository"
              title="Audit and reproducibility health"
              description="Repository diagnostics check immutable versions, notes, stale scenarios, orphaned records, and reproducibility metadata completeness."
            >
              <StatusList
                items={[
                  {
                    label: "Scenarios",
                    status: String(
                      valuationDiagnosticsResult.data.repositoryHealth
                        .scenarioCount,
                    ),
                  },
                  {
                    label: "Versions",
                    status: String(
                      valuationDiagnosticsResult.data.repositoryHealth
                        .versionCount,
                    ),
                  },
                  {
                    label: "Audit events",
                    status: String(
                      valuationDiagnosticsResult.data.repositoryHealth
                        .auditEventCount,
                    ),
                  },
                  {
                    label: "Notes",
                    status: String(
                      valuationDiagnosticsResult.data.repositoryHealth
                        .noteCount,
                    ),
                  },
                  {
                    label: "Orphaned versions",
                    status: String(
                      valuationDiagnosticsResult.data.repositoryHealth
                        .orphanedScenarioVersionCount,
                    ),
                  },
                  {
                    label: "Stale scenarios",
                    status: String(
                      valuationDiagnosticsResult.data.repositoryHealth
                        .staleScenarioCount,
                    ),
                  },
                  {
                    label: "Reproducibility complete",
                    status: String(
                      valuationDiagnosticsResult.data.repositoryHealth
                        .reproducibility.completeScenarioCount,
                    ),
                  },
                  {
                    label: "Model versions",
                    status:
                      valuationDiagnosticsResult.data.repositoryHealth.modelVersionDistribution
                        .map((item) => `${item.modelVersion}:${item.count}`)
                        .join(", ") || "none",
                  },
                ]}
              />
            </PlaceholderCard>

            <PlaceholderCard
              label="Valuation readiness"
              title="Endpoint readiness"
              description="Readiness covers DCF creation, saved scenario loading, and saved case comparison."
            >
              <StatusList
                items={valuationDiagnosticsResult.data.endpointReadiness.map(
                  (endpoint) => ({
                    label: `${endpoint.method} ${endpoint.path}`,
                    status: endpoint.state,
                  }),
                )}
              />
            </PlaceholderCard>

            {rankingDiagnosticsResult.ok ? (
              <PlaceholderCard
                label="Ranking engine"
                title="Ranking readiness"
                description="Rankings are deterministic screens over normalized fundamentals and snapshot-backed screener rows."
              >
                <ApiState
                  title={`Provider ${rankingDiagnosticsResult.data.provider.state}`}
                  message={rankingDiagnosticsResult.data.message}
                  provider={rankingDiagnosticsResult.data.provider}
                  endpoint="/api/diagnostics/rankings"
                />
                <div className="mt-4">
                  <StatusList
                    items={[
                      {
                        label: "Engine",
                        status: rankingDiagnosticsResult.data.engineVersion,
                      },
                      {
                        label: "Strategies",
                        status:
                          rankingDiagnosticsResult.data.availableStrategies.join(
                            ", ",
                          ),
                      },
                      {
                        label: "Universe",
                        status: `${rankingDiagnosticsResult.data.universe.size} tickers`,
                      },
                      {
                        label: "Eligible rows",
                        status: String(
                          rankingDiagnosticsResult.data.eligibleRows,
                        ),
                      },
                      {
                        label: "Ineligible rows",
                        status: String(
                          rankingDiagnosticsResult.data.ineligibleRows,
                        ),
                      },
                      {
                        label: "Missing-data rows",
                        status: String(
                          rankingDiagnosticsResult.data.unrankedMissingDataRows,
                        ),
                      },
                      {
                        label: "Ranking runs",
                        status: String(
                          rankingDiagnosticsResult.data.rankingStore.runCount,
                        ),
                      },
                      {
                        label: "Saved screens",
                        status: String(
                          rankingDiagnosticsResult.data.rankingStore
                            .savedScreenCounts.active ?? 0,
                        ),
                      },
                      {
                        label: "Refresh runs",
                        status: String(
                          rankingDiagnosticsResult.data.rankingStore
                            .refreshRunCount,
                        ),
                      },
                      {
                        label: "Refresh jobs",
                        status: String(
                          rankingDiagnosticsResult.data.jobStore.jobCount,
                        ),
                      },
                      {
                        label: "Refresh policies",
                        status: String(
                          rankingDiagnosticsResult.data.policyStore.policyCount,
                        ),
                      },
                      {
                        label: "Enabled/due policies",
                        status: `${rankingDiagnosticsResult.data.policyStore.enabledPolicyCount}/${rankingDiagnosticsResult.data.policyStore.duePolicyCount}`,
                      },
                      {
                        label: "Failed refreshes",
                        status: String(
                          rankingDiagnosticsResult.data.rankingStore
                            .failedRefreshCount,
                        ),
                      },
                      {
                        label: "Failed jobs",
                        status: String(
                          rankingDiagnosticsResult.data.jobStore.failedCount,
                        ),
                      },
                      {
                        label: "Queued/running jobs",
                        status: `${rankingDiagnosticsResult.data.jobStore.queuedCount}/${rankingDiagnosticsResult.data.jobStore.runningCount}`,
                      },
                      {
                        label: "Workflow states",
                        status:
                          rankingDiagnosticsResult.data.rankingStore.workflowStatusDistribution
                            .map((item) => `${item.status}:${item.count}`)
                            .join(", ") || "none",
                      },
                      {
                        label: "Job states",
                        status:
                          Object.entries(
                            rankingDiagnosticsResult.data.jobStore.statusCounts,
                          )
                            .map(([status, count]) => `${status}:${count}`)
                            .join(", ") || "none",
                      },
                      {
                        label: "Policy targets",
                        status:
                          rankingDiagnosticsResult.data.policyStore.targetDistribution
                            .map((item) => `${item.target}:${item.count}`)
                            .join(", ") || "none",
                      },
                      {
                        label: "Stale-only refresh",
                        status: rankingDiagnosticsResult.data.policyStore
                          .staleOnlyRefreshReady
                          ? "ready"
                          : "unavailable",
                      },
                      {
                        label: "Latest run",
                        status:
                          rankingDiagnosticsResult.data.rankingStore
                            .latestRuns[0]?.computedAt ?? "none",
                      },
                      {
                        label: "Latest refresh",
                        status:
                          rankingDiagnosticsResult.data.rankingStore
                            .latestRefreshes[0]?.completedAt ??
                          rankingDiagnosticsResult.data.rankingStore
                            .latestRefreshes[0]?.failedAt ??
                          "none",
                      },
                      {
                        label: "Latest job",
                        status:
                          rankingDiagnosticsResult.data.jobStore.latestJob
                            ?.completedAt ??
                          rankingDiagnosticsResult.data.jobStore.latestJob
                            ?.failedAt ??
                          rankingDiagnosticsResult.data.jobStore.latestJob
                            ?.startedAt ??
                          rankingDiagnosticsResult.data.jobStore.latestJob
                            ?.createdAt ??
                          "none",
                      },
                      {
                        label: "Stale runs",
                        status: String(
                          rankingDiagnosticsResult.data.rankingStore
                            .staleRunCount,
                        ),
                      },
                    ]}
                  />
                </div>
              </PlaceholderCard>
            ) : (
              <PlaceholderCard
                label="Ranking diagnostics"
                title="Ranking diagnostics API unavailable"
                description="The web app could not reach the backend ranking diagnostics endpoint."
              >
                <ApiState
                  title="API unavailable"
                  message={rankingDiagnosticsResult.error.message}
                  endpoint={rankingDiagnosticsResult.error.endpoint}
                />
              </PlaceholderCard>
            )}

            {watchlistDiagnosticsResult.ok ? (
              <PlaceholderCard
                label="Watchlists"
                title="Watchlist intelligence readiness"
                description="Watchlists are persistent research workspaces with deterministic alerts over snapshots, rankings, valuations, and provider status."
              >
                <ApiState
                  title={`Provider ${watchlistDiagnosticsResult.data.provider.state}`}
                  message={watchlistDiagnosticsResult.data.message}
                  provider={watchlistDiagnosticsResult.data.provider}
                  endpoint="/api/diagnostics/watchlists"
                />
                <div className="mt-4">
                  <StatusList
                    items={[
                      {
                        label: "Watchlists",
                        status: String(
                          watchlistDiagnosticsResult.data.watchlistCount,
                        ),
                      },
                      {
                        label: "Items",
                        status: String(
                          watchlistDiagnosticsResult.data.watchlistItemCount,
                        ),
                      },
                      {
                        label: "Alerts",
                        status: String(
                          watchlistDiagnosticsResult.data.alertCount,
                        ),
                      },
                      {
                        label: "Saved views",
                        status: String(
                          watchlistDiagnosticsResult.data
                            .savedWatchlistViewCount,
                        ),
                      },
                      {
                        label: "Active alerts",
                        status: String(
                          watchlistDiagnosticsResult.data.activeAlertCount,
                        ),
                      },
                      {
                        label: "Acknowledged alerts",
                        status: String(
                          watchlistDiagnosticsResult.data
                            .acknowledgedAlertCount,
                        ),
                      },
                      {
                        label: "Dismissed alerts",
                        status: String(
                          watchlistDiagnosticsResult.data.dismissedAlertCount,
                        ),
                      },
                      {
                        label: "Stale items",
                        status: String(
                          watchlistDiagnosticsResult.data
                            .staleWatchlistItemCount,
                        ),
                      },
                      {
                        label: "Store",
                        status:
                          watchlistDiagnosticsResult.data.watchlistStore
                            .repository.state,
                      },
                      {
                        label: "Archived lists",
                        status: String(
                          watchlistDiagnosticsResult.data.watchlistStore
                            .archivedWatchlistCount,
                        ),
                      },
                      {
                        label: "Alert store",
                        status:
                          watchlistDiagnosticsResult.data.alertStore.repository
                            .state,
                      },
                    ]}
                  />
                </div>
              </PlaceholderCard>
            ) : (
              <PlaceholderCard
                label="Watchlists"
                title="Watchlist diagnostics API unavailable"
                description="The web app could not reach the backend watchlist diagnostics endpoint."
              >
                <ApiState
                  title="API unavailable"
                  message={watchlistDiagnosticsResult.error.message}
                  endpoint={watchlistDiagnosticsResult.error.endpoint}
                />
              </PlaceholderCard>
            )}

            <PlaceholderCard
              label="Assumption validation"
              title="DCF hardening bounds"
              description="Out-of-range assumptions remain visible through quality flags instead of silently driving black-box outputs."
            >
              <StatusList
                items={valuationDiagnosticsResult.data.assumptionLimits.map(
                  (limit) => ({
                    label: `${limit.group}.${limit.name}`,
                    status: `${limit.minimum} to ${limit.maximum}`,
                  }),
                )}
              />
            </PlaceholderCard>
          </>
        ) : (
          <PlaceholderCard
            label="Valuation diagnostics"
            title="Valuation diagnostics API unavailable"
            description="The web app could not reach the backend valuation diagnostics endpoint."
          >
            <ApiState
              title="API unavailable"
              message={valuationDiagnosticsResult.error.message}
              endpoint={valuationDiagnosticsResult.error.endpoint}
            />
          </PlaceholderCard>
        )}

        {fundamentalsDiagnosticsResult.ok ? (
          <>
            <PlaceholderCard
              label="Fundamentals provider"
              title="FMP provider status"
              description="FMP credentials stay on the backend. This panel reports only safe readiness metadata."
            >
              <ApiState
                title={`Provider ${fundamentalsDiagnosticsResult.data.provider.state}`}
                message={fundamentalsDiagnosticsResult.data.provider.message}
                provider={fundamentalsDiagnosticsResult.data.provider}
                endpoint="/api/diagnostics/fundamentals"
              />
            </PlaceholderCard>

            <PlaceholderCard
              label="FMP configuration"
              title="Fundamentals environment readiness"
              description="The API reports whether required variables are present, without exposing their values."
            >
              <StatusList
                items={fundamentalsDiagnosticsResult.data.environment.map(
                  (variable) => ({
                    label: variable.name,
                    status: variable.present
                      ? "present"
                      : variable.required
                        ? "missing"
                        : "default",
                  }),
                )}
              />
              {fundamentalsDiagnosticsResult.data.provider.state ===
              "not_connected" ? (
                <p className="text-amber mt-4 text-sm leading-6">
                  FMP keys are missing. Add backend environment variables to
                  enable normalized fundamentals.
                </p>
              ) : null}
            </PlaceholderCard>

            <PlaceholderCard
              label="Fundamentals readiness"
              title="Endpoint readiness"
              description="Annual and quarterly contracts are provider-backed when FMP is configured. TTM is contract-ready for a future phase."
            >
              <StatusList
                items={fundamentalsDiagnosticsResult.data.endpointReadiness.map(
                  (endpoint) => ({
                    label: `${endpoint.method} ${endpoint.path}`,
                    status: endpoint.state,
                  }),
                )}
              />
            </PlaceholderCard>

            <PlaceholderCard
              label="Fundamentals cache"
              title="In-memory TTL settings"
              description="These backend-only TTLs reduce repeated FMP calls before a durable database or Redis cache exists."
            >
              <StatusList
                items={[
                  {
                    label: "Company profile",
                    status: `${fundamentalsDiagnosticsResult.data.cacheTtls.companyProfileSeconds}s`,
                  },
                  {
                    label: "Income statement",
                    status: `${fundamentalsDiagnosticsResult.data.cacheTtls.incomeStatementSeconds}s`,
                  },
                  {
                    label: "Balance sheet",
                    status: `${fundamentalsDiagnosticsResult.data.cacheTtls.balanceSheetSeconds}s`,
                  },
                  {
                    label: "Cash flow",
                    status: `${fundamentalsDiagnosticsResult.data.cacheTtls.cashFlowSeconds}s`,
                  },
                  {
                    label: "Key metrics",
                    status: `${fundamentalsDiagnosticsResult.data.cacheTtls.keyMetricsSeconds}s`,
                  },
                  {
                    label: "Computed metrics",
                    status: `${fundamentalsDiagnosticsResult.data.cacheTtls.computedMetricsSeconds}s`,
                  },
                ]}
              />
            </PlaceholderCard>

            {fundamentalsDiagnosticsResult.data.screener ? (
              <PlaceholderCard
                label="Screener readiness"
                title="Snapshot-backed screener dependency"
                description="The screener reads SQLite snapshots first and falls back to provider data only when rows are missing."
              >
                <StatusList
                  items={[
                    {
                      label: "Readiness",
                      status:
                        fundamentalsDiagnosticsResult.data.screener.readiness,
                    },
                    {
                      label: "Universe",
                      status: `${fundamentalsDiagnosticsResult.data.screener.universeSize} tickers`,
                    },
                    {
                      label: "Persisted universe",
                      status: `${fundamentalsDiagnosticsResult.data.screener.persistedUniverseSize} tickers`,
                    },
                    {
                      label: "Provider dependency",
                      status:
                        fundamentalsDiagnosticsResult.data.screener
                          .providerDependency.state,
                    },
                    {
                      label: "Snapshot store",
                      status:
                        fundamentalsDiagnosticsResult.data.screener
                          .snapshotStore.state,
                    },
                    {
                      label: "Snapshot-backed",
                      status: fundamentalsDiagnosticsResult.data.screener
                        .cacheBacked
                        ? "yes"
                        : "no",
                    },
                  ]}
                />
              </PlaceholderCard>
            ) : null}

            {fundamentalsDiagnosticsResult.data.screener ? (
              <PlaceholderCard
                label="Snapshot freshness"
                title="Screener row snapshots"
                description="Stale snapshots are still readable and clearly marked until async refresh jobs exist."
              >
                <StatusList
                  items={fundamentalsDiagnosticsResult.data.screener.snapshotFreshness.flatMap(
                    (summary) => [
                      {
                        label: `${summary.period} persisted`,
                        status: `${summary.persistedCount}/${summary.universeSize}`,
                      },
                      {
                        label: `${summary.period} fresh/stale/missing`,
                        status: `${summary.freshCount}/${summary.staleCount}/${summary.missingCount}`,
                      },
                      {
                        label: `${summary.period} newest refresh`,
                        status: summary.newestRefreshedAt ?? "none",
                      },
                    ],
                  )}
                />
              </PlaceholderCard>
            ) : null}

            <PlaceholderCard
              label="Fundamentals periods"
              title="Statement period support"
              description="Annual remains the default. Quarterly is supported. TTM is visible in contracts and may return not implemented."
            >
              <StatusList
                items={[
                  {
                    label: "Default period",
                    status: fundamentalsDiagnosticsResult.data.defaultPeriod,
                  },
                  {
                    label: "Supported periods",
                    status:
                      fundamentalsDiagnosticsResult.data.supportedPeriods.join(
                        ", ",
                      ),
                  },
                  {
                    label: "Last successful provider call",
                    status:
                      fundamentalsDiagnosticsResult.data.provider
                        .lastSuccessfulCallAt ?? "none",
                  },
                  {
                    label: "Last provider error",
                    status:
                      fundamentalsDiagnosticsResult.data.provider
                        .lastErrorMessage ?? "none",
                  },
                ]}
              />
            </PlaceholderCard>
          </>
        ) : (
          <PlaceholderCard
            label="Fundamentals diagnostics"
            title="Fundamentals diagnostics API unavailable"
            description="The web app could not reach the backend fundamentals diagnostics endpoint."
          >
            <ApiState
              title="API unavailable"
              message={fundamentalsDiagnosticsResult.error.message}
              endpoint={fundamentalsDiagnosticsResult.error.endpoint}
            />
          </PlaceholderCard>
        )}
      </section>
    </TerminalShell>
  );
}
