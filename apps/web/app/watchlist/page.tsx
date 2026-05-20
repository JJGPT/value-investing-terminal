import Link from "next/link";
import type {
  SavedWatchlistView,
  Watchlist,
  WatchlistAlert,
  WatchlistFilter,
  WatchlistIntelligenceItem,
  WatchlistSort,
  WatchlistVisibleColumn,
} from "@value-terminal/types";

import { ApiState } from "../../components/data-status/api-state";
import { TerminalShell } from "../../components/shell/terminal-shell";
import { PlaceholderCard } from "../../components/ui/placeholder-card";
import { StatusList } from "../../components/ui/status-list";
import {
  acknowledgeWatchlistAlert,
  addWatchlistItem,
  createWatchlist,
  createWatchlistView,
  dismissWatchlistAlert,
  duplicateWatchlistView,
  getWatchlistAlertHistory,
  getWatchlistAlerts,
  getWatchlistIntelligence,
  getWatchlistRefreshHistory,
  getWatchlistStaleness,
  listWatchlists,
  listWatchlistViews,
  removeWatchlistItem,
  refreshWatchlist,
  restoreWatchlistAlert,
  setWatchlistLifecycle,
  setWatchlistViewLifecycle,
  updateWatchlist,
  updateWatchlistItem,
  updateWatchlistView,
} from "../../lib/api/client";

const AVAILABLE_COLUMNS: { key: WatchlistVisibleColumn; label: string }[] = [
  { key: "ticker", label: "Ticker" },
  { key: "company", label: "Company" },
  { key: "price", label: "Price" },
  { key: "target", label: "Target" },
  { key: "valuationGap", label: "Gap" },
  { key: "rank", label: "Rank" },
  { key: "eligibility", label: "Eligibility" },
  { key: "freshness", label: "Freshness" },
  { key: "staleness", label: "Staleness" },
  { key: "provider", label: "Provider" },
  { key: "status", label: "Status" },
  { key: "workflowState", label: "Workflow" },
  { key: "priority", label: "Priority" },
  { key: "alerts", label: "Alerts" },
  { key: "flags", label: "Flags" },
  { key: "notes", label: "Notes" },
];

const DEFAULT_VISIBLE_COLUMNS = AVAILABLE_COLUMNS.map((column) => column.key);

type SearchParams = Record<string, string | string[] | undefined>;

type WatchlistPageProps = {
  searchParams?: Promise<SearchParams>;
};

function getQueryValue(value: string | string[] | undefined) {
  if (Array.isArray(value)) {
    return value[0] ?? "";
  }

  return value ?? "";
}

function getQueryValues(value: string | string[] | undefined) {
  if (Array.isArray(value)) {
    return value;
  }

  return value ? [value] : [];
}

function parseTags(value: string) {
  return value
    .split(",")
    .map((tag) => tag.trim())
    .filter(Boolean)
    .slice(0, 12);
}

function parseOptionalNumber(value: string) {
  if (!value.trim()) {
    return null;
  }

  const parsed = Number(value);

  return Number.isFinite(parsed) ? parsed : null;
}

function parsePercent(value: string) {
  const parsed = parseOptionalNumber(value);

  return parsed === null ? null : parsed / 100;
}

function parseBooleanFilter(value: string) {
  if (value !== "true" && value !== "false") {
    return null;
  }

  return value === "true";
}

function buildFilters(params: SearchParams): WatchlistFilter[] {
  const filters: WatchlistFilter[] = [];
  const ticker = getQueryValue(params.filterTicker).trim().toUpperCase();
  const tag = getQueryValue(params.filterTag).trim();
  const thesisStatus = getQueryValue(params.filterThesisStatus).trim();
  const priority = getQueryValue(params.filterPriority).trim();
  const workflowState = getQueryValue(params.filterWorkflowState).trim();
  const rankingStatus = getQueryValue(params.filterRankingStatus).trim();
  const alertType = getQueryValue(params.filterAlertType).trim();
  const gapMin = parsePercent(getQueryValue(params.filterValuationGapMin));
  const gapMax = parsePercent(getQueryValue(params.filterValuationGapMax));
  const staleSnapshot = parseBooleanFilter(getQueryValue(params.filterStaleSnapshot));
  const missingCriticalData = parseBooleanFilter(
    getQueryValue(params.filterMissingCriticalData),
  );
  const providerDegraded = parseBooleanFilter(
    getQueryValue(params.filterProviderDegraded),
  );

  if (ticker) {
    filters.push({ field: "ticker", operator: "contains", value: ticker });
  }

  if (tag) {
    filters.push({ field: "tags", operator: "contains", value: tag });
  }

  if (thesisStatus) {
    filters.push({ field: "thesisStatus", operator: "eq", value: thesisStatus });
  }

  if (priority) {
    filters.push({ field: "priority", operator: "eq", value: priority });
  }

  if (workflowState) {
    filters.push({ field: "workflowState", operator: "eq", value: workflowState });
  }

  if (rankingStatus) {
    filters.push({ field: "rankingStatus", operator: "eq", value: rankingStatus });
  }

  if (alertType) {
    filters.push({ field: "alertType", operator: "eq", value: alertType });
  }

  if (gapMin !== null && gapMax !== null) {
    filters.push({
      field: "valuationGap",
      operator: "between",
      value: [gapMin, gapMax],
    });
  } else if (gapMin !== null) {
    filters.push({ field: "valuationGap", operator: "gte", value: gapMin });
  } else if (gapMax !== null) {
    filters.push({ field: "valuationGap", operator: "lte", value: gapMax });
  }

  if (staleSnapshot !== null) {
    filters.push({ field: "staleSnapshot", operator: "eq", value: staleSnapshot });
  }

  if (missingCriticalData !== null) {
    filters.push({
      field: "missingCriticalData",
      operator: "eq",
      value: missingCriticalData,
    });
  }

  if (providerDegraded !== null) {
    filters.push({
      field: "providerDegraded",
      operator: "eq",
      value: providerDegraded,
    });
  }

  return filters;
}

function buildSort(params: SearchParams): WatchlistSort | null {
  const field = getQueryValue(params.sortField).trim();
  const direction =
    getQueryValue(params.sortDirection).trim().toLowerCase() === "asc"
      ? "asc"
      : "desc";
  const allowedFields = new Set([
    "ticker",
    "priority",
    "valuationGap",
    "latestRank",
    "alertCount",
    "snapshotFreshness",
    "addedAt",
  ]);

  if (!allowedFields.has(field)) {
    return null;
  }

  return { field: field as WatchlistSort["field"], direction };
}

function parseVisibleColumns(params: SearchParams) {
  const rawValues = getQueryValues(params.visibleColumns)
    .flatMap((value) => value.split(","))
    .map((value) => value.trim())
    .filter(Boolean);

  if (!rawValues.length) {
    return null;
  }

  const available = new Set(AVAILABLE_COLUMNS.map((column) => column.key));
  const columns = rawValues.filter((column) => available.has(column));

  return columns.length ? (columns as WatchlistVisibleColumn[]) : null;
}

function formatMoney(
  value: number | null | undefined,
  currency: string | null | undefined,
) {
  if (value === null || value === undefined) {
    return "Unavailable";
  }

  const formatted = Intl.NumberFormat("en-US", {
    notation: Math.abs(value) >= 1_000_000 ? "compact" : "standard",
    maximumFractionDigits: 2,
  }).format(value);

  return currency ? `${formatted} ${currency}` : formatted;
}

function formatPercent(value: number | null | undefined) {
  if (value === null || value === undefined) {
    return "Unavailable";
  }

  return `${(value * 100).toFixed(1)}%`;
}

function formatTimestamp(value: string | null | undefined) {
  if (!value) {
    return "Unavailable";
  }

  return new Intl.DateTimeFormat("en-US", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function formatAge(seconds: number | null | undefined) {
  if (seconds === null || seconds === undefined) {
    return "Unavailable";
  }

  if (seconds < 3600) {
    return `${Math.round(seconds / 60)}m`;
  }

  if (seconds < 86400) {
    return `${Math.round(seconds / 3600)}h`;
  }

  return `${Math.round(seconds / 86400)}d`;
}

function watchlistStatus(watchlist: Watchlist) {
  return `${watchlist.items.length} items | ${watchlist.status}`;
}

function itemAlertSummary(alerts: WatchlistAlert[]) {
  if (!alerts.length) {
    return "clear";
  }

  return alerts.map((alert) => alert.type).slice(0, 3).join(", ");
}

function itemFlagSummary(item: WatchlistIntelligenceItem) {
  if (item.qualityFlags.length) {
    return item.qualityFlags.slice(0, 4).join(", ");
  }

  return "clean";
}

function providerState(item: WatchlistIntelligenceItem) {
  return item.marketSnapshot.provider.state;
}

function researchStatusValue(value: string | null) {
  return value ?? "watching";
}

function priorityValue(value: string | null) {
  return value ?? "medium";
}

function workflowStateValue(value: string | null | undefined) {
  return value ?? "not_started";
}

function viewStatus(view: SavedWatchlistView) {
  return `${view.filters.length} filters | ${view.status}`;
}

function currentUrl(
  params: SearchParams,
  overrides: Record<string, string | null | undefined>,
) {
  const search = new URLSearchParams();

  for (const [key, value] of Object.entries(params)) {
    if (value === undefined) {
      continue;
    }

    const values = Array.isArray(value) ? value : [value];

    values.forEach((item) => {
      if (item) {
        search.append(key, item);
      }
    });
  }

  for (const [key, value] of Object.entries(overrides)) {
    search.delete(key);

    if (value) {
      search.set(key, value);
    }
  }

  const query = search.toString();

  return query ? `/watchlist?${query}` : "/watchlist";
}

function columnVisible(
  columns: WatchlistVisibleColumn[],
  column: WatchlistVisibleColumn,
) {
  return columns.includes(column);
}

function columnCount(columns: WatchlistVisibleColumn[]) {
  return columns.length + 1;
}

function HiddenQueryFields({
  includeArchived,
  watchlistId,
  viewId,
}: {
  includeArchived: boolean;
  watchlistId?: string | null;
  viewId?: string | null;
}) {
  return (
    <>
      <input name="includeArchived" type="hidden" value={String(includeArchived)} />
      {watchlistId ? (
        <input name="watchlistId" type="hidden" value={watchlistId} />
      ) : null}
      {viewId ? <input name="viewId" type="hidden" value={viewId} /> : null}
    </>
  );
}

export default async function WatchlistPage({
  searchParams,
}: WatchlistPageProps) {
  const params = searchParams ? await searchParams : {};
  const requestedWatchlistId = getQueryValue(params.watchlistId);
  const includeArchived = getQueryValue(params.includeArchived) === "true";
  const action = getQueryValue(params.action);
  const viewAction = getQueryValue(params.viewAction);
  const alertAction = getQueryValue(params.alertAction);
  const requestedViewId = getQueryValue(params.viewId);
  const alertId = getQueryValue(params.alertId);
  const name = getQueryValue(params.name).trim();
  const description = getQueryValue(params.description).trim();
  const ticker = getQueryValue(params.ticker).trim().toUpperCase();
  const companyName = getQueryValue(params.companyName).trim();
  const notes = getQueryValue(params.notes).trim();
  const tags = getQueryValue(params.tags);
  const targetPrice = getQueryValue(params.targetPrice);
  const thesisStatus = getQueryValue(params.thesisStatus).trim();
  const priority = getQueryValue(params.priority).trim();
  const workflowState = getQueryValue(params.workflowState).trim();
  const refreshPeriod =
    getQueryValue(params.refreshPeriod) === "quarter" ? "quarter" : "annual";
  const staleOnlyRefresh = getQueryValue(params.staleOnlyRefresh) !== "false";
  const filters = buildFilters(params);
  const sorting = buildSort(params);
  const selectedVisibleColumns = parseVisibleColumns(params);
  const viewName = getQueryValue(params.viewName).trim();

  const watchlistMutationResult =
    action === "create"
      ? await createWatchlist({
          name: name || "Untitled watchlist",
          description: description || null,
        })
      : action === "update" && requestedWatchlistId
        ? await updateWatchlist(requestedWatchlistId, {
            name: name || undefined,
            description: description || null,
          })
        : action === "archive" && requestedWatchlistId
          ? await setWatchlistLifecycle(requestedWatchlistId, "archive")
          : action === "restore" && requestedWatchlistId
            ? await setWatchlistLifecycle(requestedWatchlistId, "restore")
            : action === "delete" && requestedWatchlistId
              ? await setWatchlistLifecycle(requestedWatchlistId, "delete")
              : action === "add-item" && requestedWatchlistId && ticker
                ? await addWatchlistItem(requestedWatchlistId, {
                    ticker,
                    companyName: companyName || null,
                    notes: notes || null,
                    tags: parseTags(tags),
                    targetPrice: parseOptionalNumber(targetPrice),
                    thesisStatus: thesisStatus || null,
                    priority: priority || null,
                    workflowState: workflowState || null,
                  })
                : action === "update-item" && requestedWatchlistId && ticker
                  ? await updateWatchlistItem(requestedWatchlistId, ticker, {
                      companyName: companyName || null,
                      notes: notes || null,
                      tags: parseTags(tags),
                      targetPrice: parseOptionalNumber(targetPrice),
                      thesisStatus: thesisStatus || null,
                      priority: priority || null,
                      workflowState: workflowState || null,
                    })
                  : action === "remove-item" && requestedWatchlistId && ticker
                    ? await removeWatchlistItem(requestedWatchlistId, ticker)
                    : null;
  const activeMutationId =
    watchlistMutationResult?.ok && !["archive", "delete"].includes(action)
      ? watchlistMutationResult.data.watchlistId
      : "";
  const watchlistsResult = await listWatchlists({
    includeArchived,
    limit: 50,
  });
  const firstVisibleWatchlist =
    watchlistsResult.ok && watchlistsResult.data.watchlists.length
      ? watchlistsResult.data.watchlists[0]
      : null;
  const activeWatchlistId =
    activeMutationId || requestedWatchlistId || firstVisibleWatchlist?.watchlistId;
  const activeWatchlist =
    watchlistsResult.ok && activeWatchlistId
      ? watchlistsResult.data.watchlists.find(
          (watchlist) => watchlist.watchlistId === activeWatchlistId,
        ) ?? null
      : null;

  const viewPayload = {
    name: viewName || "Saved watchlist view",
    filters,
    sorting,
    visibleColumns: selectedVisibleColumns ?? DEFAULT_VISIBLE_COLUMNS,
  };
  const viewMutationResult =
    activeWatchlistId && viewAction === "create-view"
      ? await createWatchlistView(activeWatchlistId, viewPayload)
      : activeWatchlistId && requestedViewId && viewAction === "update-view"
        ? await updateWatchlistView(activeWatchlistId, requestedViewId, viewPayload)
        : activeWatchlistId && requestedViewId && viewAction === "duplicate-view"
          ? await duplicateWatchlistView(
              activeWatchlistId,
              requestedViewId,
              viewName || undefined,
            )
          : activeWatchlistId && requestedViewId && viewAction === "archive-view"
            ? await setWatchlistViewLifecycle(
                activeWatchlistId,
                requestedViewId,
                "archive",
              )
            : activeWatchlistId && requestedViewId && viewAction === "restore-view"
              ? await setWatchlistViewLifecycle(
                  activeWatchlistId,
                  requestedViewId,
                  "restore",
                )
              : activeWatchlistId && requestedViewId && viewAction === "delete-view"
                ? await setWatchlistViewLifecycle(
                    activeWatchlistId,
                    requestedViewId,
                    "delete",
                  )
                : null;
  const activeViewId =
    viewMutationResult?.ok &&
    !["archive-view", "delete-view"].includes(viewAction)
      ? viewMutationResult.data.viewId
      : requestedViewId;

  const alertMutationResult =
    activeWatchlistId && alertId && alertAction === "acknowledge"
      ? await acknowledgeWatchlistAlert(activeWatchlistId, alertId)
      : activeWatchlistId && alertId && alertAction === "dismiss"
        ? await dismissWatchlistAlert(activeWatchlistId, alertId)
        : activeWatchlistId && alertId && alertAction === "restore"
          ? await restoreWatchlistAlert(activeWatchlistId, alertId)
          : null;
  const refreshMutationResult =
    activeWatchlistId && action === "refresh-watchlist"
      ? await refreshWatchlist({
          watchlistId: activeWatchlistId,
          period: refreshPeriod,
          staleOnly: staleOnlyRefresh,
        })
      : null;

  const viewsResult = activeWatchlistId
    ? await listWatchlistViews(activeWatchlistId, {
        includeArchived,
        limit: 50,
      })
    : null;
  const intelligenceResult = activeWatchlistId
    ? await getWatchlistIntelligence(activeWatchlistId, {
        filters,
        sort: sorting,
        viewId: activeViewId || null,
      })
    : null;
  const alertsResult = activeWatchlistId
    ? await getWatchlistAlerts(activeWatchlistId)
    : null;
  const alertHistoryResult = activeWatchlistId
    ? await getWatchlistAlertHistory(activeWatchlistId)
    : null;
  const stalenessResult = activeWatchlistId
    ? await getWatchlistStaleness(activeWatchlistId)
    : null;
  const refreshHistoryResult = activeWatchlistId
    ? await getWatchlistRefreshHistory(activeWatchlistId)
    : null;
  const intelligenceItems =
    intelligenceResult?.ok ? intelligenceResult.data.items : [];
  const alerts = alertsResult?.ok ? alertsResult.data.alerts : [];
  const alertHistory = alertHistoryResult?.ok ? alertHistoryResult.data.alerts : [];
  const refreshJobs = refreshHistoryResult?.ok
    ? refreshHistoryResult.data.jobs
    : [];
  const activeView =
    viewsResult?.ok && activeViewId
      ? viewsResult.data.views.find((view) => view.viewId === activeViewId) ?? null
      : null;
  const visibleColumns =
    selectedVisibleColumns ??
    (intelligenceResult?.ok
      ? intelligenceResult.data.query.visibleColumns
      : DEFAULT_VISIBLE_COLUMNS);
  const activeViewLabel = activeView ? activeView.name : "Ad hoc view";

  return (
    <TerminalShell
      eyebrow="Watchlist"
      title="Deterministic watchlist intelligence."
      description="Persistent research workspaces tied to market snapshots, fundamentals freshness, rankings, valuation scenarios, and rule-based alerts."
    >
      <section className="grid gap-4 xl:grid-cols-[320px_1fr]">
        <div className="space-y-4">
          <PlaceholderCard
            label="Saved watchlists"
            title="Research workspaces"
            description="Watchlists persist locally in SQLite and can be archived or restored without destroying history."
          >
            <form action="/watchlist" className="space-y-3">
              <HiddenQueryFields
                includeArchived={includeArchived}
                watchlistId={activeWatchlist?.watchlistId}
                viewId={activeViewId}
              />
              <label className="grid gap-2">
                <span className="text-muted font-mono text-[11px] uppercase">
                  Name
                </span>
                <input
                  className="border-line bg-obsidian text-ink min-h-10 border px-3 text-sm outline-none"
                  defaultValue={activeWatchlist?.name ?? ""}
                  name="name"
                  placeholder="Compounders research"
                />
              </label>
              <label className="grid gap-2">
                <span className="text-muted font-mono text-[11px] uppercase">
                  Description
                </span>
                <input
                  className="border-line bg-obsidian text-ink min-h-10 border px-3 text-sm outline-none"
                  defaultValue={activeWatchlist?.description ?? ""}
                  name="description"
                  placeholder="Quality names under active review"
                />
              </label>
              <div className="grid grid-cols-2 gap-2">
                <button
                  className="border-line text-muted hover:text-accent min-h-10 border px-3 font-mono text-[10px] uppercase transition"
                  name="action"
                  type="submit"
                  value="create"
                >
                  Create
                </button>
                {activeWatchlist ? (
                  <button
                    className="border-line text-muted hover:text-accent min-h-10 border px-3 font-mono text-[10px] uppercase transition"
                    name="action"
                    type="submit"
                    value="update"
                  >
                    Update
                  </button>
                ) : null}
              </div>
            </form>

            <div className="mt-4 flex items-center justify-between">
              <Link
                className="text-muted hover:text-accent font-mono text-[10px] uppercase"
                href={`/watchlist?includeArchived=${String(!includeArchived)}`}
              >
                {includeArchived ? "Hide archived" : "Show archived"}
              </Link>
              <span className="text-muted font-mono text-[10px] uppercase">
                {watchlistsResult.ok
                  ? `${watchlistsResult.data.watchlists.length} lists`
                  : "API unavailable"}
              </span>
            </div>

            <div className="border-line divide-line mt-4 max-h-[300px] overflow-auto border">
              {watchlistsResult.ok && watchlistsResult.data.watchlists.length ? (
                watchlistsResult.data.watchlists.map((watchlist) => (
                  <Link
                    className={`block px-3 py-3 transition ${
                      activeWatchlist?.watchlistId === watchlist.watchlistId
                        ? "bg-accent/10 text-accent"
                        : "text-muted hover:text-ink"
                    }`}
                    href={`/watchlist?watchlistId=${watchlist.watchlistId}&includeArchived=${includeArchived}`}
                    key={watchlist.watchlistId}
                  >
                    <span className="block text-sm text-ink">
                      {watchlist.name}
                    </span>
                    <span className="font-mono text-[10px] uppercase">
                      {watchlistStatus(watchlist)}
                    </span>
                  </Link>
                ))
              ) : (
                <div className="text-muted px-3 py-4 text-sm">
                  No saved watchlists yet.
                </div>
              )}
            </div>
          </PlaceholderCard>

          {activeWatchlist ? (
            <PlaceholderCard
              label="Saved views"
              title="Reusable lenses"
              description="Saved views preserve deterministic filters, sorting, and visible columns for this watchlist."
            >
              <div className="border-line divide-line max-h-[260px] overflow-auto border">
                {viewsResult?.ok && viewsResult.data.views.length ? (
                  viewsResult.data.views.map((view) => (
                    <Link
                      className={`block px-3 py-3 transition ${
                        activeViewId === view.viewId
                          ? "bg-accent/10 text-accent"
                          : "text-muted hover:text-ink"
                      }`}
                      href={currentUrl(params, {
                        watchlistId: activeWatchlist.watchlistId,
                        viewId: view.viewId,
                        viewAction: null,
                        alertAction: null,
                      })}
                      key={view.viewId}
                    >
                      <span className="block text-sm text-ink">{view.name}</span>
                      <span className="font-mono text-[10px] uppercase">
                        {viewStatus(view)}
                      </span>
                    </Link>
                  ))
                ) : (
                  <div className="text-muted px-3 py-4 text-sm">
                    No saved views for this workspace.
                  </div>
                )}
              </div>
              {activeView ? (
                <form action="/watchlist" className="mt-3 grid grid-cols-3 gap-2">
                  <HiddenQueryFields
                    includeArchived={includeArchived}
                    watchlistId={activeWatchlist.watchlistId}
                    viewId={activeView.viewId}
                  />
                  <button
                    className="border-line text-muted hover:text-accent min-h-9 border px-2 font-mono text-[10px] uppercase transition"
                    name="viewAction"
                    type="submit"
                    value="duplicate-view"
                  >
                    Duplicate
                  </button>
                  <button
                    className="border-line text-muted hover:text-accent min-h-9 border px-2 font-mono text-[10px] uppercase transition"
                    name="viewAction"
                    type="submit"
                    value={activeView.status === "archived" ? "restore-view" : "archive-view"}
                  >
                    {activeView.status === "archived" ? "Restore" : "Archive"}
                  </button>
                  <button
                    className="border-line text-muted hover:text-amber min-h-9 border px-2 font-mono text-[10px] uppercase transition"
                    name="viewAction"
                    type="submit"
                    value="delete-view"
                  >
                    Delete
                  </button>
                </form>
              ) : null}
            </PlaceholderCard>
          ) : null}

          {activeWatchlist ? (
            <PlaceholderCard
              label="Lifecycle"
              title="Archive controls"
              description="Archive and restore preserve history. Delete is a soft-delete boundary for the local store."
            >
              <form action="/watchlist" className="grid grid-cols-3 gap-2">
                <HiddenQueryFields
                  includeArchived={includeArchived}
                  watchlistId={activeWatchlist.watchlistId}
                  viewId={activeViewId}
                />
                <button
                  className="border-line text-muted hover:text-accent min-h-10 border px-2 font-mono text-[10px] uppercase transition"
                  name="action"
                  type="submit"
                  value="archive"
                >
                  Archive
                </button>
                <button
                  className="border-line text-muted hover:text-accent min-h-10 border px-2 font-mono text-[10px] uppercase transition"
                  name="action"
                  type="submit"
                  value="restore"
                >
                  Restore
                </button>
                <button
                  className="border-line text-muted hover:text-amber min-h-10 border px-2 font-mono text-[10px] uppercase transition"
                  name="action"
                  type="submit"
                  value="delete"
                >
                  Delete
                </button>
              </form>
            </PlaceholderCard>
          ) : null}
        </div>

        <div className="space-y-4">
          {watchlistsResult.ok ? (
            <PlaceholderCard
              label="Store"
              title="Watchlist persistence"
              description="The watchlist store is separate from provider credentials and market data access."
            >
              <ApiState
                title={`Store ${watchlistsResult.data.provider.state}`}
                message={watchlistsResult.data.message}
                provider={watchlistsResult.data.provider}
                endpoint="/api/watchlists"
              />
              {alertMutationResult && !alertMutationResult.ok ? (
                <div className="border-amber text-amber mt-4 border px-3 py-2 text-xs">
                  Alert lifecycle update failed: {alertMutationResult.error.message}
                </div>
              ) : null}
              {refreshMutationResult?.ok ? (
                <div className="border-line mt-4 border px-3 py-2 font-mono text-[11px] uppercase text-muted">
                  Latest refresh job: {refreshMutationResult.data.status} |{" "}
                  {refreshMutationResult.data.jobId}
                </div>
              ) : refreshMutationResult && !refreshMutationResult.ok ? (
                <div className="border-amber text-amber mt-4 border px-3 py-2 text-xs">
                  Watchlist refresh failed to queue:{" "}
                  {refreshMutationResult.error.message}
                </div>
              ) : null}
            </PlaceholderCard>
          ) : (
            <PlaceholderCard
              label="Store"
              title="Watchlist API unavailable"
              description="The web app could not reach the backend watchlist endpoint."
            >
              <ApiState
                title="API unavailable"
                message={watchlistsResult.error.message}
                endpoint={watchlistsResult.error.endpoint}
              />
            </PlaceholderCard>
          )}

          {activeWatchlist ? (
            <PlaceholderCard
              label="Refresh"
              title="Watchlist refresh workflow"
              description="Runs a local job for this watchlist's tickers. Stale-only mode limits work to stale, missing, or degraded items."
            >
              <form
                action="/watchlist"
                className="grid gap-3 md:grid-cols-[150px_170px_1fr_150px]"
              >
                <HiddenQueryFields
                  includeArchived={includeArchived}
                  watchlistId={activeWatchlist.watchlistId}
                  viewId={activeViewId}
                />
                <select
                  className="border-line bg-obsidian text-ink min-h-10 border px-3 text-sm outline-none"
                  defaultValue={refreshPeriod}
                  name="refreshPeriod"
                >
                  <option value="annual">Annual</option>
                  <option value="quarter">Quarter</option>
                </select>
                <select
                  className="border-line bg-obsidian text-ink min-h-10 border px-3 text-sm outline-none"
                  defaultValue={String(staleOnlyRefresh)}
                  name="staleOnlyRefresh"
                >
                  <option value="true">Stale only</option>
                  <option value="false">Full watchlist</option>
                </select>
                <StatusList
                  items={[
                    {
                      label: "Fresh",
                      status: String(stalenessResult?.ok ? stalenessResult.data.counts.fresh : 0),
                    },
                    {
                      label: "Stale/missing/degraded",
                      status: String(
                        stalenessResult?.ok
                          ? stalenessResult.data.counts.stale +
                              stalenessResult.data.counts.missing +
                              stalenessResult.data.counts.degraded
                          : 0,
                      ),
                    },
                  ]}
                />
                <button
                  className="border-line text-muted hover:text-accent min-h-10 border px-4 font-mono text-[10px] uppercase transition"
                  name="action"
                  type="submit"
                  value="refresh-watchlist"
                >
                  Refresh
                </button>
              </form>
            </PlaceholderCard>
          ) : null}

          {activeWatchlist ? (
            <PlaceholderCard
              label="Views"
              title={`${activeViewLabel} controls`}
              description="Filters are deterministic and run against persisted intelligence rows. Saving a view stores the current lens for reuse."
            >
              <form action="/watchlist" className="space-y-4">
                <HiddenQueryFields
                  includeArchived={includeArchived}
                  watchlistId={activeWatchlist.watchlistId}
                  viewId={activeViewId}
                />
                <div className="grid gap-3 lg:grid-cols-4">
                  <input
                    className="border-line bg-obsidian text-ink min-h-10 border px-3 font-mono text-sm uppercase outline-none"
                    defaultValue={getQueryValue(params.filterTicker)}
                    name="filterTicker"
                    placeholder="Ticker contains"
                  />
                  <input
                    className="border-line bg-obsidian text-ink min-h-10 border px-3 text-sm outline-none"
                    defaultValue={getQueryValue(params.filterTag)}
                    name="filterTag"
                    placeholder="Tag"
                  />
                  <select
                    className="border-line bg-obsidian text-ink min-h-10 border px-3 text-sm outline-none"
                    defaultValue={getQueryValue(params.filterThesisStatus)}
                    name="filterThesisStatus"
                  >
                    <option value="">Any thesis status</option>
                    <option value="watching">Watching</option>
                    <option value="researching">Researching</option>
                    <option value="under_review">Under review</option>
                    <option value="passed">Passed</option>
                    <option value="owned">Owned</option>
                  </select>
                  <select
                    className="border-line bg-obsidian text-ink min-h-10 border px-3 text-sm outline-none"
                    defaultValue={getQueryValue(params.filterPriority)}
                    name="filterPriority"
                  >
                    <option value="">Any priority</option>
                    <option value="high">High</option>
                    <option value="medium">Medium</option>
                    <option value="low">Low</option>
                  </select>
                  <select
                    className="border-line bg-obsidian text-ink min-h-10 border px-3 text-sm outline-none"
                    defaultValue={getQueryValue(params.filterWorkflowState)}
                    name="filterWorkflowState"
                  >
                    <option value="">Any workflow state</option>
                    <option value="needs_review">Needs review</option>
                    <option value="under_review">Under review</option>
                    <option value="monitoring">Monitoring</option>
                    <option value="not_started">Not started</option>
                    <option value="thesis_ready">Thesis ready</option>
                    <option value="archived">Archived</option>
                  </select>
                  <select
                    className="border-line bg-obsidian text-ink min-h-10 border px-3 text-sm outline-none"
                    defaultValue={getQueryValue(params.filterRankingStatus)}
                    name="filterRankingStatus"
                  >
                    <option value="">Any ranking status</option>
                    <option value="eligible">Eligible</option>
                    <option value="ineligible">Ineligible</option>
                    <option value="unranked_missing_data">Missing data</option>
                  </select>
                  <select
                    className="border-line bg-obsidian text-ink min-h-10 border px-3 text-sm outline-none"
                    defaultValue={getQueryValue(params.filterAlertType)}
                    name="filterAlertType"
                  >
                    <option value="">Any alert type</option>
                    <option value="priceAboveTarget">Price above target</option>
                    <option value="priceBelowTarget">Price below target</option>
                    <option value="valuationGapAboveThreshold">Valuation gap</option>
                    <option value="rankingStatusChanged">Ranking changed</option>
                    <option value="snapshotStale">Snapshot stale</option>
                    <option value="providerDegraded">Provider degraded</option>
                    <option value="missingCriticalData">Missing critical data</option>
                  </select>
                  <input
                    className="border-line bg-obsidian text-ink min-h-10 border px-3 text-sm outline-none"
                    defaultValue={getQueryValue(params.filterValuationGapMin)}
                    name="filterValuationGapMin"
                    placeholder="Min gap %"
                  />
                  <input
                    className="border-line bg-obsidian text-ink min-h-10 border px-3 text-sm outline-none"
                    defaultValue={getQueryValue(params.filterValuationGapMax)}
                    name="filterValuationGapMax"
                    placeholder="Max gap %"
                  />
                  <select
                    className="border-line bg-obsidian text-ink min-h-10 border px-3 text-sm outline-none"
                    defaultValue={getQueryValue(params.filterStaleSnapshot)}
                    name="filterStaleSnapshot"
                  >
                    <option value="">Any freshness</option>
                    <option value="true">Stale only</option>
                    <option value="false">Fresh or missing</option>
                  </select>
                  <select
                    className="border-line bg-obsidian text-ink min-h-10 border px-3 text-sm outline-none"
                    defaultValue={getQueryValue(params.filterMissingCriticalData)}
                    name="filterMissingCriticalData"
                  >
                    <option value="">Any data state</option>
                    <option value="true">Missing critical data</option>
                    <option value="false">No missing critical data</option>
                  </select>
                  <select
                    className="border-line bg-obsidian text-ink min-h-10 border px-3 text-sm outline-none"
                    defaultValue={getQueryValue(params.filterProviderDegraded)}
                    name="filterProviderDegraded"
                  >
                    <option value="">Any provider state</option>
                    <option value="true">Provider degraded</option>
                    <option value="false">Provider healthy</option>
                  </select>
                  <div className="grid grid-cols-2 gap-2">
                    <select
                      className="border-line bg-obsidian text-ink min-h-10 border px-3 text-sm outline-none"
                      defaultValue={getQueryValue(params.sortField)}
                      name="sortField"
                    >
                      <option value="">No sort</option>
                      <option value="ticker">Ticker</option>
                      <option value="priority">Priority</option>
                      <option value="valuationGap">Valuation gap</option>
                      <option value="latestRank">Latest rank</option>
                      <option value="alertCount">Alert count</option>
                      <option value="snapshotFreshness">Freshness</option>
                      <option value="addedAt">Added at</option>
                    </select>
                    <select
                      className="border-line bg-obsidian text-ink min-h-10 border px-3 text-sm outline-none"
                      defaultValue={getQueryValue(params.sortDirection) || "desc"}
                      name="sortDirection"
                    >
                      <option value="desc">Desc</option>
                      <option value="asc">Asc</option>
                    </select>
                  </div>
                </div>
                <div className="border-line grid gap-2 border p-3 sm:grid-cols-2 lg:grid-cols-7">
                  {AVAILABLE_COLUMNS.map((column) => (
                    <label
                      className="text-muted flex items-center gap-2 font-mono text-[10px] uppercase"
                      key={column.key}
                    >
                      <input
                        className="accent-accent"
                        defaultChecked={visibleColumns.includes(column.key)}
                        name="visibleColumns"
                        type="checkbox"
                        value={column.key}
                      />
                      {column.label}
                    </label>
                  ))}
                </div>
                <div className="grid gap-2 lg:grid-cols-[1fr_repeat(3,140px)]">
                  <input
                    className="border-line bg-obsidian text-ink min-h-10 border px-3 text-sm outline-none"
                    defaultValue={activeView?.name ?? ""}
                    name="viewName"
                    placeholder="View name"
                  />
                  <button
                    className="border-line text-muted hover:text-accent min-h-10 border px-3 font-mono text-[10px] uppercase transition"
                    type="submit"
                  >
                    Apply
                  </button>
                  <button
                    className="border-line text-muted hover:text-accent min-h-10 border px-3 font-mono text-[10px] uppercase transition"
                    name="viewAction"
                    type="submit"
                    value="create-view"
                  >
                    Save view
                  </button>
                  {activeView ? (
                    <button
                      className="border-line text-muted hover:text-accent min-h-10 border px-3 font-mono text-[10px] uppercase transition"
                      name="viewAction"
                      type="submit"
                      value="update-view"
                    >
                      Update view
                    </button>
                  ) : null}
                </div>
              </form>
            </PlaceholderCard>
          ) : null}

          {activeWatchlist ? (
            <PlaceholderCard
              label="Add ticker"
              title="Add a company to this workspace"
              description="Targets and notes are analyst inputs. Market prices, rankings, and valuation gaps remain source-backed or unavailable."
            >
              <form
                action="/watchlist"
                className="grid gap-3 lg:grid-cols-[90px_1fr_1fr_110px_130px_120px_130px_auto]"
              >
                <HiddenQueryFields
                  includeArchived={includeArchived}
                  watchlistId={activeWatchlist.watchlistId}
                  viewId={activeViewId}
                />
                <input
                  className="border-line bg-obsidian text-ink min-h-10 border px-3 font-mono text-sm uppercase outline-none"
                  name="ticker"
                  placeholder="AAPL"
                />
                <input
                  className="border-line bg-obsidian text-ink min-h-10 border px-3 text-sm outline-none"
                  name="notes"
                  placeholder="Working note"
                />
                <input
                  className="border-line bg-obsidian text-ink min-h-10 border px-3 text-sm outline-none"
                  name="tags"
                  placeholder="quality, moat"
                />
                <input
                  className="border-line bg-obsidian text-ink min-h-10 border px-3 text-sm outline-none"
                  name="targetPrice"
                  placeholder="Target"
                />
                <select
                  className="border-line bg-obsidian text-ink min-h-10 border px-3 text-sm outline-none"
                  name="thesisStatus"
                  defaultValue="watching"
                >
                  <option value="watching">Watching</option>
                  <option value="researching">Researching</option>
                  <option value="under_review">Under review</option>
                  <option value="passed">Passed</option>
                  <option value="owned">Owned</option>
                </select>
                <select
                  className="border-line bg-obsidian text-ink min-h-10 border px-3 text-sm outline-none"
                  name="priority"
                  defaultValue="medium"
                >
                  <option value="low">Low</option>
                  <option value="medium">Medium</option>
                  <option value="high">High</option>
                </select>
                <select
                  className="border-line bg-obsidian text-ink min-h-10 border px-3 text-sm outline-none"
                  name="workflowState"
                  defaultValue="not_started"
                >
                  <option value="not_started">Not started</option>
                  <option value="monitoring">Monitoring</option>
                  <option value="needs_review">Needs review</option>
                  <option value="under_review">Under review</option>
                  <option value="thesis_ready">Thesis ready</option>
                  <option value="archived">Archived</option>
                </select>
                <button
                  className="border-line text-muted hover:text-accent min-h-10 border px-4 font-mono text-[10px] uppercase transition"
                  name="action"
                  type="submit"
                  value="add-item"
                >
                  Add
                </button>
              </form>
            </PlaceholderCard>
          ) : null}

          {intelligenceResult?.ok ? (
            <PlaceholderCard
              label="Intelligence"
              title={intelligenceResult.data.watchlist.name}
              description="Rows aggregate current deterministic context. Missing fields stay unavailable until snapshots, rankings, valuations, or providers exist."
            >
              <ApiState
                title={`Intelligence ${intelligenceResult.data.provider.state}`}
                message={intelligenceResult.data.message}
                provider={intelligenceResult.data.provider}
                endpoint={`/api/watchlists/${intelligenceResult.data.watchlist.watchlistId}/intelligence`}
              />
              <StatusList
                items={[
                  {
                    label: "Visible rows",
                    status: `${intelligenceItems.length} of ${intelligenceResult.data.allItemCount}`,
                  },
                  {
                    label: "Active alerts",
                    status: String(intelligenceResult.data.activeAlertCount),
                  },
                  {
                    label: "View",
                    status: activeViewLabel,
                  },
                ]}
              />
              <div className="mt-5 overflow-hidden border border-line">
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[1320px] border-collapse text-left text-sm">
                    <thead className="bg-graphite2 text-muted font-mono text-[11px] uppercase">
                      <tr>
                        {AVAILABLE_COLUMNS.filter((column) =>
                          columnVisible(visibleColumns, column.key),
                        ).map((column) => (
                          <th className="border-line border-b px-4 py-3" key={column.key}>
                            {column.label}
                          </th>
                        ))}
                        <th className="border-line border-b px-4 py-3">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-line divide-y">
                      {intelligenceItems.length ? (
                        intelligenceItems.map((item) => (
                          <tr className="bg-panel/60" key={item.ticker}>
                            {columnVisible(visibleColumns, "ticker") ? (
                              <td className="text-accent px-4 py-3 font-mono text-xs">
                                <Link href={`/company/${item.ticker}`}>
                                  {item.ticker}
                                </Link>
                              </td>
                            ) : null}
                            {columnVisible(visibleColumns, "company") ? (
                              <td className="text-ink max-w-[220px] px-4 py-3">
                                {item.companyName ?? "Unavailable"}
                              </td>
                            ) : null}
                            {columnVisible(visibleColumns, "price") ? (
                              <td className="text-ink px-4 py-3">
                                {formatMoney(
                                  item.marketSnapshot.price,
                                  item.marketSnapshot.currency,
                                )}
                              </td>
                            ) : null}
                            {columnVisible(visibleColumns, "target") ? (
                              <td className="text-ink px-4 py-3">
                                {formatMoney(
                                  item.item.targetPrice,
                                  item.marketSnapshot.currency,
                                )}
                              </td>
                            ) : null}
                            {columnVisible(visibleColumns, "valuationGap") ? (
                              <td className="text-ink px-4 py-3">
                                {formatPercent(item.valuationGap.gapPercent)}
                              </td>
                            ) : null}
                            {columnVisible(visibleColumns, "rank") ? (
                              <td className="text-ink px-4 py-3 font-mono text-xs">
                                {item.ranking?.rank ?? "NR"}
                              </td>
                            ) : null}
                            {columnVisible(visibleColumns, "eligibility") ? (
                              <td className="text-muted px-4 py-3 font-mono text-[11px] uppercase">
                                {item.magicFormulaEligibility.status}
                              </td>
                            ) : null}
                            {columnVisible(visibleColumns, "freshness") ? (
                              <td className="text-muted px-4 py-3 font-mono text-[11px] uppercase">
                                {item.fundamentalsSnapshot.state} |{" "}
                                {formatTimestamp(
                                  item.fundamentalsSnapshot.refreshedAt,
                                )}
                              </td>
                            ) : null}
                            {columnVisible(visibleColumns, "staleness") ? (
                              <td className="text-muted max-w-[240px] px-4 py-3 font-mono text-[11px] uppercase">
                                <span className="border-line inline-block border px-2 py-1">
                                  {item.staleness.state}
                                </span>
                                <span className="mt-1 block normal-case">
                                  {item.staleness.staleReasons.slice(0, 2).join(", ") ||
                                    `age ${formatAge(item.staleness.maxAgeSeconds)}`}
                                </span>
                              </td>
                            ) : null}
                            {columnVisible(visibleColumns, "provider") ? (
                              <td className="text-muted px-4 py-3 font-mono text-[11px] uppercase">
                                {providerState(item)}
                              </td>
                            ) : null}
                            {columnVisible(visibleColumns, "status") ? (
                              <td className="px-4 py-3">
                                <span className="border-line text-muted inline-block border px-2 py-1 font-mono text-[10px] uppercase">
                                  {researchStatusValue(item.item.thesisStatus)}
                                </span>
                              </td>
                            ) : null}
                            {columnVisible(visibleColumns, "workflowState") ? (
                              <td className="px-4 py-3">
                                <span className="border-line text-muted inline-block border px-2 py-1 font-mono text-[10px] uppercase">
                                  {workflowStateValue(item.item.workflowState)}
                                </span>
                              </td>
                            ) : null}
                            {columnVisible(visibleColumns, "priority") ? (
                              <td className="px-4 py-3">
                                <span className="border-line text-muted inline-block border px-2 py-1 font-mono text-[10px] uppercase">
                                  {priorityValue(item.item.priority)}
                                </span>
                              </td>
                            ) : null}
                            {columnVisible(visibleColumns, "alerts") ? (
                              <td className="text-muted max-w-[220px] px-4 py-3 font-mono text-[11px]">
                                {itemAlertSummary(item.alerts)}
                              </td>
                            ) : null}
                            {columnVisible(visibleColumns, "flags") ? (
                              <td className="text-muted max-w-[280px] px-4 py-3 font-mono text-[11px]">
                                {itemFlagSummary(item)}
                              </td>
                            ) : null}
                            {columnVisible(visibleColumns, "notes") ? (
                              <td className="text-muted max-w-[260px] px-4 py-3">
                                {item.item.notes ?? "No note"}
                              </td>
                            ) : null}
                            <td className="px-4 py-3">
                              <form
                                action="/watchlist"
                                className="grid min-w-[280px] gap-2"
                              >
                                <HiddenQueryFields
                                  includeArchived={includeArchived}
                                  watchlistId={
                                    intelligenceResult.data.watchlist.watchlistId
                                  }
                                  viewId={activeViewId}
                                />
                                <input
                                  name="ticker"
                                  type="hidden"
                                  value={item.ticker}
                                />
                                <input
                                  className="border-line bg-obsidian text-ink min-h-9 border px-2 text-xs outline-none"
                                  defaultValue={item.item.notes ?? ""}
                                  name="notes"
                                  placeholder="Note"
                                />
                                <input
                                  className="border-line bg-obsidian text-ink min-h-9 border px-2 text-xs outline-none"
                                  defaultValue={item.item.tags.join(", ")}
                                  name="tags"
                                  placeholder="Tags"
                                />
                                <div className="grid grid-cols-4 gap-2">
                                  <input
                                    className="border-line bg-obsidian text-ink min-h-9 border px-2 text-xs outline-none"
                                    defaultValue={item.item.targetPrice ?? ""}
                                    name="targetPrice"
                                    placeholder="Target"
                                  />
                                  <select
                                    className="border-line bg-obsidian text-ink min-h-9 border px-2 text-xs outline-none"
                                    defaultValue={researchStatusValue(
                                      item.item.thesisStatus,
                                    )}
                                    name="thesisStatus"
                                  >
                                    <option value="watching">Watching</option>
                                    <option value="researching">Researching</option>
                                    <option value="under_review">Review</option>
                                    <option value="passed">Passed</option>
                                    <option value="owned">Owned</option>
                                  </select>
                                  <select
                                    className="border-line bg-obsidian text-ink min-h-9 border px-2 text-xs outline-none"
                                    defaultValue={priorityValue(item.item.priority)}
                                    name="priority"
                                  >
                                    <option value="low">Low</option>
                                    <option value="medium">Medium</option>
                                    <option value="high">High</option>
                                  </select>
                                  <select
                                    className="border-line bg-obsidian text-ink min-h-9 border px-2 text-xs outline-none"
                                    defaultValue={workflowStateValue(
                                      item.item.workflowState,
                                    )}
                                    name="workflowState"
                                  >
                                    <option value="not_started">Not started</option>
                                    <option value="monitoring">Monitoring</option>
                                    <option value="needs_review">Needs review</option>
                                    <option value="under_review">Review</option>
                                    <option value="thesis_ready">Ready</option>
                                    <option value="archived">Archived</option>
                                  </select>
                                </div>
                                <div className="grid grid-cols-2 gap-2">
                                  <button
                                    className="border-line text-muted hover:text-accent min-h-9 border px-2 font-mono text-[10px] uppercase transition"
                                    name="action"
                                    type="submit"
                                    value="update-item"
                                  >
                                    Save
                                  </button>
                                  <button
                                    className="border-line text-muted hover:text-amber min-h-9 border px-2 font-mono text-[10px] uppercase transition"
                                    name="action"
                                    type="submit"
                                    value="remove-item"
                                  >
                                    Remove
                                  </button>
                                </div>
                              </form>
                            </td>
                          </tr>
                        ))
                      ) : (
                        <tr>
                          <td
                            className="text-muted px-4 py-6 text-sm"
                            colSpan={columnCount(visibleColumns)}
                          >
                            No rows match this watchlist view.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </PlaceholderCard>
          ) : activeWatchlistId ? (
            <PlaceholderCard
              label="Intelligence"
              title="Watchlist intelligence unavailable"
              description="The backend intelligence endpoint could not be loaded for this watchlist."
            >
              {intelligenceResult && !intelligenceResult.ok ? (
                <ApiState
                  title="API unavailable"
                  message={intelligenceResult.error.message}
                  endpoint={intelligenceResult.error.endpoint}
                />
              ) : null}
            </PlaceholderCard>
          ) : null}

          {refreshHistoryResult?.ok ? (
            <PlaceholderCard
              label="Refresh history"
              title="Watchlist-scoped jobs"
              description="Refresh history is persisted in the local job store and remains separate from recommendations or notifications."
            >
              <div className="border-line divide-line border">
                {refreshJobs.length ? (
                  refreshJobs.slice(0, 8).map((job) => (
                    <div
                      className="grid gap-2 px-4 py-3 text-sm lg:grid-cols-[180px_120px_1fr_160px]"
                      key={job.jobId}
                    >
                      <span className="text-accent font-mono text-[11px] uppercase">
                        {job.jobId}
                      </span>
                      <span className="text-muted font-mono text-[11px] uppercase">
                        {job.status}
                      </span>
                      <span className="text-ink">
                        {job.resultMetadata.refreshedCount ?? 0} refreshed,{" "}
                        {job.resultMetadata.skippedFreshCount ?? 0} skipped
                      </span>
                      <span className="text-muted font-mono text-[11px]">
                        {formatTimestamp(job.completedAt ?? job.createdAt)}
                      </span>
                    </div>
                  ))
                ) : (
                  <div className="text-muted px-4 py-4 text-sm">
                    No watchlist refresh jobs have run for this workspace.
                  </div>
                )}
              </div>
            </PlaceholderCard>
          ) : null}

          {alertsResult?.ok ? (
            <PlaceholderCard
              label="Alerts"
              title="Alert inbox"
              description="Alerts are deterministic records for analyst review. Acknowledgement and dismissal are local audit states, not notifications."
            >
              <StatusList
                items={[
                  { label: "Active inbox", status: String(alerts.length) },
                  {
                    label: "Acknowledged history",
                    status: String(
                      alertHistory.filter((alert) => alert.acknowledgedAt).length,
                    ),
                  },
                  {
                    label: "Dismissed history",
                    status: String(
                      alertHistory.filter((alert) => alert.dismissedAt).length,
                    ),
                  },
                ]}
              />
              <div className="border-line divide-line mt-4 border">
                {alerts.length ? (
                  alerts.map((alert) => (
                    <div
                      className="grid gap-2 px-4 py-3 text-sm lg:grid-cols-[110px_170px_1fr_110px_210px]"
                      key={alert.alertId}
                    >
                      <span className="text-accent font-mono text-[11px] uppercase">
                        {alert.ticker}
                      </span>
                      <span className="text-muted font-mono text-[11px] uppercase">
                        {alert.type}
                      </span>
                      <span className="text-ink">{alert.message}</span>
                      <span className="text-muted font-mono text-[11px] uppercase">
                        {alert.severity} | {alert.status}
                      </span>
                      <form action="/watchlist" className="grid grid-cols-2 gap-2">
                        <HiddenQueryFields
                          includeArchived={includeArchived}
                          watchlistId={activeWatchlistId}
                          viewId={activeViewId}
                        />
                        <input name="alertId" type="hidden" value={alert.alertId} />
                        <button
                          className="border-line text-muted hover:text-accent min-h-8 border px-2 font-mono text-[10px] uppercase transition"
                          name="alertAction"
                          type="submit"
                          value="acknowledge"
                        >
                          Ack
                        </button>
                        <button
                          className="border-line text-muted hover:text-amber min-h-8 border px-2 font-mono text-[10px] uppercase transition"
                          name="alertAction"
                          type="submit"
                          value="dismiss"
                        >
                          Dismiss
                        </button>
                      </form>
                    </div>
                  ))
                ) : (
                  <div className="text-muted px-4 py-4 text-sm">
                    No active deterministic alerts for the selected watchlist.
                  </div>
                )}
              </div>
            </PlaceholderCard>
          ) : null}

          {alertHistoryResult?.ok ? (
            <PlaceholderCard
              label="History"
              title="Alert acknowledgment history"
              description="Historical alert records preserve acknowledgement and dismissal timestamps for local auditability."
            >
              <div className="border-line divide-line border">
                {alertHistory.length ? (
                  alertHistory.slice(0, 50).map((alert) => (
                    <div
                      className="grid gap-2 px-4 py-3 text-sm lg:grid-cols-[110px_170px_1fr_130px_180px_110px]"
                      key={alert.alertId}
                    >
                      <span className="text-accent font-mono text-[11px] uppercase">
                        {alert.ticker}
                      </span>
                      <span className="text-muted font-mono text-[11px] uppercase">
                        {alert.type}
                      </span>
                      <span className="text-ink">{alert.message}</span>
                      <span className="text-muted font-mono text-[11px] uppercase">
                        {alert.status}
                      </span>
                      <span className="text-muted font-mono text-[11px]">
                        Ack {formatTimestamp(alert.acknowledgedAt)}
                        <br />
                        Dismissed {formatTimestamp(alert.dismissedAt)}
                      </span>
                      {alert.dismissedAt ? (
                        <form action="/watchlist">
                          <HiddenQueryFields
                            includeArchived={includeArchived}
                            watchlistId={activeWatchlistId}
                            viewId={activeViewId}
                          />
                          <input
                            name="alertId"
                            type="hidden"
                            value={alert.alertId}
                          />
                          <button
                            className="border-line text-muted hover:text-accent min-h-8 border px-2 font-mono text-[10px] uppercase transition"
                            name="alertAction"
                            type="submit"
                            value="restore"
                          >
                            Restore
                          </button>
                        </form>
                      ) : (
                        <span className="text-muted font-mono text-[10px] uppercase">
                          Active
                        </span>
                      )}
                    </div>
                  ))
                ) : (
                  <div className="text-muted px-4 py-4 text-sm">
                    No alert history for the selected watchlist.
                  </div>
                )}
              </div>
            </PlaceholderCard>
          ) : null}
        </div>
      </section>
    </TerminalShell>
  );
}
