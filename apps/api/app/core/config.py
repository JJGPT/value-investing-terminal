from functools import lru_cache
from os import getenv
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


class Settings(BaseModel):
    app_name: str = "Value Investing Terminal API"
    version: str = "0.0.0"
    environment: str = "development"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    alpaca_api_key: Optional[str] = None
    alpaca_secret_key: Optional[str] = None
    alpaca_base_url: str = "https://paper-api.alpaca.markets"
    alpaca_data_base_url: str = "https://data.alpaca.markets"
    security_search_cache_ttl_seconds: int = 300
    security_lookup_cache_ttl_seconds: int = 900
    market_snapshot_cache_ttl_seconds: int = 30
    fmp_api_key: Optional[str] = None
    fmp_base_url: str = "https://financialmodelingprep.com/stable"
    fundamentals_profile_cache_ttl_seconds: int = 3600
    fundamentals_income_statement_cache_ttl_seconds: int = 3600
    fundamentals_balance_sheet_cache_ttl_seconds: int = 3600
    fundamentals_cash_flow_cache_ttl_seconds: int = 3600
    fundamentals_key_metrics_cache_ttl_seconds: int = 3600
    computed_metrics_cache_ttl_seconds: int = 900
    value_terminal_db_path: str
    snapshot_stale_after_seconds: int = 86400


def default_db_path() -> str:
    return str(Path(__file__).resolve().parents[2] / "data" / "value_terminal.db")


def optional_env(name: str) -> Optional[str]:
    value = getenv(name)

    if value and value.strip():
        return value.strip()

    return None


def int_env(name: str, default: int) -> int:
    value = getenv(name)

    if not value:
        return default

    try:
        return int(value)
    except ValueError:
        return default


def list_env(name: str, default: list[str]) -> list[str]:
    value = getenv(name)

    if not value:
        return default

    parsed = [item.strip() for item in value.split(",") if item.strip()]

    return parsed or default


@lru_cache
def get_settings() -> Settings:
    return Settings(
        app_name=getenv("APP_NAME", "Value Investing Terminal API"),
        version=getenv("APP_VERSION", "0.0.0"),
        environment=getenv("APP_ENV", "development"),
        cors_origins=list_env("CORS_ORIGINS", ["http://localhost:3000"]),
        alpaca_api_key=optional_env("ALPACA_API_KEY"),
        alpaca_secret_key=optional_env("ALPACA_SECRET_KEY"),
        alpaca_base_url=getenv(
            "ALPACA_BASE_URL",
            "https://paper-api.alpaca.markets",
        ).rstrip("/"),
        alpaca_data_base_url=getenv(
            "ALPACA_DATA_BASE_URL",
            "https://data.alpaca.markets",
        ).rstrip("/"),
        security_search_cache_ttl_seconds=int_env(
            "SECURITY_SEARCH_CACHE_TTL_SECONDS",
            300,
        ),
        security_lookup_cache_ttl_seconds=int_env(
            "SECURITY_LOOKUP_CACHE_TTL_SECONDS",
            900,
        ),
        market_snapshot_cache_ttl_seconds=int_env(
            "MARKET_SNAPSHOT_CACHE_TTL_SECONDS",
            30,
        ),
        fmp_api_key=optional_env("FMP_API_KEY"),
        fmp_base_url=getenv(
            "FMP_BASE_URL",
            "https://financialmodelingprep.com/stable",
        ).rstrip("/"),
        fundamentals_profile_cache_ttl_seconds=int_env(
            "FUNDAMENTALS_PROFILE_CACHE_TTL_SECONDS",
            3600,
        ),
        fundamentals_income_statement_cache_ttl_seconds=int_env(
            "FUNDAMENTALS_INCOME_STATEMENT_CACHE_TTL_SECONDS",
            3600,
        ),
        fundamentals_balance_sheet_cache_ttl_seconds=int_env(
            "FUNDAMENTALS_BALANCE_SHEET_CACHE_TTL_SECONDS",
            3600,
        ),
        fundamentals_cash_flow_cache_ttl_seconds=int_env(
            "FUNDAMENTALS_CASH_FLOW_CACHE_TTL_SECONDS",
            3600,
        ),
        fundamentals_key_metrics_cache_ttl_seconds=int_env(
            "FUNDAMENTALS_KEY_METRICS_CACHE_TTL_SECONDS",
            3600,
        ),
        computed_metrics_cache_ttl_seconds=int_env(
            "COMPUTED_METRICS_CACHE_TTL_SECONDS",
            900,
        ),
        value_terminal_db_path=getenv(
            "VALUE_TERMINAL_DB_PATH",
            default_db_path(),
        ),
        snapshot_stale_after_seconds=int_env(
            "SNAPSHOT_STALE_AFTER_SECONDS",
            86400,
        ),
    )
