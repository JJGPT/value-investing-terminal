import json
from typing import Annotated, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.config import Settings, get_settings
from app.services.fundamentals.provider import (
    FundamentalsProvider,
    get_fundamentals_provider,
)
from app.services.persistence.provider import get_snapshot_repository
from app.services.persistence.repository import SnapshotRepository
from app.services.screener.engine import (
    build_screener_response,
    refresh_screener_snapshots,
)

router = APIRouter(prefix="/api/screener", tags=["screener"])

ScreenerPeriod = Literal["annual", "quarter"]
ProviderDependency = Annotated[FundamentalsProvider, Depends(get_fundamentals_provider)]
RepositoryDependency = Annotated[SnapshotRepository, Depends(get_snapshot_repository)]
SettingsDependency = Annotated[Settings, Depends(get_settings)]


@router.get("")
def run_screener(
    provider: ProviderDependency,
    repository: RepositoryDependency,
    settings: SettingsDependency,
    filters: Optional[str] = Query(default=None),
    sort: Optional[str] = Query(default=None),
    period: ScreenerPeriod = Query(default="annual"),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=25, ge=1, le=100),
) -> dict:
    return build_screener_response(
        provider=provider,
        period=period,
        page=page,
        limit=limit,
        filters=parse_filters(filters),
        sort=parse_sort(sort),
        repository=repository,
        stale_after_seconds=settings.snapshot_stale_after_seconds,
    )


@router.post("/refresh")
def refresh_screener(
    provider: ProviderDependency,
    repository: RepositoryDependency,
    period: ScreenerPeriod = Query(default="annual"),
) -> dict:
    return refresh_screener_snapshots(
        provider=provider,
        repository=repository,
        period=period,
    )


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
