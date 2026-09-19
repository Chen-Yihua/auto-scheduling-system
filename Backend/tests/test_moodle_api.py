# 透過 HTTP 測試 /moodle 這組 API：路由有註冊、登入驗證有掛上、
# 回傳的 JSON 格式（response_model）跟 header 真的送得出去。
# 爬蟲、快取、fallback 等細節由 test_moodle_crud.py、test_moodle_router.py 負責，這裡不重複測。
from datetime import datetime, timezone

import pytest
from fastapi import status
from httpx import AsyncClient
from httpx._transports.asgi import ASGITransport

import cache
from main import app
from db.crypto import encrypt_secret
import routers.moodle as moodle_router


@pytest.fixture(autouse=True)
def clear_moodle_cache():
    """get_assignments 有 TTL 快取，清乾淨避免測試之間互相汙染。"""
    cache._memory_store.clear()
    yield
    cache._memory_store.clear()


class MockLinkedAccounts:
    """模擬 db.linkedAccounts.find_one：使用者有綁定 Moodle，密碼是真的加密過的。"""

    async def find_one(self, query):
        return {"username": "stu001", "password": encrypt_secret("decrypted_pw")}


class EmptyLinkedAccounts:
    """模擬 db.linkedAccounts.find_one：使用者還沒綁定 Moodle。"""

    async def find_one(self, query):
        return None


# 測試 GET /moodle/assignments —— 爬 Moodle 作業並用統一格式回傳
@pytest.mark.asyncio
async def test_get_moodle_assignments(monkeypatch, logged_in_user):
    assignments = [
        {
            "id": "https://moodle.nccu.edu.tw/mod/assign/view.php?id=1",
            "course_name": "資料結構",
            "title": "HW1",
            "url": "https://moodle.nccu.edu.tw/mod/assign/view.php?id=1",
            "due_date": "2026-09-10",
        }
    ]

    async def mock_sync(user_id, fetch_fn):
        # (作業清單, 是不是舊資料, 同步時間, 登入是否失敗)
        return assignments, False, datetime(2026, 9, 1, tzinfo=timezone.utc), False

    monkeypatch.setattr(moodle_router.db, "linkedAccounts", MockLinkedAccounts())
    monkeypatch.setattr(moodle_router, "sync_moodle_assignments", mock_sync)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/moodle/assignments")

    assert res.status_code == status.HTTP_200_OK
    assert res.json() == assignments
    assert res.headers["X-Data-Stale"] == "false"
    assert res.headers["X-Synced-At"] == "2026-09-01T00:00:00+00:00"


# 使用者還沒綁定 Moodle：HTTP 回應要是 400 加上說明，前端才能顯示「請先設定帳號」
@pytest.mark.asyncio
async def test_get_moodle_assignments_when_account_not_linked(monkeypatch, logged_in_user):
    monkeypatch.setattr(moodle_router.db, "linkedAccounts", EmptyLinkedAccounts())

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/moodle/assignments")

    assert res.status_code == status.HTTP_400_BAD_REQUEST
    assert res.json() == {"detail": "No Moodle linked account"}


# 沒帶登入 token（這個測試沒有用 logged_in_user）-> 要被擋在門外，不能進到函式裡
@pytest.mark.asyncio
async def test_get_moodle_assignments_requires_login():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/moodle/assignments")

    assert res.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)
