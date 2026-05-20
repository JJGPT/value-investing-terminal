import json

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app
from app.services.fundamentals.provider import get_fundamentals_provider
from app.services.market_data.alpaca import AlpacaMarketDataProvider
from app.services.market_data.provider import get_market_data_provider
from app.services.persistence.provider import get_snapshot_repository
from app.services.provider_status import provider_connected

client = TestClient(app)


@pytest.fixture(autouse=True)
def clear_provider_state(monkeypatch, tmp_path):
    monkeypatch.delenv("ALPACA_API_KEY", raising=False)
    monkeypatch.delenv("ALPACA_SECRET_KEY", raising=False)
    monkeypatch.delenv("FMP_API_KEY", raising=False)
    monkeypatch.setenv("VALUE_TERMINAL_DB_PATH", str(tmp_path / "snapshots.db"))
    get_settings.cache_clear()
    get_market_data_provider.cache_clear()
    get_fundamentals_provider.cache_clear()
    get_snapshot_repository.cache_clear()
    app.dependency_overrides.clear()

    yield

    get_settings.cache_clear()
    get_market_data_provider.cache_clear()
    get_fundamentals_provider.cache_clear()
    get_snapshot_repository.cache_clear()
    app.dependency_overrides.clear()


def test_market_data_diagnostics_without_credentials() -> None:
    response = client.get("/api/diagnostics/market-data")

    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"]["provider"] == "alpaca"
    assert payload["provider"]["state"] == "not_connected"
    assert payload["cacheTtls"] == {
        "securitySearchSeconds": 300,
        "securityLookupSeconds": 900,
        "marketSnapshotSeconds": 30,
    }

    env_by_name = {item["name"]: item for item in payload["environment"]}
    assert env_by_name["ALPACA_API_KEY"]["present"] is False
    assert env_by_name["ALPACA_SECRET_KEY"]["present"] is False
    assert all(item["state"] == "blocked" for item in payload["endpointReadiness"])


def test_market_data_diagnostics_with_credentials(monkeypatch) -> None:
    monkeypatch.setenv("ALPACA_API_KEY", "test-key")
    monkeypatch.setenv("ALPACA_SECRET_KEY", "test-secret")
    monkeypatch.setenv("SECURITY_SEARCH_CACHE_TTL_SECONDS", "11")
    monkeypatch.setenv("SECURITY_LOOKUP_CACHE_TTL_SECONDS", "22")
    monkeypatch.setenv("MARKET_SNAPSHOT_CACHE_TTL_SECONDS", "33")
    get_settings.cache_clear()
    get_market_data_provider.cache_clear()

    response = client.get("/api/diagnostics/market-data")
    payload = response.json()
    response_text = json.dumps(payload)

    assert response.status_code == 200
    assert payload["provider"]["state"] == "connected"
    assert payload["cacheTtls"] == {
        "securitySearchSeconds": 11,
        "securityLookupSeconds": 22,
        "marketSnapshotSeconds": 33,
    }
    assert all(item["state"] == "ready" for item in payload["endpointReadiness"])
    assert "test-key" not in response_text
    assert "test-secret" not in response_text


def test_market_data_diagnostics_with_degraded_provider(monkeypatch) -> None:
    monkeypatch.setenv("ALPACA_API_KEY", "test-key")
    monkeypatch.setenv("ALPACA_SECRET_KEY", "test-secret")
    get_settings.cache_clear()
    get_market_data_provider.cache_clear()
    provider = get_market_data_provider()

    assert isinstance(provider, AlpacaMarketDataProvider)

    provider.record_error("Provider failure for test-key and test-secret")

    response = client.get("/api/diagnostics/market-data")
    payload = response.json()
    response_text = json.dumps(payload)

    assert response.status_code == 200
    assert payload["provider"]["state"] == "degraded"
    assert payload["provider"]["lastErrorMessage"] == (
        "Provider failure for [redacted] and [redacted]"
    )
    assert all(
        item["state"] == "degraded" for item in payload["endpointReadiness"]
    )
    assert "test-key" not in response_text
    assert "test-secret" not in response_text


def test_market_data_probe_uses_provider_methods() -> None:
    calls = []

    class FakeProbeProvider:
        def provider_status(self):
            return provider_connected("alpaca", "fake provider connected")

        def get_security(self, ticker):
            calls.append(("security", ticker))

            return {
                "ticker": ticker,
                "security": {
                    "ticker": ticker,
                    "name": "Apple Inc.",
                    "exchange": "NASDAQ",
                    "region": "US",
                    "currency": "USD",
                    "assetType": "equity",
                    "provider": "alpaca",
                    "providerState": "connected",
                },
                "businessSummary": None,
                "sector": None,
                "industry": None,
                "domicile": None,
                "fiscalYearEnd": None,
                "provider": self.provider_status(),
                "message": "fake security lookup",
            }

        def get_market_snapshot(self, ticker):
            calls.append(("snapshot", ticker))

            return {
                "ticker": ticker,
                "price": 190.12,
                "currency": "USD",
                "marketCap": None,
                "enterpriseValue": None,
                "volume": 123456,
                "asOf": "2026-05-18T14:30:00Z",
                "provider": self.provider_status(),
                "message": "fake market snapshot",
            }

        def search_securities(self, query):
            raise AssertionError("Probe should not call search_securities")

    app.dependency_overrides[get_market_data_provider] = lambda: FakeProbeProvider()

    response = client.get("/api/diagnostics/market-data/probe", params={"ticker": "aapl"})
    payload = response.json()

    assert response.status_code == 200
    assert calls == [("security", "AAPL"), ("snapshot", "AAPL")]
    assert payload["ticker"] == "AAPL"
    assert payload["provider"]["state"] == "connected"
    assert payload["securityLookup"]["security"]["name"] == "Apple Inc."
    assert payload["marketSnapshot"]["price"] == 190.12
    assert payload["latencyMs"]["total"] >= 0
    assert payload["error"] is None


def test_market_data_probe_redacts_provider_exception() -> None:
    class FailingProbeProvider:
        api_key = "test-key"
        secret_key = "test-secret"

        def provider_status(self):
            return provider_connected("alpaca", "fake provider connected")

        def get_security(self, ticker):
            raise RuntimeError("provider failed for test-key and test-secret")

        def get_market_snapshot(self, ticker):
            raise AssertionError("Snapshot should not run after security failure")

        def search_securities(self, query):
            raise AssertionError("Probe should not call search_securities")

    app.dependency_overrides[get_market_data_provider] = lambda: FailingProbeProvider()

    response = client.get("/api/diagnostics/market-data/probe", params={"ticker": "AAPL"})
    payload = response.json()
    response_text = json.dumps(payload)

    assert response.status_code == 200
    assert payload["provider"]["state"] == "degraded"
    assert payload["securityLookup"] is None
    assert payload["marketSnapshot"] is None
    assert "[redacted]" in payload["error"]
    assert "test-key" not in response_text
    assert "test-secret" not in response_text


def test_fundamentals_diagnostics_without_credentials() -> None:
    response = client.get("/api/diagnostics/fundamentals")

    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"]["provider"] == "fmp"
    assert payload["provider"]["state"] == "not_connected"
    assert payload["cacheTtls"] == {
        "companyProfileSeconds": 3600,
        "incomeStatementSeconds": 3600,
        "balanceSheetSeconds": 3600,
        "cashFlowSeconds": 3600,
        "keyMetricsSeconds": 3600,
        "computedMetricsSeconds": 900,
    }
    assert payload["supportedPeriods"] == ["annual", "quarter", "ttm"]
    assert payload["defaultPeriod"] == "annual"
    assert payload["screener"]["snapshotStore"]["state"] == "connected"
    assert payload["screener"]["snapshotFreshness"][0]["missingCount"] == 12

    env_by_name = {item["name"]: item for item in payload["environment"]}
    assert env_by_name["FMP_API_KEY"]["present"] is False
    assert env_by_name["FMP_BASE_URL"]["present"] is True
    assert all(item["state"] == "blocked" for item in payload["endpointReadiness"])


def test_valuation_diagnostics_shape_and_no_secret_leakage(monkeypatch) -> None:
    monkeypatch.setenv("FMP_API_KEY", "test-fmp-key")
    monkeypatch.setenv("ALPACA_API_KEY", "test-alpaca-key")
    monkeypatch.setenv("ALPACA_SECRET_KEY", "test-alpaca-secret")
    get_settings.cache_clear()

    response = client.get("/api/diagnostics/valuation", params={"ticker": "aapl"})
    payload = response.json()
    response_text = json.dumps(payload)
    limits = {
        (item["group"], item["name"]): item
        for item in payload["assumptionLimits"]
    }

    assert response.status_code == 200
    assert payload["provider"]["provider"] == "platform_valuation"
    assert payload["provider"]["state"] == "connected"
    assert payload["ticker"] == "AAPL"
    assert payload["engineVersion"] == "platform-fcff-dcf-v1"
    assert payload["repository"]["state"] == "connected"
    assert payload["repositoryHealth"]["scenarioCount"] == 0
    assert payload["repositoryHealth"]["orphanedScenarioVersionCount"] == 0
    assert payload["repositoryHealth"]["reproducibility"] == {
        "completeScenarioCount": 0,
        "incompleteScenarioCount": 0,
    }
    assert payload["savedScenarioCount"] == 0
    assert limits[("discountRate", "wacc")]["minimum"] == -0.5
    assert all(item["state"] == "ready" for item in payload["endpointReadiness"])
    assert "test-fmp-key" not in response_text
    assert "test-alpaca-key" not in response_text
    assert "test-alpaca-secret" not in response_text


def test_fundamentals_diagnostics_with_credentials(monkeypatch) -> None:
    monkeypatch.setenv("FMP_API_KEY", "test-fmp-key")
    monkeypatch.setenv("FMP_BASE_URL", "https://example-fmp.test")
    monkeypatch.setenv("FUNDAMENTALS_PROFILE_CACHE_TTL_SECONDS", "101")
    monkeypatch.setenv("FUNDAMENTALS_INCOME_STATEMENT_CACHE_TTL_SECONDS", "102")
    monkeypatch.setenv("FUNDAMENTALS_BALANCE_SHEET_CACHE_TTL_SECONDS", "103")
    monkeypatch.setenv("FUNDAMENTALS_CASH_FLOW_CACHE_TTL_SECONDS", "104")
    monkeypatch.setenv("FUNDAMENTALS_KEY_METRICS_CACHE_TTL_SECONDS", "105")
    monkeypatch.setenv("COMPUTED_METRICS_CACHE_TTL_SECONDS", "106")
    get_settings.cache_clear()
    get_fundamentals_provider.cache_clear()

    response = client.get("/api/diagnostics/fundamentals")
    payload = response.json()
    response_text = json.dumps(payload)

    assert response.status_code == 200
    assert payload["provider"]["state"] == "connected"
    assert payload["cacheTtls"] == {
        "companyProfileSeconds": 101,
        "incomeStatementSeconds": 102,
        "balanceSheetSeconds": 103,
        "cashFlowSeconds": 104,
        "keyMetricsSeconds": 105,
        "computedMetricsSeconds": 106,
    }
    assert all(item["state"] == "ready" for item in payload["endpointReadiness"])
    assert "test-fmp-key" not in response_text


def test_fundamentals_diagnostics_with_degraded_provider(monkeypatch) -> None:
    monkeypatch.setenv("FMP_API_KEY", "test-fmp-key")
    get_settings.cache_clear()
    get_fundamentals_provider.cache_clear()
    provider = get_fundamentals_provider()
    provider.record_error("Provider failure for test-fmp-key")

    response = client.get("/api/diagnostics/fundamentals")
    payload = response.json()
    response_text = json.dumps(payload)

    assert response.status_code == 200
    assert payload["provider"]["state"] == "degraded"
    assert payload["provider"]["lastErrorMessage"] == (
        "Provider failure for [redacted]"
    )
    assert all(
        item["state"] == "degraded" for item in payload["endpointReadiness"]
    )
    assert "test-fmp-key" not in response_text
