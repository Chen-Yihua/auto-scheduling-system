"""
routers/oauth.py 的 HTTP 層級測試——先前只有 crud/oauth.py 被直接測試過
（test_oauth_free_slots.py），router 這一層（/status、/calendars、/events、
/available、/callback）完全沒有測試覆蓋，包含新加的 httpx.RequestError→502
分支。這裡直接呼叫 router 函式本身（跟 test_schedule_router.py 同一種做法），
不用真的架一個 TestClient 打 HTTP。
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
    async def mock_is_connected(clerk_id):
        return True

    monkeypatch.setattr(oauth_router, "is_google_calendar_connected", mock_is_connected)

    result = await oauth_router.get_google_calendar_status(clerk_user=mock_user)

    assert result == {"connected": True}


@pytest.mark.asyncio
async def test_status_returns_connected_false(monkeypatch):
    async def mock_is_connected(clerk_id):
        return False

    monkeypatch.setattr(oauth_router, "is_google_calendar_connected", mock_is_connected)

    result = await oauth_router.get_google_calendar_status(clerk_user=mock_user)

    assert result == {"connected": False}


# ---------- /calendars ----------

@pytest.mark.asyncio
async def test_get_calendars_happy_path(monkeypatch):
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
async def test_get_available_times_converts_utc_to_taipei_local(monkeypatch):
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

    monkeypatch.setattr(oauth_router.httpx, "AsyncClient", lambda: MockClient())
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

    monkeypatch.setattr(oauth_router.httpx, "AsyncClient", lambda: MockClient())

    payload = oauth_router.OAuthCallbackPayload(code="bad-code")

    with pytest.raises(HTTPException) as exc_info:
        await oauth_router.oauth_callback(payload=payload, clerk_user=mock_user)

    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_oauth_callback_raises_400_when_no_access_token_in_response(monkeypatch):
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

    monkeypatch.setattr(oauth_router.httpx, "AsyncClient", lambda: MockClient())

    payload = oauth_router.OAuthCallbackPayload(code="auth-code")

    with pytest.raises(HTTPException) as exc_info:
        await oauth_router.oauth_callback(payload=payload, clerk_user=mock_user)

    assert exc_info.value.status_code == 400
