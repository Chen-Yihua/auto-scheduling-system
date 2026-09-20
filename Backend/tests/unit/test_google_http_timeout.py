"""
呼叫 Google 的逾時時間。

httpx 預設只等 5 秒（連線階段包含 DNS 查詢）。在 DNS 偶爾卡住 5 秒的網路環境，
第一次呼叫剛好逾時、回 502，下一次 DNS 有快取又成功——使用者看到的就是
「授權完先跳失敗、過幾秒又連成功」。所以每個會呼叫 Google 的地方都要放寬逾時，
這裡對每一個呼叫點各驗一次，避免以後有人改回預設值。

用 httpx.MockTransport 讓真正的 httpx.AsyncClient 建立起來（才拿得到它實際用的
timeout 設定），只是不會真的連上 Google。
"""
import json

import httpx
import pytest

import crud.oauth as oauth_crud
import routers.oauth as oauth_router
import services.google_calendar as gcal

# httpx 預設 5 秒；DNS 卡住的時間剛好也是 5 秒，要明顯大於它才夠
MIN_CONNECT_TIMEOUT_SECONDS = 10


def _record_timeouts(monkeypatch, handler):
    """把 httpx.AsyncClient 換成會記錄「建立時用了什麼 timeout」的版本，回傳記錄用的 list。"""
    timeouts = []
    transport = httpx.MockTransport(handler)
    real_async_client = httpx.AsyncClient

    def factory(**kw):
        timeouts.append(kw.get("timeout", "未指定（httpx 預設 5 秒）"))
        return real_async_client(transport=transport, **kw)

    monkeypatch.setattr(httpx, "AsyncClient", factory)
    return timeouts


def _assert_relaxed(timeouts):
    assert len(timeouts) == 1
    timeout = timeouts[0]
    assert isinstance(timeout, httpx.Timeout), f"沒有指定逾時：{timeout}"
    assert timeout.connect >= MIN_CONNECT_TIMEOUT_SECONDS


@pytest.mark.asyncio
async def test_fetch_google_calendar_list_uses_relaxed_timeout(monkeypatch):
    """取得行事曆清單：呼叫 Google 時的逾時要比 httpx 預設的 5 秒長。"""
    timeouts = _record_timeouts(monkeypatch, lambda req: httpx.Response(200, json={"items": []}))
    await gcal.fetch_google_calendar_list("token")
    _assert_relaxed(timeouts)


@pytest.mark.asyncio
async def test_fetch_events_in_next_7_days_uses_relaxed_timeout(monkeypatch):
    """取得 7 天內事件：呼叫 Google 時的逾時要比 httpx 預設的 5 秒長。"""
    timeouts = _record_timeouts(monkeypatch, lambda req: httpx.Response(200, json={"items": []}))
    await gcal.fetch_events_in_next_7_days("token", "primary")
    _assert_relaxed(timeouts)


@pytest.mark.asyncio
async def test_fetch_freebusy_uses_relaxed_timeout(monkeypatch):
    """查詢忙碌時段：呼叫 Google 時的逾時要比 httpx 預設的 5 秒長。"""
    timeouts = _record_timeouts(monkeypatch, lambda req: httpx.Response(200, json={"calendars": {}}))
    await gcal.fetch_freebusy("token", "primary")
    _assert_relaxed(timeouts)


@pytest.mark.asyncio
async def test_oauth_callback_uses_relaxed_timeout(monkeypatch):
    """授權完成後用授權碼換 token（使用者實際遇到失敗的那一步）：逾時要比 httpx 預設的 5 秒長。"""
    timeouts = _record_timeouts(monkeypatch, lambda req: httpx.Response(200, json={"access_token": "a", "refresh_token": "r"}))

    async def mock_save(clerk_id, access_token, refresh_token):
        pass

    monkeypatch.setattr(oauth_router, "save_google_calendar_token", mock_save)

    result = await oauth_router.oauth_callback(
        payload=oauth_router.OAuthCallbackPayload(code="auth-code"),
        clerk_user={"sub": "uid123"},
    )

    assert json.loads(result.body) == {"message": "Google Calendar 授權成功"}
    _assert_relaxed(timeouts)


@pytest.mark.asyncio
async def test_refresh_google_calendar_token_uses_relaxed_timeout(monkeypatch):
    """用 refresh token 換新的 access token：逾時要比 httpx 預設的 5 秒長。"""
    timeouts = _record_timeouts(monkeypatch, lambda req: httpx.Response(200, json={"access_token": "new-access"}))

    async def mock_find_one(query):
        return {"_id": "uid123", "refresh_token": "rt"}

    async def mock_update_one(*a, **k):
        pass

    monkeypatch.setattr(oauth_crud.db.googleCalendarTokens, "find_one", mock_find_one)
    monkeypatch.setattr(oauth_crud.db.googleCalendarTokens, "update_one", mock_update_one)

    assert await oauth_crud.refresh_google_calendar_token("uid123") == "new-access"
    _assert_relaxed(timeouts)
