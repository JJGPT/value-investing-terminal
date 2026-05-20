import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app
from app.services.fundamentals.provider import get_fundamentals_provider
from app.services.market_data.provider import get_market_data_provider

client = TestClient(app)


@pytest.fixture(autouse=True)
def clear_alpaca_env(monkeypatch):
    monkeypatch.delenv("ALPACA_API_KEY", raising=False)
    monkeypatch.delenv("ALPACA_SECRET_KEY", raising=False)
    monkeypatch.delenv("FMP_API_KEY", raising=False)
    get_settings.cache_clear()
    get_market_data_provider.cache_clear()
    get_fundamentals_provider.cache_clear()

    yield

    get_settings.cache_clear()
    get_market_data_provider.cache_clear()
    get_fundamentals_provider.cache_clear()


def assert_provider_not_connected(provider: dict) -> None:
    assert provider["state"] == "not_connected"
    assert isinstance(provider["provider"], str)
    assert isinstance(provider["message"], str)
    assert isinstance(provider["requiredEnvironmentVariables"], list)
    assert provider["lastCheckedAt"] is None
    assert provider["lastSuccessfulCallAt"] is None
    assert provider["lastErrorMessage"] is None


def test_health_contract() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "Value Investing Terminal API"
    assert payload["version"] == "0.0.0"
    assert payload["environment"] == "development"


def test_api_status_contract() -> None:
    response = client.get("/api/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert isinstance(payload["providers"], list)
    assert payload["providers"]

    for provider in payload["providers"]:
        assert set(
            [
                "provider",
                "state",
                "message",
                "requiredEnvironmentVariables",
                "lastCheckedAt",
                "lastSuccessfulCallAt",
                "lastErrorMessage",
            ]
        ).issubset(provider)
        assert_provider_not_connected(provider)


def test_security_search_contract() -> None:
    response = client.get("/api/securities/search", params={"q": "AAPL"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["query"] == "AAPL"
    assert payload["results"] == []
    assert isinstance(payload["message"], str)
    assert_provider_not_connected(payload["provider"])


def test_security_overview_contract() -> None:
    response = client.get("/api/securities/AAPL")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ticker"] == "AAPL"
    assert payload["businessSummary"] is None
    assert payload["sector"] is None
    assert payload["industry"] is None
    assert payload["security"]["ticker"] == "AAPL"
    assert payload["security"]["providerState"] == "not_connected"
    assert_provider_not_connected(payload["provider"])


def test_market_snapshot_contract() -> None:
    response = client.get("/api/securities/AAPL/snapshot")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ticker"] == "AAPL"
    assert payload["price"] is None
    assert payload["marketCap"] is None
    assert payload["enterpriseValue"] is None
    assert payload["asOf"] is None
    assert_provider_not_connected(payload["provider"])


def test_watchlists_contract() -> None:
    response = client.get("/api/watchlists")

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload["watchlists"], list)
    assert payload["provider"]["provider"] == "watchlist_store"
    assert payload["provider"]["state"] == "connected"
    assert payload["message"]


def test_fundamentals_profile_contract_without_credentials() -> None:
    response = client.get("/api/fundamentals/AAPL/profile")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ticker"] == "AAPL"
    assert payload["profile"] is None
    assert_provider_not_connected(payload["provider"])


@pytest.mark.parametrize(
    ("route", "data_key"),
    [
        ("/api/fundamentals/AAPL/income-statement", "incomeStatements"),
        ("/api/fundamentals/AAPL/balance-sheet", "balanceSheets"),
        ("/api/fundamentals/AAPL/cash-flow", "cashFlowStatements"),
        ("/api/fundamentals/AAPL/metrics", "metrics"),
    ],
)
def test_fundamentals_statement_contract_without_credentials(
    route: str,
    data_key: str,
) -> None:
    response = client.get(route, params={"period": "annual", "limit": 5})

    assert response.status_code == 200
    payload = response.json()
    assert payload["ticker"] == "AAPL"
    assert payload["period"] == "annual"
    assert payload["limit"] == 5
    assert payload[data_key] == []
    assert_provider_not_connected(payload["provider"])


def test_fundamentals_ttm_contract_returns_not_implemented() -> None:
    response = client.get(
        "/api/fundamentals/AAPL/income-statement",
        params={"period": "ttm", "limit": 5},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ticker"] == "AAPL"
    assert payload["period"] == "ttm"
    assert payload["incomeStatements"] == []
    assert payload["provider"]["state"] == "not_implemented"
