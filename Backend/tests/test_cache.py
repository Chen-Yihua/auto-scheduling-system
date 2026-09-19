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
    """沒存過的 key → 回傳 None，不是丟例外。"""
    result = await cache.cache_get("does-not-exist")
    assert result is None


@pytest.mark.asyncio
async def test_cache_set_then_get_returns_same_value():
    """存進去的值（含巢狀的 dict 和 list）取出來要跟原本一樣。"""
    await cache.cache_set("key1", {"a": 1, "b": [1, 2, 3]}, ttl_seconds=60)
    result = await cache.cache_get("key1")

    assert result == {"a": 1, "b": [1, 2, 3]}


@pytest.mark.asyncio
async def test_cache_expires_after_ttl(monkeypatch):
    """超過 TTL 的快取要失效：30 秒時還在、61 秒時回傳 None。"""
    fake_now = {"t": 1000.0}
    monkeypatch.setattr(cache.time, "time", lambda: fake_now["t"])

    await cache.cache_set("key1", "value", ttl_seconds=60)

    fake_now["t"] += 30
    assert await cache.cache_get("key1") == "value"  # 還沒過期

    fake_now["t"] += 31  # 總共過了 61 秒
    assert await cache.cache_get("key1") is None  # 過期了，該回傳 None


@pytest.mark.asyncio
async def test_cache_get_uses_redis_when_configured(monkeypatch):
    """有設定 Redis 時，cache_get 要從 Redis 讀取，而不是記憶體。"""
    # 測試環境沒設 REDIS_URL、平常走記憶體，這裡換上假的 Redis client 才測得到 Redis 這條路
    class FakeRedis:
        async def get(self, key):
            return '{"a": 1}'

    monkeypatch.setattr(cache, "_redis_client", FakeRedis())

    result = await cache.cache_get("key1")

    assert result == {"a": 1}


@pytest.mark.asyncio
async def test_cache_get_returns_none_when_redis_has_no_value(monkeypatch):
    """Redis 裡沒有這個 key → 回傳 None。"""
    class FakeRedis:
        async def get(self, key):
            return None

    monkeypatch.setattr(cache, "_redis_client", FakeRedis())

    result = await cache.cache_get("key1")

    assert result is None


@pytest.mark.asyncio
async def test_cache_set_uses_redis_when_configured(monkeypatch):
    """有設定 Redis 時，cache_set 要把值（轉成 JSON）連同 TTL 一起寫進 Redis。"""
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
    """記憶體快取裡過期的項目，被讀到時要順便刪掉，不能一直佔著記憶體。"""
    fake_now = {"t": 1000.0}
    monkeypatch.setattr(cache.time, "time", lambda: fake_now["t"])

    await cache.cache_set("key1", "value", ttl_seconds=10)
    fake_now["t"] += 11
    await cache.cache_get("key1")

    assert "key1" not in cache._memory_store
