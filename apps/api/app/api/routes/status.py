from fastapi import APIRouter

from app.core.config import get_settings
from app.services.fundamentals.provider import get_fundamentals_provider
from app.services.market_data.provider import get_market_data_provider
from app.services.provider_status import provider_not_connected

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/status")
def api_status() -> dict:
    settings = get_settings()

    return {
        "status": "ok",
        "service": settings.app_name,
        "version": settings.version,
        "environment": settings.environment,
        "message": (
            "API contracts are available. Backend-only providers report their "
            "current connection state."
        ),
        "providers": [
            get_market_data_provider().provider_status(),
            get_fundamentals_provider().provider_status(),
            provider_not_connected("sec", ["SEC_USER_AGENT"]),
            provider_not_connected("news", ["NEWS_API_KEY"]),
        ],
    }
