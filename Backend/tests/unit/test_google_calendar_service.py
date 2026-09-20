"""
services/google_calendar.py——真正打 Google Calendar API 的 client 函式，
先前完全沒有專屬測試（都是被其他測試 monkeypatch 掉，函式本體從沒被執行過）。

用 httpx.MockTransport 讓這裡測到的是「真正的」httpx.AsyncClient 行為
（URL 組成、header、raise_for_status()、json() 解析），只是把底層的網路
請求換成假的 transport，不用真的連上 Google。
"""
import pytest
import httpx

import services.google_calendar as gcal


def _mock_client(monkeypatch, handler):
    # gcal.httpx 跟這裡的 httpx 是同一個模組物件，要先把原本的 AsyncClient
    # 存起來再 patch，不然 lambda 裡面的 httpx.AsyncClient 會變成呼叫到
    # 剛剛才 patch 上去的自己，無限遞迴
    transport = httpx.MockTransport(handler)
    real_async_client = httpx.AsyncClient
    monkeypatch.setattr(gcal.httpx, "AsyncClient", lambda **kw: real_async_client(transport=transport, **kw))


# ---------- fetch_google_calendar_list ----------

@pytest.mark.asyncio
async def test_fetch_google_calendar_list_returns_items_with_bearer_auth(monkeypatch):
    """取得行事曆清單：要帶 Authorization: Bearer <token>、打 calendarList 這個 URL，並回傳 items。"""
    captured = {}

    def handler(request):
        captured["url"] = str(request.url)
        captured["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json={"items": [{"id": "cal1"}]})

    _mock_client(monkeypatch, handler)

    result = await gcal.fetch_google_calendar_list("my-token")

    assert result == [{"id": "cal1"}]
    assert captured["auth"] == "Bearer my-token"
    assert "calendarList" in captured["url"]


@pytest.mark.asyncio
async def test_fetch_google_calendar_list_returns_empty_list_when_no_items_key(monkeypatch):
    """Google 回應沒有 items 欄位 → 回傳空清單，不是 KeyError。"""
    _mock_client(monkeypatch, lambda request: httpx.Response(200, json={}))

    result = await gcal.fetch_google_calendar_list("token")

    assert result == []


@pytest.mark.asyncio
async def test_fetch_google_calendar_list_raises_http_status_error_on_failure(monkeypatch):
    """Google 回 401（授權失效）→ 丟出帶狀態碼的錯誤，呼叫端才能判斷要不要 refresh token。"""
    _mock_client(monkeypatch, lambda request: httpx.Response(401, json={"error": "invalid_token"}))

    with pytest.raises(httpx.HTTPStatusError):
        await gcal.fetch_google_calendar_list("bad-token")


# ---------- fetch_events_in_next_7_days ----------

@pytest.mark.asyncio
async def test_fetch_events_in_next_7_days_returns_items_for_given_calendar(monkeypatch):
    """取得未來 7 天事件：URL 要帶指定的行事曆 ID，並回傳 items。"""
    captured = {}

    def handler(request):
        captured["url"] = str(request.url)
        return httpx.Response(200, json={"items": [{"id": "evt1"}]})

    _mock_client(monkeypatch, handler)

    result = await gcal.fetch_events_in_next_7_days("token", "primary-cal-id")

    assert result == [{"id": "evt1"}]
    assert "primary-cal-id" in captured["url"]


@pytest.mark.asyncio
async def test_fetch_events_in_next_7_days_raises_http_status_error_on_failure(monkeypatch):
    """Google 回 403（沒有權限）→ 丟出錯誤，不能回傳空清單假裝成功。"""
    _mock_client(monkeypatch, lambda request: httpx.Response(403, json={"error": "forbidden"}))

    with pytest.raises(httpx.HTTPStatusError):
        await gcal.fetch_events_in_next_7_days("token", "cal1")


# ---------- fetch_freebusy ----------

@pytest.mark.asyncio
async def test_fetch_freebusy_returns_json_body(monkeypatch):
    """查詢忙碌時段：請求內容要帶指定的行事曆 ID，並回傳 Google 的 JSON。"""
    captured = {}

    def handler(request):
        captured["body"] = request.content
        return httpx.Response(200, json={"calendars": {"cal1": {"busy": []}}})

    _mock_client(monkeypatch, handler)

    result = await gcal.fetch_freebusy("token", "cal1")

    assert result == {"calendars": {"cal1": {"busy": []}}}
    assert b"cal1" in captured["body"]


@pytest.mark.asyncio
async def test_fetch_freebusy_raises_http_status_error_on_failure(monkeypatch):
    """Google 回 500 → 丟出錯誤，不能回傳空結果假裝成功。"""
    _mock_client(monkeypatch, lambda request: httpx.Response(500))

    with pytest.raises(httpx.HTTPStatusError):
        await gcal.fetch_freebusy("token", "cal1")


# ---------- compute_free_times ----------

def test_compute_free_times_no_busy_returns_whole_window():
    """完全沒有忙碌時段 → 整段時間都是空檔。"""
    result = gcal.compute_free_times([], "2026-09-10T00:00:00Z", "2026-09-10T08:00:00Z")

    assert result == [{"start": "2026-09-10T00:00:00Z", "end": "2026-09-10T08:00:00Z"}]


def test_compute_free_times_single_busy_block_splits_window():
    """中間有一段忙碌時段 → 空檔被切成前後兩段。"""
    busy = [{"start": "2026-09-10T02:00:00Z", "end": "2026-09-10T03:00:00Z"}]

    result = gcal.compute_free_times(busy, "2026-09-10T00:00:00Z", "2026-09-10T08:00:00Z")

    assert result == [
        {"start": "2026-09-10T00:00:00Z", "end": "2026-09-10T02:00:00Z"},
        {"start": "2026-09-10T03:00:00Z", "end": "2026-09-10T08:00:00Z"},
    ]


def test_compute_free_times_busy_covering_entire_window_returns_no_free_slots():
    """忙碌時段涵蓋整個時間窗 → 沒有任何空檔。"""
    busy = [{"start": "2026-09-10T00:00:00Z", "end": "2026-09-10T08:00:00Z"}]

    result = gcal.compute_free_times(busy, "2026-09-10T00:00:00Z", "2026-09-10T08:00:00Z")

    assert result == []


def test_compute_free_times_overlapping_busy_blocks_are_merged():
    """兩個重疊的忙碌時段（02:00-04:00 和 03:00-05:00）要當成一個連續時段處理，不能因為重疊產生時間倒著走的假空檔。"""
    busy = [
        {"start": "2026-09-10T02:00:00Z", "end": "2026-09-10T04:00:00Z"},
        {"start": "2026-09-10T03:00:00Z", "end": "2026-09-10T05:00:00Z"},
    ]

    result = gcal.compute_free_times(busy, "2026-09-10T00:00:00Z", "2026-09-10T08:00:00Z")

    assert result == [
        {"start": "2026-09-10T00:00:00Z", "end": "2026-09-10T02:00:00Z"},
        {"start": "2026-09-10T05:00:00Z", "end": "2026-09-10T08:00:00Z"},
    ]


def test_compute_free_times_unsorted_busy_blocks_are_handled():
    """忙碌時段沒照時間排序也要能正確算出空檔。"""
    busy = [
        {"start": "2026-09-10T05:00:00Z", "end": "2026-09-10T06:00:00Z"},
        {"start": "2026-09-10T02:00:00Z", "end": "2026-09-10T03:00:00Z"},
    ]

    result = gcal.compute_free_times(busy, "2026-09-10T00:00:00Z", "2026-09-10T08:00:00Z")

    assert result == [
        {"start": "2026-09-10T00:00:00Z", "end": "2026-09-10T02:00:00Z"},
        {"start": "2026-09-10T03:00:00Z", "end": "2026-09-10T05:00:00Z"},
        {"start": "2026-09-10T06:00:00Z", "end": "2026-09-10T08:00:00Z"},
    ]
