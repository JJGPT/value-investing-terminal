from time import perf_counter

from app.core.config import Settings
from app.services.market_data.provider import MarketDataProvider
from app.services.provider_status import provider_degraded


def sanitize_probe_error(message: str, provider: MarketDataProvider) -> str:
    sanitizer = getattr(provider, "sanitize_error", None)

    if callable(sanitizer):
        return sanitizer(message)[:300]

    sanitized = message

    for attribute in ("api_key", "secret_key"):
        value = getattr(provider, attribute, None)

        if value:
            sanitized = sanitized.replace(str(value), "[redacted]")

    return sanitized[:300]


def env_status(name: str, present: bool, required: bool) -> dict:
    return {
        "name": name,
        "present": present,
        "required": required,
    }


def readiness_state(provider_state: str) -> str:
    if provider_state == "connected":
        return "ready"

    if provider_state == "degraded":
        return "degraded"

    return "blocked"


def readiness_message(provider_state: str, endpoint_name: str) -> str:
    if provider_state == "connected":
        return f"{endpoint_name} can use the configured market data provider."

    if provider_state == "degraded":
        return f"{endpoint_name} is available, but the provider is degraded."

    return f"{endpoint_name} is blocked until Alpaca credentials are configured."


def endpoint_readiness(provider_state: str) -> list[dict]:
    endpoints = [
        ("Securities search", "GET", "/api/securities/search?q="),
        ("Security lookup", "GET", "/api/securities/{ticker}"),
        ("Market snapshot", "GET", "/api/securities/{ticker}/snapshot"),
    ]

    return [
        {
            "name": name,
            "method": method,
            "path": path,
            "state": readiness_state(provider_state),
            "message": readiness_message(provider_state, name),
        }
        for name, method, path in endpoints
    ]


def build_market_data_diagnostics(
    provider: MarketDataProvider,
    settings: Settings,
) -> dict:
    provider_status = provider.provider_status()

    return {
        "provider": provider_status,
        "environment": [
            env_status("ALPACA_API_KEY", bool(settings.alpaca_api_key), True),
            env_status("ALPACA_SECRET_KEY", bool(settings.alpaca_secret_key), True),
            env_status("ALPACA_BASE_URL", bool(settings.alpaca_base_url), False),
            env_status(
                "ALPACA_DATA_BASE_URL",
                bool(settings.alpaca_data_base_url),
                False,
            ),
        ],
        "cacheTtls": {
            "securitySearchSeconds": settings.security_search_cache_ttl_seconds,
            "securityLookupSeconds": settings.security_lookup_cache_ttl_seconds,
            "marketSnapshotSeconds": settings.market_snapshot_cache_ttl_seconds,
        },
        "endpointReadiness": endpoint_readiness(provider_status["state"]),
        "message": (
            "Market data diagnostics are backend-only and expose provider health "
            "without revealing credential values."
        ),
    }


def build_market_data_probe(provider: MarketDataProvider, ticker: str) -> dict:
    normalized_ticker = ticker.strip().upper() or "AAPL"
    started_at = perf_counter()
    security_lookup = None
    market_snapshot = None
    error_message = None

    security_latency_ms = None
    snapshot_latency_ms = None

    try:
        security_started_at = perf_counter()
        security_lookup = provider.get_security(normalized_ticker)
        security_latency_ms = round((perf_counter() - security_started_at) * 1000, 2)

        snapshot_started_at = perf_counter()
        market_snapshot = provider.get_market_snapshot(normalized_ticker)
        snapshot_latency_ms = round((perf_counter() - snapshot_started_at) * 1000, 2)
    except Exception as error:  # defensive diagnostics boundary
        error_message = sanitize_probe_error(str(error), provider)

    provider_status = provider.provider_status()

    if error_message:
        provider_status = provider_degraded(
            provider_status["provider"],
            "Market data probe failed before both provider calls completed.",
            provider_status.get("requiredEnvironmentVariables", []),
            provider_status.get("lastSuccessfulCallAt"),
            error_message,
        )

    return {
        "ticker": normalized_ticker,
        "provider": provider_status,
        "securityLookup": security_lookup,
        "marketSnapshot": market_snapshot,
        "latencyMs": {
            "securityLookup": security_latency_ms,
            "marketSnapshot": snapshot_latency_ms,
            "total": round((perf_counter() - started_at) * 1000, 2),
        },
        "error": error_message,
        "message": (
            "Market data probe executed through the backend provider abstraction."
        ),
    }
