"""
routers/oauth.py 的 router 層測試：直接呼叫 router 函式（/status、/calendars、
/events、/available、/callback），驗證各種錯誤分支回什麼狀態碼，包含
httpx.RequestError→502。不經過 HTTP，路由註冊、登入驗證、JSON 格式由
test_oauth_api.py 負責；crud 層由 test_oauth_free_slots.py 負責。
"""
import pytest
import httpx
from fastapi import HTTPException

import routers.oauth as oauth_router

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

    monkeypatch.setattr(oauth_router, "is_google_calendar_connected", mock_is_connected)

    result = await oauth_router.get_google_calendar_status(clerk_user=mock_user)

    assert result == {"connected": True}


@pytest.mark.asyncio
async def test_status_returns_connected_false(monkeypatch):
    """/oauth/status：資料庫沒有 Google token → {"connected": False}。"""
    async def mock_is_connected(clerk_id):
        return False

    monkeypatch.setattr(oauth_router, "is_google_calendar_connected", mock_is_connected)

    result = await oauth_router.get_google_calendar_status(clerk_user=mock_user)

    assert result == {"connected": False}


# ---------- /calendars ----------

@pytest.mark.asyncio
async def test_get_calendars_happy_path(monkeypatch):
    """/oauth/calendars：用資料庫裡的 access token 取得行事曆清單，並用 items 回傳。"""
    async def mock_get_token(clerk_id):
        return "valid-token"

    async def mock_fetch_list(token):
        assert token == "valid-token"
        return [{"id": "cal1", "primary": True}]

    monkeypatch.setattr(oauth_router, "get_google_calendar_token", mock_get_token)
    monkeypatch.setattr(oauth_router, "fetch_google_calendar_list", mock_fetch_list)

    result = await oauth_router.get_google_calendars(clerk_user=mock_user)

    assert result == {"items": [{"id": "cal1", "primary": True}]}


@pytest.mark.asyncio
async def test_get_calendars_refreshes_token_on_401(monkeypatch):
    """access token 過期（Google 回 401）→ 自動 refresh 換新 token，再重打一次成功（共打 2 次）。"""
    calls = {"n": 0}

    async def mock_get_token(clerk_id):
        return "expired-token"

    async def mock_fetch_list(token):
        calls["n"] += 1
        if token == "expired-token":
            raise _http_status_error(401)
        return [{"id": "cal1", "primary": True}]

    async def mock_refresh(clerk_id):
        return "new-token"

    monkeypatch.setattr(oauth_router, "get_google_calendar_token", mock_get_token)
    monkeypatch.setattr(oauth_router, "fetch_google_calendar_list", mock_fetch_list)
    monkeypatch.setattr(oauth_router, "refresh_google_calendar_token", mock_refresh)

    result = await oauth_router.get_google_calendars(clerk_user=mock_user)

    assert calls["n"] == 2
    assert result == {"items": [{"id": "cal1", "primary": True}]}


@pytest.mark.asyncio
async def test_get_calendars_raises_400_on_non_401_status_error(monkeypatch):
    """Google 回 401 以外的錯誤（例如 500）→ 400，不做 refresh。"""
    async def mock_get_token(clerk_id):
        return "token"

    async def mock_fetch_list(token):
        raise _http_status_error(500)

    monkeypatch.setattr(oauth_router, "get_google_calendar_token", mock_get_token)
    monkeypatch.setattr(oauth_router, "fetch_google_calendar_list", mock_fetch_list)

    with pytest.raises(HTTPException) as exc_info:
        await oauth_router.get_google_calendars(clerk_user=mock_user)

    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_get_calendars_raises_502_when_google_unreachable(monkeypatch):
    """連不上 Google → 502。"""
    async def mock_get_token(clerk_id):
        return "token"

    async def mock_fetch_list(token):
        raise httpx.ConnectError("Google 掛了")

    monkeypatch.setattr(oauth_router, "get_google_calendar_token", mock_get_token)
    monkeypatch.setattr(oauth_router, "fetch_google_calendar_list", mock_fetch_list)

    with pytest.raises(HTTPException) as exc_info:
        await oauth_router.get_google_calendars(clerk_user=mock_user)

    assert exc_info.value.status_code == 502


# ---------- /events ----------

@pytest.mark.asyncio
async def test_get_events_happy_path(monkeypatch):
    """/oauth/events：找到 primary 行事曆，取它未來 7 天的事件並用 items 回傳。"""
    async def mock_get_token(clerk_id):
        return "token"

    async def mock_fetch_list(token):
        return [{"id": "cal1", "primary": True}]

    async def mock_fetch_events(token, calendar_id):
        assert calendar_id == "cal1"
        return [{"id": "evt1"}]

    monkeypatch.setattr(oauth_router, "get_google_calendar_token", mock_get_token)
    monkeypatch.setattr(oauth_router, "fetch_google_calendar_list", mock_fetch_list)
    monkeypatch.setattr(oauth_router, "fetch_events_in_next_7_days", mock_fetch_events)

    result = await oauth_router.get_primary_calendar_events(clerk_user=mock_user)

    assert result == {"items": [{"id": "evt1"}]}


@pytest.mark.asyncio
async def test_get_events_refreshes_token_on_401_when_fetching_calendar_list(monkeypatch):
    """取得行事曆清單時 token 過期（401）→ 自動 refresh 後重試。"""
    calls = {"n": 0}

    async def mock_get_token(clerk_id):
        return "expired-token"

    async def mock_fetch_list(token):
        calls["n"] += 1
        if token == "expired-token":
            raise _http_status_error(401)
        return [{"id": "cal1", "primary": True}]

    async def mock_fetch_events(token, calendar_id):
        return [{"id": "evt1"}]

    async def mock_refresh(clerk_id):
        return "new-token"

    monkeypatch.setattr(oauth_router, "get_google_calendar_token", mock_get_token)
    monkeypatch.setattr(oauth_router, "fetch_google_calendar_list", mock_fetch_list)
    monkeypatch.setattr(oauth_router, "fetch_events_in_next_7_days", mock_fetch_events)
    monkeypatch.setattr(oauth_router, "refresh_google_calendar_token", mock_refresh)

    result = await oauth_router.get_primary_calendar_events(clerk_user=mock_user)

    assert calls["n"] == 2
    assert result == {"items": [{"id": "evt1"}]}


@pytest.mark.asyncio
async def test_get_events_raises_404_when_no_primary_calendar(monkeypatch):
    """行事曆清單裡沒有 primary → 404。"""
    async def mock_get_token(clerk_id):
        return "token"

    async def mock_fetch_list(token):
        return [{"id": "cal1", "primary": False}]

    monkeypatch.setattr(oauth_router, "get_google_calendar_token", mock_get_token)
    monkeypatch.setattr(oauth_router, "fetch_google_calendar_list", mock_fetch_list)

    with pytest.raises(HTTPException) as exc_info:
        await oauth_router.get_primary_calendar_events(clerk_user=mock_user)

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_get_events_raises_400_on_non_401_status_error_when_fetching_calendar_list(monkeypatch):
    """取得行事曆清單時 Google 回 401 以外的錯誤 → 400。"""
    async def mock_get_token(clerk_id):
        return "token"

    async def mock_fetch_list(token):
        raise _http_status_error(500)

    monkeypatch.setattr(oauth_router, "get_google_calendar_token", mock_get_token)
    monkeypatch.setattr(oauth_router, "fetch_google_calendar_list", mock_fetch_list)

    with pytest.raises(HTTPException) as exc_info:
        await oauth_router.get_primary_calendar_events(clerk_user=mock_user)

    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_get_events_raises_502_when_calendar_list_unreachable(monkeypatch):
    """取得行事曆清單時連不上 Google → 502。"""
    async def mock_get_token(clerk_id):
        return "token"

    async def mock_fetch_list(token):
        raise httpx.ConnectError("Google 掛了")

    monkeypatch.setattr(oauth_router, "get_google_calendar_token", mock_get_token)
    monkeypatch.setattr(oauth_router, "fetch_google_calendar_list", mock_fetch_list)

    with pytest.raises(HTTPException) as exc_info:
        await oauth_router.get_primary_calendar_events(clerk_user=mock_user)

    assert exc_info.value.status_code == 502


@pytest.mark.asyncio
async def test_get_events_refreshes_token_on_401_when_fetching_events(monkeypatch):
    """取得事件時 token 過期（401）→ 自動 refresh 後重試。"""
    calls = {"n": 0}

    async def mock_get_token(clerk_id):
        return "token"

    async def mock_fetch_list(token):
        return [{"id": "cal1", "primary": True}]

    async def mock_fetch_events(token, calendar_id):
        calls["n"] += 1
        if token == "token":
            raise _http_status_error(401)
        return [{"id": "evt1"}]

    async def mock_refresh(clerk_id):
        return "new-token"

    monkeypatch.setattr(oauth_router, "get_google_calendar_token", mock_get_token)
    monkeypatch.setattr(oauth_router, "fetch_google_calendar_list", mock_fetch_list)
    monkeypatch.setattr(oauth_router, "fetch_events_in_next_7_days", mock_fetch_events)
    monkeypatch.setattr(oauth_router, "refresh_google_calendar_token", mock_refresh)

    result = await oauth_router.get_primary_calendar_events(clerk_user=mock_user)

    assert calls["n"] == 2
    assert result == {"items": [{"id": "evt1"}]}


@pytest.mark.asyncio
async def test_get_events_raises_400_on_non_401_status_error_when_fetching_events(monkeypatch):
    """取得事件時 Google 回 401 以外的錯誤 → 400。"""
    async def mock_get_token(clerk_id):
        return "token"

    async def mock_fetch_list(token):
        return [{"id": "cal1", "primary": True}]

    async def mock_fetch_events(token, calendar_id):
        raise _http_status_error(500)

    monkeypatch.setattr(oauth_router, "get_google_calendar_token", mock_get_token)
    monkeypatch.setattr(oauth_router, "fetch_google_calendar_list", mock_fetch_list)
    monkeypatch.setattr(oauth_router, "fetch_events_in_next_7_days", mock_fetch_events)

    with pytest.raises(HTTPException) as exc_info:
        await oauth_router.get_primary_calendar_events(clerk_user=mock_user)

    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_get_events_raises_502_when_events_fetch_unreachable(monkeypatch):
    """取得事件時連不上 Google → 502。"""
    async def mock_get_token(clerk_id):
        return "token"

    async def mock_fetch_list(token):
        return [{"id": "cal1", "primary": True}]

    async def mock_fetch_events(token, calendar_id):
        raise httpx.ConnectError("Google 掛了")

    monkeypatch.setattr(oauth_router, "get_google_calendar_token", mock_get_token)
    monkeypatch.setattr(oauth_router, "fetch_google_calendar_list", mock_fetch_list)
    monkeypatch.setattr(oauth_router, "fetch_events_in_next_7_days", mock_fetch_events)

    with pytest.raises(HTTPException) as exc_info:
        await oauth_router.get_primary_calendar_events(clerk_user=mock_user)

    assert exc_info.value.status_code == 502


# ---------- /available ----------

@pytest.mark.asyncio
async def test_get_available_times_returns_slots_in_utc(monkeypatch):
    """/oauth/available：回給前端的空檔維持 UTC 格式（freeSlotsUtc）；轉成台北時區只是為了寫 log 方便檢查，不影響回傳內容。"""
    async def mock_get_free_slots(clerk_id):
        return [{"start": "2026-09-10T00:00:00Z", "end": "2026-09-10T01:00:00Z"}]

    monkeypatch.setattr(oauth_router, "get_free_slots_for_user", mock_get_free_slots)

    result = await oauth_router.get_available_times(clerk_user=mock_user)

    import json
    body = json.loads(result.body)
    assert body["freeSlotsUtc"] == [{"start": "2026-09-10T00:00:00Z", "end": "2026-09-10T01:00:00Z"}]


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

    monkeypatch.setattr(oauth_router.httpx, "AsyncClient", lambda *a, **kw: MockClient())
    monkeypatch.setattr(oauth_router, "save_google_calendar_token", mock_save)

    payload = oauth_router.OAuthCallbackPayload(code="auth-code")
    result = await oauth_router.oauth_callback(payload=payload, clerk_user=mock_user)

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

    monkeypatch.setattr(oauth_router.httpx, "AsyncClient", lambda *a, **kw: MockClient())

    payload = oauth_router.OAuthCallbackPayload(code="bad-code")

    with pytest.raises(HTTPException) as exc_info:
        await oauth_router.oauth_callback(payload=payload, clerk_user=mock_user)

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

    monkeypatch.setattr(oauth_router.httpx, "AsyncClient", lambda *a, **kw: MockClient())

    payload = oauth_router.OAuthCallbackPayload(code="auth-code")

    with pytest.raises(HTTPException) as exc_info:
        await oauth_router.oauth_callback(payload=payload, clerk_user=mock_user)

    assert exc_info.value.status_code == 400
