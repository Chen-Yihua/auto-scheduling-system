# 透過 HTTP 測試 /oauth 這組 API：路由有註冊、登入驗證有掛上、
# 回傳的 JSON 格式跟錯誤狀態碼真的送得出去。
# 跟 Google 換 token、refresh、算空檔等細節由 test_oauth_router.py、
# test_oauth_free_slots.py、test_google_calendar_service.py 負責，這裡不重複測。
import pytest
from fastapi import HTTPException, status
from httpx import AsyncClient
from httpx._transports.asgi import ASGITransport

from main import app
import routers.oauth as oauth_router


@pytest.mark.asyncio
async def test_get_google_calendar_status(monkeypatch, logged_in_user):
    """GET /oauth/status：回報使用者有沒有連接過 Google Calendar（{"connected": true/false}），只查資料庫、不打 Google API。"""
    async def mock_is_connected(clerk_id):
        return True

    monkeypatch.setattr(oauth_router, "is_google_calendar_connected", mock_is_connected)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/oauth/status")

    assert res.status_code == status.HTTP_200_OK
    assert res.json() == {"connected": True}


@pytest.mark.asyncio
async def test_get_available_times(monkeypatch, logged_in_user):
    """GET /oauth/available：回傳未來 7 天的空閒時段（UTC），格式是 {"freeSlotsUtc": [...]}。"""
    free_slots = [{"start": "2026-09-10T09:00:00Z", "end": "2026-09-10T10:00:00Z"}]

    async def mock_get_free_slots(clerk_id):
        return free_slots

    monkeypatch.setattr(oauth_router, "get_free_slots_for_user", mock_get_free_slots)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/oauth/available")

    assert res.status_code == status.HTTP_200_OK
    assert res.json() == {"freeSlotsUtc": free_slots}


@pytest.mark.asyncio
async def test_get_calendars_when_not_connected(monkeypatch, logged_in_user):
    """使用者還沒授權 Google Calendar → 400 加中文說明。"""
    async def mock_get_token(clerk_id):
        raise HTTPException(status_code=400, detail="尚未連接 Google Calendar")

    monkeypatch.setattr(oauth_router, "get_google_calendar_token", mock_get_token)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/oauth/calendars")

    assert res.status_code == status.HTTP_400_BAD_REQUEST
    assert res.json() == {"detail": "尚未連接 Google Calendar"}


@pytest.mark.asyncio
async def test_oauth_callback_requires_code(logged_in_user):
    """POST /oauth/callback 沒帶 code → 回 422，請求根本不會進到處理函式。"""
    # 這是 FastAPI 在進函式前做的請求驗證，得走 HTTP 才測得到；直接呼叫函式不會經過這一層
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post("/oauth/callback", json={})

    assert res.status_code == 422  # Starlette 新舊版常數名不同（ENTITY / CONTENT），直接用數字


@pytest.mark.asyncio
async def test_get_google_calendar_status_requires_login():
    """沒帶登入 token → 被擋在門外（401/403），不能進到函式裡。"""
    # 這個測試刻意不用 logged_in_user，所以請求是沒登入的
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/oauth/status")

    assert res.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)
