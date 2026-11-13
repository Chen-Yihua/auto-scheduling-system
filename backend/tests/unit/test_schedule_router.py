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

    async def mock_set_event_id(user_id, task_id, event_id):
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
