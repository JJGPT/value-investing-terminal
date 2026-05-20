import json
from typing import Annotated, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

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
from app.services.watchlists import (
    add_watchlist_item,
    build_watchlist_alerts,
    build_watchlist_alert_history,
    build_watchlist_intelligence,
    build_watchlist_refresh_history,
    build_watchlist_staleness,
    create_watchlist_view,
    create_watchlist,
    duplicate_watchlist_view,
    list_watchlists_response,
    list_watchlist_views_response,
    remove_watchlist_item,
    run_watchlist_refresh_job,
    set_watchlist_lifecycle,
    set_watchlist_view_lifecycle,
    update_watchlist,
    update_watchlist_alert_lifecycle,
    update_watchlist_item,
    update_watchlist_view,
    with_provider,
)

router = APIRouter(prefix="/api/watchlists", tags=["watchlists"])

RepositoryDependency = Annotated[SnapshotRepository, Depends(get_snapshot_repository)]
MarketDataProviderDependency = Annotated[
    MarketDataProvider,
    Depends(get_market_data_provider),
]
FundamentalsProviderDependency = Annotated[
    FundamentalsProvider,
    Depends(get_fundamentals_provider),
]
SettingsDependency = Annotated[Settings, Depends(get_settings)]


class CreateWatchlistRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: Optional[str] = Field(default=None, max_length=500)


class UpdateWatchlistRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    description: Optional[str] = Field(default=None, max_length=500)


class AddWatchlistItemRequest(BaseModel):
    ticker: str = Field(min_length=1, max_length=16)
    companyName: Optional[str] = Field(default=None, max_length=180)
    notes: Optional[str] = Field(default=None, max_length=1000)
    tags: list[str] = Field(default_factory=list, max_length=12)
    targetPrice: Optional[float] = None
    thesisStatus: Optional[str] = Field(default=None, max_length=80)
    priority: Optional[str] = Field(default=None, max_length=40)
    workflowState: Optional[str] = Field(default=None, max_length=40)


class UpdateWatchlistItemRequest(BaseModel):
    companyName: Optional[str] = Field(default=None, max_length=180)
    notes: Optional[str] = Field(default=None, max_length=1000)
    tags: Optional[list[str]] = Field(default=None, max_length=12)
    targetPrice: Optional[float] = None
    thesisStatus: Optional[str] = Field(default=None, max_length=80)
    priority: Optional[str] = Field(default=None, max_length=40)
    workflowState: Optional[str] = Field(default=None, max_length=40)


class WatchlistViewRequest(BaseModel):
    name: Optional[str] = Field(default=None, max_length=120)
    filters: list[dict] = Field(default_factory=list)
    sorting: Optional[dict] = None
    visibleColumns: list[str] = Field(default_factory=list, max_length=32)


class AlertAcknowledgementRequest(BaseModel):
    acknowledgedBy: Optional[str] = Field(default="local-user", max_length=120)


@router.get("")
def list_watchlists(
    repository: RepositoryDependency,
    include_archived: bool = Query(default=False, alias="includeArchived"),
    include_deleted: bool = Query(default=False, alias="includeDeleted"),
    limit: int = Query(default=50, ge=1, le=100),
) -> dict:
    return list_watchlists_response(
        repository,
        include_archived,
        include_deleted,
        limit,
    )


@router.post("", status_code=status.HTTP_201_CREATED)
def create_watchlist_route(
    repository: RepositoryDependency,
    payload: CreateWatchlistRequest,
) -> dict:
    return create_watchlist(repository, payload.model_dump())


@router.get("/{watchlist_id}/views")
def list_watchlist_views(
    repository: RepositoryDependency,
    watchlist_id: str,
    include_archived: bool = Query(default=False, alias="includeArchived"),
    include_deleted: bool = Query(default=False, alias="includeDeleted"),
    limit: int = Query(default=50, ge=1, le=100),
) -> dict:
    result = list_watchlist_views_response(
        repository,
        watchlist_id,
        include_archived,
        include_deleted,
        limit,
    )

    if result is None:
        raise HTTPException(status_code=404, detail="Watchlist not found.")

    return result


@router.post("/{watchlist_id}/views", status_code=status.HTTP_201_CREATED)
def create_watchlist_view_route(
    repository: RepositoryDependency,
    watchlist_id: str,
    payload: WatchlistViewRequest,
) -> dict:
    view = create_watchlist_view(repository, watchlist_id, payload.model_dump())

    if view is None:
        raise HTTPException(status_code=404, detail="Watchlist not found.")

    return view


@router.get("/{watchlist_id}/views/{view_id}")
def get_watchlist_view(
    repository: RepositoryDependency,
    watchlist_id: str,
    view_id: str,
) -> dict:
    view = repository.get_watchlist_view(watchlist_id, view_id)

    if view is None:
        raise HTTPException(status_code=404, detail="Watchlist view not found.")

    return view


@router.patch("/{watchlist_id}/views/{view_id}")
def patch_watchlist_view(
    repository: RepositoryDependency,
    watchlist_id: str,
    view_id: str,
    payload: WatchlistViewRequest,
) -> dict:
    view = update_watchlist_view(
        repository,
        watchlist_id,
        view_id,
        payload.model_dump(exclude_unset=True),
    )

    if view is None:
        raise HTTPException(status_code=404, detail="Watchlist view not found.")

    return view


@router.post("/{watchlist_id}/views/{view_id}/duplicate")
def duplicate_watchlist_view_route(
    repository: RepositoryDependency,
    watchlist_id: str,
    view_id: str,
    payload: Optional[dict] = Body(default=None),
) -> dict:
    view = duplicate_watchlist_view(repository, watchlist_id, view_id, payload or {})

    if view is None:
        raise HTTPException(status_code=404, detail="Watchlist view not found.")

    return view


@router.post("/{watchlist_id}/views/{view_id}/archive")
def archive_watchlist_view(
    repository: RepositoryDependency,
    watchlist_id: str,
    view_id: str,
) -> dict:
    return view_lifecycle_or_404(repository, watchlist_id, view_id, "archive")


@router.post("/{watchlist_id}/views/{view_id}/restore")
def restore_watchlist_view(
    repository: RepositoryDependency,
    watchlist_id: str,
    view_id: str,
) -> dict:
    return view_lifecycle_or_404(repository, watchlist_id, view_id, "restore")


@router.delete("/{watchlist_id}/views/{view_id}")
def delete_watchlist_view(
    repository: RepositoryDependency,
    watchlist_id: str,
    view_id: str,
) -> dict:
    return view_lifecycle_or_404(repository, watchlist_id, view_id, "delete")


@router.get("/{watchlist_id}")
def get_watchlist(
    repository: RepositoryDependency,
    watchlist_id: str,
) -> dict:
    watchlist = repository.get_watchlist(watchlist_id)

    if watchlist is None:
        raise HTTPException(status_code=404, detail="Watchlist not found.")

    return with_provider(watchlist, repository)


@router.patch("/{watchlist_id}")
def patch_watchlist(
    repository: RepositoryDependency,
    watchlist_id: str,
    payload: UpdateWatchlistRequest,
) -> dict:
    watchlist = update_watchlist(
        repository,
        watchlist_id,
        payload.model_dump(exclude_unset=True),
    )

    if watchlist is None:
        raise HTTPException(status_code=404, detail="Watchlist not found.")

    return watchlist


@router.post("/{watchlist_id}/archive")
def archive_watchlist(
    repository: RepositoryDependency,
    watchlist_id: str,
) -> dict:
    return lifecycle_or_404(repository, watchlist_id, "archive")


@router.post("/{watchlist_id}/restore")
def restore_watchlist(
    repository: RepositoryDependency,
    watchlist_id: str,
) -> dict:
    return lifecycle_or_404(repository, watchlist_id, "restore")


@router.delete("/{watchlist_id}")
def soft_delete_watchlist(
    repository: RepositoryDependency,
    watchlist_id: str,
) -> dict:
    return lifecycle_or_404(repository, watchlist_id, "delete")


@router.post("/{watchlist_id}/items", status_code=status.HTTP_201_CREATED)
def add_watchlist_item_route(
    repository: RepositoryDependency,
    watchlist_id: str,
    payload: AddWatchlistItemRequest,
) -> dict:
    watchlist = add_watchlist_item(
        repository,
        watchlist_id,
        payload.model_dump(),
    )

    if watchlist is None:
        raise HTTPException(status_code=404, detail="Watchlist not found.")

    return watchlist


@router.patch("/{watchlist_id}/items/{ticker}")
def patch_watchlist_item(
    repository: RepositoryDependency,
    watchlist_id: str,
    ticker: str,
    payload: UpdateWatchlistItemRequest,
) -> dict:
    watchlist = update_watchlist_item(
        repository,
        watchlist_id,
        ticker,
        payload.model_dump(exclude_unset=True),
    )

    if watchlist is None:
        raise HTTPException(status_code=404, detail="Watchlist item not found.")

    return watchlist


@router.delete("/{watchlist_id}/items/{ticker}")
def delete_watchlist_item(
    repository: RepositoryDependency,
    watchlist_id: str,
    ticker: str,
) -> dict:
    watchlist = remove_watchlist_item(repository, watchlist_id, ticker)

    if watchlist is None:
        raise HTTPException(status_code=404, detail="Watchlist not found.")

    return watchlist


@router.get("/{watchlist_id}/intelligence")
def watchlist_intelligence(
    repository: RepositoryDependency,
    market_data_provider: MarketDataProviderDependency,
    settings: SettingsDependency,
    watchlist_id: str,
    filters: Optional[str] = Query(default=None),
    sort: Optional[str] = Query(default=None),
    view_id: Optional[str] = Query(default=None, alias="viewId"),
) -> dict:
    result = build_watchlist_intelligence(
        repository,
        market_data_provider,
        watchlist_id,
        settings.snapshot_stale_after_seconds,
        filters=parse_json_list(filters),
        sorting=parse_json_dict(sort),
        view_id=view_id,
    )

    if result is None:
        raise HTTPException(status_code=404, detail="Watchlist not found.")

    return result


@router.get("/{watchlist_id}/alerts")
def watchlist_alerts(
    repository: RepositoryDependency,
    market_data_provider: MarketDataProviderDependency,
    settings: SettingsDependency,
    watchlist_id: str,
    include_dismissed: bool = Query(default=False, alias="includeDismissed"),
) -> dict:
    result = build_watchlist_alerts(
        repository,
        market_data_provider,
        watchlist_id,
        settings.snapshot_stale_after_seconds,
        include_dismissed=include_dismissed,
    )

    if result is None:
        raise HTTPException(status_code=404, detail="Watchlist not found.")

    return result


@router.get("/{watchlist_id}/alerts/history")
def watchlist_alert_history(
    repository: RepositoryDependency,
    market_data_provider: MarketDataProviderDependency,
    settings: SettingsDependency,
    watchlist_id: str,
) -> dict:
    result = build_watchlist_alert_history(
        repository,
        market_data_provider,
        watchlist_id,
        settings.snapshot_stale_after_seconds,
    )

    if result is None:
        raise HTTPException(status_code=404, detail="Watchlist not found.")

    return result


@router.post("/{watchlist_id}/refresh")
def refresh_watchlist(
    fundamentals_provider: FundamentalsProviderDependency,
    market_data_provider: MarketDataProviderDependency,
    repository: RepositoryDependency,
    settings: SettingsDependency,
    watchlist_id: str,
    period: str = Query(default="annual", pattern="^(annual|quarter)$"),
    strategy: str = Query(default="magic_formula"),
    stale_only: bool = Query(default=True, alias="staleOnly"),
) -> dict:
    result = run_watchlist_refresh_job(
        fundamentals_provider,
        market_data_provider,
        repository,
        watchlist_id,
        period,
        settings.snapshot_stale_after_seconds,
        strategy=strategy,
        stale_only=stale_only,
    )

    if result is None:
        raise HTTPException(status_code=404, detail="Watchlist not found.")

    return result


@router.get("/{watchlist_id}/refresh-history")
def watchlist_refresh_history(
    repository: RepositoryDependency,
    watchlist_id: str,
    limit: int = Query(default=25, ge=1, le=100),
) -> dict:
    result = build_watchlist_refresh_history(repository, watchlist_id, limit)

    if result is None:
        raise HTTPException(status_code=404, detail="Watchlist not found.")

    return result


@router.get("/{watchlist_id}/staleness")
def watchlist_staleness(
    repository: RepositoryDependency,
    market_data_provider: MarketDataProviderDependency,
    settings: SettingsDependency,
    watchlist_id: str,
) -> dict:
    result = build_watchlist_staleness(
        repository,
        market_data_provider,
        watchlist_id,
        settings.snapshot_stale_after_seconds,
    )

    if result is None:
        raise HTTPException(status_code=404, detail="Watchlist not found.")

    return result


@router.post("/{watchlist_id}/alerts/{alert_id}/acknowledge")
def acknowledge_watchlist_alert(
    repository: RepositoryDependency,
    market_data_provider: MarketDataProviderDependency,
    settings: SettingsDependency,
    watchlist_id: str,
    alert_id: str,
    payload: Optional[AlertAcknowledgementRequest] = Body(default=None),
) -> dict:
    return alert_lifecycle_or_404(
        repository,
        market_data_provider,
        settings,
        watchlist_id,
        alert_id,
        "acknowledge",
        (payload.acknowledgedBy if payload else "local-user"),
    )


@router.post("/{watchlist_id}/alerts/{alert_id}/dismiss")
def dismiss_watchlist_alert(
    repository: RepositoryDependency,
    market_data_provider: MarketDataProviderDependency,
    settings: SettingsDependency,
    watchlist_id: str,
    alert_id: str,
) -> dict:
    return alert_lifecycle_or_404(
        repository,
        market_data_provider,
        settings,
        watchlist_id,
        alert_id,
        "dismiss",
        None,
    )


@router.post("/{watchlist_id}/alerts/{alert_id}/restore")
def restore_watchlist_alert(
    repository: RepositoryDependency,
    market_data_provider: MarketDataProviderDependency,
    settings: SettingsDependency,
    watchlist_id: str,
    alert_id: str,
) -> dict:
    return alert_lifecycle_or_404(
        repository,
        market_data_provider,
        settings,
        watchlist_id,
        alert_id,
        "restore",
        None,
    )


def lifecycle_or_404(
    repository: SnapshotRepository,
    watchlist_id: str,
    action: str,
) -> dict:
    watchlist = set_watchlist_lifecycle(repository, watchlist_id, action)

    if watchlist is None:
        raise HTTPException(status_code=404, detail="Watchlist not found.")

    return watchlist


def view_lifecycle_or_404(
    repository: SnapshotRepository,
    watchlist_id: str,
    view_id: str,
    action: str,
) -> dict:
    view = set_watchlist_view_lifecycle(repository, watchlist_id, view_id, action)

    if view is None:
        raise HTTPException(status_code=404, detail="Watchlist view not found.")

    return view


def alert_lifecycle_or_404(
    repository: SnapshotRepository,
    market_data_provider: MarketDataProvider,
    settings: Settings,
    watchlist_id: str,
    alert_id: str,
    action: str,
    acknowledged_by: Optional[str],
) -> dict:
    alert = update_watchlist_alert_lifecycle(
        repository,
        market_data_provider,
        watchlist_id,
        alert_id,
        action,
        settings.snapshot_stale_after_seconds,
        acknowledged_by,
    )

    if alert is None:
        raise HTTPException(status_code=404, detail="Watchlist alert not found.")

    return alert


def parse_json_list(value: Optional[str]) -> Optional[list[dict]]:
    if not value:
        return None

    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return None

    return parsed if isinstance(parsed, list) else None


def parse_json_dict(value: Optional[str]) -> Optional[dict]:
    if not value:
        return None

    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return None

    return parsed if isinstance(parsed, dict) else None
