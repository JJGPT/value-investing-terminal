from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from app.services.fundamentals.provider import FundamentalsProvider
from app.services.market_data.provider import MarketDataProvider
from app.services.persistence.repository import SnapshotRepository
from app.services.persistence.sqlite_repository import SCHEMA_VERSION
from app.services.provider_status import (
    provider_connected,
    provider_degraded,
    provider_not_connected,
)
from app.services.screener.engine import (
    collect_screener_materials,
    row_from_screener_snapshot,
    row_with_provider_fallback_snapshot,
)
from app.services.screener.universe import (
    PHASE_2D_TICKERS,
    PHASE_2D_UNIVERSE_NAME,
)

RANKING_STRATEGIES = {
    "magic_formula",
    "quality",
    "value",
    "growth",
    "profitability",
}
RANKING_ENGINE_VERSION = "platform-ranking-engine-v1"
MAGIC_FORMULA_VERSION = "magic-formula-v1"
DEFAULT_ELIGIBILITY_SETTINGS = {
    "minimumMarketCap": 0,
    "minimumPrice": 0,
    "minimumVolume": None,
    "excludeFinancials": False,
    "excludeUtilities": False,
    "requirePositiveEnterpriseValue": True,
    "requirePositiveInvestedCapital": True,
    "requirePositiveEbit": True,
}
ELIGIBILITY_STATUSES = {
    "eligible",
    "ineligible",
    "unranked_missing_data",
}
RANKING_FILTER_OPERATORS = {"gt", "gte", "lt", "lte", "eq", "between"}
RANKING_FILTER_FIELDS = {
    "rank",
    "score",
    "earningsYield",
    "returnOnCapital",
    "enterpriseValue",
    "investedCapital",
    "ebit",
    "marketCap",
    "price",
}
REFRESH_STATES = {"queued", "running", "completed", "failed"}


def build_ranking_response(
    fundamentals_provider: FundamentalsProvider,
    market_data_provider: MarketDataProvider,
    repository: SnapshotRepository,
    strategy: str,
    period: str,
    limit: int,
    universe: Optional[list[str]] = None,
    stale_after_seconds: int = 86400,
    include_ineligible: bool = True,
    eligibility_settings: Optional[dict] = None,
    filters: Optional[list[dict]] = None,
    sorting: Optional[dict] = None,
) -> dict:
    normalized_strategy = normalize_strategy(strategy)
    normalized_period = normalize_period(period)
    normalized_limit = max(min(limit, 100), 1)
    normalized_eligibility = normalize_eligibility_settings(eligibility_settings)
    computed_at = utc_now()
    tickers = ranking_universe(repository, universe)
    input_rows = [
        build_ranking_input(
            ticker,
            normalized_period,
            fundamentals_provider,
            market_data_provider,
            repository,
            stale_after_seconds,
        )
        for ticker in tickers
    ]
    ranked_rows = rank_inputs(
        input_rows,
        normalized_strategy,
        normalized_eligibility,
        computed_at,
    )
    normalized_filters = normalize_ranking_filters(filters)
    normalized_sorting = normalize_ranking_sort(sorting)
    filtered_rows = apply_ranking_filters(ranked_rows, normalized_filters)
    sorted_rows = apply_ranking_sort(filtered_rows, normalized_sorting)
    visible_rows = (
        sorted_rows
        if include_ineligible
        else [
            row
            for row in sorted_rows
            if row.get("eligibilityStatus") == "eligible"
        ]
    )
    limited_rows = visible_rows[:normalized_limit]
    diagnostics = ranking_diagnostics_summary(sorted_rows)
    latest_runs = repository.list_ranking_runs(
        normalized_strategy,
        normalized_period,
        1,
    )

    return {
        "strategy": normalized_strategy,
        "period": normalized_period,
        "limit": normalized_limit,
        "includeIneligible": include_ineligible,
        "filters": normalized_filters,
        "sorting": normalized_sorting,
        "rows": limited_rows,
        "provider": aggregate_provider_status(
            [row.get("provider") for row in ranked_rows],
            "Ranking rows were generated from canonical normalized data.",
        ),
        "universe": {
            "name": PHASE_2D_UNIVERSE_NAME,
            "size": len(tickers),
            "tickers": tickers,
        },
        "diagnostics": {
            "availableStrategies": sorted(RANKING_STRATEGIES),
            **diagnostics,
            "engineVersion": RANKING_ENGINE_VERSION,
        },
        "eligibilitySettings": normalized_eligibility,
        "latestRun": latest_runs[0] if latest_runs else None,
        "message": (
            "Rankings are deterministic research screens. They are not "
            "recommendations, portfolio instructions, or trading signals."
        ),
    }


def build_magic_formula_response(
    fundamentals_provider: FundamentalsProvider,
    market_data_provider: MarketDataProvider,
    repository: SnapshotRepository,
    period: str,
    limit: int,
    universe: Optional[list[str]] = None,
    stale_after_seconds: int = 86400,
) -> dict:
    return build_ranking_response(
        fundamentals_provider,
        market_data_provider,
        repository,
        "magic_formula",
        period,
        limit,
        universe,
        stale_after_seconds,
        include_ineligible=True,
    )


def refresh_ranking_run(
    fundamentals_provider: FundamentalsProvider,
    market_data_provider: MarketDataProvider,
    repository: SnapshotRepository,
    strategy: str,
    period: str,
    universe: Optional[list[str]] = None,
    stale_after_seconds: int = 86400,
    eligibility_settings: Optional[dict] = None,
    filters: Optional[list[dict]] = None,
    sorting: Optional[dict] = None,
    screen_id: Optional[str] = None,
    scope_type: str = "universe",
    tickers: Optional[list[str]] = None,
    stale_only: bool = False,
) -> dict:
    refresh_id = refresh_run_id()
    requested_at = utc_now()
    screen = repository.get_ranking_screen(screen_id) if screen_id else None
    normalized_strategy = normalize_strategy(
        (screen or {}).get("strategy") or strategy
    )
    normalized_period = normalize_period((screen or {}).get("period") or period)
    normalized_eligibility = normalize_eligibility_settings(
        (screen or {}).get("eligibilitySettings") or eligibility_settings
    )
    normalized_filters = normalize_ranking_filters(
        (screen or {}).get("filters") or filters
    )
    normalized_sorting = normalize_ranking_sort(
        (screen or {}).get("sorting") or sorting
    )
    normalized_limit = normalize_limit((screen or {}).get("limit") or 100)
    scope = refresh_scope(
        scope_type,
        tickers,
        stale_only,
        screen_id=screen.get("screenId") if screen else screen_id,
    )
    scoped_universe = tickers if scope["type"] == "tickers" and tickers else universe
    warnings = refresh_scope_warnings(scope)
    state_transitions = [
        {
            "state": "queued",
            "at": requested_at,
            "message": "Refresh request was accepted for synchronous execution.",
        }
    ]
    started_at = utc_now()
    state_transitions.append(
        {
            "state": "running",
            "at": started_at,
            "message": "Ranking refresh is running synchronously.",
        }
    )

    try:
        response = build_ranking_response(
            fundamentals_provider,
            market_data_provider,
            repository,
            normalized_strategy,
            normalized_period,
            normalized_limit,
            universe=scoped_universe,
            stale_after_seconds=stale_after_seconds,
            include_ineligible=True,
            eligibility_settings=normalized_eligibility,
            filters=normalized_filters,
            sorting=normalized_sorting,
        )
        computed_at = utc_now()
        run = {
            "runId": ranking_run_id(response["strategy"], response["period"]),
            "schemaVersion": SCHEMA_VERSION,
            "strategy": response["strategy"],
            "period": response["period"],
            "rankingEngineVersion": RANKING_ENGINE_VERSION,
            "computedAt": computed_at,
            "universe": response["universe"],
            "eligibilitySettings": response["eligibilitySettings"],
            "filters": response["filters"],
            "sorting": response["sorting"],
            "savedScreen": screen_summary(screen) if screen else None,
            "summary": {
                **response["diagnostics"],
                "totalRows": len(response["rows"]),
            },
            "provider": response["provider"],
            "rows": [
                {
                    **row,
                    "computedAt": computed_at,
                    "rankingEngineVersion": RANKING_ENGINE_VERSION,
                    "audit": {
                        **(row.get("audit") or {}),
                        "computedAt": computed_at,
                        "rankingEngineVersion": RANKING_ENGINE_VERSION,
                    },
                }
                for row in response["rows"]
            ],
            "message": (
                "Ranking run was persisted as immutable SQLite JSON snapshots. "
                "It is a deterministic research screen, not a recommendation."
            ),
        }
        persisted_run = repository.create_ranking_run(run)
        completed_at = utc_now()
        state_transitions.append(
            {
                "state": "completed",
                "at": completed_at,
                "message": "Ranking refresh completed and persisted a run.",
            }
        )
        result = {
            "refreshId": refresh_id,
            "schemaVersion": SCHEMA_VERSION,
            "status": "completed",
            "state": "completed",
            "strategy": response["strategy"],
            "period": response["period"],
            "scope": scope,
            "startedAt": started_at,
            "completedAt": completed_at,
            "failedAt": None,
            "durationMs": duration_ms(started_at, completed_at),
            "warnings": warnings,
            "errors": [],
            "stateTransitions": state_transitions,
            "metadata": {
                "synchronous": True,
                "supportsPerTickerRefresh": True,
                "supportsPartialRefresh": True,
                "supportsStaleOnlyRefresh": False,
                "supportsScheduledRefresh": False,
            },
            "runId": persisted_run["runId"],
            "run": persisted_run,
            **persisted_run,
            "message": (
                "Ranking refresh completed synchronously. The workflow shape "
                "is ready for future async, stale-only, per-ticker, and "
                "scheduled refresh runners."
            ),
        }
    except Exception as error:  # defensive workflow boundary
        failed_at = utc_now()
        sanitized_error = sanitize_error_message(str(error))
        state_transitions.append(
            {
                "state": "failed",
                "at": failed_at,
                "message": sanitized_error,
            }
        )
        result = {
            "refreshId": refresh_id,
            "schemaVersion": SCHEMA_VERSION,
            "status": "failed",
            "state": "failed",
            "strategy": normalized_strategy,
            "period": normalized_period,
            "scope": scope,
            "startedAt": started_at,
            "completedAt": None,
            "failedAt": failed_at,
            "durationMs": duration_ms(started_at, failed_at),
            "warnings": warnings,
            "errors": [{"message": sanitized_error}],
            "stateTransitions": state_transitions,
            "metadata": {
                "synchronous": True,
                "supportsPerTickerRefresh": True,
                "supportsPartialRefresh": True,
                "supportsStaleOnlyRefresh": False,
                "supportsScheduledRefresh": False,
            },
            "runId": None,
            "run": None,
            "message": "Ranking refresh failed before a ranking run could be persisted.",
        }

    return repository.record_ranking_refresh_run(result)


def create_ranking_screen(repository: SnapshotRepository, payload: dict) -> dict:
    now = utc_now()
    screen = {
        "screenId": ranking_screen_id(),
        "schemaVersion": SCHEMA_VERSION,
        "name": ranking_screen_name(payload.get("name")),
        "strategy": normalize_strategy(payload.get("strategy") or "magic_formula"),
        "filters": normalize_ranking_filters(payload.get("filters")),
        "eligibilitySettings": normalize_eligibility_settings(
            payload.get("eligibilitySettings")
        ),
        "sorting": normalize_ranking_sort(payload.get("sorting")),
        "period": normalize_period(payload.get("period") or "annual"),
        "limit": normalize_limit(payload.get("limit") or 50),
        "status": "active",
        "createdAt": now,
        "updatedAt": now,
        "archivedAt": None,
        "deletedAt": None,
        "message": "Saved ranking screen stores reusable deterministic screen settings.",
    }

    return repository.upsert_ranking_screen(screen)


def update_ranking_screen(
    repository: SnapshotRepository,
    screen_id: str,
    updates: dict,
) -> Optional[dict]:
    existing = repository.get_ranking_screen(screen_id)

    if existing is None:
        return None

    updated = {
        **existing,
        "name": ranking_screen_name(updates.get("name") or existing.get("name")),
        "strategy": normalize_strategy(updates.get("strategy") or existing.get("strategy")),
        "filters": normalize_ranking_filters(
            updates.get("filters")
            if "filters" in updates
            else existing.get("filters")
        ),
        "eligibilitySettings": normalize_eligibility_settings(
            updates.get("eligibilitySettings")
            if "eligibilitySettings" in updates
            else existing.get("eligibilitySettings")
        ),
        "sorting": normalize_ranking_sort(
            updates.get("sorting")
            if "sorting" in updates
            else existing.get("sorting")
        ),
        "period": normalize_period(updates.get("period") or existing.get("period")),
        "limit": normalize_limit(updates.get("limit") or existing.get("limit")),
        "updatedAt": utc_now(),
        "message": "Saved ranking screen was updated.",
    }

    return repository.upsert_ranking_screen(updated)


def duplicate_ranking_screen(
    repository: SnapshotRepository,
    screen_id: str,
    payload: Optional[dict] = None,
) -> Optional[dict]:
    existing = repository.get_ranking_screen(screen_id)

    if existing is None:
        return None

    now = utc_now()
    duplicate = {
        **existing,
        "screenId": ranking_screen_id(),
        "name": ranking_screen_name(
            (payload or {}).get("name") or f"{existing.get('name')} Copy"
        ),
        "status": "active",
        "parentScreenId": existing.get("screenId"),
        "createdAt": now,
        "updatedAt": now,
        "archivedAt": None,
        "deletedAt": None,
        "message": "Saved ranking screen was duplicated.",
    }

    return repository.upsert_ranking_screen(duplicate)


def set_ranking_screen_lifecycle(
    repository: SnapshotRepository,
    screen_id: str,
    action: str,
) -> Optional[dict]:
    existing = repository.get_ranking_screen(screen_id)

    if existing is None:
        return None

    now = utc_now()
    updated = dict(existing)

    if action == "archive":
        updated["status"] = "archived"
        updated["archivedAt"] = now
        updated["deletedAt"] = None
        updated["message"] = "Saved ranking screen was archived."
    elif action == "restore":
        updated["status"] = "active"
        updated["archivedAt"] = None
        updated["deletedAt"] = None
        updated["message"] = "Saved ranking screen was restored."
    elif action == "delete":
        updated["status"] = "deleted"
        updated["deletedAt"] = now
        updated["message"] = "Saved ranking screen was soft deleted."
    else:
        return None

    updated["updatedAt"] = now

    return repository.upsert_ranking_screen(updated)


def build_ranking_run_changes(
    repository: SnapshotRepository,
    run_id: str,
) -> dict:
    run = repository.get_ranking_run(run_id)

    if run is None:
        return {
            "runId": run_id,
            "run": None,
            "previousRun": None,
            "changes": [],
            "summary": {
                "newEntrants": 0,
                "dropped": 0,
                "changedEligibility": 0,
                "unchanged": 0,
            },
            "message": "Ranking run was not found.",
        }

    previous = repository.get_previous_ranking_run(
        run["strategy"],
        run["period"],
        run["computedAt"],
    )
    changes = ranking_changes(run, previous)

    return {
        "runId": run_id,
        "run": ranking_run_summary(run),
        "previousRun": ranking_run_summary(previous) if previous else None,
        "changes": changes,
        "summary": ranking_change_summary(changes),
        "message": (
            "Rank changes compare this immutable run with the immediately "
            "prior run for the same strategy and period."
        ),
    }


def build_ranking_diagnostics(
    fundamentals_provider: FundamentalsProvider,
    market_data_provider: MarketDataProvider,
    repository: SnapshotRepository,
    stale_after_seconds: int,
) -> dict:
    period = "annual"
    response = build_ranking_response(
        fundamentals_provider,
        market_data_provider,
        repository,
        "magic_formula",
        period,
        100,
        stale_after_seconds=stale_after_seconds,
        include_ineligible=True,
    )
    provider_state = response["provider"]["state"]
    ranking_store = repository.ranking_repository_diagnostics(stale_after_seconds)
    job_store = repository.refresh_job_repository_diagnostics(stale_after_seconds)
    policy_store = repository.refresh_policy_repository_diagnostics(stale_after_seconds)

    return {
        "provider": response["provider"],
        "engineVersion": RANKING_ENGINE_VERSION,
        "availableStrategies": sorted(RANKING_STRATEGIES),
        "defaultStrategy": "magic_formula",
        "defaultPeriod": period,
        "universe": response["universe"],
        "eligibleRows": response["diagnostics"]["eligibleRows"],
        "excludedRows": response["diagnostics"]["excludedRows"],
        "ineligibleRows": response["diagnostics"]["ineligibleRows"],
        "unrankedMissingDataRows": response["diagnostics"]["unrankedMissingDataRows"],
        "rankingStore": ranking_store,
        "jobStore": job_store,
        "policyStore": policy_store,
        "endpointReadiness": [
            {
                "name": "Magic Formula ranking",
                "method": "GET",
                "path": "/api/rankings/magic-formula",
                "state": readiness_state(provider_state),
                "message": readiness_message(provider_state),
            },
            {
                "name": "Strategy ranking",
                "method": "GET",
                "path": "/api/rankings",
                "state": readiness_state(provider_state),
                "message": readiness_message(provider_state),
            },
            {
                "name": "Persist ranking run",
                "method": "POST",
                "path": "/api/rankings/refresh",
                "state": readiness_state(provider_state),
                "message": readiness_message(provider_state),
            },
            {
                "name": "Ranking refresh job",
                "method": "POST",
                "path": "/api/jobs/ranking-refresh",
                "state": "ready",
                "message": "Local SQLite job runner can create and execute refresh jobs synchronously.",
            },
            {
                "name": "Refresh job history",
                "method": "GET",
                "path": "/api/jobs",
                "state": "ready",
                "message": "Refresh jobs and events are queryable from SQLite.",
            },
            {
                "name": "Refresh policies",
                "method": "GET",
                "path": "/api/refresh-policies",
                "state": "ready",
                "message": "Local refresh policy records are queryable from SQLite.",
            },
            {
                "name": "Run due refresh policies",
                "method": "POST",
                "path": "/api/jobs/run-due-refresh-policies",
                "state": "ready",
                "message": "Due policies can be evaluated through a synchronous scheduler simulation.",
            },
            {
                "name": "Ranking run history",
                "method": "GET",
                "path": "/api/rankings/runs",
                "state": "ready",
                "message": "SQLite ranking run snapshots are queryable.",
            },
        ],
        "message": (
            "Ranking diagnostics report deterministic ranking readiness over "
            "the controlled snapshot-backed universe."
        ),
    }


def build_ranking_input(
    ticker: str,
    period: str,
    fundamentals_provider: FundamentalsProvider,
    market_data_provider: MarketDataProvider,
    repository: SnapshotRepository,
    stale_after_seconds: int,
) -> dict:
    normalized_ticker = ticker.strip().upper()
    snapshot_row = repository.get_screener_row_snapshot(normalized_ticker, period)
    screener_row = (
        row_from_screener_snapshot(snapshot_row, stale_after_seconds)
        if snapshot_row is not None
        else None
    )
    profile = profile_from_snapshot(repository, normalized_ticker)
    income = statement_from_snapshot(repository, normalized_ticker, period, "income_statement", "incomeStatements")
    balance = statement_from_snapshot(repository, normalized_ticker, period, "balance_sheet", "balanceSheets")
    computed = computed_from_snapshot(repository, normalized_ticker, period)
    snapshot_state = "persisted" if snapshot_row is not None else "provider_fallback"

    if (
        screener_row is None
        and fundamentals_provider.provider_status().get("state") != "not_connected"
    ):
        materials = collect_screener_materials(
            fundamentals_provider,
            normalized_ticker,
            period,
        )
        screener_row = row_with_provider_fallback_snapshot(materials["row"])
        profile = profile or response_profile(materials["profileResponse"])
        income = income or response_first_row(materials["incomeResponse"], "incomeStatements")
        balance = balance or response_first_row(materials["balanceResponse"], "balanceSheets")
        computed = computed or response_first_row(materials["computedResponse"], "computedMetrics")

    if screener_row is None:
        screener_row = empty_screener_row(normalized_ticker, period)
        snapshot_state = "missing"

    market_snapshot = market_snapshot_if_available(market_data_provider, normalized_ticker)
    magic_formula = calculate_magic_formula(
        normalized_ticker,
        profile,
        income,
        balance,
        computed,
        market_snapshot,
        screener_row.get("metrics") or {},
    )

    return {
        "ticker": normalized_ticker,
        "companyName": screener_row.get("companyName"),
        "currency": screener_row.get("currency")
        or row_currency(profile, income, balance, market_snapshot),
        "period": period,
        "sector": profile.get("sector") if profile else None,
        "industry": profile.get("industry") if profile else None,
        "screenerMetrics": screener_row.get("metrics") or {},
        "magicFormula": magic_formula,
        "qualityFlags": sorted(
            set((screener_row.get("qualityFlags") or []) + magic_formula["qualityFlags"])
        ),
        "provider": aggregate_provider_status(
            [
                screener_row.get("provider"),
                fundamentals_provider.provider_status(),
                market_data_provider.provider_status(),
            ],
            "Ranking input was built from canonical normalized data.",
        ),
        "source": {
            **(screener_row.get("source") or {}),
            "snapshotState": snapshot_state,
            "snapshot": screener_row.get("snapshot"),
        },
    }


def calculate_magic_formula(
    ticker: str,
    profile: Optional[dict],
    income: Optional[dict],
    balance: Optional[dict],
    computed: Optional[dict],
    market_snapshot: Optional[dict],
    screener_metrics: Optional[dict] = None,
) -> dict:
    quality_flags = []
    ebit = number(income.get("operatingIncome")) if income else None
    market_cap = first_number(
        market_snapshot.get("marketCap") if market_snapshot else None,
        profile.get("marketCap") if profile else None,
        (screener_metrics or {}).get("marketCap"),
    )
    price = first_number(
        market_snapshot.get("price") if market_snapshot else None,
        profile.get("price") if profile else None,
        (screener_metrics or {}).get("price"),
    )
    volume = number(market_snapshot.get("volume")) if market_snapshot else None
    enterprise_value = first_number(
        market_snapshot.get("enterpriseValue") if market_snapshot else None,
        enterprise_value_proxy(market_cap, balance, quality_flags),
    )
    invested_capital = first_number(
        computed.get("investedCapital") if computed else None,
        invested_capital_proxy(balance, quality_flags),
    )
    earnings_yield = ratio(ebit, enterprise_value, "earningsYield", quality_flags)
    return_on_capital = ratio(ebit, invested_capital, "returnOnCapital", quality_flags)

    if ebit is None:
        add_flag(quality_flags, "missing_input:ebit")

    return {
        "inputs": {
            "ticker": ticker,
            "ebit": ebit,
            "enterpriseValue": enterprise_value,
            "marketCap": market_cap,
            "totalDebt": number(balance.get("totalDebt")) if balance else None,
            "cashAndEquivalents": (
                number(balance.get("cashAndEquivalents")) if balance else None
            ),
            "investedCapital": invested_capital,
            "tangibleCapital": invested_capital,
            "price": price,
            "volume": volume,
            "sector": profile.get("sector") if profile else None,
            "industry": profile.get("industry") if profile else None,
            "currency": row_currency(profile, income, balance, market_snapshot),
            "qualityFlags": sorted(set(quality_flags)),
        },
        "earningsYield": earnings_yield,
        "returnOnCapital": return_on_capital,
        "earningsYieldRank": None,
        "returnOnCapitalRank": None,
        "combinedRankScore": None,
        "qualityFlags": sorted(set(quality_flags)),
        "methodology": (
            "earningsYield = EBIT / enterpriseValue; "
            "returnOnCapital = EBIT / investedCapital proxy."
        ),
    }


def rank_inputs(
    inputs: list[dict],
    strategy: str,
    eligibility_settings: Optional[dict] = None,
    computed_at: Optional[str] = None,
) -> list[dict]:
    normalized_settings = normalize_eligibility_settings(eligibility_settings)
    timestamp = computed_at or utc_now()
    rows = [
        ranking_row(row, strategy, normalized_settings, timestamp)
        for row in inputs
    ]

    if strategy == "magic_formula":
        apply_magic_formula_ranks(rows)
    else:
        apply_component_rank(rows)

    for row in rows:
        refresh_row_audit(row, normalized_settings, timestamp)

    return sorted(
        rows,
        key=lambda row: (
            eligibility_sort_value(row.get("eligibilityStatus")),
            row.get("rank") or 10**9,
            row["ticker"],
        ),
    )


def ranking_row(
    row: dict,
    strategy: str,
    eligibility_settings: dict,
    computed_at: str,
) -> dict:
    if strategy == "magic_formula":
        magic = dict(row["magicFormula"])
        result = {
            "rank": None,
            "ticker": row["ticker"],
            "companyName": row.get("companyName"),
            "currency": row.get("currency"),
            "strategy": strategy,
            "score": None,
            "scoreComponents": {
                "earningsYield": magic.get("earningsYield"),
                "returnOnCapital": magic.get("returnOnCapital"),
            },
            "magicFormula": magic,
            "qualityFlags": list(row.get("qualityFlags") or []),
            "provider": row["provider"],
            "source": row["source"],
            "computedAt": computed_at,
            "rankingEngineVersion": RANKING_ENGINE_VERSION,
            "message": "Magic Formula row uses canonical EBIT, EV, and invested-capital inputs.",
        }
        apply_eligibility(result, strategy, eligibility_settings)
        refresh_row_audit(result, eligibility_settings, computed_at)

        return result

    score_components = strategy_score_components(row.get("screenerMetrics") or {}, strategy)
    quality_flags = list(row.get("qualityFlags") or [])

    for key, value in score_components.items():
        if value is None:
            add_flag(quality_flags, f"missing_ranking_component:{key}")

    score = average([value for value in score_components.values() if value is not None])

    result = {
        "rank": None,
        "ticker": row["ticker"],
        "companyName": row.get("companyName"),
        "currency": row.get("currency"),
        "strategy": strategy,
        "score": score,
        "scoreComponents": score_components,
        "magicFormula": row["magicFormula"],
        "qualityFlags": sorted(set(quality_flags)),
        "provider": row["provider"],
        "source": row["source"],
        "computedAt": computed_at,
        "rankingEngineVersion": RANKING_ENGINE_VERSION,
        "message": f"{strategy} ranking uses transparent screener metric components.",
    }
    apply_eligibility(result, strategy, eligibility_settings)
    refresh_row_audit(result, eligibility_settings, computed_at)

    return result


def apply_magic_formula_ranks(rows: list[dict]) -> None:
    eligible = [
        row
        for row in rows
        if row.get("eligibilityStatus") == "eligible"
    ]
    eligible = [
        row
        for row in eligible
        if row["magicFormula"].get("earningsYield") is not None
        and row["magicFormula"].get("returnOnCapital") is not None
    ]
    earnings_yield_order = sorted(
        eligible,
        key=lambda row: (-row["magicFormula"]["earningsYield"], row["ticker"]),
    )
    capital_order = sorted(
        eligible,
        key=lambda row: (-row["magicFormula"]["returnOnCapital"], row["ticker"]),
    )

    for index, row in enumerate(earnings_yield_order, start=1):
        row["magicFormula"]["earningsYieldRank"] = index

    for index, row in enumerate(capital_order, start=1):
        row["magicFormula"]["returnOnCapitalRank"] = index

    for row in eligible:
        magic = row["magicFormula"]
        combined = magic["earningsYieldRank"] + magic["returnOnCapitalRank"]
        magic["combinedRankScore"] = combined
        row["score"] = combined
        row["scoreComponents"] = {
            "earningsYieldRank": magic["earningsYieldRank"],
            "returnOnCapitalRank": magic["returnOnCapitalRank"],
            "earningsYield": magic["earningsYield"],
            "returnOnCapital": magic["returnOnCapital"],
        }

    ranked = sorted(
        eligible,
        key=lambda row: (
            row["magicFormula"]["combinedRankScore"],
            row["magicFormula"]["earningsYieldRank"],
            row["ticker"],
        ),
    )

    for index, row in enumerate(ranked, start=1):
        row["rank"] = index

    for row in rows:
        if row["rank"] is None:
            if row.get("eligibilityStatus") == "eligible":
                row["eligibilityStatus"] = "unranked_missing_data"
                add_eligibility_reason(row, "missing_rankable_magic_formula_inputs")
            add_flag(row["qualityFlags"], "excluded_from_ranking:missing_magic_formula_inputs")
            add_flag(row["magicFormula"]["qualityFlags"], "excluded_from_ranking:missing_magic_formula_inputs")


def apply_component_rank(rows: list[dict]) -> None:
    eligible = [
        row
        for row in rows
        if row.get("eligibilityStatus") == "eligible"
        and row.get("score") is not None
    ]
    ranked = sorted(eligible, key=lambda row: (-row["score"], row["ticker"]))

    for index, row in enumerate(ranked, start=1):
        row["rank"] = index

    for row in rows:
        if row["rank"] is None:
            if row.get("eligibilityStatus") == "eligible":
                row["eligibilityStatus"] = "unranked_missing_data"
                add_eligibility_reason(row, "missing_score_components")
            add_flag(row["qualityFlags"], "excluded_from_ranking:missing_score_components")


def strategy_score_components(metrics: dict, strategy: str) -> dict:
    if strategy == "quality":
        return {
            "returnOnInvestedCapital": number(metrics.get("returnOnInvestedCapital")),
            "returnOnEquity": number(metrics.get("returnOnEquity")),
            "freeCashFlowMargin": number(metrics.get("freeCashFlowMargin")),
        }

    if strategy == "value":
        return {
            "earningsYieldProxy": inverse_ratio(metrics.get("peRatio")),
            "bookYieldProxy": inverse_ratio(metrics.get("pbRatio")),
            "salesYieldProxy": inverse_ratio(metrics.get("psRatio")),
        }

    if strategy == "growth":
        return {
            "revenueGrowthYoY": number(metrics.get("revenueGrowthYoY")),
        }

    if strategy == "profitability":
        return {
            "grossMargin": number(metrics.get("grossMargin")),
            "operatingMargin": number(metrics.get("operatingMargin")),
            "netMargin": number(metrics.get("netMargin")),
            "freeCashFlowMargin": number(metrics.get("freeCashFlowMargin")),
        }

    return {}


def normalize_ranking_filters(filters: Optional[list[dict]]) -> list[dict]:
    if not isinstance(filters, list):
        return []

    normalized = []

    for item in filters:
        if not isinstance(item, dict):
            continue

        field = item.get("field")
        operator = item.get("operator")

        if field not in RANKING_FILTER_FIELDS:
            continue

        if operator not in RANKING_FILTER_OPERATORS:
            continue

        value = item.get("value")

        if operator == "between":
            if (
                not isinstance(value, list)
                or len(value) != 2
                or number(value[0]) is None
                or number(value[1]) is None
            ):
                continue

            normalized.append(
                {
                    "field": field,
                    "operator": operator,
                    "value": [number(value[0]), number(value[1])],
                }
            )
        elif number(value) is not None:
            normalized.append(
                {
                    "field": field,
                    "operator": operator,
                    "value": number(value),
                }
            )

    return normalized


def normalize_ranking_sort(sort: Optional[dict]) -> Optional[dict]:
    if not isinstance(sort, dict):
        return None

    field = sort.get("field")
    direction = sort.get("direction")

    if field not in RANKING_FILTER_FIELDS:
        return None

    return {
        "field": field,
        "direction": "asc" if str(direction).lower() == "asc" else "desc",
    }


def apply_ranking_filters(rows: list[dict], filters: list[dict]) -> list[dict]:
    if not filters:
        return rows

    return [
        row
        for row in rows
        if all(ranking_filter_matches(row, ranking_filter) for ranking_filter in filters)
    ]


def ranking_filter_matches(row: dict, ranking_filter: dict) -> bool:
    value = ranking_field_value(row, ranking_filter["field"])

    if value is None:
        return False

    operator = ranking_filter["operator"]
    expected = ranking_filter["value"]

    if operator == "gt":
        return value > expected

    if operator == "gte":
        return value >= expected

    if operator == "lt":
        return value < expected

    if operator == "lte":
        return value <= expected

    if operator == "eq":
        return value == expected

    if operator == "between":
        lower, upper = expected

        return lower <= value <= upper

    return False


def apply_ranking_sort(rows: list[dict], sort: Optional[dict]) -> list[dict]:
    if sort is None:
        return rows

    descending = sort["direction"] == "desc"

    return sorted(
        rows,
        key=lambda row: ranking_sort_key(row, sort["field"], descending),
    )


def ranking_sort_key(row: dict, field: str, descending: bool) -> tuple:
    value = ranking_field_value(row, field)

    if value is None:
        return (True, 0, row["ticker"])

    return (False, -value if descending else value, row["ticker"])


def ranking_field_value(row: dict, field: str) -> Optional[float]:
    magic = row.get("magicFormula") or {}
    inputs = magic.get("inputs") or {}

    if field == "rank":
        return number(row.get("rank"))

    if field == "score":
        return number(row.get("score"))

    if field == "earningsYield":
        return number(magic.get("earningsYield"))

    if field == "returnOnCapital":
        return number(magic.get("returnOnCapital"))

    if field == "enterpriseValue":
        return number(inputs.get("enterpriseValue"))

    if field == "investedCapital":
        return number(inputs.get("investedCapital"))

    if field == "ebit":
        return number(inputs.get("ebit"))

    if field == "marketCap":
        return number(inputs.get("marketCap"))

    if field == "price":
        return number(inputs.get("price"))

    return None


def apply_eligibility(row: dict, strategy: str, settings: dict) -> None:
    missing_reasons = []
    ineligible_reasons = []
    magic_inputs = row["magicFormula"].get("inputs") or {}
    score_components = row.get("scoreComponents") or {}
    market_cap = first_number(
        magic_inputs.get("marketCap"),
        score_components.get("marketCap"),
    )
    price = first_number(
        magic_inputs.get("price"),
        score_components.get("price"),
    )
    volume = number(magic_inputs.get("volume"))
    sector = text(magic_inputs.get("sector"))

    add_minimum_rule(
        "marketCap",
        market_cap,
        settings["minimumMarketCap"],
        missing_reasons,
        ineligible_reasons,
    )
    add_minimum_rule(
        "price",
        price,
        settings["minimumPrice"],
        missing_reasons,
        ineligible_reasons,
    )

    if settings["minimumVolume"] is not None:
        add_minimum_rule(
            "volume",
            volume,
            settings["minimumVolume"],
            missing_reasons,
            ineligible_reasons,
        )

    if settings["excludeFinancials"] and sector_is(sector, "financial"):
        ineligible_reasons.append("excluded_sector:financials")

    if settings["excludeUtilities"] and sector_is(sector, "utilit"):
        ineligible_reasons.append("excluded_sector:utilities")

    if strategy == "magic_formula":
        require_input("ebit", magic_inputs.get("ebit"), missing_reasons)
        require_input("enterpriseValue", magic_inputs.get("enterpriseValue"), missing_reasons)
        require_input("investedCapital", magic_inputs.get("investedCapital"), missing_reasons)
        require_input("earningsYield", row["magicFormula"].get("earningsYield"), missing_reasons)
        require_input(
            "returnOnCapital",
            row["magicFormula"].get("returnOnCapital"),
            missing_reasons,
        )

        if settings["requirePositiveEnterpriseValue"]:
            require_positive(
                "enterpriseValue",
                magic_inputs.get("enterpriseValue"),
                ineligible_reasons,
            )

        if settings["requirePositiveInvestedCapital"]:
            require_positive(
                "investedCapital",
                magic_inputs.get("investedCapital"),
                ineligible_reasons,
            )

        if settings["requirePositiveEbit"]:
            require_positive("ebit", magic_inputs.get("ebit"), ineligible_reasons)
    elif row.get("score") is None:
        missing_reasons.append("missing_score_components")

    if missing_reasons:
        row["eligibilityStatus"] = "unranked_missing_data"
    elif ineligible_reasons:
        row["eligibilityStatus"] = "ineligible"
    else:
        row["eligibilityStatus"] = "eligible"

    row["eligibilityReasons"] = sorted(set(missing_reasons + ineligible_reasons))

    for reason in row["eligibilityReasons"]:
        add_flag(row["qualityFlags"], f"eligibility:{reason}")


def add_minimum_rule(
    field: str,
    value: Optional[float],
    minimum: Optional[float],
    missing_reasons: list[str],
    ineligible_reasons: list[str],
) -> None:
    if minimum is None or minimum <= 0:
        return

    if value is None:
        missing_reasons.append(f"missing_input:{field}")
        return

    if value < minimum:
        ineligible_reasons.append(f"below_minimum:{field}")


def require_input(field: str, value, missing_reasons: list[str]) -> None:
    if number(value) is None:
        missing_reasons.append(f"missing_input:{field}")


def require_positive(field: str, value, ineligible_reasons: list[str]) -> None:
    numeric = number(value)

    if numeric is None:
        return

    if numeric <= 0:
        ineligible_reasons.append(f"non_positive:{field}")


def sector_is(sector: Optional[str], needle: str) -> bool:
    return isinstance(sector, str) and needle in sector.strip().lower()


def refresh_row_audit(row: dict, eligibility_settings: dict, computed_at: str) -> None:
    row["audit"] = {
        "eligibilityStatus": row.get("eligibilityStatus"),
        "eligibilityReasons": row.get("eligibilityReasons") or [],
        "eligibilitySettings": eligibility_settings,
        "inputValues": row.get("magicFormula", {}).get("inputs") or {},
        "formulaComponents": row.get("scoreComponents") or {},
        "snapshotMetadata": (row.get("source") or {}).get("snapshot"),
        "computedAt": computed_at,
        "rankingEngineVersion": RANKING_ENGINE_VERSION,
    }


def add_eligibility_reason(row: dict, reason: str) -> None:
    reasons = row.setdefault("eligibilityReasons", [])

    if reason not in reasons:
        reasons.append(reason)

    add_flag(row["qualityFlags"], f"eligibility:{reason}")


def ranking_diagnostics_summary(rows: list[dict]) -> dict:
    eligible = sum(
        1
        for row in rows
        if row.get("eligibilityStatus") == "eligible"
    )
    ineligible = sum(
        1
        for row in rows
        if row.get("eligibilityStatus") == "ineligible"
    )
    missing = sum(
        1
        for row in rows
        if row.get("eligibilityStatus") == "unranked_missing_data"
    )

    return {
        "eligibleRows": eligible,
        "ineligibleRows": ineligible,
        "unrankedMissingDataRows": missing,
        "excludedRows": ineligible + missing,
    }


def ranking_changes(run: dict, previous: Optional[dict]) -> list[dict]:
    current_rows = {
        row["ticker"]: row
        for row in run.get("rows") or []
        if isinstance(row, dict) and row.get("ticker")
    }
    previous_rows = {
        row["ticker"]: row
        for row in (previous or {}).get("rows") or []
        if isinstance(row, dict) and row.get("ticker")
    }
    tickers = sorted(set(current_rows) | set(previous_rows))
    changes = []

    for ticker in tickers:
        current = current_rows.get(ticker)
        prior = previous_rows.get(ticker)
        current_rank = current.get("rank") if current else None
        prior_rank = prior.get("rank") if prior else None
        current_score = current.get("score") if current else None
        prior_score = prior.get("score") if prior else None
        current_status = current.get("eligibilityStatus") if current else None
        prior_status = prior.get("eligibilityStatus") if prior else None

        if current is not None and prior is None:
            change_type = "new_entrant"
        elif current is None and prior is not None:
            change_type = "dropped"
        elif current_status != prior_status:
            change_type = "eligibility_changed"
        else:
            change_type = "unchanged"

        changes.append(
            {
                "ticker": ticker,
                "currentRank": current_rank,
                "previousRank": prior_rank,
                "rankChange": rank_delta(current_rank, prior_rank),
                "currentScore": current_score,
                "previousScore": prior_score,
                "scoreChange": score_delta(current_score, prior_score),
                "currentEligibilityStatus": current_status,
                "previousEligibilityStatus": prior_status,
                "eligibilityChange": eligibility_change(current_status, prior_status),
                "changeType": change_type,
            }
        )

    return changes


def ranking_change_summary(changes: list[dict]) -> dict:
    return {
        "newEntrants": sum(1 for change in changes if change["changeType"] == "new_entrant"),
        "dropped": sum(1 for change in changes if change["changeType"] == "dropped"),
        "changedEligibility": sum(
            1
            for change in changes
            if change["changeType"] == "eligibility_changed"
        ),
        "unchanged": sum(1 for change in changes if change["changeType"] == "unchanged"),
    }


def ranking_run_summary(payload: Optional[dict]) -> Optional[dict]:
    if payload is None:
        return None

    return {
        "runId": payload.get("runId"),
        "strategy": payload.get("strategy"),
        "period": payload.get("period"),
        "schemaVersion": payload.get("schemaVersion"),
        "rankingEngineVersion": payload.get("rankingEngineVersion"),
        "computedAt": payload.get("computedAt"),
        "universe": payload.get("universe"),
        "eligibilitySettings": payload.get("eligibilitySettings"),
        "summary": payload.get("summary") or {},
    }


def rank_delta(current_rank, previous_rank) -> Optional[int]:
    if current_rank is None or previous_rank is None:
        return None

    return int(previous_rank) - int(current_rank)


def score_delta(current_score, previous_score) -> Optional[float]:
    current = number(current_score)
    previous = number(previous_score)

    if current is None or previous is None:
        return None

    return current - previous


def eligibility_change(current_status, previous_status) -> str:
    if previous_status is None and current_status is not None:
        return "new_entrant"

    if current_status is None and previous_status is not None:
        return "dropped"

    if current_status == previous_status:
        return "unchanged"

    return f"{previous_status}->{current_status}"


def profile_from_snapshot(repository: SnapshotRepository, ticker: str) -> Optional[dict]:
    snapshot = repository.get_fundamentals_snapshot(ticker, "profile", "profile")

    if snapshot is None:
        return None

    return response_profile(snapshot.get("data") or {})


def statement_from_snapshot(
    repository: SnapshotRepository,
    ticker: str,
    period: str,
    snapshot_type: str,
    data_key: str,
) -> Optional[dict]:
    snapshot = repository.get_fundamentals_snapshot(ticker, period, snapshot_type)

    if snapshot is None:
        return None

    return response_first_row(snapshot.get("data") or {}, data_key)


def computed_from_snapshot(
    repository: SnapshotRepository,
    ticker: str,
    period: str,
) -> Optional[dict]:
    snapshot = repository.get_computed_metrics_snapshot(ticker, period)

    if snapshot is None:
        return None

    return response_first_row(snapshot.get("data") or {}, "computedMetrics")


def market_snapshot_if_available(
    market_data_provider: MarketDataProvider,
    ticker: str,
) -> Optional[dict]:
    if market_data_provider.provider_status().get("state") == "not_connected":
        return None

    try:
        snapshot = market_data_provider.get_market_snapshot(ticker)
    except Exception:
        return None

    provider = snapshot.get("provider") if isinstance(snapshot, dict) else None

    if isinstance(provider, dict) and provider.get("state") == "connected":
        return snapshot

    return None


def enterprise_value_proxy(
    market_cap: Optional[float],
    balance: Optional[dict],
    quality_flags: list[str],
) -> Optional[float]:
    if market_cap is None:
        add_flag(quality_flags, "missing_input:marketCap")
        return None

    if balance is None:
        add_flag(quality_flags, "missing_statement:balance_sheet")
        return None

    total_debt = number(balance.get("totalDebt"))
    cash = number(balance.get("cashAndEquivalents"))

    if total_debt is None:
        add_flag(quality_flags, "missing_input:totalDebt")
        return None

    if cash is None:
        add_flag(quality_flags, "missing_input:cashAndEquivalents")
        return None

    return market_cap + total_debt - cash


def invested_capital_proxy(
    balance: Optional[dict],
    quality_flags: list[str],
) -> Optional[float]:
    if balance is None:
        add_flag(quality_flags, "missing_statement:balance_sheet")
        return None

    total_debt = number(balance.get("totalDebt"))
    equity = number(balance.get("shareholdersEquity"))
    cash = number(balance.get("cashAndEquivalents"))

    if total_debt is None or equity is None or cash is None:
        add_flag(quality_flags, "missing_input:investedCapital")
        return None

    invested_capital = total_debt + equity - cash

    if invested_capital <= 0:
        add_flag(quality_flags, "invalid_input:investedCapital")
        return None

    return invested_capital


def response_profile(response: dict) -> Optional[dict]:
    profile = response.get("profile")

    return profile if isinstance(profile, dict) else None


def response_first_row(response: dict, key: str) -> Optional[dict]:
    rows = response.get(key)

    if not isinstance(rows, list) or not rows:
        return None

    row = rows[0]

    return row if isinstance(row, dict) else None


def empty_screener_row(ticker: str, period: str) -> dict:
    return {
        "ticker": ticker,
        "companyName": None,
        "currency": None,
        "period": period,
        "metrics": {},
        "qualityFlags": ["missing_screener_snapshot"],
        "provider": provider_not_connected("fmp", ["FMP_API_KEY"]),
        "source": {
            "sourceSymbol": ticker,
            "snapshotState": "missing",
        },
    }


def ranking_universe(
    repository: SnapshotRepository,
    universe: Optional[list[str]],
) -> list[str]:
    configured = normalize_universe(universe or PHASE_2D_TICKERS)
    persisted = repository.list_universe(PHASE_2D_UNIVERSE_NAME)

    return persisted or configured


def normalize_strategy(strategy: str) -> str:
    normalized = strategy.strip().lower()

    if normalized in RANKING_STRATEGIES:
        return normalized

    return "magic_formula"


def normalize_period(period: str) -> str:
    normalized = period.strip().lower()

    if normalized in {"annual", "quarter"}:
        return normalized

    return "annual"


def normalize_universe(tickers: list[str]) -> list[str]:
    normalized = []

    for ticker in tickers:
        normalized_ticker = ticker.strip().upper()

        if normalized_ticker and normalized_ticker not in normalized:
            normalized.append(normalized_ticker)

    return normalized


def normalize_eligibility_settings(settings: Optional[dict]) -> dict:
    normalized = dict(DEFAULT_ELIGIBILITY_SETTINGS)

    if not isinstance(settings, dict):
        return normalized

    for key in normalized:
        if key not in settings:
            continue

        value = settings[key]

        if key in {
            "excludeFinancials",
            "excludeUtilities",
            "requirePositiveEnterpriseValue",
            "requirePositiveInvestedCapital",
            "requirePositiveEbit",
        }:
            normalized[key] = bool(value)
        else:
            normalized[key] = number(value)

    return normalized


def normalize_limit(value) -> int:
    numeric = number(value)

    if numeric is None:
        return 50

    return max(min(int(numeric), 100), 1)


def eligibility_sort_value(status: Optional[str]) -> int:
    if status == "eligible":
        return 0

    if status == "ineligible":
        return 1

    return 2


def readiness_state(provider_state: str) -> str:
    if provider_state == "connected":
        return "ready"

    if provider_state == "degraded":
        return "degraded"

    return "blocked"


def readiness_message(provider_state: str) -> str:
    if provider_state == "connected":
        return "Ranking engine can use persisted snapshots or connected providers."

    if provider_state == "degraded":
        return "Ranking engine is available, but one or more inputs are degraded."

    return "Ranking engine requires persisted snapshots or configured provider credentials."


def aggregate_provider_status(statuses: list[Optional[dict]], connected_message: str) -> dict:
    normalized_statuses = [status for status in statuses if isinstance(status, dict)]

    if not normalized_statuses:
        return provider_not_connected("ranking_data", ["FMP_API_KEY"])

    states = {status.get("state") for status in normalized_statuses}
    last_success = max(
        [
            status.get("lastSuccessfulCallAt")
            for status in normalized_statuses
            if status.get("lastSuccessfulCallAt")
        ],
        default=None,
    )

    if states == {"connected"}:
        return provider_connected("ranking_data", connected_message, last_success)

    if "connected" in states or "degraded" in states:
        return provider_degraded(
            "ranking_data",
            "Ranking inputs are partial, degraded, or mixed between snapshots and providers.",
            required_environment_variables(normalized_statuses),
            last_success,
            "One or more ranking inputs were partial or unavailable.",
        )

    return provider_not_connected(
        "ranking_data",
        required_environment_variables(normalized_statuses) or ["FMP_API_KEY"],
    )


def required_environment_variables(statuses: list[dict]) -> list[str]:
    variables = []

    for status in statuses:
        for variable in status.get("requiredEnvironmentVariables") or []:
            if variable not in variables:
                variables.append(variable)

    return variables


def ratio(
    numerator: Optional[float],
    denominator: Optional[float],
    metric_name: str,
    quality_flags: list[str],
) -> Optional[float]:
    if numerator is None or denominator is None:
        add_flag(quality_flags, f"missing_input:{metric_name}")
        return None

    if denominator == 0:
        add_flag(quality_flags, f"zero_denominator:{metric_name}")
        return None

    if denominator < 0:
        add_flag(quality_flags, f"negative_denominator:{metric_name}")

    return numerator / denominator


def inverse_ratio(value) -> Optional[float]:
    numeric = number(value)

    if numeric is None or numeric == 0:
        return None

    return 1 / numeric


def average(values: list[float]) -> Optional[float]:
    if not values:
        return None

    return sum(values) / len(values)


def row_currency(*rows) -> Optional[str]:
    for row in rows:
        if isinstance(row, dict) and row.get("currency"):
            return row["currency"]

    return None


def first_number(*values) -> Optional[float]:
    for value in values:
        numeric = number(value)

        if numeric is not None:
            return numeric

    return None


def number(value) -> Optional[float]:
    if isinstance(value, bool):
        return None

    if isinstance(value, (int, float)):
        return float(value)

    return None


def text(value) -> Optional[str]:
    if value is None:
        return None

    if isinstance(value, str):
        return value

    return str(value)


def add_flag(flags: list[str], flag: str) -> None:
    if flag not in flags:
        flags.append(flag)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def ranking_run_id(strategy: str, period: str) -> str:
    return f"ranking-{strategy}-{period}-{uuid4().hex[:12]}"


def ranking_screen_id() -> str:
    return f"screen-{uuid4().hex[:12]}"


def refresh_run_id() -> str:
    return f"refresh-{uuid4().hex[:12]}"


def ranking_screen_name(value) -> str:
    name = text(value)

    if name is None or not name.strip():
        return "Untitled ranking screen"

    return name.strip()[:120]


def screen_summary(screen: Optional[dict]) -> Optional[dict]:
    if not isinstance(screen, dict):
        return None

    return {
        "screenId": screen.get("screenId"),
        "name": screen.get("name"),
        "status": screen.get("status"),
        "strategy": screen.get("strategy"),
        "period": screen.get("period"),
        "limit": screen.get("limit"),
    }


def refresh_scope(
    scope_type: str,
    tickers: Optional[list[str]],
    stale_only: bool,
    screen_id: Optional[str] = None,
) -> dict:
    normalized_scope = scope_type.strip().lower() if isinstance(scope_type, str) else "universe"

    if normalized_scope not in {"universe", "tickers", "stale_only", "scheduled"}:
        normalized_scope = "universe"

    normalized_tickers = normalize_universe(tickers or [])

    if normalized_scope == "tickers" and not normalized_tickers:
        normalized_scope = "universe"

    return {
        "type": normalized_scope,
        "tickers": normalized_tickers,
        "staleOnly": bool(stale_only or normalized_scope == "stale_only"),
        "screenId": screen_id,
        "refreshScopeVersion": "ranking-refresh-scope-v1",
    }


def refresh_scope_warnings(scope: dict) -> list[dict]:
    warnings = []

    if scope.get("type") == "scheduled":
        warnings.append(
            {
                "code": "scheduled_refresh_not_implemented",
                "message": "Scheduled refresh metadata is stored, but no scheduler runs yet.",
            }
        )

    if scope.get("staleOnly"):
        warnings.append(
            {
                "code": "stale_only_refresh_scope",
                "message": "Stale-only refresh is filtered by the local job runner before synchronous execution.",
            }
        )

    if scope.get("type") == "tickers":
        warnings.append(
            {
                "code": "partial_refresh_groundwork",
                "message": "Per-ticker scope is supported for ranking recomputation; provider snapshot refresh remains a future ingestion concern.",
            }
        )

    return warnings


def duration_ms(started_at: str, finished_at: str) -> Optional[int]:
    try:
        started = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        finished = datetime.fromisoformat(finished_at.replace("Z", "+00:00"))

        return max(int((finished - started).total_seconds() * 1000), 0)
    except ValueError:
        return None


def sanitize_error_message(message: str) -> str:
    sanitized = message.replace("\n", " ").strip()

    return sanitized[:500] or "Unknown ranking refresh error."
