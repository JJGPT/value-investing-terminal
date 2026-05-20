from fastapi import APIRouter

from app.core.config import get_settings

router = APIRouter(tags=["system"])


@router.get("/health")
def health_check() -> dict[str, str]:
    settings = get_settings()

    return {
        "status": "ok",
        "service": settings.app_name,
        "version": settings.version,
        "environment": settings.environment,
        "message": "API process is running. Use /api/status and /diagnostics routes for provider readiness.",
        "apiStatusPath": "/api/status",
        "diagnosticsPath": "/api/diagnostics/market-data",
        "docsPath": "/docs",
    }
