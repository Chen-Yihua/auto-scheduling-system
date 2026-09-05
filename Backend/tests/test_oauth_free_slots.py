import pytest
import httpx
from fastapi import HTTPException

import crud.oauth as oauth_crud


@pytest.mark.asyncio
async def test_get_free_slots_happy_path(monkeypatch):
    async def mock_find_one(query):
        return {"_id": "uid123", "access_token": "valid-token"}

    async def mock_fetch_calendar_list(token):
        assert token == "valid-token"
        return [{"id": "primary-cal-id", "primary": True}]

    async def mock_fetch_freebusy(token, calendar_id):
        assert calendar_id == "primary-cal-id"
        return {
            "timeMin": "2026-09-10T00:00:00Z",
            "timeMax": "2026-09-17T00:00:00Z",
            "calendars": {"primary-cal-id": {"busy": [{"start": "2026-09-10T09:00:00Z", "end": "2026-09-10T10:00:00Z"}]}},
        }

    monkeypatch.setattr(oauth_crud.db.googleCalendarTokens, "find_one", mock_find_one)
    monkeypatch.setattr(oauth_crud, "fetch_google_calendar_list", mock_fetch_calendar_list)
    monkeypatch.setattr(oauth_crud, "fetch_freebusy", mock_fetch_freebusy)

    result = await oauth_crud.get_free_slots_for_user("uid123")

    assert isinstance(result, list)
    assert result[0]["start"] == "2026-09-10T00:00:00Z"
    assert result[0]["end"] == "2026-09-10T09:00:00Z"


@pytest.mark.asyncio
async def test_get_free_slots_refreshes_token_on_401(monkeypatch):
    async def mock_find_one(query):
        return {"_id": "uid123", "access_token": "expired-token", "refresh_token": "rt"}

    calls = {"n": 0}

    async def mock_fetch_calendar_list(token):
        calls["n"] += 1
        if token == "expired-token":
            request = httpx.Request("GET", "https://example.com")
            response = httpx.Response(401, request=request)
            raise httpx.HTTPStatusError("Unauthorized", request=request, response=response)
        return [{"id": "primary-cal-id", "primary": True}]

    async def mock_refresh(clerk_id):
        return "new-token"

    async def mock_fetch_freebusy(token, calendar_id):
        assert token == "new-token"
        return {
            "timeMin": "2026-09-10T00:00:00Z",
            "timeMax": "2026-09-17T00:00:00Z",
            "calendars": {"primary-cal-id": {"busy": []}},
        }

    monkeypatch.setattr(oauth_crud.db.googleCalendarTokens, "find_one", mock_find_one)
    monkeypatch.setattr(oauth_crud, "fetch_google_calendar_list", mock_fetch_calendar_list)
    monkeypatch.setattr(oauth_crud, "refresh_google_calendar_token", mock_refresh)
    monkeypatch.setattr(oauth_crud, "fetch_freebusy", mock_fetch_freebusy)

    result = await oauth_crud.get_free_slots_for_user("uid123")

    assert calls["n"] == 2  # 第一次拿到 401，refresh 後重打一次
    assert result[0]["start"] == "2026-09-10T00:00:00Z"
    assert result[0]["end"] == "2026-09-17T00:00:00Z"


@pytest.mark.asyncio
async def test_get_free_slots_raises_404_when_no_primary_calendar(monkeypatch):
    async def mock_find_one(query):
        return {"_id": "uid123", "access_token": "valid-token"}

    async def mock_fetch_calendar_list(token):
        return [{"id": "some-other-cal", "primary": False}]

    monkeypatch.setattr(oauth_crud.db.googleCalendarTokens, "find_one", mock_find_one)
    monkeypatch.setattr(oauth_crud, "fetch_google_calendar_list", mock_fetch_calendar_list)

    with pytest.raises(HTTPException) as exc_info:
        await oauth_crud.get_free_slots_for_user("uid123")

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_get_free_slots_raises_401_when_not_connected(monkeypatch):
    async def mock_find_one(query):
        return None

    monkeypatch.setattr(oauth_crud.db.googleCalendarTokens, "find_one", mock_find_one)

    with pytest.raises(HTTPException) as exc_info:
        await oauth_crud.get_free_slots_for_user("uid123")

    assert exc_info.value.status_code == 401
