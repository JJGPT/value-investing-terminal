from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.services.market_data.provider import (
    MarketDataProvider,
    get_market_data_provider,
)

router = APIRouter(prefix="/api/securities", tags=["securities"])


ProviderDependency = Annotated[MarketDataProvider, Depends(get_market_data_provider)]


@router.get("/search")
def search_securities(
    provider: ProviderDependency,
    q: str = Query(default="", min_length=0),
) -> dict:
    return provider.search_securities(q)


@router.get("/{ticker}")
def company_overview(ticker: str, provider: ProviderDependency) -> dict:
    return provider.get_security(ticker)


@router.get("/{ticker}/snapshot")
def market_snapshot(ticker: str, provider: ProviderDependency) -> dict:
    return provider.get_market_snapshot(ticker)
