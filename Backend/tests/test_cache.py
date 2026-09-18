import pytest

import cache


@pytest.fixture(autouse=True)
def clear_memory_store():
    """每個測試前清空記憶體快取，避免測試互相汙染。"""
    cache._memory_store.clear()
    yield
    cache._memory_store.clear()


@pytest.mark.asyncio
async def test_cache_get_returns_none_when_missing():
    result = await cache.cache_get("does-not-exist")
    assert result is None


@pytest.mark.asyncio
async def test_cache_set_then_get_returns_same_value():
    await cache.cache_set("key1", {"a": 1, "b": [1, 2, 3]}, ttl_seconds=60)
    result = await cache.cache_get("key1")

    assert result == {"a": 1, "b": [1, 2, 3]}


@pytest.mark.asyncio
async def test_cache_expires_after_ttl(monkeypatch):
    fake_now = {"t": 1000.0}
    monkeypatch.setattr(cache.time, "time", lambda: fake_now["t"])

    await cache.cache_set("key1", "value", ttl_seconds=60)

    fake_now["t"] += 30
    assert await cache.cache_get("key1") == "value"  # 還沒過期

    fake_now["t"] += 31  # 總共過了 61 秒
    assert await cache.cache_get("key1") is None  # 過期了，該回傳 None


@pytest.mark.asyncio
async def test_cache_get_uses_redis_when_configured(monkeypatch):
    # REDIS_URL 沒設定時測試環境一律走記憶體 fallback，這裡直接塞一個假的
    # redis client 進去，確保「有設定 Redis」那個分支本身也真的被測試過
    class FakeRedis:
        async def get(self, key):
            return '{"a": 1}'

    monkeypatch.setattr(cache, "_redis_client", FakeRedis())

    result = await cache.cache_get("key1")

    assert result == {"a": 1}


@pytest.mark.asyncio
async def test_cache_get_returns_none_when_redis_has_no_value(monkeypatch):
    class FakeRedis:
        async def get(self, key):
            return None

    monkeypatch.setattr(cache, "_redis_client", FakeRedis())

    result = await cache.cache_get("key1")

    assert result is None


@pytest.mark.asyncio
async def test_cache_set_uses_redis_when_configured(monkeypatch):
    captured = {}

    class FakeRedis:
        async def set(self, key, value, ex=None):
            captured["key"] = key
            captured["value"] = value
            captured["ex"] = ex

    monkeypatch.setattr(cache, "_redis_client", FakeRedis())

    await cache.cache_set("key1", {"a": 1}, ttl_seconds=60)

    import json
    assert captured["key"] == "key1"
    assert captured["ex"] == 60
    assert json.loads(captured["value"]) == {"a": 1}


@pytest.mark.asyncio
async def test_expired_entry_is_removed_from_memory_store(monkeypatch):
    fake_now = {"t": 1000.0}
    monkeypatch.setattr(cache.time, "time", lambda: fake_now["t"])

    await cache.cache_set("key1", "value", ttl_seconds=10)
    fake_now["t"] += 11
    await cache.cache_get("key1")

    assert "key1" not in cache._memory_store
