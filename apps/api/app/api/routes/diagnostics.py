from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.config import Settings, get_settings
from app.services.fundamentals.diagnostics import build_fundamentals_diagnostics
from app.services.fundamentals.provider import (
    FundamentalsProvider,
    get_fundamentals_provider,
)
from app.services.market_data.diagnostics import (
    build_market_data_diagnostics,
    build_market_data_probe,
)
from app.services.market_data.provider import (
    MarketDataProvider,
    get_market_data_provider,
)
from app.services.persistence.provider import get_snapshot_repository
from app.services.persistence.repository import SnapshotRepository
from app.services.rankings.engine import build_ranking_diagnostics
from app.services.valuation.diagnostics import build_valuation_diagnostics
from app.services.watchlists import build_watchlist_diagnostics

router = APIRouter(prefix="/api/diagnostics", tags=["diagnostics"])

MarketDataProviderDependency = Annotated[
    MarketDataProvider,
    Depends(get_market_data_provider),
]
FundamentalsProviderDependency = Annotated[
    FundamentalsProvider,
    Depends(get_fundamentals_provider),
]
SettingsDependency = Annotated[Settings, Depends(get_settings)]
RepositoryDependency = Annotated[SnapshotRepository, Depends(get_snapshot_repository)]


@router.get("/market-data")
def market_data_diagnostics(
    provider: MarketDataProviderDependency,
    settings: SettingsDependency,
) -> dict:
    return build_market_data_diagnostics(provider, settings)


@router.get("/market-data/probe")
def market_data_probe(
    provider: MarketDataProviderDependency,
    ticker: str = "AAPL",
) -> dict:
    return build_market_data_probe(provider, ticker)


@router.get("/fundamentals")
def fundamentals_diagnostics(
    provider: FundamentalsProviderDependency,
    settings: SettingsDependency,
    repository: RepositoryDependency,
) -> dict:
    return build_fundamentals_diagnostics(provider, settings, repository)


@router.get("/valuation")
def valuation_diagnostics(
    repository: RepositoryDependency,
    ticker: str = "AAPL",
) -> dict:
    return build_valuation_diagnostics(repository, ticker)


@router.get("/rankings")
def rankings_diagnostics(
    fundamentals_provider: FundamentalsProviderDependency,
    market_data_provider: MarketDataProviderDependency,
    settings: SettingsDependency,
    repository: RepositoryDependency,
) -> dict:
    return build_ranking_diagnostics(
        fundamentals_provider,
        market_data_provider,
        repository,
        settings.snapshot_stale_after_seconds,
    )


@router.get("/watchlists")
def watchlists_diagnostics(
    market_data_provider: MarketDataProviderDependency,
    settings: SettingsDependency,
    repository: RepositoryDependency,
) -> dict:
    return build_watchlist_diagnostics(
        repository,
        market_data_provider,
        settings.snapshot_stale_after_seconds,
    )
