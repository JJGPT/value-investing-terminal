from typing import Annotated, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query

from app.services.fundamentals.provider import (
    FundamentalsProvider,
    get_fundamentals_provider,
)
from app.services.market_data.provider import (
    MarketDataProvider,
    get_market_data_provider,
)
from app.services.persistence.provider import get_snapshot_repository
from app.services.persistence.repository import SnapshotRepository
from app.services.valuation.dcf import (
    add_dcf_note,
    build_dcf_comparison,
    build_dcf_result,
    build_dcf_sensitivity,
    build_dcf_history,
    build_dcf_scenario_version,
    build_dcf_scenario_diff,
    duplicate_dcf_scenario,
    export_dcf_assumptions,
    get_or_build_dcf_result,
    get_saved_dcf_result,
    import_dcf_assumptions,
    list_dcf_notes,
    list_dcf_scenarios,
    rename_dcf_scenario,
    set_dcf_scenario_status,
)

router = APIRouter(prefix="/api/valuation", tags=["valuation"])

FundamentalsProviderDependency = Annotated[
    FundamentalsProvider,
    Depends(get_fundamentals_provider),
]
MarketDataProviderDependency = Annotated[
    MarketDataProvider,
    Depends(get_market_data_provider),
]
RepositoryDependency = Annotated[SnapshotRepository, Depends(get_snapshot_repository)]


@router.post("/dcf/{ticker}")
def create_dcf_result(
    ticker: str,
    fundamentals_provider: FundamentalsProviderDependency,
    market_data_provider: MarketDataProviderDependency,
    repository: RepositoryDependency,
    payload: Optional[dict] = Body(default=None),
) -> dict:
    return build_dcf_result(
        ticker,
        fundamentals_provider,
        market_data_provider,
        overrides=payload or {},
        persist=True,
        repository=repository,
    )


@router.get("/dcf/{ticker}")
def get_dcf_result(
    ticker: str,
    fundamentals_provider: FundamentalsProviderDependency,
    market_data_provider: MarketDataProviderDependency,
    repository: RepositoryDependency,
) -> dict:
    return get_or_build_dcf_result(
        ticker,
        fundamentals_provider,
        market_data_provider,
        repository,
    )


@router.get("/dcf/{ticker}/scenarios")
def list_dcf_results(
    ticker: str,
    repository: RepositoryDependency,
    limit: int = Query(default=10, ge=1, le=50),
    includeArchived: bool = Query(default=False),
    includeDeleted: bool = Query(default=False),
) -> dict:
    return list_dcf_scenarios(
        ticker,
        repository,
        limit,
        includeArchived,
        includeDeleted,
    )


@router.get("/dcf/{ticker}/scenarios/{scenario_id}")
def get_saved_dcf_scenario(
    ticker: str,
    scenario_id: str,
    repository: RepositoryDependency,
) -> dict:
    result = get_saved_dcf_result(ticker, scenario_id, repository)

    if result is None:
        raise HTTPException(status_code=404, detail="DCF scenario not found.")

    return result


@router.post("/dcf/{ticker}/scenarios/{scenario_id}/versions")
def create_dcf_scenario_version(
    ticker: str,
    scenario_id: str,
    fundamentals_provider: FundamentalsProviderDependency,
    market_data_provider: MarketDataProviderDependency,
    repository: RepositoryDependency,
    payload: Optional[dict] = Body(default=None),
) -> dict:
    try:
        return build_dcf_scenario_version(
            ticker,
            scenario_id,
            fundamentals_provider,
            market_data_provider,
            repository,
            payload or {},
        )
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.patch("/dcf/{ticker}/scenarios/{scenario_id}/rename")
def rename_scenario(
    ticker: str,
    scenario_id: str,
    repository: RepositoryDependency,
    payload: Optional[dict] = Body(default=None),
) -> dict:
    try:
        return rename_dcf_scenario(
            ticker,
            scenario_id,
            repository,
            (payload or {}).get("name") or (payload or {}).get("scenarioName") or "",
        )
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post("/dcf/{ticker}/scenarios/{scenario_id}/duplicate")
def duplicate_scenario(
    ticker: str,
    scenario_id: str,
    repository: RepositoryDependency,
    payload: Optional[dict] = Body(default=None),
) -> dict:
    try:
        return duplicate_dcf_scenario(
            ticker,
            scenario_id,
            repository,
            (payload or {}).get("name") or (payload or {}).get("scenarioName"),
        )
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post("/dcf/{ticker}/scenarios/{scenario_id}/archive")
def archive_scenario(
    ticker: str,
    scenario_id: str,
    repository: RepositoryDependency,
) -> dict:
    try:
        return set_dcf_scenario_status(ticker, scenario_id, repository, "archived")
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post("/dcf/{ticker}/scenarios/{scenario_id}/restore")
def restore_scenario(
    ticker: str,
    scenario_id: str,
    repository: RepositoryDependency,
) -> dict:
    try:
        return set_dcf_scenario_status(ticker, scenario_id, repository, "active")
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.delete("/dcf/{ticker}/scenarios/{scenario_id}")
def soft_delete_scenario(
    ticker: str,
    scenario_id: str,
    repository: RepositoryDependency,
) -> dict:
    try:
        return set_dcf_scenario_status(ticker, scenario_id, repository, "deleted")
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.get("/dcf/{ticker}/scenarios/{scenario_id}/history")
def scenario_history(
    ticker: str,
    scenario_id: str,
    repository: RepositoryDependency,
) -> dict:
    try:
        return build_dcf_history(ticker, scenario_id, repository)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.get("/dcf/{ticker}/scenarios/{scenario_id}/notes")
def scenario_notes(
    ticker: str,
    scenario_id: str,
    repository: RepositoryDependency,
) -> dict:
    try:
        return list_dcf_notes(ticker, scenario_id, repository)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post("/dcf/{ticker}/scenarios/{scenario_id}/notes")
def create_scenario_note(
    ticker: str,
    scenario_id: str,
    repository: RepositoryDependency,
    payload: Optional[dict] = Body(default=None),
) -> dict:
    try:
        return add_dcf_note(ticker, scenario_id, repository, payload or {})
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get("/dcf/{ticker}/comparison")
def get_dcf_comparison(
    ticker: str,
    repository: RepositoryDependency,
    limit: int = Query(default=5, ge=1, le=20),
) -> dict:
    return build_dcf_comparison(ticker, repository, limit)


@router.get("/dcf/{ticker}/compare")
def get_dcf_scenario_diff(
    ticker: str,
    repository: RepositoryDependency,
    leftScenarioId: str = Query(),
    rightScenarioId: str = Query(),
    leftVersionId: Optional[str] = Query(default=None),
    rightVersionId: Optional[str] = Query(default=None),
) -> dict:
    try:
        return build_dcf_scenario_diff(
            ticker,
            repository,
            leftScenarioId,
            rightScenarioId,
            leftVersionId,
            rightVersionId,
        )
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.get("/dcf/{ticker}/export/{scenario_id}")
def export_dcf_scenario_assumptions(
    ticker: str,
    scenario_id: str,
    repository: RepositoryDependency,
) -> dict:
    try:
        return export_dcf_assumptions(ticker, scenario_id, repository)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post("/dcf/{ticker}/import")
def import_dcf_scenario_assumptions(
    ticker: str,
    fundamentals_provider: FundamentalsProviderDependency,
    market_data_provider: MarketDataProviderDependency,
    repository: RepositoryDependency,
    payload: Optional[dict] = Body(default=None),
) -> dict:
    try:
        return import_dcf_assumptions(
            ticker,
            fundamentals_provider,
            market_data_provider,
            repository,
            payload or {},
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get("/dcf/{ticker}/sensitivity")
def get_dcf_sensitivity(
    ticker: str,
    fundamentals_provider: FundamentalsProviderDependency,
    market_data_provider: MarketDataProviderDependency,
    repository: RepositoryDependency,
) -> dict:
    return build_dcf_sensitivity(
        ticker,
        fundamentals_provider,
        market_data_provider,
        repository,
    )
