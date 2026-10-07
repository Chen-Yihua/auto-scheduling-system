import pytest
import pytest_asyncio
from datetime import datetime, timezone
from pydantic import ValidationError

from fastapi import HTTPException

import routers.schedule as schedule_router
from core.cache import cache_get, cache_set, cache_delete
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
    blocked_recurring／blocked_exceptions 要轉成 dict 交給 apply_blocked_periods，
    使用者的時區兩邊都要拿到（不工作時段、每日上限都是用當地時間算的）。"""
    async def mock_get_tasks(user_id):
        return [{"id": "t1", "title": "任務一", "priority": "High", "status": "To Do", "due_date": None}]

    async def mock_get_free_slots(user_id):
        return [{"start": "2026-09-10T09:00:00Z", "end": "2026-09-10T10:00:00Z"}]

    captured = {}

    def mock_apply_blocked_periods(free_slots, blocked_recurring, blocked_exceptions, tz_name):
        captured["blocked_recurring"] = blocked_recurring
        captured["blocked_exceptions"] = blocked_exceptions
        captured["blocking_tz"] = tz_name
        return free_slots

    def mock_build_schedule_suggestion(tasks, free_slots, **kwargs):
        captured["buffer_minutes"] = kwargs.get("buffer_minutes")
        captured["daily_max_minutes"] = kwargs.get("daily_max_minutes")
        captured["build_tz"] = kwargs.get("tz_name")
        return {"scheduled": [], "unscheduled": []}

    monkeypatch.setattr(schedule_router, "get_all_schedulable_items", mock_get_tasks)
    monkeypatch.setattr(schedule_router, "get_free_slots_for_user", mock_get_free_slots)
    monkeypatch.setattr(schedule_router, "apply_blocked_periods", mock_apply_blocked_periods)
    monkeypatch.setattr(schedule_router, "build_schedule_suggestion", mock_build_schedule_suggestion)

    preferences = SchedulePreferences(
        blocked_recurring=[BlockedRecurringRule(days_of_week=[5, 6], all_day=True)],
        buffer_minutes=15,
        daily_max_minutes=240,
        timezone="Asia/Taipei",
    )
    await schedule_router.suggest_schedule(preferences=preferences, clerk_user=mock_user)

    assert captured["blocked_recurring"] == [{"days_of_week": [5, 6], "all_day": True, "start_time": None, "end_time": None}]
    assert captured["blocked_exceptions"] == []
    assert captured["buffer_minutes"] == 15
    assert captured["daily_max_minutes"] == 240
    assert captured["blocking_tz"] == "Asia/Taipei"
    assert captured["build_tz"] == "Asia/Taipei"



def test_schedule_preferences_rejects_unknown_timezone():
    """前端送來不認得的時區名稱 → 驗證時就擋下（422），不能等到排程計算時才噴 500。"""
    with pytest.raises(ValidationError):
        SchedulePreferences(timezone="Mars/Olympus_Mons")

    assert SchedulePreferences().timezone == "UTC"  # 舊版前端沒帶時區時，維持原本的行為

# ---------- confirm_schedule ----------

def _snapshot_item(task_id, title, start, end):
    return {"task_id": task_id, "title": title, "priority": "High", "start": start, "end": end}


@pytest_asyncio.fixture
async def clean_snapshot():
    """每個確認排程的測試都從「沒有快照」開始，不受其他測試留下的快取影響。"""
    await cache_delete(schedule_router._suggestion_snapshot_key(mock_user["sub"]))
    yield
    await cache_delete(schedule_router._suggestion_snapshot_key(mock_user["sub"]))


@pytest.mark.asyncio
async def test_suggest_schedule_saves_what_the_user_sees_as_a_snapshot(monkeypatch, clean_snapshot):
    """產生排程建議時，把回傳給使用者的那份 scheduled 存起來，確認時才能照這份寫入。"""
    async def mock_get_tasks(user_id):
        return [{"id": "t1", "title": "任務一", "priority": "High", "status": "To Do", "due_date": None}]

    async def mock_get_free_slots(user_id):
        return [{"start": "2030-01-01T09:00:00Z", "end": "2030-01-01T10:00:00Z"}]

    monkeypatch.setattr(schedule_router, "get_all_schedulable_items", mock_get_tasks)
    monkeypatch.setattr(schedule_router, "get_free_slots_for_user", mock_get_free_slots)

    await schedule_router.suggest_schedule(preferences=SchedulePreferences(), clerk_user=mock_user)

    snapshot = await cache_get(schedule_router._suggestion_snapshot_key(mock_user["sub"]))
    assert [item["task_id"] for item in snapshot] == ["t1"]
    assert snapshot[0]["start"] == "2030-01-01T09:00:00+00:00"


@pytest.mark.asyncio
async def test_confirm_schedule_writes_the_snapshot_without_recomputing(monkeypatch, clean_snapshot):
    """確認時寫入的是使用者看到的那份快照，不重新計算——看到建議之後才新增的任務
    不會被寫進去，時間也跟畫面上一樣。寫入前要用「此刻」的行事曆檢查（不用快取），
    確認完快照就刪掉，同一份建議不能確認兩次。"""
    await cache_set(
        schedule_router._suggestion_snapshot_key(mock_user["sub"]),
        [_snapshot_item("manual:t1", "任務一", "2030-01-01T09:00:00+00:00", "2030-01-01T10:00:00+00:00")],
        60,
    )

    async def mock_get_tasks(user_id):
        return [
            {"id": "manual:t1", "title": "任務一", "status": "To Do", "calendar_event_id": None},
            {"id": "manual:new", "title": "看到建議之後才新增的", "status": "To Do", "calendar_event_id": None},
        ]

    free_slots_calls = []

    async def mock_get_free_slots(user_id, use_cache=True):
        free_slots_calls.append(use_cache)
        return [{"start": "2030-01-01T08:00:00Z", "end": "2030-01-01T12:00:00Z"}]

    def fail_if_recomputed(*args, **kwargs):
        raise AssertionError("確認排程不該重新計算")

    captured = {}

    async def mock_create_events(user_id, scheduled):
        captured["scheduled"] = scheduled
        return {"confirmed": [{"task_id": "manual:t1", "title": "任務一", "calendar_event_id": "event-1"}], "failed": []}

    monkeypatch.setattr(schedule_router, "get_all_schedulable_items", mock_get_tasks)
    monkeypatch.setattr(schedule_router, "get_free_slots_for_user", mock_get_free_slots)
    monkeypatch.setattr(schedule_router, "build_schedule_suggestion", fail_if_recomputed)
    monkeypatch.setattr(schedule_router, "create_calendar_events_for_scheduled_tasks", mock_create_events)

    result = await schedule_router.confirm_schedule(clerk_user=mock_user)

    assert [item["task_id"] for item in captured["scheduled"]] == ["manual:t1"]
    assert captured["scheduled"][0]["start"] == datetime(2030, 1, 1, 9, 0, tzinfo=timezone.utc)
    assert free_slots_calls == [False]
    assert result == {"confirmed": [{"task_id": "manual:t1", "title": "任務一", "calendar_event_id": "event-1"}], "failed": []}
    assert await cache_get(schedule_router._suggestion_snapshot_key(mock_user["sub"])) is None


@pytest.mark.asyncio
async def test_confirm_schedule_reports_items_that_can_no_longer_be_written(monkeypatch, clean_snapshot):
    """快照裡有一筆的時段已經被新行程占用 → 不寫入、列進 failed 說明原因，其餘照寫；
    寫入 Google Calendar 本身失敗的也一起回報。"""
    await cache_set(
        schedule_router._suggestion_snapshot_key(mock_user["sub"]),
        [
            _snapshot_item("manual:ok", "還空著", "2030-01-01T09:00:00+00:00", "2030-01-01T10:00:00+00:00"),
            _snapshot_item("manual:busy", "被占用了", "2030-01-01T14:00:00+00:00", "2030-01-01T15:00:00+00:00"),
        ],
        60,
    )

    async def mock_get_tasks(user_id):
        return [
            {"id": "manual:ok", "title": "還空著", "status": "To Do", "calendar_event_id": None},
            {"id": "manual:busy", "title": "被占用了", "status": "To Do", "calendar_event_id": None},
        ]

    async def mock_get_free_slots(user_id, use_cache=True):
        return [{"start": "2030-01-01T08:00:00Z", "end": "2030-01-01T12:00:00Z"}]  # 下午被新行程占掉了

    captured = {}

    async def mock_create_events(user_id, scheduled):
        captured["scheduled"] = scheduled
        return {"confirmed": [], "failed": [{"task_id": "manual:ok", "title": "還空著", "reason": "Google 寫入失敗"}]}

    monkeypatch.setattr(schedule_router, "get_all_schedulable_items", mock_get_tasks)
    monkeypatch.setattr(schedule_router, "get_free_slots_for_user", mock_get_free_slots)
    monkeypatch.setattr(schedule_router, "create_calendar_events_for_scheduled_tasks", mock_create_events)

    result = await schedule_router.confirm_schedule(clerk_user=mock_user)

    assert [item["task_id"] for item in captured["scheduled"]] == ["manual:ok"]
    assert {f["task_id"]: f["reason"] for f in result["failed"]} == {
        "manual:busy": "這個時段已被其他行程占用，請重新產生排程",
        "manual:ok": "Google 寫入失敗",
    }


@pytest.mark.asyncio
async def test_confirm_schedule_returns_409_when_suggestion_expired(monkeypatch, clean_snapshot):
    """沒有快照（超過 30 分鐘過期、或已經確認過一次）→ 409，請使用者重新產生，
    不能什麼都不寫卻回成功。"""
    async def fail(*args, **kwargs):
        raise AssertionError("沒有快照就不該往下做")

    monkeypatch.setattr(schedule_router, "create_calendar_events_for_scheduled_tasks", fail)

    with pytest.raises(HTTPException) as exc_info:
        await schedule_router.confirm_schedule(clerk_user=mock_user)

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "排程建議已過期，請重新產生"


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
