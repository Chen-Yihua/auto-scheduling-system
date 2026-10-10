"""用 httpx.MockTransport 測試 Google Calendar client，不實際連線。"""
import pytest
import httpx

import services.google_calendar_client as gcal


def _mock_client(monkeypatch, handler):
    # 先存下原本的 AsyncClient，否則 patch 後 lambda 會呼叫到自己而無限遞迴
    transport = httpx.MockTransport(handler)
    real_async_client = httpx.AsyncClient
    monkeypatch.setattr(gcal.httpx, "AsyncClient", lambda **kw: real_async_client(transport=transport, **kw))


# ---------- fetch_google_calendar_list ----------

@pytest.mark.asyncio
async def test_fetch_google_calendar_list_returns_items_with_bearer_auth(monkeypatch):
    """取得行事曆清單：帶 Bearer token 呼叫 calendarList，回傳 items。"""
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


# ---------- create_calendar_event ----------

@pytest.mark.asyncio
async def test_create_calendar_event_posts_summary_and_start_end_with_bearer_auth(monkeypatch):
    """建立事件：呼叫 events 端點，body 帶 summary/start/end，回傳建立的事件。"""
    captured = {}

    def handler(request):
        captured["url"] = str(request.url)
        captured["auth"] = request.headers.get("authorization")
        captured["body"] = request.content
        return httpx.Response(200, json={"id": "event-abc", "summary": "寫報告"})

    _mock_client(monkeypatch, handler)

    result = await gcal.create_calendar_event(
        "my-token", "primary-cal-id", "寫報告", "2026-09-10T09:00:00Z", "2026-09-10T10:00:00Z"
    )

    assert result == {"id": "event-abc", "summary": "寫報告"}
    assert captured["auth"] == "Bearer my-token"
    assert "primary-cal-id" in captured["url"]
    assert b"2026-09-10T09:00:00Z" in captured["body"]
    assert b"2026-09-10T10:00:00Z" in captured["body"]


@pytest.mark.asyncio
async def test_create_calendar_event_raises_http_status_error_on_failure(monkeypatch):
    """Google 回 400（例如時間格式不對）→ 丟出錯誤，不能假裝建立成功。"""
    _mock_client(monkeypatch, lambda request: httpx.Response(400, json={"error": "invalid time"}))

    with pytest.raises(httpx.HTTPStatusError):
        await gcal.create_calendar_event("token", "cal1", "任務", "2026-09-10T09:00:00Z", "2026-09-10T10:00:00Z")


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
