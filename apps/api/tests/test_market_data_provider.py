from app.core.config import get_settings
from app.services.market_data.alpaca import (
    AlpacaMarketDataProvider,
    AlpacaProviderError,
)
from app.services.market_data.provider import (
    NotConnectedProvider,
    get_market_data_provider,
)


def clear_provider_caches() -> None:
    get_settings.cache_clear()
    get_market_data_provider.cache_clear()


def test_missing_alpaca_credentials_use_not_connected_provider(monkeypatch) -> None:
    monkeypatch.delenv("ALPACA_API_KEY", raising=False)
    monkeypatch.delenv("ALPACA_SECRET_KEY", raising=False)
    clear_provider_caches()

    provider = get_market_data_provider()

    assert isinstance(provider, NotConnectedProvider)
    assert provider.provider_status()["state"] == "not_connected"
    assert provider.provider_status()["requiredEnvironmentVariables"] == [
        "ALPACA_API_KEY",
        "ALPACA_SECRET_KEY",
    ]

    clear_provider_caches()


def test_alpaca_credentials_select_alpaca_provider(monkeypatch) -> None:
    monkeypatch.setenv("ALPACA_API_KEY", "test-key")
    monkeypatch.setenv("ALPACA_SECRET_KEY", "test-secret")
    monkeypatch.setenv("ALPACA_BASE_URL", "https://example-trading.test")
    monkeypatch.setenv("ALPACA_DATA_BASE_URL", "https://example-data.test")
    clear_provider_caches()

    provider = get_market_data_provider()

    assert isinstance(provider, AlpacaMarketDataProvider)
    assert provider.base_url == "https://example-trading.test"
    assert provider.data_base_url == "https://example-data.test"
    assert provider.provider_status()["state"] == "connected"

    clear_provider_caches()


def test_alpaca_search_normalizes_asset_response(monkeypatch) -> None:
    provider = AlpacaMarketDataProvider(
        api_key="test-key",
        secret_key="test-secret",
        base_url="https://example-trading.test",
        data_base_url="https://example-data.test",
    )

    def fake_request_json(base_url, path, params=None):
        assert base_url == "https://example-trading.test"
        assert path == "/v2/assets"
        assert params == {"status": "active", "asset_class": "us_equity"}

        return [
            {
                "symbol": "AAPL",
                "name": "Apple Inc.",
                "exchange": "NASDAQ",
                "asset_class": "us_equity",
            },
            {
                "symbol": "MSFT",
                "name": "Microsoft Corporation",
                "exchange": "NASDAQ",
                "asset_class": "us_equity",
            },
        ]

    monkeypatch.setattr(provider, "_request_json", fake_request_json)

    payload = provider.search_securities("aap")

    assert payload["provider"]["state"] == "connected"
    assert payload["results"] == [
        {
            "ticker": "AAPL",
            "name": "Apple Inc.",
            "exchange": "NASDAQ",
            "region": "US",
            "currency": "USD",
            "assetType": "equity",
            "provider": "alpaca",
            "providerState": "connected",
        }
    ]


def test_alpaca_search_uses_normalized_cache_key(monkeypatch) -> None:
    provider = AlpacaMarketDataProvider(
        api_key="test-key",
        secret_key="test-secret",
        base_url="https://example-trading.test",
        data_base_url="https://example-data.test",
    )
    calls = []

    def fake_request_json(base_url, path, params=None):
        calls.append((base_url, path, params))

        return [
            {
                "symbol": "AAPL",
                "name": "Apple Inc.",
                "exchange": "NASDAQ",
                "asset_class": "us_equity",
            }
        ]

    monkeypatch.setattr(provider, "_request_json", fake_request_json)

    first_payload = provider.search_securities("aap")
    second_payload = provider.search_securities(" AAP ")

    assert len(calls) == 1
    assert first_payload["results"] == second_payload["results"]
    assert second_payload["query"] == " AAP "


def test_alpaca_provider_reports_degraded_state_on_error(monkeypatch) -> None:
    provider = AlpacaMarketDataProvider(
        api_key="test-key",
        secret_key="test-secret",
        base_url="https://example-trading.test",
        data_base_url="https://example-data.test",
    )

    def fake_request_json(base_url, path, params=None):
        raise AlpacaProviderError("HTTP 401 for test-secret")

    monkeypatch.setattr(provider, "_request_json", fake_request_json)

    payload = provider.search_securities("AAPL")
    status = provider.provider_status()

    assert payload["provider"]["state"] == "degraded"
    assert status["state"] == "degraded"
    assert "test-secret" not in status["lastErrorMessage"]
    assert "[redacted]" in status["lastErrorMessage"]


def test_alpaca_security_normalizes_single_asset(monkeypatch) -> None:
    provider = AlpacaMarketDataProvider(
        api_key="test-key",
        secret_key="test-secret",
        base_url="https://example-trading.test",
        data_base_url="https://example-data.test",
    )

    def fake_request_json(base_url, path, params=None):
        assert path == "/v2/assets/AAPL"

        return {
            "symbol": "AAPL",
            "name": "Apple Inc.",
            "exchange": "NASDAQ",
            "asset_class": "us_equity",
        }

    monkeypatch.setattr(provider, "_request_json", fake_request_json)

    payload = provider.get_security("aapl")

    assert payload["ticker"] == "AAPL"
    assert payload["provider"]["state"] == "connected"
    assert payload["security"]["ticker"] == "AAPL"
    assert payload["security"]["assetType"] == "equity"
    assert payload["businessSummary"] is None


def test_alpaca_snapshot_normalizes_market_data(monkeypatch) -> None:
    provider = AlpacaMarketDataProvider(
        api_key="test-key",
        secret_key="test-secret",
        base_url="https://example-trading.test",
        data_base_url="https://example-data.test",
    )

    def fake_request_json(base_url, path, params=None):
        assert base_url == "https://example-data.test"
        assert path == "/v2/stocks/snapshots"
        assert params == {"symbols": "AAPL", "feed": "iex"}

        return {
            "snapshots": {
                "AAPL": {
                    "latestTrade": {
                        "p": 190.12,
                        "t": "2026-05-18T14:30:00Z",
                    },
                    "dailyBar": {
                        "v": 123456,
                    },
                }
            }
        }

    monkeypatch.setattr(provider, "_request_json", fake_request_json)

    payload = provider.get_market_snapshot("aapl")

    assert payload["ticker"] == "AAPL"
    assert payload["price"] == 190.12
    assert payload["currency"] == "USD"
    assert payload["volume"] == 123456.0
    assert payload["marketCap"] is None
    assert payload["enterpriseValue"] is None
    assert payload["asOf"] == "2026-05-18T14:30:00Z"
    assert payload["provider"]["state"] == "connected"
