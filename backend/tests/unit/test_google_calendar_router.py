"""直接呼叫 routers/google_calendar.py 的函式，測試各錯誤分支的 error_code（狀態碼由對照表決定）。"""
import logging

import pytest
import httpx

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
# token 換新和錯誤分支在 test_google_calendar_service.py

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
    """/oauth/callback 換 token 成功 → 存入 token，回「授權成功」。"""
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
async def test_oauth_callback_unrecognized_400_is_upstream_error(monkeypatch):
    """Google 回 400 但看不出原因（沒有 error 欄位）→ UPSTREAM_ERROR（502），不當成授權碼無效。"""
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

    with pytest.raises(AppError) as exc_info:
        await google_calendar_router.oauth_callback(payload=payload, clerk_user=mock_user)

    assert exc_info.value.error_code == "UPSTREAM_ERROR"
    assert status_for_error_code(exc_info.value.error_code) == 502


@pytest.mark.asyncio
async def test_oauth_callback_rejects_response_without_access_token(monkeypatch):
    """Google 回 200 但回應裡沒有 access_token → UPSTREAM_ERROR（502），不能存一個空的 token。"""
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

    with pytest.raises(AppError) as exc_info:
        await google_calendar_router.oauth_callback(payload=payload, clerk_user=mock_user)

    assert status_for_error_code(exc_info.value.error_code) == 502


@pytest.mark.asyncio
async def test_oauth_callback_logs_error_and_returns_502_when_google_unreachable(monkeypatch, caplog):
    """連不上 Google → 記錄 error log 並回 502，跟「授權碼無效」的 400 分開。"""
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
        with pytest.raises(AppError) as exc_info:
            await google_calendar_router.oauth_callback(
                payload=payload, clerk_user={"sub": "uid123"}
            )

    assert status_for_error_code(exc_info.value.error_code) == 502
    assert any("連線 Google Token Endpoint 失敗" in record.message for record in caplog.records)


# ---------- 需求 4：OAuth 換 token 的 error_code（AC11） ----------
from core.error_codes import status_for_error_code
from core.errors import AppError

GOOGLE_RAW_TEXT = "google-oauth-raw-5d1e"


def _token_endpoint(monkeypatch, handler):
    real_client = httpx.AsyncClient
    monkeypatch.setattr(google_calendar_router.httpx, "AsyncClient",
                        lambda *a, **kw: real_client(transport=httpx.MockTransport(handler)))


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code, body, http_status, error_code", [
    (400, {"error": "invalid_grant", "error_description": GOOGLE_RAW_TEXT}, 400, "INVALID_AUTHORIZATION_CODE"),
    (401, {"error": "invalid_client"}, 500, "INTERNAL_ERROR"),
    (400, {"error": "invalid_request"}, 500, "INTERNAL_ERROR"),
    (400, {"error": "unauthorized_client"}, 500, "INTERNAL_ERROR"),
    (400, {"error": "redirect_uri_mismatch"}, 500, "INTERNAL_ERROR"),
    (400, {"error": "something_new"}, 502, "UPSTREAM_ERROR"),
    (503, {"error": "backend_error", "error_description": GOOGLE_RAW_TEXT}, 502, "UPSTREAM_ERROR"),
    (429, {"error": "rate_limit_exceeded"}, 503, "UPSTREAM_RATE_LIMITED"),
], ids=["invalid_grant", "invalid_client", "invalid_request", "unauthorized_client", "redirect_uri_mismatch",
        "other-error-code", "5xx", "429"])
async def test_oauth_callback_error_codes(monkeypatch, status_code, body, http_status, error_code):
    """只有 invalid_grant 是 INVALID_AUTHORIZATION_CODE 並說授權碼無效；Google 暫時故障、限流不說授權碼無效；
    狀態碼照 error_code 查表；detail 不帶 Google 回應原文。"""
    _token_endpoint(monkeypatch, lambda request: httpx.Response(status_code, json=body))

    with pytest.raises(AppError) as exc_info:
        await google_calendar_router.oauth_callback(
            payload=google_calendar_router.OAuthCallbackPayload(code="c"), clerk_user=mock_user)

    assert exc_info.value.error_code == error_code
    assert status_for_error_code(exc_info.value.error_code) == http_status
    assert GOOGLE_RAW_TEXT not in exc_info.value.detail
    assert ("授權碼無效" in exc_info.value.detail) is (error_code == "INVALID_AUTHORIZATION_CODE")


@pytest.mark.asyncio
@pytest.mark.parametrize("error, error_code", [
    (httpx.ConnectError("down"), "UPSTREAM_ERROR"),
    (httpx.ReadTimeout("slow"), "UPSTREAM_TIMEOUT"),
])
async def test_oauth_callback_connection_errors(monkeypatch, error, error_code):
    """連不上是 UPSTREAM_ERROR（502）、逾時是 UPSTREAM_TIMEOUT（504）。"""
    def handler(request):
        raise error

    _token_endpoint(monkeypatch, handler)

    with pytest.raises(AppError) as exc_info:
        await google_calendar_router.oauth_callback(
            payload=google_calendar_router.OAuthCallbackPayload(code="c"), clerk_user=mock_user)

    assert exc_info.value.error_code == error_code


@pytest.mark.asyncio
async def test_oauth_callback_without_access_token_is_upstream_error(monkeypatch):
    """Google 回 200 但沒有 access token → UPSTREAM_ERROR（502）。"""
    _token_endpoint(monkeypatch, lambda request: httpx.Response(200, json={}))

    with pytest.raises(AppError) as exc_info:
        await google_calendar_router.oauth_callback(
            payload=google_calendar_router.OAuthCallbackPayload(code="c"), clerk_user=mock_user)

    assert exc_info.value.error_code == "UPSTREAM_ERROR"
