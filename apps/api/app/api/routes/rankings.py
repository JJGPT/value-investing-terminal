import json
from typing import Annotated, Literal, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query

from app.core.config import Settings, get_settings
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
from app.services.jobs.runner import run_ranking_refresh_job
from app.services.rankings.engine import (
    build_ranking_run_changes,
    build_magic_formula_response,
    build_ranking_response,
    create_ranking_screen,
    duplicate_ranking_screen,
    set_ranking_screen_lifecycle,
    update_ranking_screen,
)

router = APIRouter(prefix="/api/rankings", tags=["rankings"])

RankingStrategy = Literal[
    "magic_formula",
    "quality",
    "value",
    "growth",
    "profitability",
]
RankingPeriod = Literal["annual", "quarter"]
FundamentalsProviderDependency = Annotated[
    FundamentalsProvider,
    Depends(get_fundamentals_provider),
]
MarketDataProviderDependency = Annotated[
    MarketDataProvider,
    Depends(get_market_data_provider),
]
RepositoryDependency = Annotated[SnapshotRepository, Depends(get_snapshot_repository)]
SettingsDependency = Annotated[Settings, Depends(get_settings)]


@router.get("/magic-formula")
def get_magic_formula_ranking(
    fundamentals_provider: FundamentalsProviderDependency,
    market_data_provider: MarketDataProviderDependency,
    repository: RepositoryDependency,
    settings: SettingsDependency,
    period: RankingPeriod = Query(default="annual"),
    limit: int = Query(default=50, ge=1, le=100),
) -> dict:
    return build_magic_formula_response(
        fundamentals_provider,
        market_data_provider,
        repository,
        period,
        limit,
        stale_after_seconds=settings.snapshot_stale_after_seconds,
    )


@router.get("")
def get_ranking(
    fundamentals_provider: FundamentalsProviderDependency,
    market_data_provider: MarketDataProviderDependency,
    repository: RepositoryDependency,
    settings: SettingsDependency,
    strategy: RankingStrategy = Query(default="magic_formula"),
    period: RankingPeriod = Query(default="annual"),
    limit: int = Query(default=50, ge=1, le=100),
    include_ineligible: bool = Query(default=True, alias="includeIneligible"),
    filters: Optional[str] = Query(default=None),
    sort: Optional[str] = Query(default=None),
    screen_id: Optional[str] = Query(default=None, alias="screenId"),
) -> dict:
    screen = load_screen_or_404(repository, screen_id) if screen_id else None

    return build_ranking_response(
        fundamentals_provider,
        market_data_provider,
        repository,
        screen.get("strategy") if screen else strategy,
        screen.get("period") if screen else period,
        screen.get("limit") if screen else limit,
        stale_after_seconds=settings.snapshot_stale_after_seconds,
        include_ineligible=include_ineligible,
        eligibility_settings=(screen or {}).get("eligibilitySettings"),
        filters=(screen or {}).get("filters") or parse_filters(filters),
        sorting=(screen or {}).get("sorting") or parse_sort(sort),
    )


@router.post("/refresh")
def refresh_ranking(
    fundamentals_provider: FundamentalsProviderDependency,
    market_data_provider: MarketDataProviderDependency,
    repository: RepositoryDependency,
    settings: SettingsDependency,
    strategy: RankingStrategy = Query(default="magic_formula"),
    period: RankingPeriod = Query(default="annual"),
    scope: str = Query(default="universe"),
    tickers: Optional[str] = Query(default=None),
    stale_only: bool = Query(default=False, alias="staleOnly"),
    screen_id: Optional[str] = Query(default=None, alias="screenId"),
) -> dict:
    if screen_id:
        load_screen_or_404(repository, screen_id)

    return run_ranking_refresh_job(
        fundamentals_provider,
        market_data_provider,
        repository,
        strategy,
        period,
        settings.snapshot_stale_after_seconds,
        screen_id=screen_id,
        scope_type=scope,
        tickers=parse_tickers(tickers),
        stale_only=stale_only,
    )


@router.get("/screens")
def list_saved_ranking_screens(
    repository: RepositoryDependency,
    include_archived: bool = Query(default=False, alias="includeArchived"),
    include_deleted: bool = Query(default=False, alias="includeDeleted"),
    limit: int = Query(default=25, ge=1, le=100),
) -> dict:
    return {
        "screens": repository.list_ranking_screens(
            include_archived,
            include_deleted,
            limit,
        ),
        "message": "Saved ranking screens are deterministic reusable screen definitions.",
    }


@router.post("/screens")
def create_saved_ranking_screen(
    repository: RepositoryDependency,
    payload: Optional[dict] = Body(default=None),
) -> dict:
    return create_ranking_screen(repository, payload or {})


@router.get("/screens/{screen_id}")
def get_saved_ranking_screen(
    repository: RepositoryDependency,
    screen_id: str,
) -> dict:
    return load_screen_or_404(repository, screen_id)


@router.patch("/screens/{screen_id}")
def patch_saved_ranking_screen(
    repository: RepositoryDependency,
    screen_id: str,
    payload: Optional[dict] = Body(default=None),
) -> dict:
    screen = update_ranking_screen(repository, screen_id, payload or {})

    if screen is None:
        raise HTTPException(status_code=404, detail="Saved ranking screen not found.")

    return screen


@router.post("/screens/{screen_id}/duplicate")
def duplicate_saved_ranking_screen(
    repository: RepositoryDependency,
    screen_id: str,
    payload: Optional[dict] = Body(default=None),
) -> dict:
    screen = duplicate_ranking_screen(repository, screen_id, payload or {})

    if screen is None:
        raise HTTPException(status_code=404, detail="Saved ranking screen not found.")

    return screen


@router.post("/screens/{screen_id}/archive")
def archive_saved_ranking_screen(
    repository: RepositoryDependency,
    screen_id: str,
) -> dict:
    return lifecycle_screen_or_404(repository, screen_id, "archive")


@router.post("/screens/{screen_id}/restore")
def restore_saved_ranking_screen(
    repository: RepositoryDependency,
    screen_id: str,
) -> dict:
    return lifecycle_screen_or_404(repository, screen_id, "restore")


@router.delete("/screens/{screen_id}")
def delete_saved_ranking_screen(
    repository: RepositoryDependency,
    screen_id: str,
) -> dict:
    return lifecycle_screen_or_404(repository, screen_id, "delete")


@router.get("/refresh-runs")
def list_ranking_refresh_runs(
    repository: RepositoryDependency,
    strategy: Optional[RankingStrategy] = Query(default=None),
    period: Optional[RankingPeriod] = Query(default=None),
    limit: int = Query(default=10, ge=1, le=100),
) -> dict:
    return {
        "refreshRuns": repository.list_ranking_refresh_runs(strategy, period, limit),
        "message": "Ranking refresh workflow runs are synchronous execution records.",
    }


@router.get("/runs")
def list_ranking_runs(
    repository: RepositoryDependency,
    strategy: Optional[RankingStrategy] = Query(default=None),
    period: Optional[RankingPeriod] = Query(default=None),
    limit: int = Query(default=10, ge=1, le=100),
) -> dict:
    return {
        "runs": repository.list_ranking_runs(strategy, period, limit),
        "message": "Ranking runs are immutable SQLite JSON snapshots.",
    }


@router.get("/runs/{run_id}")
def get_ranking_run(
    repository: RepositoryDependency,
    run_id: str,
) -> dict:
    run = repository.get_ranking_run(run_id)

    if run is None:
        raise HTTPException(status_code=404, detail="Ranking run not found.")

    return run


@router.get("/runs/{run_id}/changes")
def get_ranking_run_changes(
    repository: RepositoryDependency,
    run_id: str,
) -> dict:
    changes = build_ranking_run_changes(repository, run_id)

    if changes["run"] is None:
        raise HTTPException(status_code=404, detail="Ranking run not found.")

    return changes


def load_screen_or_404(repository: SnapshotRepository, screen_id: str) -> dict:
    screen = repository.get_ranking_screen(screen_id)

    if screen is None:
        raise HTTPException(status_code=404, detail="Saved ranking screen not found.")

    return screen


def lifecycle_screen_or_404(
    repository: SnapshotRepository,
    screen_id: str,
    action: str,
) -> dict:
    screen = set_ranking_screen_lifecycle(repository, screen_id, action)

    if screen is None:
        raise HTTPException(status_code=404, detail="Saved ranking screen not found.")

    return screen


def parse_filters(raw_filters: Optional[str]) -> list[dict]:
    if not raw_filters:
        return []

    try:
        payload = json.loads(raw_filters)
    except json.JSONDecodeError as error:
        raise HTTPException(
            status_code=400,
            detail="filters must be a JSON object or array.",
        ) from error

    if isinstance(payload, dict):
        return [payload]

    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]

    raise HTTPException(
        status_code=400,
        detail="filters must be a JSON object or array.",
    )


def parse_sort(raw_sort: Optional[str]) -> Optional[dict]:
    if not raw_sort:
        return None

    if ":" in raw_sort and not raw_sort.lstrip().startswith("{"):
        field, direction = raw_sort.split(":", 1)

        return {
            "field": field,
            "direction": direction,
        }

    try:
        payload = json.loads(raw_sort)
    except json.JSONDecodeError as error:
        raise HTTPException(
            status_code=400,
            detail="sort must be a JSON object or field:direction shorthand.",
        ) from error

    if isinstance(payload, dict):
        return payload

    raise HTTPException(
        status_code=400,
        detail="sort must be a JSON object or field:direction shorthand.",
    )


def parse_tickers(raw_tickers: Optional[str]) -> Optional[list[str]]:
    if not raw_tickers:
        return None

    return [
        ticker.strip().upper()
        for ticker in raw_tickers.split(",")
        if ticker.strip()
    ]
