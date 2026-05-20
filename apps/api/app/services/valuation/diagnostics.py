from app.services.persistence.repository import SnapshotRepository
from app.services.provider_status import provider_connected, provider_degraded
from app.services.valuation.dcf import (
    ASSUMPTION_LIMITS,
    DCF_ENGINE_VERSION,
    LONG_TERM_GDP_GROWTH_PROXY,
    VALUATION_METHODOLOGY_VERSION,
    scenario_summary,
)

VALUATION_STALE_AFTER_SECONDS = 60 * 60 * 24 * 90


def build_valuation_diagnostics(
    repository: SnapshotRepository,
    ticker: str = "AAPL",
) -> dict:
    normalized_ticker = ticker.strip().upper()
    repository_status = repository.repository_status()
    repository_ready = repository_status.get("state") == "connected"
    scenarios = repository.list_valuation_scenarios(normalized_ticker, 10)
    provider = (
        provider_connected(
            "platform_valuation",
            "Platform valuation engine is available.",
        )
        if repository_ready
        else provider_degraded(
            "platform_valuation",
            "Valuation engine is available, but scenario persistence is degraded.",
            [],
            None,
            repository_status.get("message"),
        )
    )

    return {
        "provider": provider,
        "engineVersion": DCF_ENGINE_VERSION,
        "valuationMethodologyVersion": VALUATION_METHODOLOGY_VERSION,
        "schemaVersion": 1,
        "repository": repository_status,
        "repositoryHealth": repository.valuation_repository_diagnostics(
            normalized_ticker,
            VALUATION_STALE_AFTER_SECONDS,
        ),
        "ticker": normalized_ticker,
        "savedScenarioCount": len(scenarios),
        "latestScenario": scenario_summary(scenarios[0]) if scenarios else None,
        "assumptionLimits": assumption_limits(),
        "warningRules": warning_rules(),
        "endpointReadiness": endpoint_readiness(repository_ready),
        "message": (
            "Valuation diagnostics expose DCF route readiness, scenario "
            "persistence health, reproducibility checks, and assumption "
            "validation bounds."
        ),
    }


def assumption_limits() -> list[dict]:
    return [
        {
            "group": group,
            "name": name,
            "minimum": limits[0],
            "maximum": limits[1],
        }
        for (group, name), limits in sorted(ASSUMPTION_LIMITS.items())
    ]


def warning_rules() -> list[dict]:
    return [
        {
            "code": "terminal_value_dominance",
            "message": "Warns when terminal value exceeds 75% of enterprise value.",
        },
        {
            "code": "terminal_growth_above_gdp_proxy",
            "message": (
                "Warns when perpetual growth exceeds the long-term GDP proxy "
                f"of {LONG_TERM_GDP_GROWTH_PROXY}."
            ),
        },
        {
            "code": "wacc_lte_terminal_growth",
            "message": "Warns when WACC is less than or equal to terminal growth.",
        },
        {
            "code": "unrealistic_operating_margin",
            "message": "Warns when operating margin is outside the review band.",
        },
        {
            "code": "negative_reinvestment_inconsistency",
            "message": "Warns when reinvestment is negative in the FCFF model.",
        },
        {
            "code": "roic_below_wacc_with_growth",
            "message": "Warns when positive growth is paired with ROIC below WACC.",
        },
        {
            "code": "projection_instability",
            "message": "Warns when explicit growth assumptions are unusually high.",
        },
        {
            "code": "missing_diluted_share_assumption",
            "message": "Warns when per-share valuation cannot be audited.",
        },
    ]


def endpoint_readiness(repository_ready: bool) -> list[dict]:
    state = "ready" if repository_ready else "degraded"
    message = (
        "Endpoint is ready."
        if repository_ready
        else "Endpoint can calculate fresh scenarios, but persistence is degraded."
    )

    return [
        {
            "name": "Create DCF scenario",
            "method": "POST",
            "path": "/api/valuation/dcf/{ticker}",
            "state": state,
            "message": message,
        },
        {
            "name": "Latest DCF scenario",
            "method": "GET",
            "path": "/api/valuation/dcf/{ticker}",
            "state": state,
            "message": message,
        },
        {
            "name": "Saved DCF scenarios",
            "method": "GET",
            "path": "/api/valuation/dcf/{ticker}/scenarios",
            "state": state,
            "message": message,
        },
        {
            "name": "DCF scenario comparison",
            "method": "GET",
            "path": "/api/valuation/dcf/{ticker}/comparison",
            "state": state,
            "message": message,
        },
        {
            "name": "DCF scenario diff",
            "method": "GET",
            "path": "/api/valuation/dcf/{ticker}/compare",
            "state": state,
            "message": message,
        },
        {
            "name": "DCF assumption export",
            "method": "GET",
            "path": "/api/valuation/dcf/{ticker}/export/{scenarioId}",
            "state": state,
            "message": message,
        },
        {
            "name": "DCF assumption import",
            "method": "POST",
            "path": "/api/valuation/dcf/{ticker}/import",
            "state": state,
            "message": message,
        },
        {
            "name": "DCF scenario history",
            "method": "GET",
            "path": "/api/valuation/dcf/{ticker}/scenarios/{scenarioId}/history",
            "state": state,
            "message": message,
        },
        {
            "name": "DCF analyst notes",
            "method": "GET/POST",
            "path": "/api/valuation/dcf/{ticker}/scenarios/{scenarioId}/notes",
            "state": state,
            "message": message,
        },
        {
            "name": "DCF scenario lifecycle",
            "method": "POST/PATCH/DELETE",
            "path": "/api/valuation/dcf/{ticker}/scenarios/{scenarioId}/...",
            "state": state,
            "message": message,
        },
    ]
