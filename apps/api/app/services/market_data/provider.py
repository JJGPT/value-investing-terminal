from functools import lru_cache
from typing import Protocol

from app.core.config import get_settings
from app.services.market_data.alpaca import AlpacaMarketDataProvider
from app.services.provider_status import provider_not_connected


class MarketDataProvider(Protocol):
    def provider_status(self) -> dict:
        """Return provider connectivity metadata."""

    def search_securities(self, query: str) -> dict:
        """Search tradable securities by ticker or company name."""

    def get_security(self, ticker: str) -> dict:
        """Return the company/security overview contract for a ticker."""

    def get_market_snapshot(self, ticker: str) -> dict:
        """Return the point-in-time market snapshot contract for a ticker."""


class NotConnectedProvider:
    provider_name = "alpaca"
    required_environment_variables = [
        "ALPACA_API_KEY",
        "ALPACA_SECRET_KEY",
    ]

    def provider_status(self) -> dict:
        return provider_not_connected(
            self.provider_name,
            self.required_environment_variables,
        )

    def search_securities(self, query: str) -> dict:
        return {
            "query": query,
            "results": [],
            "provider": self.provider_status(),
            "message": (
                "Securities search is contracted, but the market data provider "
                "is not connected yet."
            ),
        }

    def get_security(self, ticker: str) -> dict:
        normalized_ticker = ticker.upper()

        return {
            "ticker": normalized_ticker,
            "security": {
                "ticker": normalized_ticker,
                "name": "Security details unavailable",
                "exchange": None,
                "region": None,
                "currency": None,
                "assetType": "unknown",
                "provider": None,
                "providerState": "not_connected",
            },
            "businessSummary": None,
            "sector": None,
            "industry": None,
            "domicile": None,
            "fiscalYearEnd": None,
            "provider": provider_not_connected(
                "company_reference",
                [
                    "ALPACA_API_KEY",
                    "ALPACA_SECRET_KEY",
                    "SEC_USER_AGENT",
                ],
            ),
            "message": (
                "Company overview is contracted, but reference data and filings "
                "providers are not connected yet."
            ),
        }

    def get_market_snapshot(self, ticker: str) -> dict:
        normalized_ticker = ticker.upper()

        return {
            "ticker": normalized_ticker,
            "price": None,
            "currency": None,
            "marketCap": None,
            "enterpriseValue": None,
            "volume": None,
            "asOf": None,
            "provider": self.provider_status(),
            "message": (
                "Market snapshot is contracted, but real-time and historical "
                "market data are not connected yet."
            ),
        }


@lru_cache
def get_market_data_provider() -> MarketDataProvider:
    settings = get_settings()

    if settings.alpaca_api_key and settings.alpaca_secret_key:
        return AlpacaMarketDataProvider(
            api_key=settings.alpaca_api_key,
            secret_key=settings.alpaca_secret_key,
            base_url=settings.alpaca_base_url,
            data_base_url=settings.alpaca_data_base_url,
            search_cache_ttl_seconds=settings.security_search_cache_ttl_seconds,
            security_cache_ttl_seconds=settings.security_lookup_cache_ttl_seconds,
            snapshot_cache_ttl_seconds=settings.market_snapshot_cache_ttl_seconds,
        )

    return NotConnectedProvider()
