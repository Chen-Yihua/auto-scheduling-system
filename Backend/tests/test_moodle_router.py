# 直接呼叫 router 函式（await moodle_router.get_assignments(...)）測試它自己的判斷分支：
# 查不到帳號、解密失敗、爬蟲失敗各回什麼狀態碼、有沒有設定回應 header，以及 router 這一層的快取。
# 同步流程（重試、退回舊資料、寫入資料庫）由 test_external_sync.py 負責，這裡直接把它換成假的。
# 不經過 HTTP，所以不涉及路由註冊、登入驗證、response_model —— 那些由 test_moodle_api.py 負責。
import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock
from fastapi import HTTPException, Response

import cache
import routers.moodle as moodle_router
from crud.errors import NonRetryableError
from db.crypto import encrypt_secret

mock_user = {"sub": "test_user_123"}

ASSIGNMENT = {
    "id": "https://moodle.nccu.edu.tw/mod/assign/view.php?id=1",
    "course_name": "資料結構",
    "title": "HW1",
    "url": "https://moodle.nccu.edu.tw/mod/assign/view.php?id=1",
    "due_date": "2026-09-10",
}


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


async def _call_get_assignments(response=None):
    return await moodle_router.get_assignments(
        request=MagicMock(), response=response or Response(), clerk_user=mock_user
    )


@pytest.mark.asyncio
async def test_get_assignments_success(monkeypatch):
    """成功流程：查到帳號 → 解密密碼 → 爬 Moodle → 回傳作業清單，X-Data-Stale 為 false；爬蟲拿到的是解密後的明文密碼，不是資料庫裡的密文。"""
    fetch_calls = []

    def mock_fetch_assignments(username, password):
        fetch_calls.append((username, password))
        return [ASSIGNMENT]

    async def mock_sync(user_id, fetch_fn):
        # 真的執行 router 交給 sync 的 fetch_fn，才測得到「解密 → 爬蟲」這段
        return (await fetch_fn(), False, datetime(2026, 9, 1, tzinfo=timezone.utc), False)

    monkeypatch.setattr(moodle_router.db, "linkedAccounts", MockLinkedAccounts())
    monkeypatch.setattr(moodle_router, "fetch_assignments", mock_fetch_assignments)
    monkeypatch.setattr(moodle_router, "sync_moodle_assignments", mock_sync)

    response = Response()
    result = await _call_get_assignments(response)

    assert result == [ASSIGNMENT]
    assert response.headers["X-Data-Stale"] == "false"
    assert fetch_calls == [("stu001", "decrypted_pw")]


@pytest.mark.asyncio
async def test_get_assignments_raises_400_when_account_not_linked(monkeypatch):
    """使用者還沒綁定 Moodle → 回 400 "No Moodle linked account"。"""
    class EmptyLinkedAccounts:
        async def find_one(self, query):
            return None

    monkeypatch.setattr(moodle_router.db, "linkedAccounts", EmptyLinkedAccounts())

    with pytest.raises(HTTPException) as exc_info:
        await _call_get_assignments()

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
        await _call_get_assignments()

    assert exc_info.value.status_code == 500


@pytest.mark.asyncio
async def test_get_assignments_raises_500_on_unexpected_sync_error(monkeypatch):
    """同步時出現未預期的錯誤 → 回 500 和固定中文訊息；內部錯誤原因只寫進 log，不回傳給前端。"""
    async def mock_sync(user_id, fetch_fn):
        raise RuntimeError("unexpected bug")

    monkeypatch.setattr(moodle_router.db, "linkedAccounts", MockLinkedAccounts())
    monkeypatch.setattr(moodle_router, "sync_moodle_assignments", mock_sync)

    with pytest.raises(HTTPException) as exc_info:
        await _call_get_assignments()

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == "無法取得 Moodle 資料，請稍後再試"


@pytest.mark.asyncio
async def test_get_assignments_login_failure_raises_401(monkeypatch):
    """Moodle 帳密驗證失敗（NonRetryableError）→ 回 401 和固定訊息；內部原因（含帳號資訊）只寫進 log，不回傳給前端。"""
    async def mock_sync(user_id, fetch_fn):
        raise NonRetryableError("Moodle 登入失敗，使用者：stu001")

    monkeypatch.setattr(moodle_router.db, "linkedAccounts", MockLinkedAccounts())
    monkeypatch.setattr(moodle_router, "sync_moodle_assignments", mock_sync)

    with pytest.raises(HTTPException) as exc_info:
        await _call_get_assignments()

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "無法取得 Moodle 資料，請確認帳號密碼是否正確"


@pytest.mark.asyncio
async def test_get_assignments_sets_auth_error_header(monkeypatch):
    """帳密已失效、但有舊資料可顯示 → 回舊資料，並用 X-Auth-Error 告訴前端要重新連結帳號、X-Data-Stale 標示資料是舊的。"""
    async def mock_sync(user_id, fetch_fn):
        return ([], True, None, True)

    monkeypatch.setattr(moodle_router.db, "linkedAccounts", MockLinkedAccounts())
    monkeypatch.setattr(moodle_router, "sync_moodle_assignments", mock_sync)

    response = Response()
    result = await _call_get_assignments(response)

    assert result == []
    assert response.headers["X-Auth-Error"] == "true"
    assert response.headers["X-Data-Stale"] == "true"


@pytest.mark.asyncio
async def test_get_assignments_stale_cache_without_auth_error_omits_auth_header(monkeypatch):
    """爬蟲暫時失敗、退回舊資料（不是帳密問題）→ 回舊資料，X-Data-Stale 為 true 並帶 X-Synced-At，但不設 X-Auth-Error（沒有要使用者重新連結）。"""
    synced_at = datetime(2026, 9, 1, tzinfo=timezone.utc)

    async def mock_sync(user_id, fetch_fn):
        return ([ASSIGNMENT], True, synced_at, False)

    monkeypatch.setattr(moodle_router.db, "linkedAccounts", MockLinkedAccounts())
    monkeypatch.setattr(moodle_router, "sync_moodle_assignments", mock_sync)

    response = Response()
    result = await _call_get_assignments(response)

    assert result == [ASSIGNMENT]
    assert response.headers["X-Data-Stale"] == "true"
    assert response.headers["X-Synced-At"] == synced_at.isoformat()
    assert "X-Auth-Error" not in response.headers


@pytest.mark.asyncio
async def test_get_assignments_second_call_within_ttl_skips_scrape_entirely(monkeypatch):
    """短時間內重複整理：第二次要直接用快取，不再重新爬 Moodle（爬蟲要開瀏覽器，成本高）。"""
    sync_calls = {"n": 0}

    async def mock_sync(user_id, fetch_fn):
        sync_calls["n"] += 1
        return ([ASSIGNMENT], False, datetime(2026, 9, 1, tzinfo=timezone.utc), False)

    monkeypatch.setattr(moodle_router.db, "linkedAccounts", MockLinkedAccounts())
    monkeypatch.setattr(moodle_router, "sync_moodle_assignments", mock_sync)

    first = await _call_get_assignments()
    second_response = Response()
    second = await _call_get_assignments(second_response)

    assert first == second
    # 第二次應該直接命中快取，完全不該再爬一次
    assert sync_calls["n"] == 1
    assert second_response.headers["X-Data-Stale"] == "false"


@pytest.mark.asyncio
async def test_get_assignments_does_not_cache_stale_fallback_result(monkeypatch):
    """爬蟲失敗、只能退回舊資料時，這份舊資料不能被快取——否則下一次請求會直接讀到「已知是舊的」快取，錯過重新嘗試爬蟲的機會。"""
    sync_calls = {"n": 0}

    async def mock_sync(user_id, fetch_fn):
        sync_calls["n"] += 1
        return ([ASSIGNMENT], True, datetime(2026, 9, 1, tzinfo=timezone.utc), True)

    monkeypatch.setattr(moodle_router.db, "linkedAccounts", MockLinkedAccounts())
    monkeypatch.setattr(moodle_router, "sync_moodle_assignments", mock_sync)

    await _call_get_assignments()
    await _call_get_assignments()

    # 兩次都該真的重新嘗試同步，因為舊資料沒有被快取
    assert sync_calls["n"] == 2
