from datetime import datetime, timezone
from typing import Optional

from app.services.fundamentals.provider import FundamentalsProvider
from app.services.provider_status import provider_not_implemented

SUPPORTED_COMPUTED_PERIODS = {"annual", "quarter"}
PLATFORM_PROVIDER = "platform"


def build_computed_metrics_response(
    provider: FundamentalsProvider,
    ticker: str,
    period: str,
    limit: int,
) -> dict:
    normalized_ticker = ticker.strip().upper()
    normalized_period = normalize_period(period)
    normalized_limit = max(min(limit, 20), 1)

    if normalized_period == "ttm":
        return {
            "ticker": normalized_ticker,
            "period": normalized_period,
            "limit": normalized_limit,
            "computedMetrics": [],
            "provider": provider_not_implemented(
                PLATFORM_PROVIDER,
                "TTM computed metrics are contract-ready but not implemented in Phase 2C.",
                [],
            ),
            "message": (
                "TTM computed metrics are contract-ready but not implemented in Phase 2C."
            ),
        }

    cache = getattr(provider, "computed_metrics_cache", None)
    cache_key = None

    if cache is not None:
        cache_key = cache.normalize_key(
            "computedMetrics",
            normalized_ticker,
            normalized_period,
            normalized_limit,
        )
        cached = cache.get(cache_key)

        if cached is not None:
            return cached

    income_response = provider.get_income_statement(
        normalized_ticker,
        normalized_period,
        normalized_limit,
    )
    degraded_provider = response_provider_if_not_connected(income_response)

    if degraded_provider is not None:
        return empty_provider_response(
            normalized_ticker,
            normalized_period,
            normalized_limit,
            degraded_provider,
        )

    balance_response = provider.get_balance_sheet(
        normalized_ticker,
        normalized_period,
        normalized_limit,
    )
    degraded_provider = response_provider_if_not_connected(balance_response)

    if degraded_provider is not None:
        return empty_provider_response(
            normalized_ticker,
            normalized_period,
            normalized_limit,
            degraded_provider,
        )

    cash_flow_response = provider.get_cash_flow_statement(
        normalized_ticker,
        normalized_period,
        normalized_limit,
    )
    degraded_provider = response_provider_if_not_connected(cash_flow_response)

    if degraded_provider is not None:
        return empty_provider_response(
            normalized_ticker,
            normalized_period,
            normalized_limit,
            degraded_provider,
        )

    income_rows = rows_from_response(income_response, "incomeStatements")
    balance_rows = rows_from_response(balance_response, "balanceSheets")
    cash_flow_rows = rows_from_response(cash_flow_response, "cashFlowStatements")

    computed_rows = compute_metric_rows(
        normalized_ticker,
        normalized_period,
        normalized_limit,
        income_rows,
        balance_rows,
        cash_flow_rows,
    )

    payload = {
        "ticker": normalized_ticker,
        "period": normalized_period,
        "limit": normalized_limit,
        "computedMetrics": computed_rows,
        "provider": platform_provider_status(
            "Platform-owned metrics were calculated from canonical normalized statements."
        ),
        "message": (
            "Platform-owned metrics were calculated from canonical normalized statements."
        ),
    }

    if cache is not None and cache_key is not None:
        cache.set(cache_key, payload)

    return payload


def compute_metric_rows(
    ticker: str,
    period: str,
    limit: int,
    income_rows: list[dict],
    balance_rows: list[dict],
    cash_flow_rows: list[dict],
) -> list[dict]:
    computed_rows = []

    for index, income in enumerate(income_rows[:limit]):
        balance, balance_index = find_matching_row(income, balance_rows, index)
        cash_flow, cash_flow_index = find_matching_row(income, cash_flow_rows, index)
        previous_income = find_prior_row(income, income_rows, index, period)
        previous_cash_flow = (
            find_prior_row(cash_flow, cash_flow_rows, cash_flow_index, period)
            if cash_flow is not None and cash_flow_index is not None
            else None
        )
        quality_flags = list(source_quality_flags(income, balance, cash_flow))

        metrics = calculate_metrics(
            income,
            balance,
            cash_flow,
            previous_income,
            previous_cash_flow,
            quality_flags,
        )

        computed_rows.append(
            {
                **source_metadata(income, balance, cash_flow, ticker),
                **metrics,
                "date": text(income.get("date")),
                "period": period,
                "sourceProviders": source_providers(income, balance, cash_flow),
                "calculationEngine": "platform-normalized-metrics-v1",
            }
        )

    return computed_rows


def calculate_metrics(
    income: dict,
    balance: Optional[dict],
    cash_flow: Optional[dict],
    previous_income: Optional[dict],
    previous_cash_flow: Optional[dict],
    quality_flags: list[str],
) -> dict:
    revenue = number(income.get("revenue"))
    gross_profit = number(income.get("grossProfit"))
    operating_income = number(income.get("operatingIncome"))
    net_income = number(income.get("netIncome"))
    shares_diluted = number(income.get("sharesDiluted"))
    free_cash_flow = number(cash_flow.get("freeCashFlow")) if cash_flow else None

    total_debt = number(balance.get("totalDebt")) if balance else None
    shareholders_equity = (
        number(balance.get("shareholdersEquity")) if balance else None
    )
    current_assets = number(balance.get("currentAssets")) if balance else None
    current_liabilities = (
        number(balance.get("currentLiabilities")) if balance else None
    )
    cash_and_equivalents = (
        number(balance.get("cashAndEquivalents")) if balance else None
    )

    invested_capital = calculate_invested_capital(
        total_debt,
        shareholders_equity,
        cash_and_equivalents,
        quality_flags,
    )

    if shares_diluted is None:
        add_flag(quality_flags, "shares_missing")

    return {
        "grossMargin": ratio(
            gross_profit,
            revenue,
            "grossMargin",
            quality_flags,
        ),
        "operatingMargin": ratio(
            operating_income,
            revenue,
            "operatingMargin",
            quality_flags,
        ),
        "netMargin": ratio(net_income, revenue, "netMargin", quality_flags),
        "freeCashFlowMargin": ratio(
            free_cash_flow,
            revenue,
            "freeCashFlowMargin",
            quality_flags,
        ),
        "revenueGrowthYoY": growth(
            revenue,
            number(previous_income.get("revenue")) if previous_income else None,
            "revenueGrowthYoY",
            quality_flags,
        ),
        "netIncomeGrowthYoY": growth(
            net_income,
            number(previous_income.get("netIncome")) if previous_income else None,
            "netIncomeGrowthYoY",
            quality_flags,
        ),
        "operatingIncomeGrowthYoY": growth(
            operating_income,
            number(previous_income.get("operatingIncome"))
            if previous_income
            else None,
            "operatingIncomeGrowthYoY",
            quality_flags,
        ),
        "freeCashFlowGrowthYoY": growth(
            free_cash_flow,
            number(previous_cash_flow.get("freeCashFlow"))
            if previous_cash_flow
            else None,
            "freeCashFlowGrowthYoY",
            quality_flags,
        ),
        "returnOnEquity": ratio(
            net_income,
            shareholders_equity,
            "returnOnEquity",
            quality_flags,
        ),
        "debtToEquity": ratio(
            total_debt,
            shareholders_equity,
            "debtToEquity",
            quality_flags,
        ),
        "currentRatio": ratio(
            current_assets,
            current_liabilities,
            "currentRatio",
            quality_flags,
        ),
        "freeCashFlowPerShare": ratio(
            free_cash_flow,
            shares_diluted,
            "freeCashFlowPerShare",
            quality_flags,
        ),
        "bookValuePerShare": ratio(
            shareholders_equity,
            shares_diluted,
            "bookValuePerShare",
            quality_flags,
        ),
        "earningsPerShareDiluted": ratio(
            net_income,
            shares_diluted,
            "earningsPerShareDiluted",
            quality_flags,
        ),
        "investedCapital": invested_capital,
        "returnOnInvestedCapital": ratio(
            operating_income,
            invested_capital,
            "returnOnInvestedCapital",
            quality_flags,
        ),
        "qualityFlags": dedupe_flags(quality_flags),
    }


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


def growth(
    current: Optional[float],
    previous: Optional[float],
    metric_name: str,
    quality_flags: list[str],
) -> Optional[float]:
    if current is None or previous is None:
        add_flag(quality_flags, f"missing_prior_period:{metric_name}")
        return None

    if previous == 0:
        add_flag(quality_flags, f"zero_prior_period:{metric_name}")
        return None

    if previous < 0:
        add_flag(quality_flags, f"negative_prior_period:{metric_name}")

    return (current - previous) / abs(previous)


def calculate_invested_capital(
    total_debt: Optional[float],
    shareholders_equity: Optional[float],
    cash_and_equivalents: Optional[float],
    quality_flags: list[str],
) -> Optional[float]:
    if (
        total_debt is None
        or shareholders_equity is None
        or cash_and_equivalents is None
    ):
        add_flag(quality_flags, "missing_input:investedCapital")
        add_flag(quality_flags, "invested_capital_unavailable")
        return None

    invested_capital = total_debt + shareholders_equity - cash_and_equivalents

    if invested_capital < 0:
        add_flag(quality_flags, "negative_invested_capital")

    if invested_capital == 0:
        add_flag(quality_flags, "invested_capital_unavailable")

    return invested_capital


def source_metadata(
    income: dict,
    balance: Optional[dict],
    cash_flow: Optional[dict],
    ticker: str,
) -> dict:
    return {
        "provider": PLATFORM_PROVIDER,
        "fetchedAt": datetime.now(timezone.utc).isoformat(),
        "sourceSymbol": text(income.get("sourceSymbol")) or ticker.upper(),
        "currency": first_text(
            income.get("currency"),
            balance.get("currency") if balance else None,
            cash_flow.get("currency") if cash_flow else None,
        ),
        "fiscalYear": text(income.get("fiscalYear")),
        "fiscalPeriod": text(income.get("fiscalPeriod")),
    }


def response_provider_if_not_connected(response: dict) -> Optional[dict]:
    provider = response.get("provider")

    if not isinstance(provider, dict):
        return None

    if provider.get("state") != "connected":
        return provider

    return None


def empty_provider_response(
    ticker: str,
    period: str,
    limit: int,
    provider_status: dict,
) -> dict:
    return {
        "ticker": ticker,
        "period": period,
        "limit": limit,
        "computedMetrics": [],
        "provider": provider_status,
        "message": "Computed metrics require connected normalized statement data.",
    }


def rows_from_response(response: dict, key: str) -> list[dict]:
    rows = response.get(key)

    if not isinstance(rows, list):
        return []

    return [row for row in rows if isinstance(row, dict)]


def find_matching_row(
    income: dict,
    rows: list[dict],
    fallback_index: int,
) -> tuple[Optional[dict], Optional[int]]:
    income_key = row_key(income)

    for index, row in enumerate(rows):
        if row_key(row) == income_key:
            return row, index

    if fallback_index < len(rows):
        return rows[fallback_index], fallback_index

    return None, None


def find_prior_row(
    current: dict,
    rows: list[dict],
    current_index: Optional[int],
    period: str,
) -> Optional[dict]:
    if current_index is None:
        return None

    if period == "quarter":
        current_fiscal_period = text(current.get("fiscalPeriod"))

        for row in rows[current_index + 1 :]:
            if text(row.get("fiscalPeriod")) == current_fiscal_period:
                return row

        return None

    prior_index = current_index + 1

    if prior_index < len(rows):
        return rows[prior_index]

    return None


def row_key(row: dict) -> tuple[Optional[str], Optional[str], Optional[str]]:
    return (
        text(row.get("fiscalYear")),
        text(row.get("fiscalPeriod")),
        text(row.get("date")),
    )


def source_quality_flags(
    income: dict,
    balance: Optional[dict],
    cash_flow: Optional[dict],
) -> list[str]:
    flags = []

    if not income.get("currency"):
        add_flag(flags, "currency_missing")

    if not income.get("fiscalYear"):
        add_flag(flags, "fiscal_year_missing")

    if is_stale_fetched_at(income.get("fetchedAt")):
        add_flag(flags, "stale_provider_response")

    for flag in income.get("qualityFlags") or []:
        add_flag(flags, f"source:{flag}")

    if balance is None:
        add_flag(flags, "missing_statement:balance_sheet")
    else:
        for flag in balance.get("qualityFlags") or []:
            add_flag(flags, f"source:{flag}")

        if is_stale_fetched_at(balance.get("fetchedAt")):
            add_flag(flags, "stale_provider_response")

    if cash_flow is None:
        add_flag(flags, "missing_statement:cash_flow")
    else:
        for flag in cash_flow.get("qualityFlags") or []:
            add_flag(flags, f"source:{flag}")

        if is_stale_fetched_at(cash_flow.get("fetchedAt")):
            add_flag(flags, "stale_provider_response")

    currencies = {
        value
        for value in [
            income.get("currency"),
            balance.get("currency") if balance else None,
            cash_flow.get("currency") if cash_flow else None,
        ]
        if value
    }

    if len(currencies) > 1:
        add_flag(flags, "currency_mismatch")

    return flags


def source_providers(
    income: dict,
    balance: Optional[dict],
    cash_flow: Optional[dict],
) -> list[str]:
    providers = [
        text(income.get("provider")),
        text(balance.get("provider")) if balance else None,
        text(cash_flow.get("provider")) if cash_flow else None,
    ]

    return sorted({provider for provider in providers if provider})


def platform_provider_status(message: str) -> dict:
    return {
        "provider": PLATFORM_PROVIDER,
        "state": "connected",
        "message": message,
        "requiredEnvironmentVariables": [],
        "lastCheckedAt": None,
        "lastSuccessfulCallAt": datetime.now(timezone.utc).isoformat(),
        "lastErrorMessage": None,
    }


def normalize_period(period: str) -> str:
    normalized = period.strip().lower()

    if normalized in {"annual", "quarter", "ttm"}:
        return normalized

    return "annual"


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


def add_flag(flags: list[str], flag: str) -> None:
    if flag not in flags:
        flags.append(flag)


def dedupe_flags(flags: list[str]) -> list[str]:
    return list(dict.fromkeys(flags))


def is_stale_fetched_at(value, max_age_seconds: int = 86400) -> bool:
    if not isinstance(value, str):
        return False

    try:
        normalized = value.replace("Z", "+00:00")
        fetched_at = datetime.fromisoformat(normalized)

        if fetched_at.tzinfo is None:
            fetched_at = fetched_at.replace(tzinfo=timezone.utc)

        age_seconds = (datetime.now(timezone.utc) - fetched_at).total_seconds()

        return age_seconds > max_age_seconds
    except ValueError:
        return False
