"""platforms/sync.py 的抓取重試與項目寫入；同步流程（鎖、新舊判斷）由 test_account_sync.py 負責。"""
import pytest
from datetime import datetime, timezone

from platforms.sync import (
    NonRetryableError,
    delete_missing_items,
    fetch_with_retry,
    read_items,
    upsert_items,
)


class FakeCursor:
    def __init__(self, docs):
        self._docs = docs

    async def to_list(self, length=None):
        return [dict(d) for d in self._docs]


class FakeCollection:
    """簡化的 in-memory collection，模擬 update_one(upsert)、find().to_list() 和 delete_many。"""

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


NOW = datetime(2026, 11, 14, 4, 0, tzinfo=timezone.utc)


# ---------- 寫入項目 ----------

@pytest.mark.asyncio
async def test_upsert_items_writes_user_id_and_synced_at():
    """抓到的項目存進資料庫，帶上使用者 id 與這次同步時間。"""
    collection = FakeCollection()

    written = await upsert_items(collection, "u1", "id", [{"id": 1, "title": "a"}, {"id": 2, "title": "b"}], NOW)

    assert [i["title"] for i in written] == ["a", "b"]
    assert len(collection._docs) == 2
    assert collection._docs[0]["user_id"] == "u1"
    assert collection._docs[0]["synced_at"] == NOW


@pytest.mark.asyncio
async def test_upsert_items_removes_duplicate_ids():
    """抓回來的資料裡同一個 id 出現兩次（例如翻頁時資料變動）→ 只保留一筆，用最後一次的內容。"""
    collection = FakeCollection()

    written = await upsert_items(
        collection, "u1", "id", [{"id": 1, "title": "舊"}, {"id": 2, "title": "b"}, {"id": 1, "title": "新"}], NOW,
    )

    assert [(i["id"], i["title"]) for i in written] == [(1, "新"), (2, "b")]
    assert len(collection._docs) == 2


@pytest.mark.asyncio
async def test_upsert_items_updates_existing_item_and_keeps_user_fields():
    """AC49：DB 已有同 id 的項目時更新它，不重複新增；使用者設定的排程欄位要保留。"""
    collection = FakeCollection(initial=[{"id": 1, "title": "old", "user_id": "u1", "priority": "high", "done": True}])

    await upsert_items(collection, "u1", "id", [{"id": 1, "title": "new"}], NOW)

    assert len(collection._docs) == 1
    assert collection._docs[0]["title"] == "new"
    assert collection._docs[0]["priority"] == "high"
    assert collection._docs[0]["done"] is True


@pytest.mark.asyncio
async def test_delete_missing_items_removes_items_no_longer_returned():
    """這次沒抓到的項目要從 DB 刪除，否則畫面會出現平台上早就不存在的項目。"""
    collection = FakeCollection(initial=[
        {"id": 1, "title": "still open", "user_id": "u1"},
        {"id": 2, "title": "already closed on github", "user_id": "u1"},
    ])

    await delete_missing_items(collection, "u1", "id", [1])

    assert [d["id"] for d in collection._docs] == [1]


@pytest.mark.asyncio
async def test_delete_missing_items_does_not_affect_other_users():
    """清掉「這次已不存在」的項目時，只能動當前使用者的資料，不能誤刪其他使用者同 id 的項目。"""
    collection = FakeCollection(initial=[
        {"id": 1, "title": "user u1's item", "user_id": "u1"},
        {"id": 1, "title": "user u2's item", "user_id": "u2"},
    ])

    await delete_missing_items(collection, "u1", "id", [])

    assert [(d["user_id"], d["id"]) for d in collection._docs] == [("u2", 1)]


@pytest.mark.asyncio
async def test_read_items_returns_only_this_users_items_without_mongo_id():
    """讀資料庫的項目只拿當前使用者的，回傳的資料不含資料庫內部 id。"""
    collection = FakeCollection(initial=[
        {"_id": "m1", "id": 1, "title": "mine", "user_id": "u1"},
        {"_id": "m2", "id": 2, "title": "other", "user_id": "u2"},
    ])

    items = await read_items(collection, "u1")

    assert [i["title"] for i in items] == ["mine"]
    assert "_id" not in items[0]


# ---------- 抓取重試 ----------

@pytest.mark.asyncio
async def test_fetch_with_retry_retries_and_recovers_on_second_attempt():
    """第一次抓失敗、第二次就成功 → 回傳重試後拿到的資料。"""
    call_count = {"n": 0}

    async def fetch():
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise Exception("暫時性失敗")
        return [{"id": 1, "title": "recovered"}]

    items = await fetch_with_retry("u1", fetch, retry_delay_seconds=0)

    assert call_count["n"] == 2
    assert items[0]["title"] == "recovered"


@pytest.mark.asyncio
async def test_fetch_with_retry_raises_last_error_after_max_attempts():
    """max_attempts=3 時剛好嘗試 3 次都失敗，才把最後的例外往外丟——不多試也不少試。"""
    call_count = {"n": 0}

    async def fetch():
        call_count["n"] += 1
        raise Exception(f"失敗 {call_count['n']}")

    with pytest.raises(Exception, match="失敗 3"):
        await fetch_with_retry("u1", fetch, max_attempts=3, retry_delay_seconds=0)

    assert call_count["n"] == 3


@pytest.mark.asyncio
async def test_fetch_with_retry_backs_off_exponentially_between_retries(monkeypatch):
    """重試之間的等待時間要指數成長（1 秒、2 秒、4 秒…），不是每次都等一樣久。"""
    sleep_calls = []

    async def fake_sleep(seconds):
        sleep_calls.append(seconds)

    monkeypatch.setattr("platforms.sync.asyncio.sleep", fake_sleep)

    async def fetch():
        raise Exception("一直失敗")

    with pytest.raises(Exception):
        await fetch_with_retry("u1", fetch, max_attempts=4, retry_delay_seconds=1.0)

    assert sleep_calls == [1.0, 2.0, 4.0]


@pytest.mark.asyncio
async def test_fetch_with_retry_does_not_retry_non_retryable_error(monkeypatch):
    """NonRetryableError（例如帳密/token 錯誤）不重試、不等待，抓一次失敗就直接放棄。"""
    sleep_calls = []

    async def fake_sleep(seconds):
        sleep_calls.append(seconds)

    monkeypatch.setattr("platforms.sync.asyncio.sleep", fake_sleep)
    call_count = {"n": 0}

    async def fetch():
        call_count["n"] += 1
        raise NonRetryableError("401 Unauthorized")

    with pytest.raises(NonRetryableError):
        await fetch_with_retry("u1", fetch, max_attempts=5, retry_delay_seconds=1.0)

    assert call_count["n"] == 1
    assert sleep_calls == []
