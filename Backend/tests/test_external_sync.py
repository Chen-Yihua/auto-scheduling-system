import pytest
from datetime import datetime, timezone

from crud.external_sync import sync_platform_items
from crud.errors import NonRetryableError


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

    async def delete_many(self, filter):
        """簡化版：只支援這裡實際會用到的兩種條件——一般 key=value，和 {"$nin": [...]}。"""
        def matches(doc):
            for k, v in filter.items():
                if isinstance(v, dict) and "$nin" in v:
                    if doc.get(k) in v["$nin"]:
                        return False
                elif doc.get(k) != v:
                    return False
            return True

        self._docs = [d for d in self._docs if not matches(d)]


@pytest.mark.asyncio
async def test_sync_platform_items_live_success_upserts_and_returns_fresh():
    """即時抓資料成功 → 資料存進資料庫並原樣回傳，且標示為「不是舊資料、沒有授權問題」。"""
    collection = FakeCollection()

    async def fetch():
        return [{"id": 1, "title": "a"}, {"id": 2, "title": "b"}]

    items, stale, synced_at, auth_error = await sync_platform_items(
        collection=collection, user_id="u1", id_field="id", fetch_fn=fetch
    )

    assert stale is False
    assert auth_error is False
    assert synced_at is not None
    assert [i["title"] for i in items] == ["a", "b"]
    assert len(collection._docs) == 2
    assert collection._docs[0]["user_id"] == "u1"
    assert collection._docs[0]["synced_at"] == synced_at


@pytest.mark.asyncio
async def test_sync_platform_items_removes_items_no_longer_returned_by_live_fetch():
    """使用者的第 2 筆項目（例如 issue 被關閉）這次即時抓資料已經不存在 → 應該從 DB 清掉，
    不然之後即時抓資料失敗、退回快取時，會被當成還存在的資料顯示給使用者。"""
    collection = FakeCollection(initial=[
        {"id": 1, "title": "still open", "user_id": "u1"},
        {"id": 2, "title": "already closed on github", "user_id": "u1"},
    ])

    async def fetch():
        return [{"id": 1, "title": "still open"}]

    items, stale, _, _ = await sync_platform_items(
        collection=collection, user_id="u1", id_field="id", fetch_fn=fetch
    )

    assert stale is False
    assert [d["id"] for d in collection._docs] == [1]


@pytest.mark.asyncio
async def test_sync_platform_items_removal_does_not_affect_other_users():
    """清掉「這次已不存在」的項目時，只能動當前使用者的資料，不能誤刪其他使用者同 id 的項目。"""
    collection = FakeCollection(initial=[
        {"id": 1, "title": "user u1's item", "user_id": "u1"},
        {"id": 1, "title": "user u2's item", "user_id": "u2"},
    ])

    async def fetch():
        return []  # u1 這次即時抓資料是空的（例如全部關閉了）

    items, stale, _, _ = await sync_platform_items(
        collection=collection, user_id="u1", id_field="id", fetch_fn=fetch
    )

    assert stale is False
    assert items == []
    remaining = [(d["user_id"], d["id"]) for d in collection._docs]
    assert remaining == [("u2", 1)]


@pytest.mark.asyncio
async def test_sync_platform_items_live_fetch_upserts_existing_item():
    """DB 已有同 id 的舊項目時，即時抓到的新內容要更新它（upsert），不能重複新增一筆。"""
    collection = FakeCollection(initial=[{"id": 1, "title": "old", "user_id": "u1"}])

    async def fetch():
        return [{"id": 1, "title": "new"}]

    items, stale, _, _ = await sync_platform_items(
        collection=collection, user_id="u1", id_field="id", fetch_fn=fetch
    )

    assert stale is False
    assert len(collection._docs) == 1
    assert collection._docs[0]["title"] == "new"


@pytest.mark.asyncio
async def test_sync_platform_items_falls_back_to_cache_on_failure():
    """即時抓資料失敗（暫時性問題）→ 退回資料庫裡的舊資料並標示為舊資料；因為不是憑證問題，不標示授權失效；回傳的資料不含資料庫內部 id。"""
    synced_at = datetime.now(timezone.utc)
    collection = FakeCollection(initial=[
        {"_id": "mongo_id", "id": 1, "title": "cached", "user_id": "u1", "synced_at": synced_at}
    ])

    async def fetch():
        raise Exception("API down")

    items, stale, returned_synced_at, auth_error = await sync_platform_items(
        collection=collection, user_id="u1", id_field="id", fetch_fn=fetch,
        retry_delay_seconds=0,
    )

    assert stale is True
    assert auth_error is False  # 一般 Exception，不是憑證問題
    assert returned_synced_at == synced_at
    assert items[0]["title"] == "cached"
    assert "_id" not in items[0]


@pytest.mark.asyncio
async def test_sync_platform_items_raises_when_no_cache_available():
    """即時抓資料失敗、DB 又沒有舊資料可退回 → 把原本的例外往外丟，不能回傳空清單假裝成功。"""
    collection = FakeCollection()

    async def fetch():
        raise Exception("API down, no cache either")

    with pytest.raises(Exception, match="API down, no cache either"):
        await sync_platform_items(
            collection=collection, user_id="u1", id_field="id", fetch_fn=fetch,
            retry_delay_seconds=0,
        )


@pytest.mark.asyncio
async def test_sync_platform_items_only_returns_cache_for_matching_user():
    """退回舊資料時只能拿當前使用者的；DB 裡只有別人的資料就等於沒有快取，要丟例外，不能把別人的資料回給他。"""
    collection = FakeCollection(initial=[
        {"id": 1, "title": "other user's cached data", "user_id": "someone_else"}
    ])

    async def fetch():
        raise Exception("API down")

    with pytest.raises(Exception, match="API down"):
        await sync_platform_items(
            collection=collection, user_id="u1", id_field="id", fetch_fn=fetch,
            retry_delay_seconds=0,
        )


@pytest.mark.asyncio
async def test_sync_platform_items_retries_and_recovers_on_second_attempt():
    """第一次抓失敗、第二次就成功 → 不需要退回快取，直接回傳重試後拿到的新資料。"""
    collection = FakeCollection()
    call_count = {"n": 0}

    async def fetch():
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise Exception("暫時性失敗")
        return [{"id": 1, "title": "recovered"}]

    items, stale, synced_at, _ = await sync_platform_items(
        collection=collection, user_id="u1", id_field="id", fetch_fn=fetch,
        retry_delay_seconds=0,
    )

    assert call_count["n"] == 2
    assert stale is False
    assert items[0]["title"] == "recovered"
    assert len(collection._docs) == 1


@pytest.mark.asyncio
async def test_sync_platform_items_respects_max_attempts_before_falling_back():
    """max_attempts=3 時應該剛好嘗試 3 次都失敗，才退回快取——不多試也不少試。"""
    synced_at = datetime.now(timezone.utc)
    collection = FakeCollection(initial=[
        {"id": 1, "title": "cached", "user_id": "u1", "synced_at": synced_at}
    ])
    call_count = {"n": 0}

    async def fetch():
        call_count["n"] += 1
        raise Exception("一直失敗")

    items, stale, _, auth_error = await sync_platform_items(
        collection=collection, user_id="u1", id_field="id", fetch_fn=fetch,
        max_attempts=3, retry_delay_seconds=0,
    )

    assert call_count["n"] == 3
    assert stale is True
    assert auth_error is False  # 一般 Exception，不是憑證問題
    assert items[0]["title"] == "cached"


@pytest.mark.asyncio
async def test_sync_platform_items_backs_off_exponentially_between_retries(monkeypatch):
    """重試之間的等待時間要指數成長（1 秒、2 秒、4 秒…），不是每次都等一樣久。"""
    sleep_calls = []

    async def fake_sleep(seconds):
        sleep_calls.append(seconds)

    monkeypatch.setattr("crud.external_sync.asyncio.sleep", fake_sleep)

    collection = FakeCollection()

    async def fetch():
        raise Exception("一直失敗")

    with pytest.raises(Exception):
        await sync_platform_items(
            collection=collection, user_id="u1", id_field="id", fetch_fn=fetch,
            max_attempts=4, retry_delay_seconds=1.0,
        )

    assert sleep_calls == [1.0, 2.0, 4.0]


@pytest.mark.asyncio
async def test_sync_platform_items_does_not_retry_non_retryable_error():
    """NonRetryableError（例如帳密/token 錯誤）不該被重試，抓一次失敗就直接放棄。"""
    synced_at = datetime.now(timezone.utc)
    collection = FakeCollection(initial=[
        {"id": 1, "title": "cached", "user_id": "u1", "synced_at": synced_at}
    ])
    call_count = {"n": 0}

    async def fetch():
        call_count["n"] += 1
        raise NonRetryableError("401 Unauthorized")

    items, stale, _, auth_error = await sync_platform_items(
        collection=collection, user_id="u1", id_field="id", fetch_fn=fetch,
        max_attempts=5, retry_delay_seconds=0,
    )

    # 就算 max_attempts=5，NonRetryableError 也只該打一次就放棄，不多試
    assert call_count["n"] == 1
    assert stale is True
    # NonRetryableError 導致的退回快取，要標記成 auth_error，讓呼叫端知道
    # 這不是暫時性問題，使用者的憑證可能已經失效——不能悄悄退回舊資料就當沒事
    assert auth_error is True
    assert items[0]["title"] == "cached"


@pytest.mark.asyncio
async def test_sync_platform_items_non_retryable_error_skips_sleep(monkeypatch):
    """NonRetryableError 不該觸發任何退避等待，直接跳過重試邏輯。"""
    sleep_calls = []

    async def fake_sleep(seconds):
        sleep_calls.append(seconds)

    monkeypatch.setattr("crud.external_sync.asyncio.sleep", fake_sleep)

    collection = FakeCollection()

    async def fetch():
        raise NonRetryableError("404 Not Found")

    with pytest.raises(NonRetryableError):
        await sync_platform_items(
            collection=collection, user_id="u1", id_field="id", fetch_fn=fetch,
            max_attempts=3, retry_delay_seconds=1.0,
        )

    assert sleep_calls == []
