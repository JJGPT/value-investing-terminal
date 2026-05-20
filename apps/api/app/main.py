from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.diagnostics import router as diagnostics_router
from app.api.routes.fundamentals import router as fundamentals_router
from app.api.routes.health import router as health_router
from app.api.routes.jobs import router as jobs_router
from app.api.routes.rankings import router as rankings_router
from app.api.routes.refresh_policies import router as refresh_policies_router
from app.api.routes.screener import router as screener_router
from app.api.routes.securities import router as securities_router
from app.api.routes.status import router as status_router
from app.api.routes.valuation import router as valuation_router
from app.api.routes.watchlists import router as watchlists_router
from app.core.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.version,
        description="Backend API for the Value Investing Terminal research workspace.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health_router)
    app.include_router(status_router)
    app.include_router(securities_router)
    app.include_router(watchlists_router)
    app.include_router(diagnostics_router)
    app.include_router(fundamentals_router)
    app.include_router(screener_router)
    app.include_router(rankings_router)
    app.include_router(jobs_router)
    app.include_router(refresh_policies_router)
    app.include_router(valuation_router)

    return app


app = create_app()
