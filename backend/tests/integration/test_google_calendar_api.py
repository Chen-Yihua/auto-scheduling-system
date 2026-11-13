# 透過 HTTP 確認路由、登入驗證、回應格式和錯誤狀態碼；細部邏輯由 unit 測試負責
import httpx
import pytest
from cryptography.fernet import Fernet
from fastapi import status
from httpx import AsyncClient
from httpx._transports.asgi import ASGITransport

from main import app
from core.errors import InvalidRequestError
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
    """使用者還沒授權 Google Calendar → 409 NOT_LINKED 加中文說明。"""
    async def mock_get_token(clerk_id):
        raise InvalidRequestError("尚未連接 Google Calendar", error_code="NOT_LINKED")

    monkeypatch.setattr(calendar_service, "get_google_calendar_token", mock_get_token)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/oauth/calendars")

    assert res.status_code == status.HTTP_409_CONFLICT
    assert res.json() == {"detail": "尚未連接 Google Calendar", "error_code": "NOT_LINKED"}


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
    """GET /oauth/calendars 在 token 不能用時（unauthorized_client／解密失敗／換新後仍 401）回 409 REAUTH_REQUIRED，
    detail 請使用者重新連接 Google Calendar，而且不刪 DB 裡的 token。"""
    deleted = _token_unusable(monkeypatch, case)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/oauth/calendars")

    assert res.status_code == status.HTTP_409_CONFLICT
    assert res.json()["error_code"] == "REAUTH_REQUIRED"
    assert "重新連接 Google Calendar" in res.json()["detail"]
    assert deleted == []


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ["unauthorized_client", "decrypt_failed", "still_401_after_refresh"])
async def test_schedule_suggest_requires_reauth_when_token_unusable(monkeypatch, logged_in_user, case):
    """POST /schedule/suggest 在 token 不能用時也回 409 REAUTH_REQUIRED 請使用者重新連接，不刪 token。"""
    async def mock_get_tasks(user_id):
        return []

    cache._memory_store.clear()  # 空檔有快取，不清掉可能直接用到別的測試留下的結果
    monkeypatch.setattr(schedule_router, "get_all_schedulable_items", mock_get_tasks)
    deleted = _token_unusable(monkeypatch, case)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post("/schedule/suggest", json={})

    assert res.status_code == status.HTTP_409_CONFLICT
    assert res.json()["error_code"] == "REAUTH_REQUIRED"
    assert "重新連接 Google Calendar" in res.json()["detail"]
    assert deleted == []


# ---------- Google 錯誤依原因給 error_code，狀態碼照對照表 ----------
UPSTREAM_SECRET_TEXT = "google-raw-text-91c2"


def _google_error(status_code: int, reason: str | None = None) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", "https://www.googleapis.com/calendar/v3/users/me/calendarList")
    errors = [{"domain": "global", "reason": reason, "message": UPSTREAM_SECRET_TEXT}] if reason else []
    body = {"error": {"code": status_code, "message": UPSTREAM_SECRET_TEXT, "errors": errors}}
    return httpx.HTTPStatusError("error", request=request, response=httpx.Response(status_code, json=body, request=request))


def _connected_with_calendar_list_error(monkeypatch, error):
    async def mock_find_one(query):
        return {"_id": "test_user_123", "access_token": encrypt_secret("at"), "refresh_token": encrypt_secret("rt")}

    async def mock_fetch_calendar_list(token):
        raise error

    cache._memory_store.clear()
    monkeypatch.setattr(db.googleCalendarTokens, "find_one", mock_find_one)
    monkeypatch.setattr(calendar_service, "fetch_google_calendar_list", mock_fetch_calendar_list)


# (Google 的錯誤, 狀態碼, error_code)
GOOGLE_LIST_CASES = [
    pytest.param(_google_error(403, "rateLimitExceeded"), 503, "UPSTREAM_RATE_LIMITED", id="403-rateLimitExceeded"),
    pytest.param(_google_error(403, "userRateLimitExceeded"), 503, "UPSTREAM_RATE_LIMITED", id="403-userRateLimitExceeded"),
    pytest.param(_google_error(403, "quotaExceeded"), 503, "UPSTREAM_RATE_LIMITED", id="403-quotaExceeded"),
    pytest.param(_google_error(403, "dailyLimitExceeded"), 503, "UPSTREAM_RATE_LIMITED", id="403-dailyLimitExceeded"),
    pytest.param(_google_error(429, "rateLimitExceeded"), 503, "UPSTREAM_RATE_LIMITED", id="429"),
    pytest.param(_google_error(403, "insufficientPermissions"), 409, "REAUTH_REQUIRED", id="403-insufficientPermissions"),
    pytest.param(_google_error(403, "forbidden"), 409, "REAUTH_REQUIRED", id="403-forbidden"),
    pytest.param(_google_error(403), 502, "UPSTREAM_ERROR", id="403-unknown-reason"),
    pytest.param(_google_error(404, "notFound"), 502, "UPSTREAM_ERROR", id="other-4xx"),
    pytest.param(_google_error(400, "badRequest"), 500, "INTERNAL_ERROR", id="400"),
    pytest.param(_google_error(503), 502, "UPSTREAM_ERROR", id="5xx"),
    pytest.param(httpx.ConnectError("down"), 502, "UPSTREAM_ERROR", id="connect-error"),
    pytest.param(httpx.ReadTimeout("slow"), 504, "UPSTREAM_TIMEOUT", id="timeout"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("error, status_code, error_code", GOOGLE_LIST_CASES)
async def test_get_calendars_google_error_codes(monkeypatch, logged_in_user, error, status_code, error_code):
    """AC1、AC10：已連接時 Google 回錯誤，GET /oauth/calendars 依原因給 error_code（不是 NOT_LINKED），狀態碼照 error_code 查表；detail 不帶 Google 原文。"""
    _connected_with_calendar_list_error(monkeypatch, error)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/oauth/calendars")

    body = res.json()
    assert res.status_code == status_code
    assert body["error_code"] == error_code
    assert UPSTREAM_SECRET_TEXT not in res.text
    if error_code != "REAUTH_REQUIRED":
        assert "授權已失效" not in body["detail"]
        assert "權限不足" not in body["detail"]


@pytest.mark.asyncio
@pytest.mark.parametrize("error, status_code, error_code", GOOGLE_LIST_CASES)
async def test_schedule_suggest_google_error_codes(monkeypatch, logged_in_user, error, status_code, error_code):
    """AC1：產生排程建議時 Google 回錯誤，error_code 照原因、不是 NOT_LINKED，狀態碼照 error_code 查表。"""
    async def mock_get_tasks(user_id):
        return []

    monkeypatch.setattr(schedule_router, "get_all_schedulable_items", mock_get_tasks)
    _connected_with_calendar_list_error(monkeypatch, error)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post("/schedule/suggest", json={})

    assert res.status_code == status_code
    assert res.json()["error_code"] == error_code


@pytest.mark.asyncio
async def test_get_calendars_not_linked_has_not_linked_code(monkeypatch, logged_in_user):
    """還沒連接 Google → 409 NOT_LINKED。"""
    async def mock_find_one(query):
        return None

    monkeypatch.setattr(db.googleCalendarTokens, "find_one", mock_find_one)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/oauth/calendars")

    assert res.status_code == 409
    assert res.json()["error_code"] == "NOT_LINKED"


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ["unauthorized_client", "decrypt_failed", "still_401_after_refresh"])
async def test_get_calendars_unusable_token_has_reauth_required_code(monkeypatch, logged_in_user, case):
    """token 不能用（含換新後仍 401、解密失敗）→ 409 REAUTH_REQUIRED。"""
    _token_unusable(monkeypatch, case)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/oauth/calendars")

    assert res.status_code == 409
    assert res.json()["error_code"] == "REAUTH_REQUIRED"


# ---------- 外部限流帶 Retry-After（AC5）----------

def _google_rate_limited(status_code: int, reason: str | None, retry_after: str | None) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", "https://www.googleapis.com/calendar/v3/users/me/calendarList")
    errors = [{"domain": "usageLimits", "reason": reason}] if reason else []
    headers = {"Retry-After": retry_after} if retry_after is not None else {}
    response = httpx.Response(status_code, json={"error": {"code": status_code, "errors": errors}}, headers=headers, request=request)
    return httpx.HTTPStatusError("error", request=request, response=response)


@pytest.mark.asyncio
@pytest.mark.parametrize("error, retry_after", [
    pytest.param(_google_rate_limited(429, "rateLimitExceeded", "30"), "30", id="429-seconds"),
    pytest.param(_google_rate_limited(403, "userRateLimitExceeded", "8"), "8", id="403-seconds"),
    pytest.param(_google_rate_limited(429, "rateLimitExceeded", None), None, id="429-without"),
    pytest.param(_google_rate_limited(429, "rateLimitExceeded", "Wed, 21 Oct 2026 07:28:00 GMT"), None, id="429-http-date"),
])
async def test_get_calendars_rate_limited_forwards_retry_after_seconds(monkeypatch, logged_in_user, error, retry_after):
    """AC5：Google 限流 → 503 UPSTREAM_RATE_LIMITED；帶秒數的 Retry-After 原樣帶上，沒帶或日期格式不帶。"""
    _connected_with_calendar_list_error(monkeypatch, error)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/oauth/calendars")

    assert res.status_code == 503
    assert res.json()["error_code"] == "UPSTREAM_RATE_LIMITED"
    assert res.headers.get("Retry-After") == retry_after


@pytest.mark.asyncio
@pytest.mark.parametrize("retry_after", ["45", None])
async def test_token_refresh_rate_limited_forwards_retry_after_seconds(monkeypatch, logged_in_user, retry_after):
    """AC5：換新 token 時 Google 限流 → 503 UPSTREAM_RATE_LIMITED，帶秒數的 Retry-After 原樣帶上。"""
    _connected_with_calendar_list_error(monkeypatch, _unauthorized_error())
    headers = {"Retry-After": retry_after} if retry_after else {}
    real_client = httpx.AsyncClient
    transport = httpx.MockTransport(lambda request: httpx.Response(429, json={"error": "rate_limited"}, headers=headers))
    monkeypatch.setattr(google_oauth.httpx, "AsyncClient", lambda *a, **k: real_client(transport=transport))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/oauth/calendars")

    assert res.status_code == 503
    assert res.json()["error_code"] == "UPSTREAM_RATE_LIMITED"
    assert res.headers.get("Retry-After") == retry_after


@pytest.mark.asyncio
@pytest.mark.parametrize("retry_after", ["90", None])
async def test_oauth_callback_rate_limited_forwards_retry_after_seconds(monkeypatch, logged_in_user, retry_after):
    """AC5：OAuth 換 token 時 Google 限流 → 503 UPSTREAM_RATE_LIMITED，帶秒數的 Retry-After 原樣帶上。"""
    headers = {"Retry-After": retry_after} if retry_after else {}
    real_client = httpx.AsyncClient
    transport = httpx.MockTransport(lambda request: httpx.Response(429, json={"error": "rate_limited"}, headers=headers))
    monkeypatch.setattr(google_calendar_router.httpx, "AsyncClient", lambda *a, **k: real_client(transport=transport))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post("/oauth/callback", json={"code": "auth-code"})

    assert res.status_code == 503
    assert res.json()["error_code"] == "UPSTREAM_RATE_LIMITED"
    assert res.headers.get("Retry-After") == retry_after
