import pytest

from fastapi import HTTPException

import routers.schedule as schedule_router
from schemas.schedule import (
    ScheduleReorderInput,
    ScheduleTaskFieldsUpdate,
    ScheduleTaskDoneUpdate,
    SchedulePreferences,
    BlockedRecurringRule,
)

mock_user = {"sub": "test_user_123"}


@pytest.mark.asyncio
async def test_suggest_schedule_combines_tasks_and_free_slots(monkeypatch):
    """把使用者的任務和 Google Calendar 空檔組合成排程建議：高優先度的排進唯一的空檔，其餘進 unscheduled。"""
    async def mock_get_tasks(user_id):
        return [
            {"id": "t1", "title": "任務一", "priority": "High", "status": "To Do", "due_date": None},
            {"id": "t2", "title": "任務二", "priority": "Low", "status": "To Do", "due_date": None},
        ]

    async def mock_get_free_slots(user_id):
        return [{"start": "2026-09-10T09:00:00Z", "end": "2026-09-10T10:00:00Z"}]

    monkeypatch.setattr(schedule_router, "get_all_schedulable_items", mock_get_tasks)
    monkeypatch.setattr(schedule_router, "get_free_slots_for_user", mock_get_free_slots)

    result = await schedule_router.suggest_schedule(clerk_user=mock_user)

    assert len(result["scheduled"]) == 1
    assert result["scheduled"][0]["task_id"] == "t1"  # 高優先權先排
    assert len(result["unscheduled"]) == 1
    assert result["unscheduled"][0]["task_id"] == "t2"


@pytest.mark.asyncio
async def test_suggest_schedule_handles_no_tasks(monkeypatch):
    """使用者沒有任務（crud 回傳空清單）→ scheduled 和 unscheduled 都是空清單，不能出錯。"""
    async def mock_get_tasks(user_id):
        return []  # get_all_schedulable_items 沒有任何項目時回傳空清單

    async def mock_get_free_slots(user_id):
        return [{"start": "2026-09-10T09:00:00Z", "end": "2026-09-10T10:00:00Z"}]

    monkeypatch.setattr(schedule_router, "get_all_schedulable_items", mock_get_tasks)
    monkeypatch.setattr(schedule_router, "get_free_slots_for_user", mock_get_free_slots)

    result = await schedule_router.suggest_schedule(clerk_user=mock_user)

    assert result["scheduled"] == []
    assert result["unscheduled"] == []


@pytest.mark.asyncio
async def test_suggest_schedule_returns_clean_500_when_build_suggestion_fails(monkeypatch):
    """排程計算意外出錯 → 回 500 和清楚的中文訊息，而不是沒有說明的原始例外。"""
    # build_schedule_suggestion 本身不會丟 HTTPException，這裡模擬它出意外（例如未來資料格式跟假設的不一樣）
    async def mock_get_tasks(user_id):
        return [{"id": "t1", "title": "任務一", "priority": "High", "status": "To Do", "due_date": None}]

    async def mock_get_free_slots(user_id):
        return [{"start": "2026-09-10T09:00:00Z", "end": "2026-09-10T10:00:00Z"}]

    def mock_build_schedule_suggestion(tasks, free_slots, **kwargs):
        raise KeyError("unexpected")

    monkeypatch.setattr(schedule_router, "get_all_schedulable_items", mock_get_tasks)
    monkeypatch.setattr(schedule_router, "get_free_slots_for_user", mock_get_free_slots)
    monkeypatch.setattr(schedule_router, "build_schedule_suggestion", mock_build_schedule_suggestion)

    with pytest.raises(HTTPException) as exc_info:
        await schedule_router.suggest_schedule(clerk_user=mock_user)

    assert exc_info.value.status_code == 500


@pytest.mark.asyncio
async def test_suggest_schedule_returns_clean_500_when_apply_blocked_periods_fails(monkeypatch):
    """套用不工作時段這一步意外出錯，也要回清楚的中文 500，不是沒接住的原始例外
    ——這一步以前沒被包進 try/except，曾經是真的會讓使用者看到沒有說明的 500。"""
    async def mock_get_tasks(user_id):
        return [{"id": "t1", "title": "任務一", "priority": "High", "status": "To Do", "due_date": None}]

    async def mock_get_free_slots(user_id):
        return [{"start": "2026-09-10T09:00:00Z", "end": "2026-09-10T10:00:00Z"}]

    def mock_apply_blocked_periods(free_slots, blocked_recurring, blocked_exceptions):
        raise AttributeError("unexpected")

    monkeypatch.setattr(schedule_router, "get_all_schedulable_items", mock_get_tasks)
    monkeypatch.setattr(schedule_router, "get_free_slots_for_user", mock_get_free_slots)
    monkeypatch.setattr(schedule_router, "apply_blocked_periods", mock_apply_blocked_periods)

    with pytest.raises(HTTPException) as exc_info:
        await schedule_router.suggest_schedule(clerk_user=mock_user)

    assert exc_info.value.status_code == 500


@pytest.mark.asyncio
async def test_suggest_schedule_passes_preferences_through_to_blocking_and_build(monkeypatch):
    """preferences 的 buffer_minutes／daily_max_minutes 要原封不動轉給 build_schedule_suggestion，
    blocked_recurring／blocked_exceptions 要轉成 dict 交給 apply_blocked_periods。"""
    async def mock_get_tasks(user_id):
        return [{"id": "t1", "title": "任務一", "priority": "High", "status": "To Do", "due_date": None}]

    async def mock_get_free_slots(user_id):
        return [{"start": "2026-09-10T09:00:00Z", "end": "2026-09-10T10:00:00Z"}]

    captured = {}

    def mock_apply_blocked_periods(free_slots, blocked_recurring, blocked_exceptions):
        captured["blocked_recurring"] = blocked_recurring
        captured["blocked_exceptions"] = blocked_exceptions
        return free_slots

    def mock_build_schedule_suggestion(tasks, free_slots, **kwargs):
        captured["buffer_minutes"] = kwargs.get("buffer_minutes")
        captured["daily_max_minutes"] = kwargs.get("daily_max_minutes")
        return {"scheduled": [], "unscheduled": []}

    monkeypatch.setattr(schedule_router, "get_all_schedulable_items", mock_get_tasks)
    monkeypatch.setattr(schedule_router, "get_free_slots_for_user", mock_get_free_slots)
    monkeypatch.setattr(schedule_router, "apply_blocked_periods", mock_apply_blocked_periods)
    monkeypatch.setattr(schedule_router, "build_schedule_suggestion", mock_build_schedule_suggestion)

    preferences = SchedulePreferences(
        blocked_recurring=[BlockedRecurringRule(days_of_week=[5, 6], all_day=True)],
        buffer_minutes=15,
        daily_max_minutes=240,
    )
    await schedule_router.suggest_schedule(preferences=preferences, clerk_user=mock_user)

    assert captured["blocked_recurring"] == [{"days_of_week": [5, 6], "all_day": True, "start_time": None, "end_time": None}]
    assert captured["blocked_exceptions"] == []
    assert captured["buffer_minutes"] == 15
    assert captured["daily_max_minutes"] == 240


# ---------- confirm_schedule ----------

@pytest.mark.asyncio
async def test_confirm_schedule_recomputes_suggestion_and_delegates_to_calendar_creation(monkeypatch):
    """確認排程時重新計算一次排程建議（不吃前端傳來的結果），把 scheduled 清單交給
    create_calendar_events_for_scheduled_tasks 寫進 Google Calendar。"""
    async def mock_get_tasks(user_id):
        return [{"id": "t1", "title": "任務一", "priority": "High", "status": "To Do", "due_date": None}]

    async def mock_get_free_slots(user_id):
        return [{"start": "2026-09-10T09:00:00Z", "end": "2026-09-10T10:00:00Z"}]

    captured = {}

    async def mock_create_events(user_id, scheduled):
        captured["user_id"] = user_id
        captured["scheduled"] = scheduled
        return {"confirmed": [{"task_id": "t1", "title": "任務一", "calendar_event_id": "event-1"}], "failed": []}

    monkeypatch.setattr(schedule_router, "get_all_schedulable_items", mock_get_tasks)
    monkeypatch.setattr(schedule_router, "get_free_slots_for_user", mock_get_free_slots)
    monkeypatch.setattr(schedule_router, "create_calendar_events_for_scheduled_tasks", mock_create_events)

    result = await schedule_router.confirm_schedule(clerk_user=mock_user)

    assert captured["user_id"] == "test_user_123"
    assert captured["scheduled"][0]["task_id"] == "t1"
    assert result == {"confirmed": [{"task_id": "t1", "title": "任務一", "calendar_event_id": "event-1"}], "failed": []}


@pytest.mark.asyncio
async def test_confirm_schedule_returns_clean_500_when_build_suggestion_fails(monkeypatch):
    """重新計算排程建議這一步意外出錯 → 回 500，不會漏接例外變成沒有說明的錯誤。"""
    async def mock_get_tasks(user_id):
        return [{"id": "t1", "title": "任務一", "priority": "High", "status": "To Do", "due_date": None}]

    async def mock_get_free_slots(user_id):
        return [{"start": "2026-09-10T09:00:00Z", "end": "2026-09-10T10:00:00Z"}]

    def mock_build_schedule_suggestion(tasks, free_slots, **kwargs):
        raise KeyError("unexpected")

    monkeypatch.setattr(schedule_router, "get_all_schedulable_items", mock_get_tasks)
    monkeypatch.setattr(schedule_router, "get_free_slots_for_user", mock_get_free_slots)
    monkeypatch.setattr(schedule_router, "build_schedule_suggestion", mock_build_schedule_suggestion)

    with pytest.raises(HTTPException) as exc_info:
        await schedule_router.confirm_schedule(clerk_user=mock_user)

    assert exc_info.value.status_code == 500


# ---------- list_schedulable_tasks ----------

@pytest.mark.asyncio
async def test_list_schedulable_tasks_delegates_to_crud_with_logged_in_user(monkeypatch):
    async def mock_get_items(user_id):
        assert user_id == "test_user_123"
        return [{"id": "manual:t1", "source": "manual", "title": "任務"}]

    monkeypatch.setattr(schedule_router, "get_all_schedulable_items", mock_get_items)

    result = await schedule_router.list_schedulable_tasks(clerk_user=mock_user)

    assert result == [{"id": "manual:t1", "source": "manual", "title": "任務"}]


# ---------- reorder_schedule_tasks ----------

@pytest.mark.asyncio
async def test_reorder_schedule_tasks_reorders_then_returns_fresh_list(monkeypatch):
    captured = {}

    async def mock_reorder(user_id, items):
        captured["user_id"] = user_id
        captured["items"] = items

    async def mock_get_items(user_id):
        return [{"id": "manual:t1", "source": "manual", "title": "任務", "priority": "High"}]

    monkeypatch.setattr(schedule_router, "reorder_schedulable_items", mock_reorder)
    monkeypatch.setattr(schedule_router, "get_all_schedulable_items", mock_get_items)

    result = await schedule_router.reorder_schedule_tasks(
        ScheduleReorderInput(items=[{"task_id": "manual:t1", "priority": "High"}]),
        clerk_user=mock_user,
    )

    assert captured == {
        "user_id": "test_user_123",
        "items": [{"task_id": "manual:t1", "priority": "High"}],
    }
    assert result[0]["priority"] == "High"


# ---------- update_schedule_task_fields ----------

@pytest.mark.asyncio
async def test_update_schedule_task_fields_only_sends_non_none_fields(monkeypatch):
    captured = {}

    async def mock_update(user_id, task_id, data):
        captured["user_id"] = user_id
        captured["task_id"] = task_id
        captured["data"] = data

    monkeypatch.setattr(schedule_router, "update_scheduling_fields", mock_update)

    result = await schedule_router.update_schedule_task_fields(
        ScheduleTaskFieldsUpdate(task_id="github:42", duration=90),
        clerk_user=mock_user,
    )

    assert captured["user_id"] == "test_user_123"
    assert captured["task_id"] == "github:42"
    assert captured["data"] == {"duration": 90}  # due_date 留空，不該出現在要更新的資料裡
    assert result == {"task_id": "github:42", "updated": True}


@pytest.mark.asyncio
async def test_update_schedule_task_fields_skips_update_call_when_nothing_to_set(monkeypatch):
    """兩個欄位都沒帶 → 不需要呼叫 crud，不該無意義地打一次資料庫。"""
    async def fail_if_called(*args, **kwargs):
        raise AssertionError("不該呼叫 update_scheduling_fields")

    monkeypatch.setattr(schedule_router, "update_scheduling_fields", fail_if_called)

    result = await schedule_router.update_schedule_task_fields(
        ScheduleTaskFieldsUpdate(task_id="github:42"),
        clerk_user=mock_user,
    )

    assert result == {"task_id": "github:42", "updated": True}


# ---------- update_schedule_task_done ----------

@pytest.mark.asyncio
async def test_update_schedule_task_done_delegates_to_crud(monkeypatch):
    captured = {}

    async def mock_set_done(user_id, task_id, done):
        captured["user_id"] = user_id
        captured["task_id"] = task_id
        captured["done"] = done

    monkeypatch.setattr(schedule_router, "set_done", mock_set_done)

    result = await schedule_router.update_schedule_task_done(
        ScheduleTaskDoneUpdate(task_id="moodle:https://m/1", done=True),
        clerk_user=mock_user,
    )

    assert captured == {"user_id": "test_user_123", "task_id": "moodle:https://m/1", "done": True}
    assert result == {"task_id": "moodle:https://m/1", "done": True}
