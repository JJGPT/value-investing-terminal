from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

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
from app.services.refresh_policies import (
    create_refresh_policy,
    run_refresh_policy_now,
    set_refresh_policy_enabled,
    update_refresh_policy,
)

router = APIRouter(prefix="/api/refresh-policies", tags=["refresh-policies"])

FundamentalsProviderDependency = Annotated[
    FundamentalsProvider,
    Depends(get_fundamentals_provider),
]
MarketDataProviderDependency = Annotated[
    MarketDataProvider,
    Depends(get_market_data_provider),
]
RepositoryDependency = Annotated[SnapshotRepository, Depends(get_snapshot_repository)]


@router.get("")
def list_policies(
    repository: RepositoryDependency,
    include_disabled: bool = Query(default=True, alias="includeDisabled"),
    limit: int = Query(default=50, ge=1, le=100),
) -> dict:
    policies = repository.list_refresh_policies(include_disabled, limit)

    return {
        "policies": policies,
        "message": "Refresh policies are local SQLite orchestration records.",
    }


@router.post("")
def create_policy(
    repository: RepositoryDependency,
    payload: dict,
) -> dict:
    return create_refresh_policy(repository, payload)


@router.get("/{policy_id}")
def get_policy(
    repository: RepositoryDependency,
    policy_id: str,
) -> dict:
    policy = repository.get_refresh_policy(policy_id)

    if policy is None:
        raise HTTPException(status_code=404, detail="Refresh policy not found.")

    return policy


@router.patch("/{policy_id}")
def patch_policy(
    repository: RepositoryDependency,
    policy_id: str,
    payload: dict,
) -> dict:
    policy = update_refresh_policy(repository, policy_id, payload)

    if policy is None:
        raise HTTPException(status_code=404, detail="Refresh policy not found.")

    return policy


@router.post("/{policy_id}/enable")
def enable_policy(
    repository: RepositoryDependency,
    policy_id: str,
) -> dict:
    policy = set_refresh_policy_enabled(repository, policy_id, True)

    if policy is None:
        raise HTTPException(status_code=404, detail="Refresh policy not found.")

    return policy


@router.post("/{policy_id}/disable")
def disable_policy(
    repository: RepositoryDependency,
    policy_id: str,
) -> dict:
    policy = set_refresh_policy_enabled(repository, policy_id, False)

    if policy is None:
        raise HTTPException(status_code=404, detail="Refresh policy not found.")

    return policy


@router.post("/{policy_id}/run-now")
def run_policy_now(
    fundamentals_provider: FundamentalsProviderDependency,
    market_data_provider: MarketDataProviderDependency,
    repository: RepositoryDependency,
    policy_id: str,
) -> dict:
    result = run_refresh_policy_now(
        fundamentals_provider,
        market_data_provider,
        repository,
        policy_id,
    )

    if result is None:
        raise HTTPException(status_code=404, detail="Refresh policy not found.")

    return result

