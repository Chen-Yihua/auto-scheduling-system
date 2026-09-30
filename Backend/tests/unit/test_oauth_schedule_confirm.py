import pytest
import httpx
from datetime import datetime, timezone

import crud.oauth as oauth_crud


def _scheduled_task(task_id, title="任務", start=None, end=None):
    return {
        "task_id": task_id,
        "title": title,
        "priority": "High",
        "start": start or datetime(2026, 9, 10, 9, 0, tzinfo=timezone.utc),
        "end": end or datetime(2026, 9, 10, 10, 0, tzinfo=timezone.utc),
    }


def _mock_token_and_primary_calendar(monkeypatch, calendar_id="primary-cal-id"):
    async def mock_find_one(query):
        return {"_id": "uid123", "access_token": "valid-token"}

    async def mock_fetch_calendar_list(token):
        return [{"id": calendar_id, "primary": True}]

    monkeypatch.setattr(oauth_crud.db.googleCalendarTokens, "find_one", mock_find_one)
    monkeypatch.setattr(oauth_crud, "fetch_google_calendar_list", mock_fetch_calendar_list)


@pytest.mark.asyncio
async def test_create_calendar_events_returns_empty_result_without_calling_google_when_no_scheduled_tasks(monkeypatch):
    """沒有任何「已排入時段」的任務 → 直接回空結果，完全不打 Google API。"""
    async def fail_if_called(*args, **kwargs):
        raise AssertionError("不該呼叫 Google API")

    monkeypatch.setattr(oauth_crud, "fetch_google_calendar_list", fail_if_called)

    result = await oauth_crud.create_calendar_events_for_scheduled_tasks("uid123", [])

    assert result == {"confirmed": [], "failed": []}


@pytest.mark.asyncio
async def test_create_calendar_events_success_writes_calendar_event_id(monkeypatch):
    """成功建立事件 → 回傳 confirmed 清單，並把 calendar_event_id 存回對應任務。"""
    _mock_token_and_primary_calendar(monkeypatch)

    captured_calls = []

    async def mock_create_event(access_token, calendar_id, summary, start, end):
        captured_calls.append((access_token, calendar_id, summary, start, end))
        return {"id": f"event-{summary}"}

    saved = {}

    async def mock_set_calendar_event_id_for_composite(user_id, task_id, calendar_event_id):
        saved[task_id] = (user_id, calendar_event_id)

    monkeypatch.setattr(oauth_crud, "create_calendar_event", mock_create_event)
    monkeypatch.setattr(oauth_crud, "set_calendar_event_id_for_composite", mock_set_calendar_event_id_for_composite)

    scheduled = [_scheduled_task("t1", title="寫報告")]
    result = await oauth_crud.create_calendar_events_for_scheduled_tasks("uid123", scheduled)

    assert result == {
        "confirmed": [{"task_id": "t1", "title": "寫報告", "calendar_event_id": "event-寫報告"}],
        "failed": [],
    }
    assert saved["t1"] == ("uid123", "event-寫報告")
    # start/end 要轉成 Google API 要的 ISO 字串（帶 Z），不是原本的 datetime 物件
    assert captured_calls[0][3] == "2026-09-10T09:00:00Z"
    assert captured_calls[0][4] == "2026-09-10T10:00:00Z"


@pytest.mark.asyncio
async def test_create_calendar_events_partial_failure_keeps_successful_ones(monkeypatch):
    """一批裡有成功有失敗 → 各自進對應的清單，不會因為一筆失敗就整批放棄。"""
    _mock_token_and_primary_calendar(monkeypatch)

    async def mock_create_event(access_token, calendar_id, summary, start, end):
        if summary == "會失敗的任務":
            request = httpx.Request("POST", "https://example.com")
            response = httpx.Response(500, request=request)
            raise httpx.HTTPStatusError("error", request=request, response=response)
        return {"id": "event-ok"}

    async def mock_set_calendar_event_id_for_composite(user_id, task_id, calendar_event_id):
        pass

    monkeypatch.setattr(oauth_crud, "create_calendar_event", mock_create_event)
    monkeypatch.setattr(oauth_crud, "set_calendar_event_id_for_composite", mock_set_calendar_event_id_for_composite)

    scheduled = [
        _scheduled_task("t1", title="會成功的任務"),
        _scheduled_task("t2", title="會失敗的任務"),
    ]
    result = await oauth_crud.create_calendar_events_for_scheduled_tasks("uid123", scheduled)

    assert len(result["confirmed"]) == 1
    assert result["confirmed"][0]["task_id"] == "t1"
    assert len(result["failed"]) == 1
    assert result["failed"][0]["task_id"] == "t2"
    assert result["failed"][0]["reason"]


@pytest.mark.asyncio
async def test_create_calendar_events_network_error_marks_task_as_failed(monkeypatch):
    """連不上 Google（網路問題）→ 該筆進 failed，不會讓整個請求噴例外。"""
    _mock_token_and_primary_calendar(monkeypatch)

    async def mock_create_event(access_token, calendar_id, summary, start, end):
        raise httpx.ConnectError("Google 掛了")

    monkeypatch.setattr(oauth_crud, "create_calendar_event", mock_create_event)

    result = await oauth_crud.create_calendar_events_for_scheduled_tasks("uid123", [_scheduled_task("t1")])

    assert result["confirmed"] == []
    assert result["failed"][0]["task_id"] == "t1"
