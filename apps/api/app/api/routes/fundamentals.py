from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query

from app.services.fundamentals.computed_metrics import (
    build_computed_metrics_response,
)
from app.services.fundamentals.provider import (
    FundamentalsProvider,
    get_fundamentals_provider,
)

router = APIRouter(prefix="/api/fundamentals", tags=["fundamentals"])

FundamentalsPeriod = Literal["annual", "quarter", "ttm"]
ProviderDependency = Annotated[FundamentalsProvider, Depends(get_fundamentals_provider)]


@router.get("/{ticker}/profile")
def company_profile(ticker: str, provider: ProviderDependency) -> dict:
    return provider.get_company_profile(ticker)


@router.get("/{ticker}/income-statement")
def income_statement(
    ticker: str,
    provider: ProviderDependency,
    period: FundamentalsPeriod = Query(default="annual"),
    limit: int = Query(default=5, ge=1, le=20),
) -> dict:
    return provider.get_income_statement(ticker, period, limit)


@router.get("/{ticker}/balance-sheet")
def balance_sheet(
    ticker: str,
    provider: ProviderDependency,
    period: FundamentalsPeriod = Query(default="annual"),
    limit: int = Query(default=5, ge=1, le=20),
) -> dict:
    return provider.get_balance_sheet(ticker, period, limit)


@router.get("/{ticker}/cash-flow")
def cash_flow_statement(
    ticker: str,
    provider: ProviderDependency,
    period: FundamentalsPeriod = Query(default="annual"),
    limit: int = Query(default=5, ge=1, le=20),
) -> dict:
    return provider.get_cash_flow_statement(ticker, period, limit)


@router.get("/{ticker}/metrics")
def key_metrics(
    ticker: str,
    provider: ProviderDependency,
    period: FundamentalsPeriod = Query(default="annual"),
    limit: int = Query(default=5, ge=1, le=20),
) -> dict:
    return provider.get_key_metrics(ticker, period, limit)


@router.get("/{ticker}/computed-metrics")
def computed_metrics(
    ticker: str,
    provider: ProviderDependency,
    period: FundamentalsPeriod = Query(default="annual"),
    limit: int = Query(default=5, ge=1, le=20),
) -> dict:
    return build_computed_metrics_response(provider, ticker, period, limit)
