# 直接呼叫 router 函式（await moodle_router.get_assignments(...)）測試它自己的判斷分支：
# 查不到帳號、DB 掛掉、解密失敗、爬蟲失敗各回什麼狀態碼，以及有沒有設定回應 header。
# 不經過 HTTP，所以不涉及路由註冊、登入驗證、response_model —— 那些由 test_moodle_api.py 負責。
import pytest
from unittest.mock import MagicMock
from fastapi import HTTPException, Response

import cache
import routers.moodle as moodle_router
from crud.errors import NonRetryableError
from db.crypto import encrypt_secret

mock_user = {"sub": "test_user_123"}


class MockLinkedAccounts:
    """模擬 db.linkedAccounts.find_one，回傳的密碼是真的加密過的，
    確保 router 裡的 decrypt_secret 呼叫真的會被跑到、不是被繞過。"""

    async def find_one(self, query):
        return {"username": "stu001", "password": encrypt_secret("decrypted_pw")}


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
    """成功流程：查到帳號 → 解密密碼 → 爬 Moodle → 存進 DB 並回傳作業清單，X-Data-Stale 為 false；爬蟲拿到的是解密後的明文密碼，不是資料庫裡的密文。"""
    fetch_calls = []

    def mock_fetch_assignments(username, password):
        fetch_calls.append((username, password))
        return [
            {
                "id": "https://moodle.nccu.edu.tw/mod/assign/view.php?id=1",
                "course_name": "資料結構",
                "title": "HW1",
                "url": "https://moodle.nccu.edu.tw/mod/assign/view.php?id=1",
                "due_date": "2026-09-10",
            }
        ]

    fake_collection = FakeMoodleAssignments()
    async def instant_sleep(seconds):
        pass

    monkeypatch.setattr(moodle_router.db, "linkedAccounts", MockLinkedAccounts())
    monkeypatch.setattr(moodle_router, "fetch_assignments", mock_fetch_assignments)
    monkeypatch.setattr(moodle_router.db, "moodle_assignments", fake_collection)
    monkeypatch.setattr("crud.external_sync.asyncio.sleep", instant_sleep)

    response = Response()
    result = await moodle_router.get_assignments(request=MagicMock(), response=response, clerk_user=mock_user)

    assert result[0]["title"] == "HW1"
    assert response.headers["X-Data-Stale"] == "false"
    assert len(fake_collection._docs) == 1
    # 密碼在資料庫裡是加密的（MockLinkedAccounts 用 encrypt_secret 存），爬蟲登入前
    # 一定要在伺服器內部先解密回明文，不能把密文原封不動傳給 fetch_assignments
    assert fetch_calls == [("stu001", "decrypted_pw")]


@pytest.mark.asyncio
async def test_get_assignments_falls_back_to_cache_when_scrape_fails(monkeypatch):
    """爬蟲失敗（登入失敗）但 DB 有上次成功抓到的資料 → 回舊資料，X-Data-Stale 為 true；登入失敗是 NonRetryableError，只爬一次、不重試。"""
    call_count = {"n": 0}

    def mock_fetch_assignments(username, password):
        call_count["n"] += 1
        # 真實的 crud/moodle.py 對登入失敗會拋 NonRetryableError（帳密錯誤重試也沒用）
        raise NonRetryableError("Moodle 登入失敗，使用者：stu001")

    cached_doc = {
        "id": "https://moodle.nccu.edu.tw/mod/assign/view.php?id=1",
        "course_name": "資料結構",
        "title": "HW1（上次抓到的）",
        "url": "https://moodle.nccu.edu.tw/mod/assign/view.php?id=1",
        "due_date": "2026-09-10",
        "user_id": mock_user["sub"],
    }
    fake_collection = FakeMoodleAssignments(initial=[cached_doc])
    async def instant_sleep(seconds):
        pass

    monkeypatch.setattr(moodle_router.db, "linkedAccounts", MockLinkedAccounts())
    monkeypatch.setattr(moodle_router, "fetch_assignments", mock_fetch_assignments)
    monkeypatch.setattr(moodle_router.db, "moodle_assignments", fake_collection)
    monkeypatch.setattr("crud.external_sync.asyncio.sleep", instant_sleep)

    response = Response()
    result = await moodle_router.get_assignments(request=MagicMock(), response=response, clerk_user=mock_user)

    assert result[0]["title"] == "HW1（上次抓到的）"
    assert response.headers["X-Data-Stale"] == "true"
    # 登入失敗是 NonRetryableError，不該被重試——只該爬一次
    assert call_count["n"] == 1


@pytest.mark.asyncio
async def test_get_assignments_raises_401_when_scrape_fails_and_no_cache(monkeypatch):
    """爬蟲失敗又沒有舊資料可退回 → 回 401 和固定訊息；內部原因（含帳號資訊）只寫進 log，不回傳給前端。"""
    def mock_fetch_assignments(username, password):
        raise NonRetryableError("Moodle 登入失敗，使用者：stu001")

    async def instant_sleep(seconds):
        pass

    monkeypatch.setattr(moodle_router.db, "linkedAccounts", MockLinkedAccounts())
    monkeypatch.setattr(moodle_router, "fetch_assignments", mock_fetch_assignments)
    monkeypatch.setattr(moodle_router.db, "moodle_assignments", FakeMoodleAssignments())
    monkeypatch.setattr("crud.external_sync.asyncio.sleep", instant_sleep)

    with pytest.raises(HTTPException) as exc_info:
        await moodle_router.get_assignments(request=MagicMock(), response=Response(), clerk_user=mock_user)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "無法取得 Moodle 資料，請確認帳號密碼是否正確"


@pytest.mark.asyncio
async def test_get_assignments_raises_400_when_account_not_linked(monkeypatch):
    """使用者還沒綁定 Moodle → 回 400 "No Moodle linked account"。"""
    class EmptyLinkedAccounts:
        async def find_one(self, query):
            return None

    monkeypatch.setattr(moodle_router.db, "linkedAccounts", EmptyLinkedAccounts())

    with pytest.raises(HTTPException) as exc_info:
        await moodle_router.get_assignments(request=MagicMock(), response=Response(), clerk_user=mock_user)

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "No Moodle linked account"


@pytest.mark.asyncio
async def test_get_assignments_raises_500_when_decrypt_fails(monkeypatch):
    """密碼解密失敗（資料壞掉或金鑰不對）→ 回 500。"""
    class BadlyEncryptedLinkedAccounts:
        async def find_one(self, query):
            return {"username": "stu001", "password": "not-actually-encrypted"}

    monkeypatch.setattr(moodle_router.db, "linkedAccounts", BadlyEncryptedLinkedAccounts())

    with pytest.raises(HTTPException) as exc_info:
        await moodle_router.get_assignments(request=MagicMock(), response=Response(), clerk_user=mock_user)

    assert exc_info.value.status_code == 500


@pytest.mark.asyncio
async def test_get_assignments_raises_500_on_unexpected_sync_error(monkeypatch):
    """同步時出現未預期的錯誤 → 回 500 和固定中文訊息。"""
    async def mock_sync(user_id, fetch_fn):
        raise RuntimeError("unexpected bug")

    monkeypatch.setattr(moodle_router.db, "linkedAccounts", MockLinkedAccounts())
    monkeypatch.setattr(moodle_router, "sync_moodle_assignments", mock_sync)

    with pytest.raises(HTTPException) as exc_info:
        await moodle_router.get_assignments(request=MagicMock(), response=Response(), clerk_user=mock_user)

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == "無法取得 Moodle 資料，請稍後再試"


@pytest.mark.asyncio
async def test_get_assignments_sets_auth_error_header(monkeypatch):
    """帳密已失效、但有舊資料可顯示 → 回舊資料，並用 X-Auth-Error 告訴前端要重新連結帳號、X-Data-Stale 標示資料是舊的。"""
    async def mock_sync(user_id, fetch_fn):
        return ([], True, None, True)

    monkeypatch.setattr(moodle_router.db, "linkedAccounts", MockLinkedAccounts())
    monkeypatch.setattr(moodle_router, "sync_moodle_assignments", mock_sync)

    response = Response()
    result = await moodle_router.get_assignments(request=MagicMock(), response=response, clerk_user=mock_user)

    assert result == []
    assert response.headers["X-Auth-Error"] == "true"
    assert response.headers["X-Data-Stale"] == "true"


@pytest.mark.asyncio
async def test_get_assignments_second_call_within_ttl_skips_scrape_entirely(monkeypatch):
    """短時間內重複整理：第二次要直接用快取，不再重新爬 Moodle（爬蟲要開瀏覽器，成本高）。"""
    call_count = {"n": 0}

    def mock_fetch_assignments(username, password):
        call_count["n"] += 1
        return [
            {
                "id": "https://moodle.nccu.edu.tw/mod/assign/view.php?id=1",
                "course_name": "資料結構",
                "title": "HW1",
                "url": "https://moodle.nccu.edu.tw/mod/assign/view.php?id=1",
                "due_date": "2026-09-10",
            }
        ]

    async def instant_sleep(seconds):
        pass

    monkeypatch.setattr(moodle_router.db, "linkedAccounts", MockLinkedAccounts())
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
    """爬蟲失敗、只能退回舊資料時，這份舊資料不能被快取——否則下一次請求會直接讀到「已知是舊的」快取，錯過重新嘗試爬蟲的機會。"""
    call_count = {"n": 0}

    def mock_fetch_assignments(username, password):
        call_count["n"] += 1
        raise NonRetryableError("Moodle 登入失敗，使用者：stu001")

    cached_doc = {
        "id": "https://moodle.nccu.edu.tw/mod/assign/view.php?id=1",
        "course_name": "資料結構",
        "title": "HW1（上次抓到的）",
        "url": "https://moodle.nccu.edu.tw/mod/assign/view.php?id=1",
        "due_date": "2026-09-10",
        "user_id": mock_user["sub"],
    }

    async def instant_sleep(seconds):
        pass

    monkeypatch.setattr(moodle_router.db, "linkedAccounts", MockLinkedAccounts())
    monkeypatch.setattr(moodle_router, "fetch_assignments", mock_fetch_assignments)
    monkeypatch.setattr(moodle_router.db, "moodle_assignments", FakeMoodleAssignments(initial=[cached_doc]))
    monkeypatch.setattr("crud.external_sync.asyncio.sleep", instant_sleep)

    await moodle_router.get_assignments(request=MagicMock(), response=Response(), clerk_user=mock_user)
    await moodle_router.get_assignments(request=MagicMock(), response=Response(), clerk_user=mock_user)

    # 兩次都該真的嘗試爬蟲（NonRetryableError 各自只爬一次，兩次呼叫共兩次）
    assert call_count["n"] == 2
