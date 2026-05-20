from datetime import datetime, timezone
from math import ceil
from typing import Optional

from app.services.fundamentals.computed_metrics import build_computed_metrics_response
from app.services.fundamentals.provider import FundamentalsProvider
from app.services.persistence.repository import SnapshotRepository
from app.services.persistence.sqlite_repository import SCHEMA_VERSION
from app.services.provider_status import (
    provider_connected,
    provider_degraded,
    provider_not_connected,
    provider_not_implemented,
)
from app.services.screener.universe import (
    PHASE_2D_TICKERS,
    PHASE_2D_UNIVERSE_NAME,
)

SCREENER_FIELDS = {
    "marketCap",
    "revenue",
    "revenueGrowthYoY",
    "grossMargin",
    "operatingMargin",
    "netMargin",
    "freeCashFlowMargin",
    "returnOnEquity",
    "returnOnInvestedCapital",
    "debtToEquity",
    "currentRatio",
    "freeCashFlowPerShare",
    "bookValuePerShare",
    "price",
    "peRatio",
    "pbRatio",
    "psRatio",
}

FILTER_OPERATORS = {"gt", "gte", "lt", "lte", "eq", "between"}
PROVIDER_RATIO_FIELDS = {
    "peRatio": "priceToEarnings",
    "pbRatio": "priceToBook",
    "psRatio": "priceToSales",
}
FMP_PROVIDER_VERSION = "fmp-stable-v1"
PLATFORM_METRICS_VERSION = "platform-normalized-metrics-v1"
PLATFORM_SCREENER_VERSION = "platform-screener-row-v1"


def build_screener_response(
    provider: FundamentalsProvider,
    period: str,
    page: int,
    limit: int,
    filters: list[dict],
    sort: Optional[dict],
    universe: Optional[list[str]] = None,
    repository: Optional[SnapshotRepository] = None,
    stale_after_seconds: int = 86400,
) -> dict:
    normalized_period = normalize_period(period)
    normalized_page = max(page, 1)
    normalized_limit = max(min(limit, 100), 1)
    normalized_filters = normalize_filters(filters)
    normalized_sort = normalize_sort(sort)
    configured_tickers = normalize_universe(universe or PHASE_2D_TICKERS)
    persisted_tickers = (
        repository.list_universe(PHASE_2D_UNIVERSE_NAME)
        if repository is not None
        else []
    )
    tickers = persisted_tickers or configured_tickers
    provider_status = provider.provider_status()
    rows = []
    missing_tickers = tickers

    if repository is not None:
        snapshots = repository.get_screener_row_snapshots(tickers, normalized_period)
        rows = [
            row_from_screener_snapshot(
                snapshots[ticker],
                stale_after_seconds,
            )
            for ticker in tickers
            if ticker in snapshots
        ]
        missing_tickers = [ticker for ticker in tickers if ticker not in snapshots]

    if missing_tickers and provider_status.get("state") != "not_connected":
        rows.extend(
            row_with_provider_fallback_snapshot(
                build_screener_row(provider, ticker, normalized_period),
            )
            for ticker in missing_tickers
        )

    if not rows and provider_status.get("state") == "not_connected":
        return {
            "query": {
                "filters": normalized_filters,
                "sort": normalized_sort,
                "period": normalized_period,
                "page": normalized_page,
                "limit": normalized_limit,
            },
            "rows": [],
            "provider": provider_status,
            "pagination": pagination(0, normalized_page, normalized_limit),
            "universe": universe_payload(tickers),
            "message": (
                "Screener rows require persisted snapshots or connected "
                "normalized fundamentals. Run the refresh endpoint with FMP "
                "credentials to populate the local snapshot store."
            ),
        }

    filtered_rows = apply_filters(rows, normalized_filters)
    sorted_rows = apply_sort(filtered_rows, normalized_sort)
    total = len(sorted_rows)
    start_index = (normalized_page - 1) * normalized_limit
    page_rows = sorted_rows[start_index : start_index + normalized_limit]

    return {
        "query": {
            "filters": normalized_filters,
            "sort": normalized_sort,
            "period": normalized_period,
            "page": normalized_page,
            "limit": normalized_limit,
        },
        "rows": page_rows,
        "provider": aggregate_provider_status(
            [row["provider"] for row in rows],
            "Screener rows were generated from canonical normalized fundamentals.",
        ),
        "pagination": pagination(total, normalized_page, normalized_limit),
        "universe": universe_payload(tickers),
        "message": (
            "Phase 2E screener rows are read from durable snapshots first, "
            "with provider fallback only for missing rows."
        ),
    }


def build_screener_row(
    provider: FundamentalsProvider,
    ticker: str,
    period: str,
) -> dict:
    return collect_screener_materials(provider, ticker, period)["row"]


def collect_screener_materials(
    provider: FundamentalsProvider,
    ticker: str,
    period: str,
) -> dict:
    normalized_ticker = ticker.strip().upper()
    normalized_period = normalize_period(period)
    profile_response = provider.get_company_profile(normalized_ticker)
    income_response = provider.get_income_statement(normalized_ticker, normalized_period, 5)
    balance_response = provider.get_balance_sheet(normalized_ticker, normalized_period, 5)
    cash_flow_response = provider.get_cash_flow_statement(
        normalized_ticker,
        normalized_period,
        5,
    )
    computed_response = build_computed_metrics_response(
        provider,
        normalized_ticker,
        normalized_period,
        5,
    )
    key_metrics_response = provider.get_key_metrics(
        normalized_ticker,
        normalized_period,
        1,
    )
    row = build_screener_row_from_responses(
        normalized_ticker,
        normalized_period,
        profile_response,
        income_response,
        balance_response,
        cash_flow_response,
        computed_response,
        key_metrics_response,
    )

    return {
        "ticker": normalized_ticker,
        "period": normalized_period,
        "profileResponse": profile_response,
        "incomeResponse": income_response,
        "balanceResponse": balance_response,
        "cashFlowResponse": cash_flow_response,
        "computedResponse": computed_response,
        "keyMetricsResponse": key_metrics_response,
        "row": row,
    }


def build_screener_row_from_responses(
    ticker: str,
    period: str,
    profile_response: dict,
    income_response: dict,
    balance_response: dict,
    cash_flow_response: dict,
    computed_response: dict,
    key_metrics_response: dict,
) -> dict:
    metrics = empty_metrics()
    quality_flags = []

    profile = mapping_or_none(profile_response.get("profile"))
    income_rows = rows_from_response(income_response, "incomeStatements")
    balance_rows = rows_from_response(balance_response, "balanceSheets")
    cash_flow_rows = rows_from_response(cash_flow_response, "cashFlowStatements")
    computed_rows = rows_from_response(computed_response, "computedMetrics")
    key_metric_rows = rows_from_response(key_metrics_response, "metrics")

    latest_income = first_row(income_rows)
    latest_balance = first_row(balance_rows)
    latest_cash_flow = first_row(cash_flow_rows)
    latest_computed = first_row(computed_rows)
    latest_key_metrics = first_row(key_metric_rows)

    if profile:
        metrics["marketCap"] = number(profile.get("marketCap"))
        metrics["price"] = number(profile.get("price"))
        add_source_flags(quality_flags, profile, "profile")

    if latest_income:
        metrics["revenue"] = number(latest_income.get("revenue"))
        add_source_flags(quality_flags, latest_income, "income_statement")

    if latest_computed:
        for field in [
            "revenueGrowthYoY",
            "grossMargin",
            "operatingMargin",
            "netMargin",
            "freeCashFlowMargin",
            "returnOnEquity",
            "returnOnInvestedCapital",
            "debtToEquity",
            "currentRatio",
            "freeCashFlowPerShare",
            "bookValuePerShare",
        ]:
            metrics[field] = number(latest_computed.get(field))

        add_flags(quality_flags, latest_computed.get("qualityFlags") or [])

    if latest_key_metrics:
        for screener_field, key_metric_field in PROVIDER_RATIO_FIELDS.items():
            metrics[screener_field] = number(latest_key_metrics.get(key_metric_field))

            if metrics[screener_field] is not None:
                add_flag(quality_flags, f"provider_reference_metric:{screener_field}")

        add_source_flags(quality_flags, latest_key_metrics, "key_metrics")

    for field in sorted(SCREENER_FIELDS):
        if metrics[field] is None:
            add_flag(quality_flags, f"missing_metric:{field}")

    row_provider = aggregate_provider_status(
        [
            status_from_response(profile_response),
            status_from_response(income_response),
            status_from_response(balance_response),
            status_from_response(cash_flow_response),
            status_from_response(computed_response),
            status_from_response(key_metrics_response),
        ],
        "Screener row was generated from normalized fundamentals.",
    )
    source = source_metadata(
        ticker,
        profile,
        latest_income,
        latest_balance,
        latest_cash_flow,
        latest_computed,
        latest_key_metrics,
    )

    return {
        "ticker": ticker,
        "companyName": text(profile.get("name")) if profile else None,
        "currency": source["currency"],
        "period": period,
        "metrics": metrics,
        "qualityFlags": sorted(set(quality_flags)),
        "provider": row_provider,
        "source": source,
        "message": (
            "Screener row uses platform-computed metrics. Price ratios are "
            "provider reference metrics until Phase 2B metric coverage expands."
        ),
    }


def refresh_screener_snapshots(
    provider: FundamentalsProvider,
    repository: SnapshotRepository,
    period: str,
    universe: Optional[list[str]] = None,
) -> dict:
    normalized_period = normalize_period(period)
    tickers = normalize_universe(universe or PHASE_2D_TICKERS)
    started_at = utc_now()
    refreshed_count = 0
    failures = []

    repository.upsert_universe(
        PHASE_2D_UNIVERSE_NAME,
        tickers,
        "phase-2d-controlled-universe",
    )

    for ticker in tickers:
        try:
            materials = collect_screener_materials(provider, ticker, normalized_period)
            persisted = persist_screener_materials(
                repository,
                materials,
                refreshed_at=utc_now(),
            )

            if persisted.get("screenerRow"):
                refreshed_count += 1
            else:
                failures.append(
                    {
                        "ticker": ticker,
                        "message": "No durable screener row was produced.",
                    }
                )
        except Exception as error:  # defensive refresh boundary
            failures.append(
                {
                    "ticker": ticker,
                    "message": sanitize_error_message(str(error), provider),
                }
            )

    completed_at = utc_now()
    failed_count = len(failures)

    if refreshed_count and failed_count:
        status = "partial"
    elif refreshed_count:
        status = "completed"
    else:
        status = "failed"

    repository.record_refresh_run(
        normalized_period,
        status,
        started_at,
        completed_at,
        len(tickers),
        refreshed_count,
        failed_count,
        "; ".join(failure["message"] for failure in failures[:3]) or None,
    )

    return {
        "period": normalized_period,
        "universe": universe_payload(tickers),
        "status": status,
        "refreshedCount": refreshed_count,
        "failedCount": failed_count,
        "failures": failures,
        "provider": provider.provider_status(),
        "repository": repository.repository_status(),
        "startedAt": started_at,
        "completedAt": completed_at,
        "message": (
            "Synchronous snapshot refresh completed. This is a temporary "
            "manual workflow before queued ingestion jobs are introduced."
        ),
    }


def persist_screener_materials(
    repository: SnapshotRepository,
    materials: dict,
    refreshed_at: str,
) -> dict:
    ticker = materials["ticker"]
    period = materials["period"]
    computed_from = computed_from_materials(materials)
    computed_at = utc_now()
    persisted = {
        "profile": False,
        "incomeStatement": False,
        "balanceSheet": False,
        "cashFlow": False,
        "keyMetrics": False,
        "computedMetrics": False,
        "screenerRow": False,
    }

    fundamentals = [
        (
            "profile",
            "profile",
            "profile",
            materials["profileResponse"],
            "profile",
        ),
        (
            period,
            "income_statement",
            "incomeStatements",
            materials["incomeResponse"],
            "incomeStatement",
        ),
        (
            period,
            "balance_sheet",
            "balanceSheets",
            materials["balanceResponse"],
            "balanceSheet",
        ),
        (
            period,
            "cash_flow",
            "cashFlowStatements",
            materials["cashFlowResponse"],
            "cashFlow",
        ),
        (
            period,
            "key_metrics",
            "metrics",
            materials["keyMetricsResponse"],
            "keyMetrics",
        ),
    ]

    for snapshot_period, snapshot_type, data_key, response, persisted_key in fundamentals:
        source_row = response_source_row(response, data_key)

        if source_row is None:
            continue

        repository.upsert_fundamentals_snapshot(
            ticker,
            snapshot_period,
            snapshot_type,
            snapshot_payload(
                response,
                source_row,
                provider_version=FMP_PROVIDER_VERSION,
                refreshed_at=refreshed_at,
            ),
        )
        persisted[persisted_key] = True

    computed_row = response_source_row(
        materials["computedResponse"],
        "computedMetrics",
    )

    if computed_row is not None:
        repository.upsert_computed_metrics_snapshot(
            ticker,
            period,
            snapshot_payload(
                materials["computedResponse"],
                computed_row,
                provider="platform",
                provider_version=PLATFORM_METRICS_VERSION,
                refreshed_at=refreshed_at,
                computed_from=computed_from,
                computed_at=computed_at,
            ),
        )
        persisted["computedMetrics"] = True

    row = materials["row"]

    if row_has_metrics(row):
        row_payload = {
            "schemaVersion": SCHEMA_VERSION,
            "provenance": {
                "provider": "platform",
                "providerVersion": PLATFORM_SCREENER_VERSION,
                "fetchedAt": row.get("source", {}).get("fetchedAt") or refreshed_at,
                "sourceSymbol": row.get("source", {}).get("sourceSymbol") or ticker,
            },
            "computedFrom": computed_from,
            "computedAt": computed_at,
            "refreshedAt": refreshed_at,
            "row": row,
        }
        repository.upsert_screener_row_snapshot(ticker, period, row_payload)
        persisted["screenerRow"] = True

    return persisted


def snapshot_payload(
    response: dict,
    source_row: dict,
    provider_version: str,
    refreshed_at: str,
    provider: Optional[str] = None,
    computed_from: Optional[dict] = None,
    computed_at: Optional[str] = None,
) -> dict:
    provider_name = (
        provider
        or text(source_row.get("provider"))
        or text(response.get("provider", {}).get("provider"))
        or "unknown"
    )
    payload = {
        "schemaVersion": SCHEMA_VERSION,
        "provenance": {
            "provider": provider_name,
            "providerVersion": provider_version,
            "fetchedAt": text(source_row.get("fetchedAt")) or refreshed_at,
            "sourceSymbol": text(source_row.get("sourceSymbol"))
            or text(response.get("ticker"))
            or "UNKNOWN",
        },
        "refreshedAt": refreshed_at,
        "data": response,
    }

    if computed_from is not None:
        payload["computedFrom"] = computed_from

    if computed_at is not None:
        payload["computedAt"] = computed_at

    return payload


def computed_from_materials(materials: dict) -> dict:
    income = response_source_row(materials["incomeResponse"], "incomeStatements")
    balance = response_source_row(materials["balanceResponse"], "balanceSheets")
    cash_flow = response_source_row(
        materials["cashFlowResponse"],
        "cashFlowStatements",
    )
    key_metrics = response_source_row(materials["keyMetricsResponse"], "metrics")

    return {
        "statementPeriod": materials["period"],
        "incomeStatementFiscalYear": source_value(income, "fiscalYear"),
        "incomeStatementFiscalPeriod": source_value(income, "fiscalPeriod"),
        "balanceSheetFiscalYear": source_value(balance, "fiscalYear"),
        "balanceSheetFiscalPeriod": source_value(balance, "fiscalPeriod"),
        "cashFlowFiscalYear": source_value(cash_flow, "fiscalYear"),
        "cashFlowFiscalPeriod": source_value(cash_flow, "fiscalPeriod"),
        "keyMetricsFiscalYear": source_value(key_metrics, "fiscalYear"),
        "keyMetricsFiscalPeriod": source_value(key_metrics, "fiscalPeriod"),
    }


def row_from_screener_snapshot(snapshot: dict, stale_after_seconds: int) -> dict:
    row = dict(snapshot.get("row") or {})
    row["snapshot"] = snapshot_metadata(snapshot, "persisted", stale_after_seconds)

    return row


def row_with_provider_fallback_snapshot(row: dict) -> dict:
    source = row.get("source") or {}
    fallback_row = dict(row)
    fallback_row["snapshot"] = {
        "state": "provider_fallback",
        "schemaVersion": SCHEMA_VERSION,
        "refreshedAt": None,
        "isStale": False,
        "ageSeconds": None,
        "provenance": {
            "provider": source.get("provider") or "platform",
            "providerVersion": PLATFORM_SCREENER_VERSION,
            "fetchedAt": source.get("fetchedAt") or utc_now(),
            "sourceSymbol": source.get("sourceSymbol") or row.get("ticker"),
        },
        "computedFrom": None,
        "computedAt": None,
    }

    return fallback_row


def snapshot_metadata(
    snapshot: dict,
    state: str,
    stale_after_seconds: int,
) -> dict:
    age_seconds = snapshot_age_seconds(snapshot)

    return {
        "state": state,
        "schemaVersion": snapshot.get("schemaVersion", SCHEMA_VERSION),
        "refreshedAt": snapshot.get("refreshedAt"),
        "isStale": age_seconds is None or age_seconds > stale_after_seconds,
        "ageSeconds": age_seconds,
        "provenance": snapshot.get("provenance"),
        "computedFrom": snapshot.get("computedFrom"),
        "computedAt": snapshot.get("computedAt"),
    }


def response_source_row(response: dict, data_key: str) -> Optional[dict]:
    if data_key == "profile":
        return mapping_or_none(response.get("profile"))

    rows = rows_from_response(response, data_key)

    return first_row(rows)


def row_has_metrics(row: dict) -> bool:
    metrics = row.get("metrics")

    if not isinstance(metrics, dict):
        return False

    return any(value is not None for value in metrics.values())


def apply_filters(rows: list[dict], filters: list[dict]) -> list[dict]:
    if not filters:
        return rows

    return [
        row
        for row in rows
        if all(row_matches_filter(row, screener_filter) for screener_filter in filters)
    ]


def row_matches_filter(row: dict, screener_filter: dict) -> bool:
    field = screener_filter["field"]
    operator = screener_filter["operator"]
    value = row.get("metrics", {}).get(field)
    expected = screener_filter["value"]

    if value is None:
        return False

    if operator == "between":
        if not isinstance(expected, list) or len(expected) != 2:
            return False

        lower = number(expected[0])
        upper = number(expected[1])

        if lower is None or upper is None:
            return False

        return lower <= value <= upper

    expected_number = number(expected)

    if expected_number is None:
        return False

    if operator == "gt":
        return value > expected_number

    if operator == "gte":
        return value >= expected_number

    if operator == "lt":
        return value < expected_number

    if operator == "lte":
        return value <= expected_number

    if operator == "eq":
        return value == expected_number

    return False


def apply_sort(rows: list[dict], sort: Optional[dict]) -> list[dict]:
    if sort is None:
        return rows

    field = sort["field"]
    reverse = sort["direction"] == "desc"

    rows_with_values = [
        row for row in rows if row.get("metrics", {}).get(field) is not None
    ]
    rows_without_values = [
        row for row in rows if row.get("metrics", {}).get(field) is None
    ]
    sorted_rows = sorted(
        rows_with_values,
        key=lambda row: row["metrics"][field],
        reverse=reverse,
    )

    return sorted_rows + rows_without_values


def normalize_filters(filters: list[dict]) -> list[dict]:
    normalized_filters = []

    for screener_filter in filters:
        if not isinstance(screener_filter, dict):
            continue

        field = screener_filter.get("field")
        operator = screener_filter.get("operator")
        value = screener_filter.get("value")

        if field not in SCREENER_FIELDS or operator not in FILTER_OPERATORS:
            continue

        if operator == "between":
            if not isinstance(value, list) or len(value) != 2:
                continue

            lower = number(value[0])
            upper = number(value[1])

            if lower is None or upper is None:
                continue

            normalized_filters.append(
                {
                    "field": field,
                    "operator": operator,
                    "value": [min(lower, upper), max(lower, upper)],
                }
            )
            continue

        normalized_value = number(value)

        if normalized_value is None:
            continue

        normalized_filters.append(
            {
                "field": field,
                "operator": operator,
                "value": normalized_value,
            }
        )

    return normalized_filters


def normalize_sort(sort: Optional[dict]) -> Optional[dict]:
    if not isinstance(sort, dict):
        return None

    field = sort.get("field")
    direction = sort.get("direction")

    if field not in SCREENER_FIELDS:
        return None

    if direction not in {"asc", "desc"}:
        direction = "desc"

    return {
        "field": field,
        "direction": direction,
    }


def normalize_period(period: str) -> str:
    normalized = period.strip().lower()

    if normalized in {"annual", "quarter"}:
        return normalized

    return "annual"


def normalize_universe(tickers: list[str]) -> list[str]:
    normalized = []

    for ticker in tickers:
        clean_ticker = ticker.strip().upper()

        if clean_ticker and clean_ticker not in normalized:
            normalized.append(clean_ticker)

    return normalized


def empty_metrics() -> dict:
    return {field: None for field in sorted(SCREENER_FIELDS)}


def universe_payload(tickers: list[str]) -> dict:
    return {
        "name": PHASE_2D_UNIVERSE_NAME,
        "size": len(tickers),
        "tickers": tickers,
    }


def pagination(total: int, page: int, limit: int) -> dict:
    total_pages = ceil(total / limit) if total else 0

    return {
        "page": page,
        "limit": limit,
        "total": total,
        "totalPages": total_pages,
        "hasNextPage": total_pages > 0 and page < total_pages,
        "hasPreviousPage": page > 1 and total_pages > 0,
    }


def aggregate_provider_status(statuses: list[Optional[dict]], connected_message: str) -> dict:
    normalized_statuses = [status for status in statuses if isinstance(status, dict)]

    if not normalized_statuses:
        return provider_not_connected("fmp", ["FMP_API_KEY"])

    provider_name = provider_name_from_statuses(normalized_statuses)
    required_environment_variables = required_environment_variables_from_statuses(
        normalized_statuses
    )
    last_successful_call_at = last_successful_call_at_from_statuses(normalized_statuses)
    last_error_message = last_error_message_from_statuses(normalized_statuses)
    states = {status.get("state") for status in normalized_statuses}

    if states == {"connected"}:
        return provider_connected(
            provider_name,
            connected_message,
            last_successful_call_at,
        )

    if states == {"not_connected"}:
        return provider_not_connected(provider_name, required_environment_variables)

    if states == {"not_implemented"}:
        return provider_not_implemented(
            provider_name,
            "Screener dependency is contract-ready but not implemented.",
            required_environment_variables,
            last_successful_call_at,
        )

    return provider_degraded(
        provider_name,
        "Screener dependency returned partial, degraded, or unavailable data.",
        required_environment_variables,
        last_successful_call_at,
        last_error_message
        or "One or more provider-backed screener dependencies were unavailable.",
    )


def provider_name_from_statuses(statuses: list[dict]) -> str:
    for status in statuses:
        provider_name = status.get("provider")

        if provider_name and provider_name != "platform":
            return provider_name

    provider_name = statuses[0].get("provider")

    return provider_name if provider_name else "fmp"


def required_environment_variables_from_statuses(statuses: list[dict]) -> list[str]:
    variables = []

    for status in statuses:
        for variable in status.get("requiredEnvironmentVariables") or []:
            if variable not in variables:
                variables.append(variable)

    return variables


def last_successful_call_at_from_statuses(statuses: list[dict]) -> Optional[str]:
    timestamps = [
        status.get("lastSuccessfulCallAt")
        for status in statuses
        if status.get("lastSuccessfulCallAt")
    ]

    return max(timestamps) if timestamps else None


def last_error_message_from_statuses(statuses: list[dict]) -> Optional[str]:
    for status in statuses:
        message = status.get("lastErrorMessage")

        if message:
            return message

    return None


def source_metadata(
    ticker: str,
    profile: Optional[dict],
    income: Optional[dict],
    balance: Optional[dict],
    cash_flow: Optional[dict],
    computed: Optional[dict],
    key_metrics: Optional[dict],
) -> dict:
    primary = computed or income or profile or key_metrics or {}
    source_providers = []

    for source in [profile, income, balance, cash_flow, computed, key_metrics]:
        if source is None:
            continue

        provider = text(source.get("provider"))

        if provider and provider not in source_providers:
            source_providers.append(provider)

        for provider in source.get("sourceProviders") or []:
            if provider not in source_providers:
                source_providers.append(provider)

    return {
        "provider": text(primary.get("provider")) or "platform",
        "fetchedAt": text(primary.get("fetchedAt")),
        "sourceSymbol": text(primary.get("sourceSymbol")) or ticker,
        "currency": first_text(
            profile.get("currency") if profile else None,
            income.get("currency") if income else None,
            balance.get("currency") if balance else None,
            cash_flow.get("currency") if cash_flow else None,
            computed.get("currency") if computed else None,
            key_metrics.get("currency") if key_metrics else None,
        ),
        "fiscalYear": text(primary.get("fiscalYear")),
        "fiscalPeriod": text(primary.get("fiscalPeriod")),
        "sourceProviders": sorted(source_providers),
    }


def rows_from_response(response: dict, data_key: str) -> list[dict]:
    rows = response.get(data_key)

    if not isinstance(rows, list):
        return []

    return [row for row in rows if isinstance(row, dict)]


def first_row(rows: list[dict]) -> Optional[dict]:
    return rows[0] if rows else None


def source_value(row: Optional[dict], key: str) -> Optional[str]:
    if row is None:
        return None

    value = row.get(key)

    if value is None:
        return None

    return str(value)


def snapshot_age_seconds(snapshot: dict) -> Optional[int]:
    refreshed_at = snapshot.get("refreshedAt")

    if not isinstance(refreshed_at, str):
        return None

    try:
        timestamp = datetime.fromisoformat(refreshed_at.replace("Z", "+00:00"))

        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)

        return max(int((datetime.now(timezone.utc) - timestamp).total_seconds()), 0)
    except ValueError:
        return None


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sanitize_error_message(message: str, provider: FundamentalsProvider) -> str:
    safe_message = message

    for attribute in ["api_key", "secret_key"]:
        value = getattr(provider, attribute, None)

        if isinstance(value, str) and value:
            safe_message = safe_message.replace(value, "[redacted]")

    return safe_message[:300]


def mapping_or_none(value) -> Optional[dict]:
    return value if isinstance(value, dict) else None


def status_from_response(response: dict) -> Optional[dict]:
    status = response.get("provider")

    return status if isinstance(status, dict) else None


def add_source_flags(flags: list[str], row: dict, prefix: str) -> None:
    for flag in row.get("qualityFlags") or []:
        add_flag(flags, f"{prefix}:{flag}")


def add_flags(flags: list[str], values: list[str]) -> None:
    for value in values:
        add_flag(flags, value)


def add_flag(flags: list[str], flag: str) -> None:
    if flag not in flags:
        flags.append(flag)


def number(value) -> Optional[float]:
    if isinstance(value, bool):
        return None

    if isinstance(value, (int, float)):
        return float(value)

    return None


def text(value) -> Optional[str]:
    if isinstance(value, str) and value:
        return value

    return None


def first_text(*values) -> Optional[str]:
    for value in values:
        text_value = text(value)

        if text_value:
            return text_value

    return None
