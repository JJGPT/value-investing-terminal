import json
from datetime import datetime, timezone
from typing import Any, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.services.cache import TTLCache
from app.services.provider_status import (
    provider_connected,
    provider_degraded,
    provider_not_implemented,
)

SUPPORTED_PERIODS = {"annual", "quarter"}


class FMPProviderError(Exception):
    pass


class FinancialModelingPrepProvider:
    provider_name = "fmp"
    required_environment_variables = ["FMP_API_KEY"]

    def __init__(
        self,
        api_key: str,
        base_url: str,
        profile_cache_ttl_seconds: int = 3600,
        income_statement_cache_ttl_seconds: int = 3600,
        balance_sheet_cache_ttl_seconds: int = 3600,
        cash_flow_cache_ttl_seconds: int = 3600,
        key_metrics_cache_ttl_seconds: int = 3600,
        computed_metrics_cache_ttl_seconds: int = 900,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.profile_cache = TTLCache(profile_cache_ttl_seconds)
        self.income_statement_cache = TTLCache(income_statement_cache_ttl_seconds)
        self.balance_sheet_cache = TTLCache(balance_sheet_cache_ttl_seconds)
        self.cash_flow_cache = TTLCache(cash_flow_cache_ttl_seconds)
        self.key_metrics_cache = TTLCache(key_metrics_cache_ttl_seconds)
        self.computed_metrics_cache = TTLCache(computed_metrics_cache_ttl_seconds)
        self.last_successful_call_at: Optional[str] = None
        self.last_error_message: Optional[str] = None

    def provider_status(self) -> dict:
        if self.last_error_message:
            return provider_degraded(
                self.provider_name,
                "FMP provider is configured but the latest provider call failed.",
                self.required_environment_variables,
                self.last_successful_call_at,
                self.last_error_message,
            )

        return provider_connected(
            self.provider_name,
            "FMP credentials are configured for backend fundamentals access.",
            self.last_successful_call_at,
        )

    def degraded_status(self, message: str) -> dict:
        safe_message = self.sanitize_error(message)
        self.record_error(safe_message)

        return provider_degraded(
            self.provider_name,
            safe_message,
            self.required_environment_variables,
            self.last_successful_call_at,
            self.last_error_message,
        )

    def not_implemented_status(self) -> dict:
        return provider_not_implemented(
            self.provider_name,
            "TTM fundamentals are contract-ready but not implemented in Phase 2A.",
            self.required_environment_variables,
            self.last_successful_call_at,
        )

    def get_company_profile(self, ticker: str) -> dict:
        normalized_ticker = ticker.strip().upper()
        cache_key = self.profile_cache.normalize_key("profile", normalized_ticker)
        cached = self.profile_cache.get(cache_key)

        if cached is not None:
            return cached

        fetched_at = self.utc_now()

        try:
            payload = self._request_json("/profile", {"symbol": normalized_ticker})
        except FMPProviderError as error:
            return self.profile_response(
                normalized_ticker,
                None,
                self.degraded_status(str(error)),
                "FMP company profile lookup failed.",
            )
        self.record_success()

        profile = self.first_mapping(payload)

        if profile is None:
            return self.profile_response(
                normalized_ticker,
                None,
                self.degraded_status("FMP profile response did not include a company."),
                "FMP company profile lookup failed.",
            )

        payload = self.profile_response(
            normalized_ticker,
            self.normalize_profile(profile, normalized_ticker, fetched_at),
            self.provider_status(),
            "FMP company profile returned normalized fundamentals data.",
        )
        self.profile_cache.set(cache_key, payload)

        return payload

    def get_income_statement(self, ticker: str, period: str, limit: int) -> dict:
        return self.statement_response(
            ticker,
            period,
            limit,
            "incomeStatements",
            "/income-statement",
            self.normalize_income_statement,
            "FMP income statement returned normalized canonical rows.",
        )

    def get_balance_sheet(self, ticker: str, period: str, limit: int) -> dict:
        return self.statement_response(
            ticker,
            period,
            limit,
            "balanceSheets",
            "/balance-sheet-statement",
            self.normalize_balance_sheet,
            "FMP balance sheet returned normalized canonical rows.",
        )

    def get_cash_flow_statement(self, ticker: str, period: str, limit: int) -> dict:
        return self.statement_response(
            ticker,
            period,
            limit,
            "cashFlowStatements",
            "/cash-flow-statement",
            self.normalize_cash_flow_statement,
            "FMP cash flow statement returned normalized canonical rows.",
        )

    def get_key_metrics(self, ticker: str, period: str, limit: int) -> dict:
        return self.statement_response(
            ticker,
            period,
            limit,
            "metrics",
            "/key-metrics",
            self.normalize_key_metrics,
            (
                "FMP key metrics returned normalized provider metrics. "
                "These are provisional until the platform metrics engine is built."
            ),
        )

    def statement_response(
        self,
        ticker: str,
        period: str,
        limit: int,
        data_key: str,
        endpoint: str,
        normalizer,
        success_message: str,
    ) -> dict:
        normalized_ticker = ticker.strip().upper()
        normalized_period = normalize_period(period)
        normalized_limit = max(min(limit, 20), 1)
        cache = self.cache_for_data_key(data_key)
        cache_key = cache.normalize_key(
            data_key,
            normalized_ticker,
            normalized_period,
            normalized_limit,
        )
        cached = cache.get(cache_key)

        if cached is not None:
            return cached

        fetched_at = self.utc_now()

        if normalized_period == "ttm":
            return {
                "ticker": normalized_ticker,
                "period": normalized_period,
                "limit": normalized_limit,
                data_key: [],
                "provider": self.not_implemented_status(),
                "message": (
                    "TTM fundamentals are contract-ready but not implemented in Phase 2A."
                ),
            }

        try:
            payload = self._request_json(
                endpoint,
                {
                    "symbol": normalized_ticker,
                    "period": normalized_period,
                    "limit": str(normalized_limit),
                },
            )
        except FMPProviderError as error:
            return {
                "ticker": normalized_ticker,
                "period": normalized_period,
                "limit": normalized_limit,
                data_key: [],
                "provider": self.degraded_status(str(error)),
                "message": "FMP fundamentals request failed.",
            }
        self.record_success()

        if not isinstance(payload, list):
            return {
                "ticker": normalized_ticker,
                "period": normalized_period,
                "limit": normalized_limit,
                data_key: [],
                "provider": self.degraded_status(
                    "FMP fundamentals response did not match the expected list shape."
                ),
                "message": "FMP fundamentals request failed.",
            }

        payload = {
            "ticker": normalized_ticker,
            "period": normalized_period,
            "limit": normalized_limit,
            data_key: [
                normalizer(row, normalized_ticker, fetched_at)
                for row in payload
                if isinstance(row, dict)
            ],
            "provider": self.provider_status(),
            "message": success_message,
        }
        cache.set(cache_key, payload)

        return payload

    def cache_for_data_key(self, data_key: str) -> TTLCache:
        if data_key == "incomeStatements":
            return self.income_statement_cache

        if data_key == "balanceSheets":
            return self.balance_sheet_cache

        if data_key == "cashFlowStatements":
            return self.cash_flow_cache

        if data_key == "metrics":
            return self.key_metrics_cache

        return TTLCache(0)

    def _request_json(self, path: str, params: dict[str, str]) -> Any:
        url = f"{self.base_url}{path}?{urlencode({**params, 'apikey': self.api_key})}"
        request = Request(
            url,
            headers={"Accept": "application/json"},
            method="GET",
        )

        try:
            with urlopen(request, timeout=12) as response:
                payload = json.loads(response.read().decode("utf-8"))
                self.record_success()

                return payload
        except HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise FMPProviderError(
                self.sanitize_error(f"FMP returned HTTP {error.code}: {detail[:200]}")
            ) from error
        except (URLError, TimeoutError, json.JSONDecodeError) as error:
            raise FMPProviderError(
                self.sanitize_error(f"FMP request failed: {error}")
            ) from error

    def record_success(self) -> None:
        self.last_successful_call_at = self.utc_now()
        self.last_error_message = None

    def record_error(self, message: str) -> None:
        self.last_error_message = self.sanitize_error(message)

    def sanitize_error(self, message: str) -> str:
        return message.replace(self.api_key, "[redacted]")[:300]

    @staticmethod
    def utc_now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def first_mapping(payload: Any) -> Optional[dict]:
        if isinstance(payload, list) and payload and isinstance(payload[0], dict):
            return payload[0]

        if isinstance(payload, dict):
            return payload

        return None

    @staticmethod
    def number(value: Any) -> Optional[float]:
        if isinstance(value, bool):
            return None

        if isinstance(value, (int, float)):
            return float(value)

        return None

    @staticmethod
    def text(value: Any) -> Optional[str]:
        if isinstance(value, str) and value:
            return value

        return None

    @staticmethod
    def fiscal_year(row: dict) -> Optional[str]:
        value = row.get("fiscalYear") or row.get("calendarYear")

        if value is None and isinstance(row.get("date"), str):
            value = row["date"][:4]

        return str(value) if value is not None else None

    @staticmethod
    def fiscal_period(row: dict) -> Optional[str]:
        value = row.get("period")

        return str(value) if value is not None else None

    def source_metadata(
        self,
        row: dict,
        ticker: str,
        fetched_at: str,
        fallback_currency: Optional[str] = None,
    ) -> dict:
        return {
            "provider": self.provider_name,
            "fetchedAt": fetched_at,
            "sourceSymbol": str(row.get("symbol") or ticker).upper(),
            "currency": self.text(row.get("reportedCurrency"))
            or self.text(row.get("currency"))
            or fallback_currency,
            "fiscalYear": self.fiscal_year(row),
            "fiscalPeriod": self.fiscal_period(row),
            "qualityFlags": [],
        }

    def with_quality_flags(
        self,
        payload: dict,
        required_fields: list[str],
        include_fiscal_year: bool = True,
        include_currency: bool = True,
    ) -> dict:
        flags = list(payload.get("qualityFlags") or [])

        if include_currency and payload.get("currency") is None:
            self.add_flag(flags, "currency_missing")

        if include_fiscal_year and payload.get("fiscalYear") is None:
            self.add_flag(flags, "fiscal_year_missing")

        if payload.get("date") is None and include_fiscal_year:
            self.add_flag(flags, "provider_anomaly:missing_date")

        for field in required_fields:
            if payload.get(field) is None:
                self.add_flag(flags, f"missing_core_field:{field}")

                if field == "sharesDiluted":
                    self.add_flag(flags, "shares_missing")

        return {**payload, "qualityFlags": flags}

    @staticmethod
    def add_flag(flags: list[str], flag: str) -> None:
        if flag not in flags:
            flags.append(flag)

    def normalize_profile(self, row: dict, ticker: str, fetched_at: str) -> dict:
        metadata = self.source_metadata(row, ticker, fetched_at, row.get("currency"))

        payload = {
            **metadata,
            "ticker": str(row.get("symbol") or ticker).upper(),
            "name": self.text(row.get("companyName")) or self.text(row.get("name")),
            "exchange": self.text(row.get("exchangeShortName"))
            or self.text(row.get("exchange")),
            "sector": self.text(row.get("sector")),
            "industry": self.text(row.get("industry")),
            "country": self.text(row.get("country")),
            "website": self.text(row.get("website")),
            "marketCap": self.number(row.get("marketCap")),
            "beta": self.number(row.get("beta")),
            "price": self.number(row.get("price")),
            "description": self.text(row.get("description")),
        }

        return self.with_quality_flags(
            payload,
            ["name"],
            include_fiscal_year=False,
        )

    def normalize_income_statement(
        self,
        row: dict,
        ticker: str,
        fetched_at: str,
    ) -> dict:
        metadata = self.source_metadata(row, ticker, fetched_at)

        payload = {
            **metadata,
            "date": self.text(row.get("date")),
            "revenue": self.number(row.get("revenue")),
            "grossProfit": self.number(row.get("grossProfit")),
            "operatingIncome": self.number(row.get("operatingIncome")),
            "ebitda": self.number(row.get("ebitda")),
            "netIncome": self.number(row.get("netIncome")),
            "eps": self.number(row.get("eps")),
            "epsDiluted": self.number(row.get("epsdiluted")),
            "sharesDiluted": self.number(row.get("weightedAverageShsOutDil")),
        }

        return self.with_quality_flags(
            payload,
            [
                "revenue",
                "grossProfit",
                "operatingIncome",
                "netIncome",
                "sharesDiluted",
            ],
        )

    def normalize_balance_sheet(self, row: dict, ticker: str, fetched_at: str) -> dict:
        metadata = self.source_metadata(row, ticker, fetched_at)

        payload = {
            **metadata,
            "date": self.text(row.get("date")),
            "cashAndEquivalents": self.number(row.get("cashAndCashEquivalents")),
            "totalAssets": self.number(row.get("totalAssets")),
            "currentAssets": self.number(row.get("totalCurrentAssets")),
            "totalLiabilities": self.number(row.get("totalLiabilities")),
            "currentLiabilities": self.number(row.get("totalCurrentLiabilities")),
            "totalDebt": self.number(row.get("totalDebt")),
            "shareholdersEquity": self.number(row.get("totalStockholdersEquity")),
            "retainedEarnings": self.number(row.get("retainedEarnings")),
        }

        return self.with_quality_flags(
            payload,
            [
                "cashAndEquivalents",
                "totalAssets",
                "currentAssets",
                "totalLiabilities",
                "currentLiabilities",
                "totalDebt",
                "shareholdersEquity",
            ],
        )

    def normalize_cash_flow_statement(
        self,
        row: dict,
        ticker: str,
        fetched_at: str,
    ) -> dict:
        metadata = self.source_metadata(row, ticker, fetched_at)

        payload = {
            **metadata,
            "date": self.text(row.get("date")),
            "operatingCashFlow": self.number(row.get("operatingCashFlow")),
            "capitalExpenditures": self.number(row.get("capitalExpenditure")),
            "freeCashFlow": self.number(row.get("freeCashFlow")),
            "dividendsPaid": self.number(row.get("dividendsPaid")),
            "shareRepurchases": self.number(
                row.get("commonStockRepurchased")
                or row.get("repurchasesOfCommonStock")
            ),
            "debtRepayment": self.number(row.get("debtRepayment")),
            "debtIssuance": self.number(row.get("debtIssuance")),
            "netChangeInCash": self.number(row.get("netChangeInCash")),
        }

        return self.with_quality_flags(
            payload,
            [
                "operatingCashFlow",
                "capitalExpenditures",
                "freeCashFlow",
            ],
        )

    def normalize_key_metrics(self, row: dict, ticker: str, fetched_at: str) -> dict:
        metadata = self.source_metadata(row, ticker, fetched_at)

        payload = {
            **metadata,
            "date": self.text(row.get("date")),
            "revenuePerShare": self.number(row.get("revenuePerShare")),
            "netIncomePerShare": self.number(row.get("netIncomePerShare")),
            "freeCashFlowPerShare": self.number(row.get("freeCashFlowPerShare")),
            "bookValuePerShare": self.number(row.get("bookValuePerShare")),
            "returnOnInvestedCapital": self.number(row.get("roic")),
            "returnOnEquity": self.number(row.get("roe")),
            "debtToEquity": self.number(row.get("debtToEquity")),
            "currentRatio": self.number(row.get("currentRatio")),
            "priceToEarnings": self.number(row.get("peRatio")),
            "priceToBook": self.number(row.get("pbRatio")),
            "priceToSales": self.number(row.get("priceToSalesRatio")),
            "enterpriseValueToEbitda": self.number(row.get("enterpriseValueOverEBITDA")),
        }

        return self.with_quality_flags(payload, [])

    @staticmethod
    def profile_response(
        ticker: str,
        profile: Optional[dict],
        provider: dict,
        message: str,
    ) -> dict:
        return {
            "ticker": ticker,
            "profile": profile,
            "provider": provider,
            "message": message,
        }


def normalize_period(period: str) -> str:
    normalized = period.strip().lower()

    if normalized in {"annual", "quarter", "ttm"}:
        return normalized

    return "annual"
