"""GOOGLE_API_BASE_URL 設定與否時，後端呼叫 Google 的完整網址。"""
import httpx
import pytest

import routers.google_calendar as google_calendar_router
import services.google_calendar_client as gcal
import services.google_oauth as google_oauth
from services import google_api_urls

FAKE = "http://localhost:9999"
CAL = "https://www.googleapis.com"
OAUTH = "https://oauth2.googleapis.com"


def _urls() -> dict[str, str]:
    return {
        "calendarList": google_api_urls.calendar_list_url(),
        "freeBusy": google_api_urls.freebusy_url(),
        "events": google_api_urls.events_url("cal-1"),
        "event": google_api_urls.event_url("cal-1", "ev-1"),
        "token": google_api_urls.token_url(),
    }


def test_AC1_設定_GOOGLE_API_BASE_URL_時所有網址改送到該位址_路徑不變(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_BASE_URL", FAKE)
    assert _urls() == {
        "calendarList": f"{FAKE}/calendar/v3/users/me/calendarList",
        "freeBusy": f"{FAKE}/calendar/v3/freeBusy",
        "events": f"{FAKE}/calendar/v3/calendars/cal-1/events",
        "event": f"{FAKE}/calendar/v3/calendars/cal-1/events/ev-1",
        "token": f"{FAKE}/token",
    }


def test_AC1_網址結尾的斜線不會變成雙斜線(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_BASE_URL", FAKE + "/")
    assert google_api_urls.token_url() == f"{FAKE}/token"


def test_AC2_沒設定_GOOGLE_API_BASE_URL_時送到真的_Google(monkeypatch):
    monkeypatch.delenv("GOOGLE_API_BASE_URL", raising=False)
    assert _urls() == {
        "calendarList": f"{CAL}/calendar/v3/users/me/calendarList",
        "freeBusy": f"{CAL}/calendar/v3/freeBusy",
        "events": f"{CAL}/calendar/v3/calendars/cal-1/events",
        "event": f"{CAL}/calendar/v3/calendars/cal-1/events/ev-1",
        "token": f"{OAUTH}/token",
    }


def test_AC2_設成空字串視為沒設定(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_BASE_URL", "")
    assert google_api_urls.token_url() == f"{OAUTH}/token"


@pytest.mark.asyncio
async def test_AC1_用戶端函式實際送出的請求都到設定的位址(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_BASE_URL", FAKE)
    seen: list[tuple[str, str]] = []

    def handler(request):
        seen.append((request.method, str(request.url)))
        return httpx.Response(200, json={"items": []})

    real_async_client = httpx.AsyncClient
    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(gcal.httpx, "AsyncClient", lambda **kw: real_async_client(transport=transport, **kw))

    await gcal.fetch_google_calendar_list("t")
    await gcal.fetch_freebusy("t", "c")
    await gcal.create_calendar_event("t", "c", "s", "2026-01-01T00:00:00Z", "2026-01-01T01:00:00Z")
    await gcal.get_calendar_event("t", "c", "e")
    await gcal.delete_calendar_event("t", "c", "e")

    assert seen == [
        ("GET", f"{FAKE}/calendar/v3/users/me/calendarList"),
        ("POST", f"{FAKE}/calendar/v3/freeBusy"),
        ("POST", f"{FAKE}/calendar/v3/calendars/c/events"),
        ("GET", f"{FAKE}/calendar/v3/calendars/c/events/e"),
        ("DELETE", f"{FAKE}/calendar/v3/calendars/c/events/e"),
    ]


class _TokenClient:
    """記下 post 的網址，回傳可用的 token 回應。"""

    urls: list[str] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        pass

    async def post(self, url, **kw):
        self.urls.append(url)
        return httpx.Response(200, json={"access_token": "a", "refresh_token": "r"}, request=httpx.Request("POST", url))


@pytest.mark.asyncio
async def test_AC1_token_refresh_與_oauth_callback_都送到設定的位址(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_BASE_URL", FAKE)
    _TokenClient.urls = []

    async def fake_refresh_token(clerk_id):
        return "r"

    async def noop(*a, **k):
        return None

    monkeypatch.setattr(google_oauth, "get_google_refresh_token", fake_refresh_token)
    monkeypatch.setattr(google_oauth, "update_google_calendar_token", noop)
    monkeypatch.setattr(google_oauth.httpx, "AsyncClient", lambda **kw: _TokenClient())
    monkeypatch.setattr(google_calendar_router.httpx, "AsyncClient", lambda **kw: _TokenClient())
    monkeypatch.setattr(google_calendar_router, "save_google_calendar_token", noop)

    await google_oauth.refresh_google_calendar_token("u")
    await google_calendar_router.oauth_callback(
        payload=google_calendar_router.OAuthCallbackPayload(code="c"), clerk_user={"sub": "u"}
    )

    assert _TokenClient.urls == [f"{FAKE}/token", f"{FAKE}/token"]
