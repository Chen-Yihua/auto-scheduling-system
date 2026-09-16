import pytest
from unittest.mock import MagicMock
from fastapi import HTTPException, Response

import cache
import routers.moodle as moodle_router
from crud.errors import NonRetryableError

mock_user = {"sub": "test_user_123"}


@pytest.fixture(autouse=True)
def clear_moodle_cache():
    """get_assignments 現在有 TTL 快取，清乾淨避免測試之間互相汙染。"""
    cache._memory_store.clear()
    yield
    cache._memory_store.clear()


class FakeCursor:
    def __init__(self, docs):
        self._docs = docs

    async def to_list(self, length=None):
        return [dict(d) for d in self._docs]


class FakeMoodleAssignments:
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
async def test_get_assignments_success(monkeypatch):
    async def mock_get_user_account(clerk_id):
        return {"username": "stu001", "password": "decrypted_pw"}

    def mock_fetch_assignments(username, password):
        return [
            {
                "id": "https://moodle.nccu.edu.tw/mod/assign/view.php?id=1",
                "course_name": "資料結構",
                "assignment_title": "HW1",
                "assignment_url": "https://moodle.nccu.edu.tw/mod/assign/view.php?id=1",
                "due_date": "2026-09-10",
            }
        ]

    fake_collection = FakeMoodleAssignments()
    async def instant_sleep(seconds):
        pass

    monkeypatch.setattr(moodle_router, "get_user_account", mock_get_user_account)
    monkeypatch.setattr(moodle_router, "fetch_assignments", mock_fetch_assignments)
    monkeypatch.setattr(moodle_router.db, "moodle_assignments", fake_collection)
    monkeypatch.setattr("crud.external_sync.asyncio.sleep", instant_sleep)

    response = Response()
    result = await moodle_router.get_assignments(request=MagicMock(), response=response, clerk_user=mock_user)

    assert result[0]["assignment_title"] == "HW1"
    assert response.headers["X-Data-Stale"] == "false"
    assert len(fake_collection._docs) == 1


@pytest.mark.asyncio
async def test_get_assignments_falls_back_to_cache_when_scrape_fails(monkeypatch):
    async def mock_get_user_account(clerk_id):
        return {"username": "stu001", "password": "decrypted_pw"}

    call_count = {"n": 0}

    def mock_fetch_assignments(username, password):
        call_count["n"] += 1
        # 真實的 crud/moodle.py 對登入失敗會拋 NonRetryableError（帳密錯誤重試也沒用）
        raise NonRetryableError("Moodle 登入失敗，使用者：stu001")

    cached_doc = {
        "id": "https://moodle.nccu.edu.tw/mod/assign/view.php?id=1",
        "course_name": "資料結構",
        "assignment_title": "HW1（上次抓到的）",
        "assignment_url": "https://moodle.nccu.edu.tw/mod/assign/view.php?id=1",
        "due_date": "2026-09-10",
        "user_id": mock_user["sub"],
    }
    fake_collection = FakeMoodleAssignments(initial=[cached_doc])
    async def instant_sleep(seconds):
        pass

    monkeypatch.setattr(moodle_router, "get_user_account", mock_get_user_account)
    monkeypatch.setattr(moodle_router, "fetch_assignments", mock_fetch_assignments)
    monkeypatch.setattr(moodle_router.db, "moodle_assignments", fake_collection)
    monkeypatch.setattr("crud.external_sync.asyncio.sleep", instant_sleep)

    response = Response()
    result = await moodle_router.get_assignments(request=MagicMock(), response=response, clerk_user=mock_user)

    assert result[0]["assignment_title"] == "HW1（上次抓到的）"
    assert response.headers["X-Data-Stale"] == "true"
    # 登入失敗是 NonRetryableError，不該被重試——只該爬一次
    assert call_count["n"] == 1


@pytest.mark.asyncio
async def test_get_assignments_raises_401_when_scrape_fails_and_no_cache(monkeypatch):
    async def mock_get_user_account(clerk_id):
        return {"username": "stu001", "password": "decrypted_pw"}

    def mock_fetch_assignments(username, password):
        raise NonRetryableError("Moodle 登入失敗，使用者：stu001")

    async def instant_sleep(seconds):
        pass

    monkeypatch.setattr(moodle_router, "get_user_account", mock_get_user_account)
    monkeypatch.setattr(moodle_router, "fetch_assignments", mock_fetch_assignments)
    monkeypatch.setattr(moodle_router.db, "moodle_assignments", FakeMoodleAssignments())
    monkeypatch.setattr("crud.external_sync.asyncio.sleep", instant_sleep)

    with pytest.raises(HTTPException) as exc_info:
        await moodle_router.get_assignments(request=MagicMock(), response=Response(), clerk_user=mock_user)

    assert exc_info.value.status_code == 401
    # detail 應該是給使用者看的固定訊息，內部例外原因（含帳號資訊）只會寫進 log，
    # 不會回傳給前端（避免洩漏內部細節）
    assert exc_info.value.detail == "無法取得 Moodle 資料，請確認帳號密碼是否正確"


@pytest.mark.asyncio
async def test_get_assignments_second_call_within_ttl_skips_scrape_entirely(monkeypatch):
    call_count = {"n": 0}

    async def mock_get_user_account(clerk_id):
        return {"username": "stu001", "password": "decrypted_pw"}

    def mock_fetch_assignments(username, password):
        call_count["n"] += 1
        return [
            {
                "id": "https://moodle.nccu.edu.tw/mod/assign/view.php?id=1",
                "course_name": "資料結構",
                "assignment_title": "HW1",
                "assignment_url": "https://moodle.nccu.edu.tw/mod/assign/view.php?id=1",
                "due_date": "2026-09-10",
            }
        ]

    async def instant_sleep(seconds):
        pass

    monkeypatch.setattr(moodle_router, "get_user_account", mock_get_user_account)
    monkeypatch.setattr(moodle_router, "fetch_assignments", mock_fetch_assignments)
    monkeypatch.setattr(moodle_router.db, "moodle_assignments", FakeMoodleAssignments())
    monkeypatch.setattr("crud.external_sync.asyncio.sleep", instant_sleep)

    first = await moodle_router.get_assignments(request=MagicMock(), response=Response(), clerk_user=mock_user)
    second_response = Response()
    second = await moodle_router.get_assignments(request=MagicMock(), response=second_response, clerk_user=mock_user)

    assert first == second
    # 第二次應該直接命中快取，完全不該再爬一次
    assert call_count["n"] == 1
    assert second_response.headers["X-Data-Stale"] == "false"


@pytest.mark.asyncio
async def test_get_assignments_does_not_cache_stale_fallback_result(monkeypatch):
    """
    爬蟲失敗、退回 DB 舊資料時（stale=True）不該進 TTL 快取——
    否則下一次呼叫會直接讀到「已知是舊的」快取，跳過重新嘗試爬蟲的機會。
    """
    call_count = {"n": 0}

    async def mock_get_user_account(clerk_id):
        return {"username": "stu001", "password": "decrypted_pw"}

    def mock_fetch_assignments(username, password):
        call_count["n"] += 1
        raise NonRetryableError("Moodle 登入失敗，使用者：stu001")

    cached_doc = {
        "id": "https://moodle.nccu.edu.tw/mod/assign/view.php?id=1",
        "course_name": "資料結構",
        "assignment_title": "HW1（上次抓到的）",
        "assignment_url": "https://moodle.nccu.edu.tw/mod/assign/view.php?id=1",
        "due_date": "2026-09-10",
        "user_id": mock_user["sub"],
    }

    async def instant_sleep(seconds):
        pass

    monkeypatch.setattr(moodle_router, "get_user_account", mock_get_user_account)
    monkeypatch.setattr(moodle_router, "fetch_assignments", mock_fetch_assignments)
    monkeypatch.setattr(moodle_router.db, "moodle_assignments", FakeMoodleAssignments(initial=[cached_doc]))
    monkeypatch.setattr("crud.external_sync.asyncio.sleep", instant_sleep)

    await moodle_router.get_assignments(request=MagicMock(), response=Response(), clerk_user=mock_user)
    await moodle_router.get_assignments(request=MagicMock(), response=Response(), clerk_user=mock_user)

    # 兩次都該真的嘗試爬蟲（NonRetryableError 各自只爬一次，兩次呼叫共兩次）
    assert call_count["n"] == 2
