from app.core.config import Settings
from app.services.fundamentals.provider import FundamentalsProvider
from app.services.persistence.repository import SnapshotRepository
from app.services.screener.universe import (
    PHASE_2D_TICKERS,
    PHASE_2D_UNIVERSE_NAME,
)


def env_status(name: str, present: bool, required: bool) -> dict:
    return {
        "name": name,
        "present": present,
        "required": required,
    }


def readiness_state(provider_state: str) -> str:
    if provider_state == "connected":
        return "ready"

    if provider_state in {"degraded", "not_implemented"}:
        return provider_state

    return "blocked"


def readiness_message(provider_state: str, endpoint_name: str) -> str:
    if provider_state == "connected":
        return f"{endpoint_name} can use the configured fundamentals provider."

    if provider_state == "degraded":
        return f"{endpoint_name} is available, but the fundamentals provider is degraded."

    if provider_state == "not_implemented":
        return f"{endpoint_name} is contract-ready but not implemented."

    return f"{endpoint_name} is blocked until FMP credentials are configured."


def endpoint_readiness(provider_state: str) -> list[dict]:
    endpoints = [
        ("Company profile", "GET", "/api/fundamentals/{ticker}/profile"),
        ("Income statement", "GET", "/api/fundamentals/{ticker}/income-statement"),
        ("Balance sheet", "GET", "/api/fundamentals/{ticker}/balance-sheet"),
        ("Cash flow", "GET", "/api/fundamentals/{ticker}/cash-flow"),
        ("Key metrics", "GET", "/api/fundamentals/{ticker}/metrics"),
        ("Computed metrics", "GET", "/api/fundamentals/{ticker}/computed-metrics"),
        ("Fundamentals screener", "GET", "/api/screener"),
        ("Screener snapshot refresh", "POST", "/api/screener/refresh"),
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


def build_fundamentals_diagnostics(
    provider: FundamentalsProvider,
    settings: Settings,
    repository: SnapshotRepository,
) -> dict:
    provider_status = provider.provider_status()
    repository_status = repository.repository_status()
    snapshot_freshness = repository.snapshot_freshness(
        PHASE_2D_UNIVERSE_NAME,
        PHASE_2D_TICKERS,
        ["annual", "quarter"],
        settings.snapshot_stale_after_seconds,
    )
    screener_state = screener_readiness_state(
        provider_status["state"],
        repository_status,
        snapshot_freshness,
    )
    persisted_universe_size = len(repository.list_universe(PHASE_2D_UNIVERSE_NAME))
    cache_ttls = {
        "companyProfileSeconds": (
            settings.fundamentals_profile_cache_ttl_seconds
        ),
        "incomeStatementSeconds": (
            settings.fundamentals_income_statement_cache_ttl_seconds
        ),
        "balanceSheetSeconds": (
            settings.fundamentals_balance_sheet_cache_ttl_seconds
        ),
        "cashFlowSeconds": settings.fundamentals_cash_flow_cache_ttl_seconds,
        "keyMetricsSeconds": settings.fundamentals_key_metrics_cache_ttl_seconds,
        "computedMetricsSeconds": settings.computed_metrics_cache_ttl_seconds,
    }

    return {
        "provider": provider_status,
        "environment": [
            env_status("FMP_API_KEY", bool(settings.fmp_api_key), True),
            env_status("FMP_BASE_URL", bool(settings.fmp_base_url), False),
        ],
        "cacheTtls": cache_ttls,
        "endpointReadiness": endpoint_readiness(provider_status["state"]),
        "supportedPeriods": ["annual", "quarter", "ttm"],
        "defaultPeriod": "annual",
        "screener": {
            "readiness": screener_state,
            "universeName": PHASE_2D_UNIVERSE_NAME,
            "universeSize": len(PHASE_2D_TICKERS),
            "persistedUniverseSize": persisted_universe_size,
            "providerDependency": provider_status,
            "snapshotStore": repository_status,
            "snapshotFreshness": snapshot_freshness,
            "cacheBacked": True,
            "cacheTtls": cache_ttls,
            "endpointReadiness": [
                {
                    "name": "Fundamentals screener",
                    "method": "GET",
                    "path": "/api/screener",
                    "state": screener_state,
                    "message": screener_readiness_message(
                        provider_status["state"],
                        snapshot_freshness,
                    ),
                },
                {
                    "name": "Screener snapshot refresh",
                    "method": "POST",
                    "path": "/api/screener/refresh",
                    "state": readiness_state(provider_status["state"]),
                    "message": readiness_message(
                        provider_status["state"],
                        "Screener snapshot refresh",
                    ),
                }
            ],
            "message": (
                "The Phase 2E screener reads durable SQLite snapshots first "
                "and falls back to provider data only when snapshots are missing."
            ),
        },
        "message": (
            "Fundamentals diagnostics are backend-only and expose FMP readiness "
            "without revealing credential values."
        ),
    }


def screener_readiness_state(
    provider_state: str,
    repository_status: dict,
    snapshot_freshness: list[dict],
) -> str:
    if repository_status.get("state") == "connected" and any(
        summary.get("persistedCount", 0) > 0 for summary in snapshot_freshness
    ):
        return "ready"

    return readiness_state(provider_state)


def screener_readiness_message(
    provider_state: str,
    snapshot_freshness: list[dict],
) -> str:
    if any(summary.get("persistedCount", 0) > 0 for summary in snapshot_freshness):
        return "Fundamentals screener can read persisted snapshots."

    return readiness_message(provider_state, "Fundamentals screener")
