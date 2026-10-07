"""
routers/google_calendar.py 的 router 層測試：直接呼叫 router 函式（/status、/calendars、
/callback），驗證各種錯誤分支回什麼狀態碼，包含 httpx.RequestError→502。
不經過 HTTP，路由註冊、登入驗證、JSON 格式由 integration/test_google_calendar_api.py 負責；
token 存取由 test_google_tokens.py、行事曆操作由 test_google_calendar_service.py 負責。
"""
import logging

import pytest
import httpx
from fastapi import HTTPException

import routers.google_calendar as google_calendar_router

mock_user = {"sub": "uid123"}


def _http_status_error(status_code: int) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", "https://example.com")
    response = httpx.Response(status_code, request=request)
    return httpx.HTTPStatusError("error", request=request, response=response)


# ---------- /status ----------

@pytest.mark.asyncio
async def test_status_returns_connected_true(monkeypatch):
    """/oauth/status：資料庫有存 Google token → {"connected": True}。"""
    async def mock_is_connected(clerk_id):
        return True

    monkeypatch.setattr(google_calendar_router, "is_google_calendar_connected", mock_is_connected)

    result = await google_calendar_router.get_google_calendar_status(clerk_user=mock_user)

    assert result == {"connected": True}


@pytest.mark.asyncio
async def test_status_returns_connected_false(monkeypatch):
    """/oauth/status：資料庫沒有 Google token → {"connected": False}。"""
    async def mock_is_connected(clerk_id):
        return False

    monkeypatch.setattr(google_calendar_router, "is_google_calendar_connected", mock_is_connected)

    result = await google_calendar_router.get_google_calendar_status(clerk_user=mock_user)

    assert result == {"connected": False}


# ---------- /calendars ----------
# token 過期自動換新、Google 回錯誤或連不上的分支，在共用的 services/google_calendar.py，
# 由 test_google_calendar_service.py 負責

@pytest.mark.asyncio
async def test_get_calendars_returns_items(monkeypatch):
    """/oauth/calendars：把使用者的行事曆列表用 items 回傳。"""
    async def mock_list_calendars(clerk_id):
        assert clerk_id == "uid123"
        return [{"id": "cal1", "primary": True}]

    monkeypatch.setattr(google_calendar_router, "list_calendars_for_user", mock_list_calendars)

    result = await google_calendar_router.get_google_calendars(clerk_user=mock_user)

    assert result == {"items": [{"id": "cal1", "primary": True}]}


# ---------- /callback ----------

@pytest.mark.asyncio
async def test_oauth_callback_happy_path_saves_token(monkeypatch):
    """/oauth/callback：用授權碼跟 Google 換 token 成功 → 把 access / refresh token 存進資料庫，回「授權成功」。"""
    saved = {}

    class MockResponse:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {"access_token": "new-access-token", "refresh_token": "new-refresh-token"}

    class MockClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            pass

        async def post(self, *a, **k):
            return MockResponse()

    async def mock_save(clerk_id, access_token, refresh_token):
        saved["clerk_id"] = clerk_id
        saved["access_token"] = access_token
        saved["refresh_token"] = refresh_token

    monkeypatch.setattr(google_calendar_router.httpx, "AsyncClient", lambda *a, **kw: MockClient())
    monkeypatch.setattr(google_calendar_router, "save_google_calendar_token", mock_save)

    payload = google_calendar_router.OAuthCallbackPayload(code="auth-code")
    result = await google_calendar_router.oauth_callback(payload=payload, clerk_user=mock_user)

    assert saved == {
        "clerk_id": "uid123",
        "access_token": "new-access-token",
        "refresh_token": "new-refresh-token",
    }
    import json
    assert json.loads(result.body) == {"message": "Google Calendar 授權成功"}


@pytest.mark.asyncio
async def test_oauth_callback_raises_400_when_google_rejects_code(monkeypatch):
    """Google 拒絕這個授權碼（無效或已過期）→ 400。"""
    class MockResponse:
        status_code = 400

        def raise_for_status(self):
            raise _http_status_error(400)

    class MockClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            pass

        async def post(self, *a, **k):
            return MockResponse()

    monkeypatch.setattr(google_calendar_router.httpx, "AsyncClient", lambda *a, **kw: MockClient())

    payload = google_calendar_router.OAuthCallbackPayload(code="bad-code")

    with pytest.raises(HTTPException) as exc_info:
        await google_calendar_router.oauth_callback(payload=payload, clerk_user=mock_user)

    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_oauth_callback_raises_400_when_no_access_token_in_response(monkeypatch):
    """Google 回 200 但回應裡沒有 access_token → 400，不能存一個空的 token。"""
    class MockResponse:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {}  # Google 回了 200，但沒有 access_token

    class MockClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            pass

        async def post(self, *a, **k):
            return MockResponse()

    monkeypatch.setattr(google_calendar_router.httpx, "AsyncClient", lambda *a, **kw: MockClient())

    payload = google_calendar_router.OAuthCallbackPayload(code="auth-code")

    with pytest.raises(HTTPException) as exc_info:
        await google_calendar_router.oauth_callback(payload=payload, clerk_user=mock_user)

    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_oauth_callback_logs_error_and_returns_502_when_google_unreachable(monkeypatch, caplog):
    """連不上 Google → 記錄 error log 並回 502，跟「Google 拒絕這個授權碼」的 400 分開。"""
    class FailingClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            pass

        async def post(self, *a, **k):
            raise httpx.ConnectError("Google 掛了")

    monkeypatch.setattr(google_calendar_router.httpx, "AsyncClient", lambda *a, **kw: FailingClient())

    payload = google_calendar_router.OAuthCallbackPayload(code="fake-code")

    with caplog.at_level(logging.ERROR, logger="routers.google_calendar"):
        with pytest.raises(HTTPException) as exc_info:
            await google_calendar_router.oauth_callback(
                payload=payload, clerk_user={"sub": "uid123"}
            )

    # 502 = 連不上上游服務，跟「授權碼無效」的 400 分開
    assert exc_info.value.status_code == 502
    assert any("連線 Google Token Endpoint 失敗" in record.message for record in caplog.records)
