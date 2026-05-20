from typing import Annotated, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.config import Settings, get_settings
from app.services.fundamentals.provider import (
    FundamentalsProvider,
    get_fundamentals_provider,
)
from app.services.jobs.runner import (
    cancel_job,
    create_ranking_refresh_job,
    run_ranking_refresh_job,
)
from app.services.market_data.provider import (
    MarketDataProvider,
    get_market_data_provider,
)
from app.services.persistence.provider import get_snapshot_repository
from app.services.persistence.repository import SnapshotRepository
from app.services.refresh_policies import run_due_refresh_policies

router = APIRouter(prefix="/api/jobs", tags=["jobs"])

JobStatus = Literal["queued", "running", "completed", "failed", "cancelled"]
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


@router.post("/ranking-refresh")
def create_ranking_refresh(
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
    run: bool = Query(default=True),
) -> dict:
    parsed_tickers = parse_tickers(tickers)

    if not run:
        return create_ranking_refresh_job(
            repository,
            strategy,
            period,
            scope_type=scope,
            tickers=parsed_tickers,
            stale_only=stale_only,
            screen_id=screen_id,
        )

    return run_ranking_refresh_job(
        fundamentals_provider,
        market_data_provider,
        repository,
        strategy,
        period,
        settings.snapshot_stale_after_seconds,
        scope_type=scope,
        tickers=parsed_tickers,
        stale_only=stale_only,
        screen_id=screen_id,
    )


@router.get("")
def list_jobs(
    repository: RepositoryDependency,
    job_type: Optional[str] = Query(default=None, alias="jobType"),
    status: Optional[JobStatus] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
) -> dict:
    return {
        "jobs": repository.list_refresh_jobs(job_type, status, limit),
        "message": "Refresh jobs are lightweight SQLite-backed local jobs.",
    }


@router.get("/{job_id}")
def get_job(
    repository: RepositoryDependency,
    job_id: str,
) -> dict:
    job = repository.get_refresh_job(job_id)

    if job is None:
        raise HTTPException(status_code=404, detail="Refresh job not found.")

    return job


@router.get("/{job_id}/events")
def get_job_events(
    repository: RepositoryDependency,
    job_id: str,
) -> dict:
    if repository.get_refresh_job(job_id) is None:
        raise HTTPException(status_code=404, detail="Refresh job not found.")

    return {
        "jobId": job_id,
        "events": repository.list_refresh_job_events(job_id),
        "message": "Refresh job events are append-only.",
    }


@router.post("/{job_id}/cancel")
def cancel_refresh_job(
    repository: RepositoryDependency,
    job_id: str,
) -> dict:
    job = cancel_job(repository, job_id)

    if job is None:
        raise HTTPException(status_code=404, detail="Refresh job not found.")

    return job


@router.post("/run-due-refresh-policies")
def run_due_policies(
    fundamentals_provider: FundamentalsProviderDependency,
    market_data_provider: MarketDataProviderDependency,
    repository: RepositoryDependency,
) -> dict:
    return run_due_refresh_policies(
        fundamentals_provider,
        market_data_provider,
        repository,
    )


def parse_tickers(raw_tickers: Optional[str]) -> Optional[list[str]]:
    if not raw_tickers:
        return None

    return [
        ticker.strip().upper()
        for ticker in raw_tickers.split(",")
        if ticker.strip()
    ]
