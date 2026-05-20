from app.services.cache import TTLCache


def test_ttl_cache_hit_and_miss_behavior() -> None:
    now = [100.0]
    cache = TTLCache(ttl_seconds=10, now=lambda: now[0])
    key = cache.normalize_key("search", " aapl ")

    assert key == "SEARCH:AAPL"
    assert cache.get(key) is None

    cache.set(key, {"ticker": "AAPL"})

    assert cache.get(key) == {"ticker": "AAPL"}

    now[0] = 111.0

    assert cache.get(key) is None


def test_ttl_cache_can_be_disabled() -> None:
    cache = TTLCache(ttl_seconds=0)
    key = cache.normalize_key("snapshot", "AAPL")

    cache.set(key, {"ticker": "AAPL"})

    assert cache.get(key) is None
