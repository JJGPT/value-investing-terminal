import Link from "next/link";
import type {
  RankingChangeRow,
  RankingRefreshRun,
  RankingResultRow,
  RankingRunSummary,
  RankingStrategy,
  RefreshJob,
  RefreshJobEvent,
  RefreshPolicy,
  SavedRankingScreen,
} from "@value-terminal/types";

import { ApiState } from "../../components/data-status/api-state";
import { TerminalShell } from "../../components/shell/terminal-shell";
import { PlaceholderCard } from "../../components/ui/placeholder-card";
import { StatusList } from "../../components/ui/status-list";
import {
  createRankingScreen,
  createRefreshPolicy,
  duplicateRankingScreen,
  getRankingScreen,
  getRankingRunChanges,
  getRankings,
  getRefreshJobEvents,
  listRankingRefreshRuns,
  listRankingRuns,
  listRankingScreens,
  listRefreshJobs,
  listRefreshPolicies,
  refreshRankings,
  runDueRefreshPolicies,
  runRefreshPolicyNow,
  setRankingScreenLifecycle,
  setRefreshPolicyEnabled,
  updateRankingScreen,
} from "../../lib/api/client";

type RankingsPageProps = {
  searchParams?: Promise<{
    strategy?: string | string[];
    period?: string | string[];
    action?: string | string[];
    screenId?: string | string[];
    screenName?: string | string[];
    includeArchived?: string | string[];
    policyAction?: string | string[];
    policyId?: string | string[];
    policyName?: string | string[];
    policyTarget?: string | string[];
    policySchedule?: string | string[];
    policyStaleAfterSeconds?: string | string[];
  }>;
};

const strategyOptions: Array<{ value: RankingStrategy; label: string }> = [
  { value: "magic_formula", label: "Magic Formula" },
  { value: "quality", label: "Quality" },
  { value: "value", label: "Value" },
  { value: "growth", label: "Growth" },
  { value: "profitability", label: "Profitability" },
];

function getQueryValue(value: string | string[] | undefined) {
  if (Array.isArray(value)) {
    return value[0] ?? "";
  }

  return value ?? "";
}

function normalizeStrategy(value: string): RankingStrategy {
  return strategyOptions.some((option) => option.value === value)
    ? (value as RankingStrategy)
    : "magic_formula";
}

function normalizePeriod(value: string): "annual" | "quarter" {
  return value === "quarter" ? "quarter" : "annual";
}

function formatNumber(value: number | null | undefined, digits = 2) {
  if (value === null || value === undefined) {
    return "Unavailable";
  }

  return Intl.NumberFormat("en-US", {
    maximumFractionDigits: digits,
  }).format(value);
}

function formatPercent(value: number | null | undefined) {
  if (value === null || value === undefined) {
    return "Unavailable";
  }

  return `${(value * 100).toFixed(1)}%`;
}

function formatMoney(
  value: number | null | undefined,
  currency: string | null,
) {
  if (value === null || value === undefined) {
    return "Unavailable";
  }

  const formatted = Intl.NumberFormat("en-US", {
    notation: Math.abs(value) >= 1_000_000 ? "compact" : "standard",
    maximumFractionDigits: 1,
  }).format(value);

  return currency ? `${formatted} ${currency}` : formatted;
}

function formatTimestamp(value: string | null | undefined) {
  if (!value) {
    return "No run";
  }

  return new Intl.DateTimeFormat("en-US", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function formatChange(change: RankingChangeRow | undefined) {
  if (!change) {
    return "No prior run";
  }

  if (change.changeType === "new_entrant") {
    return "New";
  }

  if (change.changeType === "dropped") {
    return "Dropped";
  }

  if (change.rankChange === null) {
    return change.eligibilityChange;
  }

  if (change.rankChange > 0) {
    return `+${change.rankChange}`;
  }

  return String(change.rankChange);
}

function snapshotStatus(row: RankingResultRow) {
  const snapshot = row.source.snapshot;

  if (!snapshot) {
    return row.source.snapshotState ?? "live";
  }

  return `${snapshot.state}${snapshot.isStale ? " stale" : ""}`;
}

function reasonsPreview(row: RankingResultRow) {
  if (row.eligibilityReasons.length) {
    return row.eligibilityReasons.slice(0, 4).join(", ");
  }

  if (row.qualityFlags.length) {
    return row.qualityFlags.slice(0, 3).join(", ");
  }

  return "clean";
}

function runSummary(run: RankingRunSummary | null | undefined) {
  if (!run) {
    return "No persisted ranking run yet";
  }

  const totalRows = run.summary.totalRows ?? run.universe.size;

  return `${run.strategy} ${run.period} | ${totalRows} rows | ${formatTimestamp(
    run.computedAt,
  )}`;
}

function refreshSummary(refresh: RankingRefreshRun | null | undefined) {
  if (!refresh) {
    return "No refresh run yet";
  }

  const timestamp =
    refresh.completedAt ?? refresh.failedAt ?? refresh.startedAt;

  return `${refresh.status} | ${refresh.scope.type} | ${formatTimestamp(
    timestamp,
  )}`;
}

function jobSummary(job: RefreshJob | null | undefined) {
  if (!job) {
    return "No refresh job yet";
  }

  const timestamp =
    job.completedAt ?? job.failedAt ?? job.startedAt ?? job.createdAt;

  return `${job.status} | ${job.scope.type} | ${formatTimestamp(timestamp)}`;
}

function isRankingRefreshRun(value: unknown): value is RankingRefreshRun {
  return (
    typeof value === "object" &&
    value !== null &&
    "refreshId" in value &&
    "state" in value &&
    "scope" in value
  );
}

function refreshRunFromJob(job: RefreshJob | null | undefined) {
  return isRankingRefreshRun(job?.result) ? job.result : null;
}

function rankingRunFromJob(job: RefreshJob | null | undefined) {
  const refresh = refreshRunFromJob(job);

  return refresh?.run ?? null;
}

function screenStatus(screen: SavedRankingScreen) {
  return `${screen.strategy} ${screen.period} | ${screen.status}`;
}

function policyStatus(policy: RefreshPolicy) {
  return `${policy.target} | ${policy.scheduleHint} | ${
    policy.enabled ? "enabled" : "disabled"
  }`;
}

function parsePositiveInt(value: string, fallback: number) {
  const parsed = Number.parseInt(value, 10);

  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}

function groupRows(rows: RankingResultRow[]) {
  return {
    eligible: rows.filter((row) => row.eligibilityStatus === "eligible"),
    ineligible: rows.filter((row) => row.eligibilityStatus === "ineligible"),
    missing: rows.filter(
      (row) => row.eligibilityStatus === "unranked_missing_data",
    ),
  };
}

function RankingTable({
  title,
  rows,
  changes,
}: {
  title: string;
  rows: RankingResultRow[];
  changes: Record<string, RankingChangeRow>;
}) {
  if (!rows.length) {
    return (
      <div className="border-line bg-panel/40 text-muted border px-4 py-4 text-sm">
        No rows in {title.toLowerCase()}.
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <div className="text-muted font-mono text-[11px] uppercase">{title}</div>
      <div className="border-line overflow-hidden border">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[1320px] border-collapse text-left text-sm">
            <thead className="bg-graphite2 text-muted font-mono text-[11px] uppercase">
              <tr>
                {[
                  "Rank",
                  "Change",
                  "Status",
                  "Ticker",
                  "Company",
                  "Earnings yield",
                  "ROC",
                  "EBIT",
                  "EV",
                  "Score",
                  "Reasons",
                  "Snapshot",
                ].map((column) => (
                  <th className="border-line border-b px-4 py-3" key={column}>
                    {column}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-line divide-y">
              {rows.map((row) => {
                const change = changes[row.ticker];

                return (
                  <tr className="bg-panel/60" key={row.ticker}>
                    <td className="text-ink px-4 py-3 font-mono text-xs">
                      {row.rank ?? "NR"}
                    </td>
                    <td className="text-accent px-4 py-3 font-mono text-xs">
                      {formatChange(change)}
                    </td>
                    <td className="text-muted px-4 py-3 font-mono text-[11px] uppercase">
                      {row.eligibilityStatus}
                    </td>
                    <td className="text-accent px-4 py-3 font-mono text-xs">
                      <Link href={`/company/${row.ticker}`}>{row.ticker}</Link>
                    </td>
                    <td className="text-ink max-w-[220px] px-4 py-3">
                      {row.companyName ?? "Unavailable"}
                    </td>
                    <td className="text-ink px-4 py-3">
                      {formatPercent(row.magicFormula.earningsYield)}
                    </td>
                    <td className="text-ink px-4 py-3">
                      {formatPercent(row.magicFormula.returnOnCapital)}
                    </td>
                    <td className="text-ink px-4 py-3">
                      {formatMoney(row.magicFormula.inputs.ebit, row.currency)}
                    </td>
                    <td className="text-ink px-4 py-3">
                      {formatMoney(
                        row.magicFormula.inputs.enterpriseValue,
                        row.currency,
                      )}
                    </td>
                    <td className="text-ink px-4 py-3">
                      {formatNumber(row.score)}
                    </td>
                    <td className="text-muted max-w-[320px] px-4 py-3 font-mono text-[11px]">
                      {reasonsPreview(row)}
                    </td>
                    <td className="text-muted px-4 py-3 font-mono text-[11px] uppercase">
                      {snapshotStatus(row)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function JobEvents({ events }: { events: RefreshJobEvent[] }) {
  if (!events.length) {
    return (
      <div className="border-line bg-panel/40 text-muted border px-4 py-4 text-sm">
        No job events recorded yet.
      </div>
    );
  }

  return (
    <div className="border-line divide-line border">
      {events.slice(-6).map((event) => (
        <div
          className="grid gap-2 px-4 py-3 text-sm md:grid-cols-[180px_120px_1fr_auto]"
          key={event.eventId}
        >
          <span className="text-accent font-mono text-[11px] uppercase">
            {event.eventType}
          </span>
          <span className="text-muted font-mono text-[11px] uppercase">
            {event.status}
          </span>
          <span className="text-ink">{event.message ?? "Event recorded."}</span>
          <span className="text-muted font-mono text-[11px] uppercase">
            {formatTimestamp(event.createdAt)}
          </span>
        </div>
      ))}
    </div>
  );
}

export default async function RankingsPage({
  searchParams,
}: RankingsPageProps) {
  const params = searchParams ? await searchParams : {};
  const requestedStrategy = normalizeStrategy(getQueryValue(params.strategy));
  const requestedPeriod = normalizePeriod(getQueryValue(params.period));
  const action = getQueryValue(params.action);
  const requestedScreenId = getQueryValue(params.screenId);
  const screenName = getQueryValue(params.screenName).trim();
  const includeArchived = getQueryValue(params.includeArchived) === "true";
  const policyAction = getQueryValue(params.policyAction);
  const requestedPolicyId = getQueryValue(params.policyId);
  const policyName = getQueryValue(params.policyName).trim();
  const policyTarget =
    getQueryValue(params.policyTarget) === "screener" ? "screener" : "ranking";
  const policySchedule = getQueryValue(params.policySchedule) || "stale_only";
  const policyStaleAfterSeconds = parsePositiveInt(
    getQueryValue(params.policyStaleAfterSeconds),
    86400,
  );
  const screenMutationResult =
    action === "save"
      ? await createRankingScreen({
          name: screenName || `${requestedStrategy} ${requestedPeriod}`,
          strategy: requestedStrategy,
          period: requestedPeriod,
          limit: 100,
        })
      : action === "rename" && requestedScreenId
        ? await updateRankingScreen(requestedScreenId, { name: screenName })
        : action === "duplicate" && requestedScreenId
          ? await duplicateRankingScreen(
              requestedScreenId,
              screenName || undefined,
            )
          : action === "archive" && requestedScreenId
            ? await setRankingScreenLifecycle(requestedScreenId, "archive")
            : action === "restore" && requestedScreenId
              ? await setRankingScreenLifecycle(requestedScreenId, "restore")
              : action === "delete" && requestedScreenId
                ? await setRankingScreenLifecycle(requestedScreenId, "delete")
                : null;
  const activeScreenId =
    screenMutationResult?.ok &&
    ["save", "rename", "duplicate", "restore"].includes(action)
      ? screenMutationResult.data.screenId
      : ["archive", "delete"].includes(action)
        ? ""
        : requestedScreenId;
  const screensResult = await listRankingScreens({
    includeArchived,
    limit: 50,
  });
  const activeScreenResult = activeScreenId
    ? await getRankingScreen(activeScreenId)
    : null;
  const activeScreen = activeScreenResult?.ok ? activeScreenResult.data : null;
  const strategy = activeScreen?.strategy ?? requestedStrategy;
  const period = activeScreen?.period ?? requestedPeriod;
  const limit = activeScreen?.limit ?? 100;
  const policyMutationResult =
    policyAction === "create"
      ? await createRefreshPolicy({
          name:
            policyName ||
            `${policyTarget === "screener" ? "Screener" : "Ranking"} stale-only`,
          target: policyTarget,
          strategy: policyTarget === "screener" ? "screener" : strategy,
          period,
          scheduleHint: policySchedule as RefreshPolicy["scheduleHint"],
          staleAfterSeconds: policyStaleAfterSeconds,
          enabled: true,
          scope: {
            type: "stale_only",
            tickers: [],
            staleOnly: true,
            scopeVersion: "refresh-policy-scope-v1",
          },
        })
      : policyAction === "run-now" && requestedPolicyId
        ? await runRefreshPolicyNow(requestedPolicyId)
        : policyAction === "enable" && requestedPolicyId
          ? await setRefreshPolicyEnabled(requestedPolicyId, true)
          : policyAction === "disable" && requestedPolicyId
            ? await setRefreshPolicyEnabled(requestedPolicyId, false)
            : policyAction === "run-due"
              ? await runDueRefreshPolicies()
              : null;
  const refreshResult =
    action === "refresh"
      ? await refreshRankings({
          strategy,
          period,
          screenId: activeScreen?.screenId ?? null,
        })
      : null;
  const rankingsResult = await getRankings({
    strategy,
    period,
    limit,
    includeIneligible: true,
    screenId: activeScreen?.screenId ?? null,
  });
  const runsResult = await listRankingRuns({ strategy, period, limit: 5 });
  const refreshRunsResult = await listRankingRefreshRuns({
    strategy,
    period,
    limit: 5,
  });
  const refreshJobsResult = await listRefreshJobs({
    jobType: "",
    limit: 5,
  });
  const refreshPoliciesResult = await listRefreshPolicies({
    includeDisabled: true,
    limit: 20,
  });
  const refreshedRun = refreshResult?.ok
    ? rankingRunFromJob(refreshResult.data)
    : null;
  const refreshedWorkflow = refreshResult?.ok
    ? refreshRunFromJob(refreshResult.data)
    : null;
  const latestRun = refreshedRun
    ? refreshedRun
    : runsResult.ok
      ? runsResult.data.runs[0]
      : rankingsResult.ok
        ? rankingsResult.data.latestRun
        : null;
  const latestJob = refreshResult?.ok
    ? refreshResult.data
    : refreshJobsResult.ok
      ? refreshJobsResult.data.jobs[0]
      : null;
  const latestRefresh = refreshedWorkflow
    ? refreshedWorkflow
    : refreshRunsResult.ok
      ? refreshRunsResult.data.refreshRuns[0]
      : null;
  const jobEventsResult = latestJob
    ? await getRefreshJobEvents(latestJob.jobId)
    : null;
  const changesResult = latestRun
    ? await getRankingRunChanges(latestRun.runId)
    : null;
  const changes =
    changesResult?.ok && changesResult.data.previousRun
      ? Object.fromEntries(
          changesResult.data.changes.map((change) => [change.ticker, change]),
        )
      : {};
  const grouped = rankingsResult.ok
    ? groupRows(rankingsResult.data.rows)
    : { eligible: [], ineligible: [], missing: [] };

  return (
    <TerminalShell
      eyebrow="Rankings"
      title="Deterministic ranking workspace."
      description="Transparent ranking over the controlled universe using canonical fundamentals, computed metrics, and snapshot-backed screener rows."
    >
      <section className="grid gap-4 xl:grid-cols-[320px_1fr]">
        <div className="space-y-4">
          <PlaceholderCard
            label="Saved screens"
            title="Reusable ranking screens"
            description="Screens persist strategy, filters, eligibility settings, sorting, period, and limit."
          >
            <div className="space-y-3">
              <form action="/rankings" className="space-y-3">
                <input name="strategy" type="hidden" value={strategy} />
                <input name="period" type="hidden" value={period} />
                <label className="grid gap-2">
                  <span className="text-muted font-mono text-[11px] uppercase">
                    Screen name
                  </span>
                  <input
                    className="border-line bg-obsidian text-ink min-h-10 border px-3 text-sm outline-none"
                    defaultValue={activeScreen?.name ?? ""}
                    name="screenName"
                    placeholder="Magic Formula working screen"
                  />
                </label>
                <div className="grid grid-cols-2 gap-2">
                  <button
                    className="border-line text-muted hover:text-accent min-h-10 border px-3 font-mono text-[10px] uppercase transition"
                    name="action"
                    type="submit"
                    value="save"
                  >
                    Save
                  </button>
                  {activeScreen ? (
                    <button
                      className="border-line text-muted hover:text-accent min-h-10 border px-3 font-mono text-[10px] uppercase transition"
                      name="action"
                      type="submit"
                      value="rename"
                    >
                      Rename
                    </button>
                  ) : null}
                </div>
                {activeScreen ? (
                  <input
                    name="screenId"
                    type="hidden"
                    value={activeScreen.screenId}
                  />
                ) : null}
              </form>

              <div className="border-line divide-line max-h-[320px] overflow-auto border">
                {screensResult.ok && screensResult.data.screens.length ? (
                  screensResult.data.screens.map((screen) => (
                    <Link
                      className={`block px-3 py-3 transition ${
                        activeScreen?.screenId === screen.screenId
                          ? "bg-accent/10 text-accent"
                          : "text-muted hover:text-ink"
                      }`}
                      href={`/rankings?screenId=${screen.screenId}&includeArchived=${includeArchived}`}
                      key={screen.screenId}
                    >
                      <span className="block text-sm text-ink">
                        {screen.name}
                      </span>
                      <span className="font-mono text-[10px] uppercase">
                        {screenStatus(screen)}
                      </span>
                    </Link>
                  ))
                ) : (
                  <div className="text-muted px-3 py-4 text-sm">
                    No saved ranking screens yet.
                  </div>
                )}
              </div>

              <form action="/rankings">
                <input
                  name="includeArchived"
                  type="hidden"
                  value={includeArchived ? "false" : "true"}
                />
                <button
                  className="border-line text-muted hover:text-accent min-h-10 w-full border px-3 font-mono text-[10px] uppercase transition"
                  type="submit"
                >
                  {includeArchived ? "Hide archived" : "Show archived"}
                </button>
              </form>

              {activeScreen ? (
                <div className="grid grid-cols-2 gap-2">
                  <form action="/rankings">
                    <input
                      name="screenId"
                      type="hidden"
                      value={activeScreen.screenId}
                    />
                    <input
                      name="screenName"
                      type="hidden"
                      value={`${activeScreen.name} Copy`}
                    />
                    <button
                      className="border-line text-muted hover:text-accent min-h-10 w-full border px-3 font-mono text-[10px] uppercase transition"
                      name="action"
                      type="submit"
                      value="duplicate"
                    >
                      Duplicate
                    </button>
                  </form>
                  <form action="/rankings">
                    <input
                      name="screenId"
                      type="hidden"
                      value={activeScreen.screenId}
                    />
                    <button
                      className="border-line text-muted hover:text-accent min-h-10 w-full border px-3 font-mono text-[10px] uppercase transition"
                      name="action"
                      type="submit"
                      value={
                        activeScreen.status === "archived"
                          ? "restore"
                          : "archive"
                      }
                    >
                      {activeScreen.status === "archived"
                        ? "Restore"
                        : "Archive"}
                    </button>
                  </form>
                </div>
              ) : null}
            </div>
          </PlaceholderCard>

          <PlaceholderCard
            label="Controls"
            title="Ranking strategy"
            description="Eligibility, exclusions, and rank assignment stay visible. Refresh persists an immutable ranking run for audit and change history."
          >
            <form action="/rankings" className="space-y-4">
              {activeScreen ? (
                <input
                  name="screenId"
                  type="hidden"
                  value={activeScreen.screenId}
                />
              ) : null}
              <label className="grid gap-3">
                <span className="text-muted font-mono text-[11px] uppercase">
                  Strategy
                </span>
                <select
                  className="border-line bg-obsidian text-ink min-h-11 border px-3 text-sm outline-none"
                  defaultValue={strategy}
                  name="strategy"
                >
                  {strategyOptions.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="grid gap-3">
                <span className="text-muted font-mono text-[11px] uppercase">
                  Period
                </span>
                <select
                  className="border-line bg-obsidian text-ink min-h-11 border px-3 text-sm outline-none"
                  defaultValue={period}
                  name="period"
                >
                  <option value="annual">Annual</option>
                  <option value="quarter">Quarter</option>
                </select>
              </label>
              <div className="grid gap-2">
                <button
                  className="border-line text-muted hover:text-accent min-h-11 w-full border px-4 font-mono text-[11px] uppercase transition"
                  type="submit"
                >
                  Run ranking
                </button>
                <button
                  className="border-accent/40 text-accent min-h-11 w-full border px-4 font-mono text-[11px] uppercase transition"
                  name="action"
                  type="submit"
                  value="refresh"
                >
                  Persist run
                </button>
              </div>
            </form>
          </PlaceholderCard>

          <PlaceholderCard
            label="Refresh policies"
            title="Scheduled stale-only policies"
            description="Policies create local jobs for stale-only or scheduled refresh simulation. Execution remains synchronous in this phase."
          >
            <div className="space-y-3">
              <form action="/rankings" className="space-y-3">
                <input name="strategy" type="hidden" value={strategy} />
                <input name="period" type="hidden" value={period} />
                <label className="grid gap-2">
                  <span className="text-muted font-mono text-[11px] uppercase">
                    Policy name
                  </span>
                  <input
                    className="border-line bg-obsidian text-ink min-h-10 border px-3 text-sm outline-none"
                    name="policyName"
                    placeholder="Annual stale-only ranking"
                  />
                </label>
                <div className="grid grid-cols-2 gap-2">
                  <label className="grid gap-2">
                    <span className="text-muted font-mono text-[11px] uppercase">
                      Target
                    </span>
                    <select
                      className="border-line bg-obsidian text-ink min-h-10 border px-3 text-sm outline-none"
                      name="policyTarget"
                    >
                      <option value="ranking">Ranking</option>
                      <option value="screener">Screener</option>
                    </select>
                  </label>
                  <label className="grid gap-2">
                    <span className="text-muted font-mono text-[11px] uppercase">
                      Schedule
                    </span>
                    <select
                      className="border-line bg-obsidian text-ink min-h-10 border px-3 text-sm outline-none"
                      name="policySchedule"
                    >
                      <option value="stale_only">Stale-only</option>
                      <option value="hourly">Hourly</option>
                      <option value="daily">Daily</option>
                      <option value="manual">Manual</option>
                    </select>
                  </label>
                </div>
                <label className="grid gap-2">
                  <span className="text-muted font-mono text-[11px] uppercase">
                    Stale after seconds
                  </span>
                  <input
                    className="border-line bg-obsidian text-ink min-h-10 border px-3 text-sm outline-none"
                    defaultValue="86400"
                    min="1"
                    name="policyStaleAfterSeconds"
                    type="number"
                  />
                </label>
                <button
                  className="border-line text-muted hover:text-accent min-h-10 w-full border px-3 font-mono text-[10px] uppercase transition"
                  name="policyAction"
                  type="submit"
                  value="create"
                >
                  Save policy
                </button>
              </form>

              <form action="/rankings">
                <button
                  className="border-accent/40 text-accent min-h-10 w-full border px-3 font-mono text-[10px] uppercase transition"
                  name="policyAction"
                  type="submit"
                  value="run-due"
                >
                  Run due policies
                </button>
              </form>

              {policyMutationResult && !policyMutationResult.ok ? (
                <ApiState
                  title="Refresh policy action failed"
                  message={policyMutationResult.error.message}
                  endpoint={policyMutationResult.error.endpoint}
                />
              ) : null}

              <div className="border-line divide-line max-h-[360px] overflow-auto border">
                {refreshPoliciesResult.ok &&
                refreshPoliciesResult.data.policies.length ? (
                  refreshPoliciesResult.data.policies.map((policy) => (
                    <div className="space-y-3 px-3 py-3" key={policy.policyId}>
                      <div>
                        <span className="text-ink block text-sm">
                          {policy.name}
                        </span>
                        <span className="text-muted font-mono text-[10px] uppercase">
                          {policyStatus(policy)}
                        </span>
                      </div>
                      <StatusList
                        items={[
                          {
                            label: "Last run",
                            status: formatTimestamp(policy.lastRunAt),
                          },
                          {
                            label: "Next hint",
                            status: policy.nextRunHint
                              ? formatTimestamp(policy.nextRunHint)
                              : "manual",
                          },
                          {
                            label: "Stale after",
                            status: `${policy.staleAfterSeconds}s`,
                          },
                        ]}
                      />
                      <div className="grid grid-cols-2 gap-2">
                        <form action="/rankings">
                          <input
                            name="policyId"
                            type="hidden"
                            value={policy.policyId}
                          />
                          <button
                            className="border-line text-muted hover:text-accent min-h-9 w-full border px-2 font-mono text-[10px] uppercase transition"
                            name="policyAction"
                            type="submit"
                            value="run-now"
                          >
                            Run now
                          </button>
                        </form>
                        <form action="/rankings">
                          <input
                            name="policyId"
                            type="hidden"
                            value={policy.policyId}
                          />
                          <button
                            className="border-line text-muted hover:text-accent min-h-9 w-full border px-2 font-mono text-[10px] uppercase transition"
                            name="policyAction"
                            type="submit"
                            value={policy.enabled ? "disable" : "enable"}
                          >
                            {policy.enabled ? "Disable" : "Enable"}
                          </button>
                        </form>
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="text-muted px-3 py-4 text-sm">
                    No refresh policies yet.
                  </div>
                )}
              </div>
            </div>
          </PlaceholderCard>
        </div>

        <div className="space-y-4">
          <PlaceholderCard
            label="Methodology"
            title="Eligibility filters and audit"
            description="Rankings classify every row before sorting. Missing critical inputs and deterministic exclusions remain in the response."
          >
            <StatusList
              items={[
                {
                  label: "Latest persisted run",
                  status: runSummary(latestRun),
                },
                {
                  label: "Active screen",
                  status: activeScreen
                    ? `${activeScreen.name} | ${activeScreen.status}`
                    : "ad hoc",
                },
                {
                  label: "Latest refresh",
                  status: refreshSummary(latestRefresh),
                },
                {
                  label: "Latest job",
                  status: jobSummary(latestJob),
                },
                {
                  label: "Eligibility",
                  status: "eligible, ineligible, or unranked_missing_data",
                },
                {
                  label: "Magic Formula",
                  status: "EBIT / EV and EBIT / invested capital",
                },
                {
                  label: "Rank change",
                  status: changesResult?.ok
                    ? changesResult.data.previousRun
                      ? "latest vs prior persisted run"
                      : "no prior run"
                    : "unavailable",
                },
              ]}
            />
            {rankingsResult.ok ? (
              <div className="mt-4">
                <StatusList
                  items={[
                    {
                      label: "Minimum market cap",
                      status: formatNumber(
                        rankingsResult.data.eligibilitySettings
                          .minimumMarketCap,
                        0,
                      ),
                    },
                    {
                      label: "Minimum price",
                      status: formatNumber(
                        rankingsResult.data.eligibilitySettings.minimumPrice,
                        0,
                      ),
                    },
                    {
                      label: "Minimum volume",
                      status:
                        rankingsResult.data.eligibilitySettings
                          .minimumVolume === null
                          ? "disabled"
                          : formatNumber(
                              rankingsResult.data.eligibilitySettings
                                .minimumVolume,
                              0,
                            ),
                    },
                    {
                      label: "Positive EV / IC / EBIT",
                      status: `${rankingsResult.data.eligibilitySettings.requirePositiveEnterpriseValue}/${rankingsResult.data.eligibilitySettings.requirePositiveInvestedCapital}/${rankingsResult.data.eligibilitySettings.requirePositiveEbit}`,
                    },
                    {
                      label: "Sector exclusions",
                      status:
                        [
                          rankingsResult.data.eligibilitySettings
                            .excludeFinancials
                            ? "financials"
                            : null,
                          rankingsResult.data.eligibilitySettings
                            .excludeUtilities
                            ? "utilities"
                            : null,
                        ]
                          .filter(Boolean)
                          .join(", ") || "disabled",
                    },
                  ]}
                />
              </div>
            ) : null}
          </PlaceholderCard>

          <PlaceholderCard
            label="Results"
            title="Ranked universe"
            description="Rows are grouped by eligibility status. This is a deterministic research screen, not a recommendation or trading signal."
          >
            {rankingsResult.ok ? (
              <div className="space-y-5">
                <ApiState
                  title={`Provider ${rankingsResult.data.provider.state}`}
                  message={rankingsResult.data.message}
                  provider={rankingsResult.data.provider}
                  endpoint="/api/rankings"
                />

                {refreshResult && !refreshResult.ok ? (
                  <ApiState
                    title="Ranking refresh job failed"
                    message={refreshResult.error.message}
                    endpoint={refreshResult.error.endpoint}
                  />
                ) : null}

                {screenMutationResult && !screenMutationResult.ok ? (
                  <ApiState
                    title="Saved screen action failed"
                    message={screenMutationResult.error.message}
                    endpoint={screenMutationResult.error.endpoint}
                  />
                ) : null}

                <StatusList
                  items={[
                    {
                      label: "Strategy",
                      status: rankingsResult.data.strategy,
                    },
                    {
                      label: "Universe",
                      status: `${rankingsResult.data.universe.size} controlled tickers`,
                    },
                    {
                      label: "Eligible",
                      status: String(
                        rankingsResult.data.diagnostics.eligibleRows,
                      ),
                    },
                    {
                      label: "Ineligible",
                      status: String(
                        rankingsResult.data.diagnostics.ineligibleRows,
                      ),
                    },
                    {
                      label: "Missing data",
                      status: String(
                        rankingsResult.data.diagnostics.unrankedMissingDataRows,
                      ),
                    },
                    {
                      label: "Engine",
                      status: rankingsResult.data.diagnostics.engineVersion,
                    },
                  ]}
                />

                {latestRefresh ? (
                  <StatusList
                    items={[
                      {
                        label: "Refresh status",
                        status: latestRefresh.status,
                      },
                      {
                        label: "Refresh scope",
                        status: latestRefresh.scope.type,
                      },
                      {
                        label: "Refresh duration",
                        status:
                          latestRefresh.durationMs === null
                            ? "Unavailable"
                            : `${latestRefresh.durationMs}ms`,
                      },
                      {
                        label: "Refresh warnings",
                        status: latestRefresh.warnings.length
                          ? latestRefresh.warnings
                              .map((warning) => warning.code)
                              .join(", ")
                          : "none",
                      },
                      {
                        label: "Refresh errors",
                        status: latestRefresh.errors.length
                          ? latestRefresh.errors
                              .map((error) => error.message)
                              .join(", ")
                          : "none",
                      },
                    ]}
                  />
                ) : null}

                {latestJob ? (
                  <div className="space-y-3">
                    <StatusList
                      items={[
                        {
                          label: "Job status",
                          status: latestJob.status,
                        },
                        {
                          label: "Job id",
                          status: latestJob.jobId,
                        },
                        {
                          label: "Job scope",
                          status: latestJob.scope.type,
                        },
                        {
                          label: "Job duration",
                          status:
                            latestJob.durationMs === null
                              ? "Unavailable"
                              : `${latestJob.durationMs}ms`,
                        },
                        {
                          label: "Result run",
                          status: latestJob.resultMetadata.runId ?? "none",
                        },
                        {
                          label: "Job errors",
                          status: latestJob.errors.length
                            ? latestJob.errors
                                .map((error) => error.message)
                                .join(", ")
                            : "none",
                        },
                      ]}
                    />
                    {jobEventsResult?.ok ? (
                      <JobEvents events={jobEventsResult.data.events} />
                    ) : null}
                  </div>
                ) : null}

                {refreshRunsResult.ok &&
                refreshRunsResult.data.refreshRuns.length ? (
                  <div className="border-line divide-line border">
                    {refreshRunsResult.data.refreshRuns
                      .slice(0, 4)
                      .map((run) => (
                        <div
                          className="grid gap-2 px-4 py-3 text-sm md:grid-cols-[1fr_auto]"
                          key={run.refreshId}
                        >
                          <span className="text-ink">
                            {run.status} | {run.scope.type}
                          </span>
                          <span className="text-muted font-mono text-[11px] uppercase">
                            {formatTimestamp(
                              run.completedAt ?? run.failedAt ?? run.startedAt,
                            )}
                          </span>
                        </div>
                      ))}
                  </div>
                ) : null}

                <RankingTable
                  changes={changes}
                  rows={grouped.eligible}
                  title="Eligible ranked rows"
                />
                <RankingTable
                  changes={changes}
                  rows={grouped.ineligible}
                  title="Ineligible rows"
                />
                <RankingTable
                  changes={changes}
                  rows={grouped.missing}
                  title="Unranked missing-data rows"
                />
              </div>
            ) : (
              <ApiState
                title="Rankings API unavailable"
                message={rankingsResult.error.message}
                endpoint={rankingsResult.error.endpoint}
              />
            )}
          </PlaceholderCard>
        </div>
      </section>
    </TerminalShell>
  );
}
