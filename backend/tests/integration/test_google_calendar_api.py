# 透過 HTTP 確認路由、登入驗證、回應格式和錯誤狀態碼；細部邏輯由 unit 測試負責
import httpx
import pytest
from cryptography.fernet import Fernet
from fastapi import HTTPException, status
from httpx import AsyncClient
from httpx._transports.asgi import ASGITransport

from main import app
from core import cache
from core.crypto import encrypt_secret
from core.database import db
import routers.google_calendar as google_calendar_router
import routers.schedule as schedule_router
import services.google_calendar as calendar_service
import services.google_oauth as google_oauth


@pytest.mark.asyncio
async def test_get_google_calendar_status(monkeypatch, logged_in_user):
    """GET /oauth/status：回報是否已連接 Google Calendar，只查資料庫。"""
    async def mock_is_connected(clerk_id):
        return True

    monkeypatch.setattr(google_calendar_router, "is_google_calendar_connected", mock_is_connected)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/oauth/status")

    assert res.status_code == status.HTTP_200_OK
    assert res.json() == {"connected": True}


@pytest.mark.asyncio
async def test_get_calendars_when_not_connected(monkeypatch, logged_in_user):
    """使用者還沒授權 Google Calendar → 400 加中文說明。"""
    async def mock_get_token(clerk_id):
        raise HTTPException(status_code=400, detail="尚未連接 Google Calendar")

    monkeypatch.setattr(calendar_service, "get_google_calendar_token", mock_get_token)

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


def _unauthorized_error() -> httpx.HTTPStatusError:
    request = httpx.Request("GET", "https://example.com")
    return httpx.HTTPStatusError("Unauthorized", request=request, response=httpx.Response(401, request=request))


def _token_unusable(monkeypatch, case: str) -> list:
    """讓 DB 裡的 Google token 照 case 的方式不能用；回傳記錄 delete_one 呼叫的 list。"""
    other_key = Fernet(Fernet.generate_key())
    access_token = encrypt_secret("expired-token")
    refresh_token = encrypt_secret("rt")
    if case == "decrypt_failed":
        access_token = other_key.encrypt(b"at").decode()

    async def mock_find_one(query):
        return {"_id": "test_user_123", "access_token": access_token, "refresh_token": refresh_token}

    deleted = []

    async def mock_delete_one(query):
        deleted.append(query)

    async def mock_fetch_calendar_list(token):
        raise _unauthorized_error()

    monkeypatch.setattr(db.googleCalendarTokens, "find_one", mock_find_one)
    monkeypatch.setattr(db.googleCalendarTokens, "delete_one", mock_delete_one)
    monkeypatch.setattr(calendar_service, "fetch_google_calendar_list", mock_fetch_calendar_list)

    if case == "unauthorized_client":
        real_client = httpx.AsyncClient
        transport = httpx.MockTransport(lambda request: httpx.Response(401, text='{"error": "unauthorized_client"}'))
        monkeypatch.setattr(google_oauth.httpx, "AsyncClient", lambda *a, **k: real_client(transport=transport))
    elif case == "still_401_after_refresh":
        async def mock_refresh(clerk_id):
            return "new-token"

        monkeypatch.setattr(calendar_service, "refresh_google_calendar_token", mock_refresh)
    return deleted


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ["unauthorized_client", "decrypt_failed", "still_401_after_refresh"])
async def test_get_calendars_requires_reauth_when_token_unusable(monkeypatch, logged_in_user, case):
    """AC2：GET /oauth/calendars 在 token 不能用時（unauthorized_client／解密失敗／換新後仍 401）回 401，
    detail 請使用者重新連接 Google Calendar，而且不刪 DB 裡的 token。"""
    deleted = _token_unusable(monkeypatch, case)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/oauth/calendars")

    assert res.status_code == status.HTTP_401_UNAUTHORIZED
    assert "重新連接 Google Calendar" in res.json()["detail"]
    assert deleted == []


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ["unauthorized_client", "decrypt_failed", "still_401_after_refresh"])
async def test_schedule_suggest_requires_reauth_when_token_unusable(monkeypatch, logged_in_user, case):
    """AC2：POST /schedule/suggest 在 token 不能用時也回 401 請使用者重新連接，不刪 token。"""
    async def mock_get_tasks(user_id):
        return []

    cache._memory_store.clear()  # 空檔有快取，不清掉可能直接用到別的測試留下的結果
    monkeypatch.setattr(schedule_router, "get_all_schedulable_items", mock_get_tasks)
    deleted = _token_unusable(monkeypatch, case)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post("/schedule/suggest", json={})

    assert res.status_code == status.HTTP_401_UNAUTHORIZED
    assert "重新連接 Google Calendar" in res.json()["detail"]
    assert deleted == []
