import pytest
from datetime import datetime, timezone

from crud.external_sync import sync_platform_items


class FakeCursor:
    def __init__(self, docs):
        self._docs = docs

    async def to_list(self, length=None):
        return [dict(d) for d in self._docs]


class FakeCollection:
    """簡化版的 in-memory collection，模擬 Motor 的 update_one(upsert)/find().to_list() 行為。"""

    def __init__(self, initial=None):
        self._docs = list(initial or [])

    async def update_one(self, filter, update, upsert=False):
        doc = update["$set"]
        for i, existing in enumerate(self._docs):
            if all(existing.get(k) == v for k, v in filter.items()):
                self._docs[i] = {**existing, **doc}
                return
        if upsert:
            self._docs.append(dict(doc))

    def find(self, filter):
        matched = [d for d in self._docs if all(d.get(k) == v for k, v in filter.items())]
        return FakeCursor(matched)


@pytest.mark.asyncio
async def test_sync_platform_items_live_success_upserts_and_returns_fresh():
    collection = FakeCollection()

    async def fetch():
        return [{"id": 1, "title": "a"}, {"id": 2, "title": "b"}]

    items, stale, synced_at = await sync_platform_items(
        collection=collection, user_id="u1", id_field="id", fetch_fn=fetch
    )

    assert stale is False
    assert synced_at is not None
    assert [i["title"] for i in items] == ["a", "b"]
    assert len(collection._docs) == 2
    assert collection._docs[0]["user_id"] == "u1"
    assert collection._docs[0]["synced_at"] == synced_at


@pytest.mark.asyncio
async def test_sync_platform_items_live_fetch_upserts_existing_item():
    collection = FakeCollection(initial=[{"id": 1, "title": "old", "user_id": "u1"}])

    async def fetch():
        return [{"id": 1, "title": "new"}]

    items, stale, _ = await sync_platform_items(
        collection=collection, user_id="u1", id_field="id", fetch_fn=fetch
    )

    assert stale is False
    assert len(collection._docs) == 1
    assert collection._docs[0]["title"] == "new"


@pytest.mark.asyncio
async def test_sync_platform_items_falls_back_to_cache_on_failure():
    synced_at = datetime.now(timezone.utc)
    collection = FakeCollection(initial=[
        {"_id": "mongo_id", "id": 1, "title": "cached", "user_id": "u1", "synced_at": synced_at}
    ])

    async def fetch():
        raise Exception("API down")

    items, stale, returned_synced_at = await sync_platform_items(
        collection=collection, user_id="u1", id_field="id", fetch_fn=fetch
    )

    assert stale is True
    assert returned_synced_at == synced_at
    assert items[0]["title"] == "cached"
    assert "_id" not in items[0]


@pytest.mark.asyncio
async def test_sync_platform_items_raises_when_no_cache_available():
    collection = FakeCollection()

    async def fetch():
        raise Exception("API down, no cache either")

    with pytest.raises(Exception, match="API down, no cache either"):
        await sync_platform_items(
            collection=collection, user_id="u1", id_field="id", fetch_fn=fetch
        )


@pytest.mark.asyncio
async def test_sync_platform_items_only_returns_cache_for_matching_user():
    collection = FakeCollection(initial=[
        {"id": 1, "title": "other user's cached data", "user_id": "someone_else"}
    ])

    async def fetch():
        raise Exception("API down")

    with pytest.raises(Exception, match="API down"):
        await sync_platform_items(
            collection=collection, user_id="u1", id_field="id", fetch_fn=fetch
        )
