import json
from datetime import datetime, timezone
from typing import Any, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from app.services.cache import TTLCache
from app.services.provider_status import provider_connected, provider_degraded


class AlpacaProviderError(Exception):
    pass


class AlpacaMarketDataProvider:
    provider_name = "alpaca"
    required_environment_variables = [
        "ALPACA_API_KEY",
        "ALPACA_SECRET_KEY",
    ]

    def __init__(
        self,
        api_key: str,
        secret_key: str,
        base_url: str,
        data_base_url: str,
        search_cache_ttl_seconds: int = 300,
        security_cache_ttl_seconds: int = 900,
        snapshot_cache_ttl_seconds: int = 30,
    ) -> None:
        self.api_key = api_key
        self.secret_key = secret_key
        self.base_url = base_url.rstrip("/")
        self.data_base_url = data_base_url.rstrip("/")
        self.search_cache = TTLCache(search_cache_ttl_seconds)
        self.security_cache = TTLCache(security_cache_ttl_seconds)
        self.snapshot_cache = TTLCache(snapshot_cache_ttl_seconds)
        self.last_successful_call_at: Optional[str] = None
        self.last_error_message: Optional[str] = None

    def provider_status(self) -> dict:
        if self.last_error_message:
            return provider_degraded(
                self.provider_name,
                "Alpaca provider is configured but the latest provider call failed.",
                self.required_environment_variables,
                self.last_successful_call_at,
                self.last_error_message,
            )

        return provider_connected(
            self.provider_name,
            "Alpaca credentials are configured for backend market data access.",
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

    def search_securities(self, query: str) -> dict:
        normalized_query = query.strip().upper()

        if not normalized_query:
            return {
                "query": query,
                "results": [],
                "provider": self.provider_status(),
                "message": "Provide a ticker or company name to search Alpaca assets.",
            }

        cache_key = self.search_cache.normalize_key("search", normalized_query)
        cached = self.search_cache.get(cache_key)

        if cached is not None:
            return {**cached, "query": query}

        try:
            assets = self._request_json(
                self.base_url,
                "/v2/assets",
                {"status": "active", "asset_class": "us_equity"},
            )
        except AlpacaProviderError as error:
            return {
                "query": query,
                "results": [],
                "provider": self.degraded_status(str(error)),
                "message": "Alpaca asset search failed; no securities were returned.",
            }

        if not isinstance(assets, list):
            payload = {
                "query": query,
                "results": [],
                "provider": self.degraded_status(
                    "Alpaca assets response did not match the expected list shape."
                ),
                "message": "Alpaca asset search failed; no securities were returned.",
            }
            return payload

        results = [
            self.normalize_asset(asset)
            for asset in assets
            if self.asset_matches_query(asset, normalized_query)
        ][:25]

        payload = {
            "query": query,
            "results": results,
            "provider": self.provider_status(),
            "message": "Alpaca asset search returned normalized securities.",
        }
        self.search_cache.set(cache_key, payload)

        return payload

    def get_security(self, ticker: str) -> dict:
        normalized_ticker = ticker.upper()
        cache_key = self.security_cache.normalize_key("security", normalized_ticker)
        cached = self.security_cache.get(cache_key)

        if cached is not None:
            return cached

        try:
            asset = self._request_json(
                self.base_url,
                f"/v2/assets/{quote(normalized_ticker)}",
            )
        except AlpacaProviderError as error:
            return self.empty_company_overview(
                normalized_ticker,
                self.degraded_status(str(error)),
                "Alpaca security lookup failed; company overview is unavailable.",
            )

        if not isinstance(asset, dict):
            return self.empty_company_overview(
                normalized_ticker,
                self.degraded_status(
                    "Alpaca asset response did not match the expected object shape."
                ),
                "Alpaca security lookup failed; company overview is unavailable.",
            )

        payload = {
            "ticker": normalized_ticker,
            "security": self.normalize_asset(asset),
            "businessSummary": None,
            "sector": None,
            "industry": None,
            "domicile": None,
            "fiscalYearEnd": None,
            "provider": self.provider_status(),
            "message": (
                "Alpaca security reference data is connected. Fundamentals and "
                "filings are not connected yet."
            ),
        }
        self.security_cache.set(cache_key, payload)

        return payload

    def get_market_snapshot(self, ticker: str) -> dict:
        normalized_ticker = ticker.upper()
        cache_key = self.snapshot_cache.normalize_key("snapshot", normalized_ticker)
        cached = self.snapshot_cache.get(cache_key)

        if cached is not None:
            return cached

        try:
            payload = self._request_json(
                self.data_base_url,
                "/v2/stocks/snapshots",
                {"symbols": normalized_ticker, "feed": "iex"},
            )
        except AlpacaProviderError as error:
            return self.empty_market_snapshot(
                normalized_ticker,
                self.degraded_status(str(error)),
                "Alpaca market snapshot failed; market data is unavailable.",
            )

        snapshot = self.extract_snapshot(payload, normalized_ticker)

        if not snapshot:
            return self.empty_market_snapshot(
                normalized_ticker,
                self.degraded_status(
                    "Alpaca snapshot response did not include the requested ticker."
                ),
                "Alpaca market snapshot did not include data for this ticker.",
            )

        latest_trade = self.optional_mapping(
            snapshot.get("latestTrade") or snapshot.get("latest_trade")
        )
        latest_quote = self.optional_mapping(
            snapshot.get("latestQuote") or snapshot.get("latest_quote")
        )
        minute_bar = self.optional_mapping(
            snapshot.get("minuteBar") or snapshot.get("minute_bar")
        )
        daily_bar = self.optional_mapping(
            snapshot.get("dailyBar") or snapshot.get("daily_bar")
        )

        payload = {
            "ticker": normalized_ticker,
            "price": self.first_number(
                latest_trade.get("p"),
                minute_bar.get("c"),
                daily_bar.get("c"),
            ),
            "currency": "USD",
            "marketCap": None,
            "enterpriseValue": None,
            "volume": self.first_number(daily_bar.get("v"), minute_bar.get("v")),
            "asOf": self.first_string(
                latest_trade.get("t"),
                latest_quote.get("t"),
                minute_bar.get("t"),
                daily_bar.get("t"),
            ),
            "provider": self.provider_status(),
            "message": "Alpaca market snapshot returned normalized market data.",
        }
        self.snapshot_cache.set(cache_key, payload)

        return payload

    def _request_json(
        self,
        base_url: str,
        path: str,
        params: Optional[dict[str, str]] = None,
    ) -> Any:
        url = f"{base_url}{path}"

        if params:
            url = f"{url}?{urlencode(params)}"

        request = Request(
            url,
            headers={
                "Accept": "application/json",
                "APCA-API-KEY-ID": self.api_key,
                "APCA-API-SECRET-KEY": self.secret_key,
            },
            method="GET",
        )

        try:
            with urlopen(request, timeout=10) as response:
                payload = json.loads(response.read().decode("utf-8"))
                self.record_success()

                return payload
        except HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise AlpacaProviderError(
                self.sanitize_error(
                    f"Alpaca returned HTTP {error.code}: {detail[:200]}"
                )
            ) from error
        except (URLError, TimeoutError, json.JSONDecodeError) as error:
            raise AlpacaProviderError(
                self.sanitize_error(f"Alpaca request failed: {error}")
            ) from error

    def record_success(self) -> None:
        self.last_successful_call_at = datetime.now(timezone.utc).isoformat()
        self.last_error_message = None

    def record_error(self, message: str) -> None:
        self.last_error_message = self.sanitize_error(message)

    def sanitize_error(self, message: str) -> str:
        sanitized = message.replace(self.api_key, "[redacted]")
        sanitized = sanitized.replace(self.secret_key, "[redacted]")

        return sanitized[:300]

    @staticmethod
    def normalize_asset(asset: dict) -> dict:
        asset_class = str(asset.get("asset_class") or "").lower()
        ticker = str(asset.get("symbol") or "").upper()

        return {
            "ticker": ticker,
            "name": asset.get("name") or ticker,
            "exchange": asset.get("exchange"),
            "region": "US" if asset_class == "us_equity" else None,
            "currency": "USD" if asset_class == "us_equity" else None,
            "assetType": "equity" if asset_class == "us_equity" else "unknown",
            "provider": "alpaca",
            "providerState": "connected",
        }

    @staticmethod
    def asset_matches_query(asset: Any, normalized_query: str) -> bool:
        if not isinstance(asset, dict):
            return False

        symbol = str(asset.get("symbol") or "").upper()
        name = str(asset.get("name") or "").upper()

        return normalized_query in symbol or normalized_query in name

    @staticmethod
    def extract_snapshot(payload: Any, ticker: str) -> Optional[dict]:
        if not isinstance(payload, dict):
            return None

        snapshots = payload.get("snapshots", payload)

        if not isinstance(snapshots, dict):
            return None

        snapshot = snapshots.get(ticker) or snapshots.get(ticker.upper())

        return snapshot if isinstance(snapshot, dict) else None

    @staticmethod
    def optional_mapping(value: Any) -> dict:
        return value if isinstance(value, dict) else {}

    @staticmethod
    def first_number(*values: Any) -> Optional[float]:
        for value in values:
            if isinstance(value, (int, float)):
                return float(value)

        return None

    @staticmethod
    def first_string(*values: Any) -> Optional[str]:
        for value in values:
            if isinstance(value, str) and value:
                return value

        return None

    @staticmethod
    def empty_company_overview(ticker: str, provider: dict, message: str) -> dict:
        return {
            "ticker": ticker,
            "security": None,
            "businessSummary": None,
            "sector": None,
            "industry": None,
            "domicile": None,
            "fiscalYearEnd": None,
            "provider": provider,
            "message": message,
        }

    @staticmethod
    def empty_market_snapshot(ticker: str, provider: dict, message: str) -> dict:
        return {
            "ticker": ticker,
            "price": None,
            "currency": None,
            "marketCap": None,
            "enterpriseValue": None,
            "volume": None,
            "asOf": None,
            "provider": provider,
            "message": message,
        }
