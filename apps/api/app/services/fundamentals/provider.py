from functools import lru_cache
from typing import Protocol

from app.core.config import get_settings
from app.services.fundamentals.fmp import FinancialModelingPrepProvider
from app.services.provider_status import provider_not_connected, provider_not_implemented


class FundamentalsProvider(Protocol):
    def provider_status(self) -> dict:
        """Return provider connectivity metadata."""

    def get_company_profile(self, ticker: str) -> dict:
        """Return normalized company profile data."""

    def get_income_statement(self, ticker: str, period: str, limit: int) -> dict:
        """Return normalized income statement rows."""

    def get_balance_sheet(self, ticker: str, period: str, limit: int) -> dict:
        """Return normalized balance sheet rows."""

    def get_cash_flow_statement(self, ticker: str, period: str, limit: int) -> dict:
        """Return normalized cash flow statement rows."""

    def get_key_metrics(self, ticker: str, period: str, limit: int) -> dict:
        """Return normalized provider key metric rows."""


class NotConnectedFundamentalsProvider:
    provider_name = "fmp"
    required_environment_variables = ["FMP_API_KEY"]

    def provider_status(self) -> dict:
        return provider_not_connected(
            self.provider_name,
            self.required_environment_variables,
        )

    def get_company_profile(self, ticker: str) -> dict:
        return {
            "ticker": ticker.strip().upper(),
            "profile": None,
            "provider": self.provider_status(),
            "message": "FMP fundamentals provider is not connected yet.",
        }

    def get_income_statement(self, ticker: str, period: str, limit: int) -> dict:
        return self.empty_statement(ticker, period, limit, "incomeStatements")

    def get_balance_sheet(self, ticker: str, period: str, limit: int) -> dict:
        return self.empty_statement(ticker, period, limit, "balanceSheets")

    def get_cash_flow_statement(self, ticker: str, period: str, limit: int) -> dict:
        return self.empty_statement(ticker, period, limit, "cashFlowStatements")

    def get_key_metrics(self, ticker: str, period: str, limit: int) -> dict:
        return self.empty_statement(ticker, period, limit, "metrics")

    def empty_statement(
        self,
        ticker: str,
        period: str,
        limit: int,
        data_key: str,
    ) -> dict:
        normalized_period = period.strip().lower()
        provider = self.provider_status()
        message = "FMP fundamentals provider is not connected yet."

        if normalized_period == "ttm":
            provider = provider_not_implemented(
                self.provider_name,
                "TTM fundamentals are contract-ready but not implemented in Phase 2A.",
                self.required_environment_variables,
            )
            message = "TTM fundamentals are contract-ready but not implemented in Phase 2A."

        return {
            "ticker": ticker.strip().upper(),
            "period": normalized_period,
            "limit": limit,
            data_key: [],
            "provider": provider,
            "message": message,
        }


@lru_cache
def get_fundamentals_provider() -> FundamentalsProvider:
    settings = get_settings()

    if settings.fmp_api_key:
        return FinancialModelingPrepProvider(
            api_key=settings.fmp_api_key,
            base_url=settings.fmp_base_url,
            profile_cache_ttl_seconds=(
                settings.fundamentals_profile_cache_ttl_seconds
            ),
            income_statement_cache_ttl_seconds=(
                settings.fundamentals_income_statement_cache_ttl_seconds
            ),
            balance_sheet_cache_ttl_seconds=(
                settings.fundamentals_balance_sheet_cache_ttl_seconds
            ),
            cash_flow_cache_ttl_seconds=(
                settings.fundamentals_cash_flow_cache_ttl_seconds
            ),
            key_metrics_cache_ttl_seconds=(
                settings.fundamentals_key_metrics_cache_ttl_seconds
            ),
            computed_metrics_cache_ttl_seconds=(
                settings.computed_metrics_cache_ttl_seconds
            ),
        )

    return NotConnectedFundamentalsProvider()
