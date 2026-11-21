import logging

import pytest
from core.errors import AppError
import pytest_asyncio
from datetime import datetime, timezone
from pydantic import ValidationError

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
async def test_suggest_schedule_returns_clean_500_when_build_suggestion_fails(monkeypatch, caplog):
    """AC4：排程計算意外出錯 → 500 INTERNAL_ERROR 和固定的中文訊息（不含例外內容），並記下例外的 log。"""
    # 模擬 build_schedule_suggestion 出意外（例如未來資料格式跟假設的不一樣）
    async def mock_get_tasks(user_id):
        return [{"id": "t1", "title": "任務一", "priority": "High", "status": "To Do", "due_date": None}]

    async def mock_get_free_slots(user_id):
        return [{"start": "2026-09-10T09:00:00Z", "end": "2026-09-10T10:00:00Z"}]

    def mock_build_schedule_suggestion(tasks, free_slots, **kwargs):
        raise KeyError("unexpected")

    monkeypatch.setattr(schedule_router, "get_all_schedulable_items", mock_get_tasks)
    monkeypatch.setattr(schedule_router, "get_free_slots_for_user", mock_get_free_slots)
    monkeypatch.setattr(schedule_router, "build_schedule_suggestion", mock_build_schedule_suggestion)

    with caplog.at_level(logging.ERROR, logger="routers.schedule"):
        with pytest.raises(AppError) as exc_info:
            await schedule_router.suggest_schedule(clerk_user=mock_user)

    assert exc_info.value.error_code == "INTERNAL_ERROR"
    assert exc_info.value.detail == "產生排程建議失敗，請稍後再試"
    assert "unexpected" not in exc_info.value.detail
    assert any(r.levelno == logging.ERROR and r.exc_info for r in caplog.records)


@pytest.mark.asyncio
async def test_suggest_schedule_returns_clean_500_when_apply_blocked_periods_fails(monkeypatch):
    """AC4：套用不工作時段出錯 → 500 INTERNAL_ERROR 和固定的說明。"""
    async def mock_get_tasks(user_id):
        return [{"id": "t1", "title": "任務一", "priority": "High", "status": "To Do", "due_date": None}]

    async def mock_get_free_slots(user_id):
        return [{"start": "2026-09-10T09:00:00Z", "end": "2026-09-10T10:00:00Z"}]

    def mock_apply_blocked_periods(free_slots, blocked_recurring, blocked_exceptions):
        raise AttributeError("unexpected")

    monkeypatch.setattr(schedule_router, "get_all_schedulable_items", mock_get_tasks)
    monkeypatch.setattr(schedule_router, "get_free_slots_for_user", mock_get_free_slots)
    monkeypatch.setattr(schedule_router, "apply_blocked_periods", mock_apply_blocked_periods)

    with pytest.raises(AppError) as exc_info:
        await schedule_router.suggest_schedule(clerk_user=mock_user)

    assert exc_info.value.error_code == "INTERNAL_ERROR"
    assert exc_info.value.detail == "產生排程建議失敗，請稍後再試"


@pytest.mark.asyncio
async def test_suggest_schedule_passes_preferences_through_to_blocking_and_build(monkeypatch):
    """preferences 的各欄位和時區要正確傳給 apply_blocked_periods 和 build_schedule_suggestion。"""
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
    """
    確認時寫入快照，不重新計算；檢查時不用快取的行事曆；
    確認後刪除快照，同一份建議不能確認兩次。
    """
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
    """時段已被占用的項目列入 failed，其餘照寫；寫入失敗的也一併回報。"""
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
    """沒有快照（已過期或已確認）→ SUGGESTION_EXPIRED（409）。"""
    async def fail(*args, **kwargs):
        raise AssertionError("沒有快照就不該往下做")

    monkeypatch.setattr(schedule_router, "create_calendar_events_for_scheduled_tasks", fail)

    with pytest.raises(AppError) as exc_info:
        await schedule_router.confirm_schedule(clerk_user=mock_user)

    assert exc_info.value.error_code == "SUGGESTION_EXPIRED"
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
async def test_update_schedule_task_fields_without_fields_still_goes_through_crud(monkeypatch):
    """AC8：兩個欄位都沒帶也交給 crud，由 crud 檢查 id（不存在 404、格式錯 400），不寫入任何欄位。"""
    captured = {}

    async def mock_update(user_id, task_id, data):
        captured.update(task_id=task_id, data=data)

    monkeypatch.setattr(schedule_router, "update_scheduling_fields", mock_update)

    result = await schedule_router.update_schedule_task_fields(
        ScheduleTaskFieldsUpdate(task_id="github:42"),
        clerk_user=mock_user,
    )

    assert captured == {"task_id": "github:42", "data": {}}
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


# ---------- 階段任務（用記憶體資料庫，測 router 與 crud 的串接）----------

from core.database import db
from core.errors import InvalidRequestError
import services.google_calendar as calendar_service

STAGE_USER = {"sub": "schedule_stage_user"}


async def _insert_stage_tasks(parent_due=None, stages=(("High", None), ("Medium", None))):
    await db.manual_tasks.insert_one({
        "_id": "sp", "user_id": STAGE_USER["sub"], "title": "主任務", "description": "",
        "is_parent": True, "due_date": parent_due, "inferred_fields": [],
        "subtask_ids": [f"ss{index}" for index in range(1, len(stages) + 1)],
    })
    for index, (priority, due) in enumerate(stages, start=1):
        await db.manual_tasks.insert_one({
            "_id": f"ss{index}", "user_id": STAGE_USER["sub"], "title": f"階段{index}", "description": "",
            "parent_id": "sp", "status": "To Do", "priority": priority,
            "duration": 60, "due_date": due,
        })


@pytest_asyncio.fixture
async def stage_tasks():
    yield _insert_stage_tasks
    await db.manual_tasks.delete_many({"user_id": STAGE_USER["sub"]})


@pytest.mark.asyncio
async def test_ac17_marking_parent_done_via_schedule_api_is_rejected(stage_tasks):
    """AC17：主任務的狀態依子任務計算，對主任務呼叫 PATCH /schedule/tasks/done 回 400。"""
    await stage_tasks()

    with pytest.raises(InvalidRequestError):
        await schedule_router.update_schedule_task_done(
            ScheduleTaskDoneUpdate(task_id="manual:sp", done=True), clerk_user=STAGE_USER,
        )


@pytest.mark.asyncio
async def test_ac18_later_stage_can_be_marked_done_before_earlier_stage(stage_tasks):
    """AC18：第 1 階段還沒完成，也可以先把第 2 階段標成完成。"""
    await stage_tasks()

    await schedule_router.update_schedule_task_done(
        ScheduleTaskDoneUpdate(task_id="manual:ss2", done=True), clerk_user=STAGE_USER,
    )

    assert (await db.manual_tasks.find_one({"_id": "ss2"}))["status"] == "Done"


@pytest.mark.asyncio
async def test_ac20_reorder_that_makes_later_stage_higher_priority_is_rejected_and_nothing_changes(stage_tasks):
    """AC20：拖拉排序讓第 2 階段（中）變成比第 1 階段（高）更高 → 400，所有任務的優先序和順序都不變。"""
    await stage_tasks(stages=(("Medium", None), ("Medium", None)))

    with pytest.raises(InvalidRequestError) as exc_info:
        await schedule_router.reorder_schedule_tasks(
            ScheduleReorderInput(items=[
                {"task_id": "manual:ss2", "priority": "High"},
                {"task_id": "manual:ss1", "priority": "Medium"},
            ]),
            clerk_user=STAGE_USER,
        )

    assert "階段 2" in exc_info.value.detail
    docs = {d["_id"]: d for d in await db.manual_tasks.find({"user_id": STAGE_USER["sub"], "parent_id": "sp"}).to_list(length=None)}
    assert docs["ss2"]["priority"] == "Medium"
    assert docs["ss2"].get("sort_order") is None


@pytest.mark.asyncio
async def test_ac20_fields_update_that_puts_stage_due_date_before_previous_stage_is_rejected(stage_tasks):
    """AC20：排程精靈把第 2 階段的截止日改到第 1 階段之前 → 400，截止日不變。"""
    stage1_due = datetime(2030, 1, 10, tzinfo=timezone.utc)
    await stage_tasks(stages=(("High", stage1_due), ("High", None)))

    with pytest.raises(InvalidRequestError) as exc_info:
        await schedule_router.update_schedule_task_fields(
            ScheduleTaskFieldsUpdate(task_id="manual:ss2", due_date=datetime(2030, 1, 5, tzinfo=timezone.utc)),
            clerk_user=STAGE_USER,
        )

    assert "階段 2" in exc_info.value.detail
    assert (await db.manual_tasks.find_one({"_id": "ss2"}))["due_date"] is None


@pytest.mark.asyncio
async def test_ac20_fields_update_that_puts_stage_after_parent_due_date_is_rejected(stage_tasks):
    """AC20 / AC8：排程精靈把子任務的截止日改到晚於主任務 → 400。"""
    await stage_tasks(parent_due=datetime(2030, 1, 10, tzinfo=timezone.utc))

    with pytest.raises(InvalidRequestError):
        await schedule_router.update_schedule_task_fields(
            ScheduleTaskFieldsUpdate(task_id="manual:ss1", due_date=datetime(2030, 2, 1, tzinfo=timezone.utc)),
            clerk_user=STAGE_USER,
        )


@pytest.mark.asyncio
async def test_ac24_suggest_asks_google_for_latest_time_of_previous_stage_event(monkeypatch):
    """AC24：前一個階段已排入行事曆 → 產生建議時向 Google 查事件最新的結束時間，後面的階段排在它之後。"""
    async def mock_get_tasks(user_id):
        return [
            {"id": "manual:s1", "title": "階段1", "priority": "High", "status": "To Do",
             "calendar_event_id": "ev-1", "parent_id": "manual:p", "stage": 1, "duration": 60},
            {"id": "manual:s2", "title": "階段2", "priority": "High", "status": "To Do",
             "calendar_event_id": None, "parent_id": "manual:p", "stage": 2, "duration": 60},
        ]

    async def mock_get_free_slots(user_id):
        return [{"start": "2030-01-01T09:00:00Z", "end": "2030-01-01T18:00:00Z"}]

    asked = []

    async def mock_event_ends(user_id, event_ids):
        asked.append(event_ids)
        return {"ev-1": datetime(2030, 1, 1, 15, 0, tzinfo=timezone.utc)}

    monkeypatch.setattr(schedule_router, "get_all_schedulable_items", mock_get_tasks)
    monkeypatch.setattr(schedule_router, "get_free_slots_for_user", mock_get_free_slots)
    monkeypatch.setattr(schedule_router, "get_calendar_event_ends", mock_event_ends)

    result = await schedule_router.suggest_schedule(preferences=SchedulePreferences(), clerk_user=mock_user)

    assert asked == [["ev-1"]]
    assert result["scheduled"][0]["task_id"] == "manual:s2"
    assert result["scheduled"][0]["start"] == datetime(2030, 1, 1, 15, 0, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_suggest_does_not_call_google_events_when_no_stage_waits_on_a_calendar_event(monkeypatch):
    """沒有子任務在等已排入行事曆的前一個階段 → 不多打 Google 的 events.get。"""
    async def mock_get_tasks(user_id):
        return [{"id": "t1", "title": "任務", "priority": "High", "status": "To Do", "due_date": None}]

    async def mock_get_free_slots(user_id):
        return [{"start": "2030-01-01T09:00:00Z", "end": "2030-01-01T10:00:00Z"}]

    async def fail_if_called(*args, **kwargs):
        raise AssertionError("不該查事件")

    monkeypatch.setattr(schedule_router, "get_all_schedulable_items", mock_get_tasks)
    monkeypatch.setattr(schedule_router, "get_free_slots_for_user", mock_get_free_slots)
    monkeypatch.setattr(schedule_router, "get_calendar_event_ends", fail_if_called)

    result = await schedule_router.suggest_schedule(preferences=SchedulePreferences(), clerk_user=mock_user)

    assert [i["task_id"] for i in result["scheduled"]] == ["t1"]


@pytest.mark.asyncio
async def test_ac26_confirm_skips_later_stage_when_previous_stage_write_fails(monkeypatch, clean_snapshot):
    """AC26：確認排程時第 1 階段寫入 Google 失敗 → 第 2 階段不寫入，原因寫前一個階段寫入失敗；其他任務照寫。"""
    import httpx

    await cache_set(
        schedule_router._suggestion_snapshot_key(mock_user["sub"]),
        [
            _snapshot_item("manual:s1", "階段1", "2030-01-01T09:00:00+00:00", "2030-01-01T10:00:00+00:00"),
            _snapshot_item("manual:s2", "階段2", "2030-01-01T10:00:00+00:00", "2030-01-01T11:00:00+00:00"),
            _snapshot_item("manual:other", "其他", "2030-01-01T11:00:00+00:00", "2030-01-01T12:00:00+00:00"),
        ],
        60,
    )

    async def mock_get_tasks(user_id):
        return [
            {"id": "manual:s1", "title": "階段1", "status": "To Do", "calendar_event_id": None, "parent_id": "manual:p", "stage": 1},
            {"id": "manual:s2", "title": "階段2", "status": "To Do", "calendar_event_id": None, "parent_id": "manual:p", "stage": 2},
            {"id": "manual:other", "title": "其他", "status": "To Do", "calendar_event_id": None},
        ]

    async def mock_get_free_slots(user_id, use_cache=True):
        return [{"start": "2030-01-01T08:00:00Z", "end": "2030-01-01T18:00:00Z"}]

    async def mock_token(user_id):
        return "token", "primary"

    written = []

    async def mock_create_event(access_token, calendar_id, summary, start, end):
        if summary == "階段1":
            request = httpx.Request("POST", "https://example.com")
            raise httpx.HTTPStatusError("error", request=request, response=httpx.Response(500, request=request))
        written.append(summary)
        return {"id": f"ev-{summary}"}

    async def mock_set_event_id(user_id, task_id, event_id, start, end):
        pass

    monkeypatch.setattr(schedule_router, "get_all_schedulable_items", mock_get_tasks)
    monkeypatch.setattr(schedule_router, "get_free_slots_for_user", mock_get_free_slots)
    monkeypatch.setattr(calendar_service, "_get_access_token_and_primary_calendar_id", mock_token)
    monkeypatch.setattr(calendar_service, "create_calendar_event", mock_create_event)
    monkeypatch.setattr(calendar_service, "set_calendar_event_id_for_composite", mock_set_event_id)

    result = await schedule_router.confirm_schedule(clerk_user=mock_user)

    assert written == ["其他"]
    reasons = {f["task_id"]: f["reason"] for f in result["failed"]}
    assert reasons["manual:s2"] == "前一個階段寫入失敗"
    assert "manual:s1" in reasons


# ---------- issue-42：處理在 Google 日曆上被刪除的事件（用記憶體資料庫）----------

from core.errors import ExternalServiceError, ReauthRequiredError
from schemas.schedule import ResolveRemovedEventsInput

REMOVED_USER = {"sub": "removed_events_user"}
OTHER_USER = "removed_events_other_user"


@pytest_asyncio.fixture
async def removed_google(monkeypatch):
    """
    假的 Google 日曆：gone 是已被刪除的事件 id；queried、deleted 記錄查過、刪過哪些事件。
    query_errors 是查到那個事件時要丟的例外；on_query、on_delete 在查詢、刪除時執行，模擬另一個分頁同時改資料。
    """
    state = {"gone": set(), "queried": [], "deleted": [], "query_errors": {}, "on_query": None, "on_delete": None}

    async def fake_find_removed(user_id, event_ids):
        assert user_id == REMOVED_USER["sub"]
        for event_id in event_ids:
            state["queried"].append(event_id)
            if event_id in state["query_errors"]:
                raise state["query_errors"][event_id]
        if state["on_query"]:
            await state["on_query"](event_ids)
        return {event_id for event_id in event_ids if event_id in state["gone"]}

    async def fake_delete(user_id, event_ids):
        if state["on_delete"]:
            await state["on_delete"](event_ids)
        state["deleted"].extend(event_ids)

    monkeypatch.setattr(schedule_router, "find_removed_calendar_events", fake_find_removed)
    monkeypatch.setattr(schedule_router, "delete_calendar_events", fake_delete)
    yield state
    for user_id in (REMOVED_USER["sub"], OTHER_USER):
        await db.manual_tasks.delete_many({"user_id": user_id})
        await db.github_issues.delete_many({"user_id": user_id})


async def _manual(task_id, event_id=None, status="To Do", user_id=REMOVED_USER["sub"], **extra):
    await db.manual_tasks.insert_one({
        "_id": task_id, "user_id": user_id, "title": f"任務{task_id}", "description": "", "status": status,
        "priority": "Medium", "duration": 60, "due_date": None, "calendar_event_id": event_id, **extra,
    })


async def _staged(parent_id, stages):
    """stages 依階段順序，每一項是 (事件 id, 狀態)；子任務 id 是 <parent_id>-<階段>。"""
    await db.manual_tasks.insert_one({
        "_id": parent_id, "user_id": REMOVED_USER["sub"], "title": f"主任務{parent_id}", "description": "",
        "is_parent": True, "due_date": None, "inferred_fields": [],
        "subtask_ids": [f"{parent_id}-{n}" for n in range(1, len(stages) + 1)],
    })
    for n, (event_id, status) in enumerate(stages, start=1):
        await _manual(f"{parent_id}-{n}", event_id, status, parent_id=parent_id)


async def _event_id(task_id):
    doc = await db.manual_tasks.find_one({"_id": task_id})
    return doc["calendar_event_id"] if doc else "<deleted>"


async def _resolve(reschedule=(), delete=()):
    return await schedule_router.resolve_removed_events(
        ResolveRemovedEventsInput(reschedule=list(reschedule), delete=list(delete)), clerk_user=REMOVED_USER,
    )


def _failed_ids(result):
    return [f["task_id"] for f in result["failed"]]


@pytest.mark.asyncio
async def test_issue42_ac1_ac2_removed_events_lists_items_whose_event_was_deleted_on_google(removed_google):
    """AC1、AC2：任務的事件在 Google 上已被刪除 → 出現在 removed-events；事件還在的已排入任務不列出。外部項目也查。"""
    await _manual("gone", "ev-gone")
    await _manual("alive", "ev-alive")
    await db.github_issues.insert_one({
        "id": 4201, "user_id": REMOVED_USER["sub"], "title": "外部項目", "status": "open", "calendar_event_id": "ev-gh",
    })
    removed_google["gone"] = {"ev-gone", "ev-gh"}

    result = await schedule_router.list_removed_events(clerk_user=REMOVED_USER)

    assert sorted(item["id"] for item in result) == ["github:4201", "manual:gone"]


@pytest.mark.asyncio
async def test_issue42_ac3_done_parent_and_unscheduled_items_are_not_asked_to_google(removed_google):
    """AC3：已完成的項目、主任務、沒有事件編號的項目不送去 Google 查，也不列出。"""
    await _manual("done", "ev-done", status="Done")
    await _manual("unscheduled", None)
    await _manual("scheduled", "ev-scheduled")
    await _manual("parent-with-id", "ev-parent", is_parent=True, subtask_ids=[])
    removed_google["gone"] = {"ev-done", "ev-parent", "ev-scheduled"}

    result = await schedule_router.list_removed_events(clerk_user=REMOVED_USER)

    assert removed_google["queried"] == ["ev-scheduled"]
    assert [item["id"] for item in result] == ["manual:scheduled"]


@pytest.mark.asyncio
async def test_issue42_ac7_removed_stage_lists_later_scheduled_stages_not_already_listed(removed_google):
    """AC7：列出的階段帶上後面「已排入、還沒完成、沒有列在這一步」的階段；已完成、沒排入、也列在這一步的不算。"""
    await _staged("p", [
        ("ev-1", "To Do"), ("ev-2", "To Do"), ("ev-3", "To Do"), ("ev-4", "Done"), (None, "To Do"), ("ev-6", "To Do"),
    ])
    removed_google["gone"] = {"ev-1", "ev-3"}

    result = {item["id"]: item for item in await schedule_router.list_removed_events(clerk_user=REMOVED_USER)}

    assert [s["stage"] for s in result["manual:p-1"]["later_stages"]] == [2, 6]
    assert [s["task_id"] for s in result["manual:p-1"]["later_stages"]] == ["manual:p-2", "manual:p-6"]
    assert [s["stage"] for s in result["manual:p-3"]["later_stages"]] == [6]


@pytest.mark.asyncio
async def test_issue42_ac10_rescheduled_items_lose_their_calendar_event_id(removed_google):
    """AC10：勾選重新排程 → 手動任務和外部項目的 Google 日曆事件編號都清掉。"""
    await _manual("t", "ev-t")
    await db.github_issues.insert_one({
        "id": 4202, "user_id": REMOVED_USER["sub"], "title": "外部項目", "status": "open", "calendar_event_id": "ev-gh",
    })
    removed_google["gone"] = {"ev-t", "ev-gh"}

    result = await _resolve(reschedule=["manual:t", "github:4202"])

    assert result["failed"] == []
    assert await _event_id("t") is None
    github = await db.github_issues.find_one({"user_id": REMOVED_USER["sub"], "id": 4202})
    assert github is not None and github["calendar_event_id"] is None


@pytest.mark.asyncio
async def test_issue42_ac11_later_scheduled_stages_are_removed_from_google_and_cleared(removed_google):
    """AC11：勾選的階段後面已排入、還沒完成的階段 → 事件從 Google 刪掉、編號清掉；已完成的後面階段不變。"""
    await _staged("p", [("ev-1", "To Do"), ("ev-2", "To Do"), ("ev-3", "Done")])
    removed_google["gone"] = {"ev-1"}

    result = await _resolve(reschedule=["manual:p-1"])

    assert result["failed"] == []
    assert removed_google["deleted"] == ["ev-2"]
    assert [await _event_id(t) for t in ("p-1", "p-2", "p-3")] == [None, None, "ev-3"]


@pytest.mark.asyncio
async def test_issue42_ac12_each_listed_stage_follows_its_own_checkbox(removed_google):
    """AC12：同一個主任務兩個階段都列出，勾前面、不勾後面 → 後面的被刪除，前面的重新排程。"""
    await _staged("p", [("ev-1", "To Do"), ("ev-2", "To Do"), ("ev-3", "To Do")])
    removed_google["gone"] = {"ev-1", "ev-2"}

    result = await _resolve(reschedule=["manual:p-1"], delete=["manual:p-2"])

    assert result["failed"] == []
    assert await _event_id("p-1") is None
    assert await _event_id("p-2") == "<deleted>"
    # 階段 3 不在請求裡，照「後面的階段一起移除」處理
    assert await _event_id("p-3") is None
    items = await schedule_router.get_all_schedulable_items(REMOVED_USER["sub"])
    assert {t["id"]: t.get("stage") for t in items if t.get("parent_id")} == {"manual:p-1": 1, "manual:p-3": 2}


@pytest.mark.asyncio
async def test_issue42_ac13_unchecked_task_and_stage_are_deleted_and_later_stages_renumbered(removed_google):
    """AC13：沒勾的一般任務、子任務從系統刪除；同一個主任務其他階段的資料與事件不變，後面的階段編號往前遞補。"""
    await _manual("plain", "ev-plain")
    await _staged("p", [("ev-1", "To Do"), ("ev-2", "To Do"), (None, "To Do")])
    removed_google["gone"] = {"ev-plain", "ev-2"}

    result = await _resolve(delete=["manual:plain", "manual:p-2"])

    assert result["failed"] == []
    assert await _event_id("plain") == "<deleted>"
    assert await _event_id("p-2") == "<deleted>"
    assert [await _event_id(t) for t in ("p-1", "p-3")] == ["ev-1", None]
    items = {t["id"]: t for t in await schedule_router.get_all_schedulable_items(REMOVED_USER["sub"])}
    assert items["manual:p-3"]["stage"] == 2
    assert "ev-1" not in removed_google["deleted"]


@pytest.mark.asyncio
async def test_issue42_ac14_deleting_every_stage_deletes_the_parent(removed_google):
    """AC14：沒勾的階段是主任務目前所有的階段 → 主任務一起刪除。"""
    await _staged("p", [("ev-1", "To Do"), ("ev-2", "To Do")])
    removed_google["gone"] = {"ev-1", "ev-2"}

    result = await _resolve(delete=["manual:p-1", "manual:p-2"])

    assert result["failed"] == []
    assert await db.manual_tasks.count_documents({"user_id": REMOVED_USER["sub"]}) == 0


@pytest.mark.asyncio
async def test_issue42_ac15_event_still_on_google_or_no_event_id_changes_nothing(removed_google):
    """AC15：處理時事件仍在 Google 上、或任務已經沒有編號 → 編號不清、任務不刪，算成功。"""
    await _manual("restored", "ev-restored")
    await _manual("restored-delete", "ev-restored-delete")
    await _manual("cleared", None)
    removed_google["gone"] = set()

    result = await _resolve(reschedule=["manual:restored", "manual:cleared"], delete=["manual:restored-delete"])

    assert result["failed"] == []
    assert sorted(result["succeeded"]) == ["manual:cleared", "manual:restored", "manual:restored-delete"]
    assert await _event_id("restored") == "ev-restored"
    assert await _event_id("restored-delete") == "ev-restored-delete"
    assert await _event_id("cleared") is None
    assert removed_google["deleted"] == []


@pytest.mark.asyncio
async def test_issue42_ac16_later_stage_event_id_replaced_meanwhile_fails_and_keeps_own_id(removed_google):
    """AC16：清後面階段的編號時，那個編號已被換成別的（另一個分頁剛排入）→ 不清它；這一項失敗，自己的編號也不清。"""
    await _staged("p", [("ev-1", "To Do"), ("ev-2", "To Do")])
    removed_google["gone"] = {"ev-1"}

    async def rescheduled_in_other_tab(event_ids):
        await db.manual_tasks.update_one({"_id": "p-2"}, {"$set": {"calendar_event_id": "ev-2-new"}})

    removed_google["on_delete"] = rescheduled_in_other_tab

    result = await _resolve(reschedule=["manual:p-1"])

    assert _failed_ids(result) == ["manual:p-1"]
    assert await _event_id("p-2") == "ev-2-new"
    assert await _event_id("p-1") == "ev-1"


@pytest.mark.asyncio
async def test_issue42_ac16_own_event_id_replaced_meanwhile_fails_and_is_not_cleared(removed_google):
    """AC16：確認事件不存在之後，這一項的編號被換成別的 → 不清除，這一項失敗。"""
    await _manual("t", "ev-t")
    removed_google["gone"] = {"ev-t"}

    async def rescheduled_in_other_tab(event_ids):
        await db.manual_tasks.update_one({"_id": "t"}, {"$set": {"calendar_event_id": "ev-t-new"}})

    removed_google["on_query"] = rescheduled_in_other_tab

    result = await _resolve(reschedule=["manual:t"])

    assert _failed_ids(result) == ["manual:t"]
    assert await _event_id("t") == "ev-t-new"


@pytest.mark.asyncio
async def test_issue42_ac16_external_event_id_replaced_meanwhile_fails_and_is_not_cleared(removed_google):
    """AC16：外部項目確認事件不存在之後，編號被換成別的（另一個分頁剛排入）→ 不清除，這一項失敗。"""
    await db.github_issues.insert_one({
        "id": 4204, "user_id": REMOVED_USER["sub"], "title": "外部項目", "status": "open", "calendar_event_id": "ev-gh",
    })
    removed_google["gone"] = {"ev-gh"}

    async def rescheduled_in_other_tab(event_ids):
        await db.github_issues.update_one(
            {"user_id": REMOVED_USER["sub"], "id": 4204}, {"$set": {"calendar_event_id": "ev-gh-new"}},
        )

    removed_google["on_query"] = rescheduled_in_other_tab

    result = await _resolve(reschedule=["github:4204"])

    assert _failed_ids(result) == ["github:4204"]
    github = await db.github_issues.find_one({"user_id": REMOVED_USER["sub"], "id": 4204})
    assert github is not None and github["calendar_event_id"] == "ev-gh-new"


@pytest.mark.asyncio
@pytest.mark.parametrize("error", [
    ExternalServiceError("Google 暫時無法處理請求", error_code="UPSTREAM_ERROR"),
    ReauthRequiredError("請重新連接"),
], ids=["google-5xx", "reauth"])
async def test_issue42_ac17_google_error_stops_and_keeps_items_already_done(removed_google, error):
    """AC17：處理到一半遇到 Google 錯誤或授權失效 → 丟出錯誤、停止；前面成功的維持結果，後面的編號不清、任務不刪。"""
    await _manual("first-delete", "ev-a")
    await _manual("second-delete", "ev-b")
    await _manual("reschedule", "ev-c")
    removed_google["gone"] = {"ev-a", "ev-b", "ev-c"}
    removed_google["query_errors"] = {"ev-b": error}

    with pytest.raises(AppError) as exc_info:
        await _resolve(reschedule=["manual:reschedule"], delete=["manual:first-delete", "manual:second-delete"])

    assert exc_info.value.error_code == error.error_code
    assert await _event_id("first-delete") == "<deleted>"
    assert await _event_id("second-delete") == "ev-b"
    assert await _event_id("reschedule") == "ev-c"


@pytest.mark.asyncio
async def test_issue42_ac18_deleting_external_item_is_rejected_and_other_items_continue(removed_google):
    """AC18：要求刪除外部項目 → 這一項失敗、外部項目不變；其他項目照常處理。"""
    await db.github_issues.insert_one({
        "id": 4203, "user_id": REMOVED_USER["sub"], "title": "外部項目", "status": "open", "calendar_event_id": "ev-gh",
    })
    await _manual("t", "ev-t")
    removed_google["gone"] = {"ev-gh", "ev-t"}

    result = await _resolve(delete=["github:4203", "manual:t"])

    assert _failed_ids(result) == ["github:4203"]
    github = await db.github_issues.find_one({"user_id": REMOVED_USER["sub"], "id": 4203})
    assert github is not None and github["calendar_event_id"] == "ev-gh"
    assert await _event_id("t") == "<deleted>"


@pytest.mark.asyncio
async def test_issue42_ac19_other_users_missing_and_malformed_ids_fail_without_revealing_existence(removed_google):
    """AC19：別人的、不存在的、格式錯的 id 都失敗，別人的和不存在的訊息相同；別人的任務不變，自己的照常處理。"""
    await _manual("others", "ev-others", user_id=OTHER_USER)
    await _manual("mine", "ev-mine")
    removed_google["gone"] = {"ev-others", "ev-mine"}

    result = await _resolve(
        reschedule=["manual:others", "manual:missing", "no-prefix", "manual:mine"],
        delete=["manual:others"],
    )

    reasons = {f["task_id"]: f["reason"] for f in result["failed"]}
    assert set(reasons) == {"manual:others", "manual:missing", "no-prefix"}
    assert reasons["manual:others"] == reasons["manual:missing"]
    assert result["succeeded"] == ["manual:mine"]
    assert await _event_id("others") == "ev-others"
    assert await _event_id("mine") is None


# ---------- 重新排程（POST /schedule/tasks/reschedule）----------

from schemas.schedule import RescheduleTasksInput

SCHEDULED_AT = datetime(2026, 11, 20, 9, 0, tzinfo=timezone.utc)


async def _scheduled(task_id, event_id, **extra):
    await _manual(task_id, event_id, scheduled_start=SCHEDULED_AT, scheduled_end=SCHEDULED_AT, **extra)


async def _reschedule(*task_ids):
    return await schedule_router.reschedule_tasks(RescheduleTasksInput(task_ids=list(task_ids)), clerk_user=REMOVED_USER)


@pytest.mark.asyncio
async def test_resolve_removed_events_reschedule_clears_scheduled_times(removed_google):
    """AC10：「處理已刪除的事件」把任務重新排程後，事件編號和開始、結束時間都是 None。"""
    await _scheduled("t", "ev-t")
    removed_google["gone"] = {"ev-t"}

    await _resolve(reschedule=["manual:t"])

    doc = await db.manual_tasks.find_one({"_id": "t"})
    assert doc["calendar_event_id"] is None and doc["scheduled_start"] is None and doc["scheduled_end"] is None


@pytest.mark.asyncio
async def test_reschedule_deletes_event_and_clears_event_id_and_times(removed_google):
    """AC38：已排程的任務 → 刪除 Google 事件，事件編號和開始、結束時間都清成 None。"""
    await _scheduled("t", "ev-t")

    result = await _reschedule("manual:t")

    assert result == {"succeeded": ["manual:t"], "failed": []}
    assert removed_google["deleted"] == ["ev-t"]
    doc = await db.manual_tasks.find_one({"_id": "t"})
    assert doc["calendar_event_id"] is None and doc["scheduled_start"] is None and doc["scheduled_end"] is None


@pytest.mark.asyncio
async def test_reschedule_external_item_clears_event_id_and_times(removed_google):
    """AC38：外部平台任務同樣刪除事件並清掉三個欄位。"""
    await db.github_issues.insert_one({
        "id": 4301, "user_id": REMOVED_USER["sub"], "title": "外部", "status": "open",
        "calendar_event_id": "ev-gh", "scheduled_start": SCHEDULED_AT, "scheduled_end": SCHEDULED_AT,
    })

    result = await _reschedule("github:4301")

    assert result["failed"] == []
    assert removed_google["deleted"] == ["ev-gh"]
    doc = await db.github_issues.find_one({"user_id": REMOVED_USER["sub"], "id": 4301})
    assert doc["calendar_event_id"] is None and doc["scheduled_start"] is None


@pytest.mark.asyncio
async def test_reschedule_stage_removes_later_scheduled_stages_and_leaves_unrelated_tasks(removed_google):
    """AC36a、AC36c、AC39：重新排程階段 1 → 後面已排程、沒完成的階段事件也刪、編號也清；不相關的任務不變。"""
    await _staged("p", [("ev-1", "To Do"), ("ev-2", "To Do"), ("ev-3", "To Do")])
    await _scheduled("other", "ev-other")

    result = await _reschedule("manual:p-1")

    assert result["failed"] == []
    assert sorted(removed_google["deleted"]) == ["ev-1", "ev-2", "ev-3"]
    assert [await _event_id(t) for t in ("p-1", "p-2", "p-3")] == [None, None, None]
    assert await _event_id("other") == "ev-other"


@pytest.mark.asyncio
async def test_reschedule_stage_leaves_earlier_and_done_stages(removed_google):
    """AC40：重新排程階段 2 → 前面的階段、已完成的後面階段不變。"""
    await _staged("p", [("ev-1", "To Do"), ("ev-2", "To Do"), ("ev-3", "Done")])

    result = await _reschedule("manual:p-2")

    assert result["failed"] == []
    assert [await _event_id(t) for t in ("p-1", "p-2", "p-3")] == ["ev-1", None, "ev-3"]
    assert removed_google["deleted"] == ["ev-2"]


@pytest.mark.asyncio
async def test_reschedule_stage_in_same_request_is_not_removed_twice(removed_google):
    """AC39：後面的階段也在這次請求裡 → 由它自己處理，不重複刪除。"""
    await _staged("p", [("ev-1", "To Do"), ("ev-2", "To Do")])

    result = await _reschedule("manual:p-1", "manual:p-2")

    assert result["failed"] == []
    assert sorted(removed_google["deleted"]) == ["ev-1", "ev-2"]


@pytest.mark.asyncio
async def test_reschedule_event_already_gone_on_google_still_clears_event_id():
    """AC41：Google 刪除回 404 → 當作成功，編號照樣清掉（走真正的 delete_calendar_events）。"""
    import httpx
    import services.google_calendar as calendar_service
    await _scheduled("t", "ev-t")
    request = httpx.Request("DELETE", "https://example.com")

    async def mock_connected(user_id):
        return True

    async def mock_token(user_id):
        return "token", "primary"

    async def mock_delete(access_token, calendar_id, event_id):
        raise httpx.HTTPStatusError("gone", request=request, response=httpx.Response(404, request=request))

    patches = pytest.MonkeyPatch()
    try:
        patches.setattr(calendar_service, "is_google_calendar_connected", mock_connected)
        patches.setattr(calendar_service, "_get_access_token_and_primary_calendar_id", mock_token)
        patches.setattr(calendar_service, "delete_calendar_event", mock_delete)

        result = await _reschedule("manual:t")
        assert await _event_id("t") is None
    finally:
        patches.undo()
        await db.manual_tasks.delete_many({"user_id": REMOVED_USER["sub"]})

    assert result == {"succeeded": ["manual:t"], "failed": []}


@pytest.mark.asyncio
async def test_reschedule_event_id_replaced_meanwhile_fails_and_keeps_new_value(removed_google):
    """AC42：處理期間編號被換成別的值 → 這一項失敗，新的值不被清掉。"""
    await _scheduled("t", "ev-t")

    async def rescheduled_in_other_tab(event_ids):
        await db.manual_tasks.update_one({"_id": "t"}, {"$set": {"calendar_event_id": "ev-t-new"}})

    removed_google["on_delete"] = rescheduled_in_other_tab

    result = await _reschedule("manual:t")

    assert _failed_ids(result) == ["manual:t"]
    assert await _event_id("t") == "ev-t-new"


@pytest.mark.asyncio
async def test_reschedule_other_users_and_missing_ids_fail_with_same_reason_and_others_continue(removed_google):
    """AC43：別人的、不存在的任務 id → 這一項失敗、原因相同；別人的任務不變，自己的照常處理。"""
    await _scheduled("others", "ev-others", user_id=OTHER_USER)
    await _scheduled("mine", "ev-mine")

    result = await _reschedule("manual:others", "manual:missing", "manual:mine")

    reasons = {f["task_id"]: f["reason"] for f in result["failed"]}
    assert set(reasons) == {"manual:others", "manual:missing"}
    assert reasons["manual:others"] == reasons["manual:missing"]
    assert result["succeeded"] == ["manual:mine"]
    assert await _event_id("others") == "ev-others"
    assert removed_google["deleted"] == ["ev-mine"]


@pytest.mark.asyncio
async def test_reschedule_parent_and_done_tasks_fail_and_change_nothing(removed_google):
    """AC44：主任務、已完成的任務 → 列為失敗，不呼叫 Google，資料不變。"""
    await _staged("p", [("ev-1", "To Do")])
    await _scheduled("done", "ev-done", status="Done")

    result = await _reschedule("manual:p", "manual:done")

    assert _failed_ids(result) == ["manual:p", "manual:done"]
    assert removed_google["deleted"] == []
    assert await _event_id("done") == "ev-done"
    assert await _event_id("p-1") == "ev-1"


@pytest.mark.asyncio
@pytest.mark.parametrize("error", [
    ExternalServiceError("Google 暫時無法處理請求", error_code="UPSTREAM_ERROR"),
    ReauthRequiredError("請重新連接"),
], ids=["google-5xx", "reauth"])
async def test_reschedule_google_error_stops_request_and_keeps_later_tasks(removed_google, error):
    """AC45、AC46：呼叫 Google 失敗（包括授權失效）→ 丟出錯誤；前面成功的不復原，後面還沒處理的編號與事件不變。"""
    await _scheduled("a", "ev-a")
    await _scheduled("b", "ev-b")
    await _scheduled("c", "ev-c")

    async def fail_on_b(event_ids):
        if "ev-b" in event_ids:
            raise error

    removed_google["on_delete"] = fail_on_b

    with pytest.raises(AppError) as exc_info:
        await _reschedule("manual:a", "manual:b", "manual:c")

    assert exc_info.value.error_code == error.error_code
    assert [await _event_id(t) for t in ("a", "b", "c")] == [None, "ev-b", "ev-c"]
    assert removed_google["deleted"] == ["ev-a"]


@pytest.mark.asyncio
async def test_reschedule_task_without_event_id_succeeds_without_calling_google(removed_google):
    """AC47：沒有事件編號的任務 → 不呼叫 Google，算成功。"""
    await _manual("t", None)

    result = await _reschedule("manual:t")

    assert result == {"succeeded": ["manual:t"], "failed": []}
    assert removed_google["deleted"] == []


@pytest.mark.asyncio
async def test_reschedule_duplicate_ids_are_processed_once(removed_google):
    """AC49：同一個任務在一個請求裡出現兩次 → 只刪一次事件，結果列一次成功。"""
    await _scheduled("t", "ev-t")

    result = await _reschedule("manual:t", "manual:t")

    assert result == {"succeeded": ["manual:t"], "failed": []}
    assert removed_google["deleted"] == ["ev-t"]
