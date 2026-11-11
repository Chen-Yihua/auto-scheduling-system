# 透過 HTTP 確認路由、登入驗證、回應格式和錯誤狀態碼；細部邏輯由 unit 測試負責
import pytest
from fastapi import HTTPException, status
from httpx import AsyncClient
from httpx._transports.asgi import ASGITransport

from main import app
from core.errors import InvalidRequestError
import routers.schedule as schedule_router


@pytest.mark.asyncio
async def test_get_schedule_suggestion(monkeypatch, logged_in_user):
    """POST /schedule/suggest 不帶 preferences → 200，回傳 scheduled 和 unscheduled。"""
    async def mock_get_tasks(user_id):
        return [{"id": "t1", "title": "任務一", "priority": "High", "status": "To Do", "due_date": None}]

    async def mock_get_free_slots(user_id):
        return [{"start": "2026-09-10T09:00:00Z", "end": "2026-09-10T10:00:00Z"}]

    monkeypatch.setattr(schedule_router, "get_all_schedulable_items", mock_get_tasks)
    monkeypatch.setattr(schedule_router, "get_free_slots_for_user", mock_get_free_slots)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post("/schedule/suggest", json={})

    assert res.status_code == status.HTTP_200_OK
    body = res.json()
    assert body["scheduled"][0]["task_id"] == "t1"
    assert body["scheduled"][0]["start"].startswith("2026-09-10T09:00:00")  # datetime 被轉成字串送出
    assert body["unscheduled"] == []


@pytest.mark.asyncio
async def test_get_schedule_suggestion_with_preferences(monkeypatch, logged_in_user):
    """帶 preferences → 先扣掉不工作時段，放不下的任務列入 unscheduled。"""
    async def mock_get_tasks(user_id):
        return [{"id": "t1", "title": "任務一", "priority": "High", "status": "To Do", "due_date": None, "duration": 60}]

    async def mock_get_free_slots(user_id):
        # 整段空檔剛好都被「每天 09:00-10:00」的固定規律擋住，應該排不進去
        return [{"start": "2026-09-10T09:00:00Z", "end": "2026-09-10T10:00:00Z"}]

    monkeypatch.setattr(schedule_router, "get_all_schedulable_items", mock_get_tasks)
    monkeypatch.setattr(schedule_router, "get_free_slots_for_user", mock_get_free_slots)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post(
            "/schedule/suggest",
            json={"blocked_recurring": [{"days_of_week": [0, 1, 2, 3, 4, 5, 6], "all_day": True}]},
        )

    assert res.status_code == status.HTTP_200_OK
    body = res.json()
    assert body["scheduled"] == []
    assert body["unscheduled"][0]["task_id"] == "t1"


@pytest.mark.asyncio
async def test_get_schedule_suggestion_with_preferences_keeps_scheduled_time_in_utc(monkeypatch, logged_in_user):
    """套用不工作時段後，回傳的 start/end 仍要帶 UTC 時區，否則前端會當成本地時間。"""
    async def mock_get_tasks(user_id):
        return [{"id": "t1", "title": "任務一", "priority": "High", "status": "To Do", "due_date": None, "duration": 60}]

    async def mock_get_free_slots(user_id):
        return [{"start": "2026-09-10T09:00:00Z", "end": "2026-09-10T17:00:00Z"}]

    monkeypatch.setattr(schedule_router, "get_all_schedulable_items", mock_get_tasks)
    monkeypatch.setattr(schedule_router, "get_free_slots_for_user", mock_get_free_slots)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post(
            "/schedule/suggest",
            json={"blocked_recurring": [{"days_of_week": [3], "all_day": False, "start_time": "12:00", "end_time": "13:00"}]},
        )

    assert res.status_code == status.HTTP_200_OK
    body = res.json()
    assert len(body["scheduled"]) == 1
    start = body["scheduled"][0]["start"]
    assert start.endswith("Z") or "+00:00" in start, f"回傳的時間沒有時區標記，會被前端誤判成本地時間: {start}"


@pytest.mark.asyncio
async def test_get_schedule_suggestion_when_calendar_not_connected(monkeypatch, logged_in_user):
    """使用者還沒連接 Google Calendar → 409 NOT_LINKED，HTTP 回應要帶著中文說明，前端才能顯示。"""
    async def mock_get_tasks(user_id):
        return []

    async def mock_get_free_slots(user_id):
        raise InvalidRequestError("尚未連接 Google Calendar", error_code="NOT_LINKED")

    monkeypatch.setattr(schedule_router, "get_all_schedulable_items", mock_get_tasks)
    monkeypatch.setattr(schedule_router, "get_free_slots_for_user", mock_get_free_slots)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post("/schedule/suggest", json={})

    assert res.status_code == status.HTTP_409_CONFLICT
    assert res.json() == {"detail": "尚未連接 Google Calendar", "error_code": "NOT_LINKED"}


@pytest.mark.asyncio
async def test_get_schedule_suggestion_requires_login():
    """沒帶登入 token → 被擋在門外（401/403），不能進到函式裡。"""
    # 這個測試刻意不用 logged_in_user，所以請求是沒登入的
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post("/schedule/suggest", json={})

    assert res.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)


@pytest.mark.asyncio
async def test_suggest_then_confirm_writes_exactly_what_the_user_saw(monkeypatch, logged_in_user):
    """
    產生建議後確認 → 寫入的就是看到的那幾筆和時間；
    同一份建議再確認一次 → 409，不會重複建立事件。
    """
    async def mock_get_tasks(user_id):
        return [{"id": "manual:t1", "title": "任務一", "priority": "High", "status": "To Do",
                 "due_date": None, "calendar_event_id": None}]

    async def mock_get_free_slots(user_id, use_cache=True):
        return [{"start": "2030-01-01T09:00:00Z", "end": "2030-01-01T10:00:00Z"}]

    written = []

    async def mock_create_events(user_id, scheduled):
        written.extend(scheduled)
        return {"confirmed": [{"task_id": "manual:t1", "title": "任務一", "calendar_event_id": "event-1"}], "failed": []}

    monkeypatch.setattr(schedule_router, "get_all_schedulable_items", mock_get_tasks)
    monkeypatch.setattr(schedule_router, "get_free_slots_for_user", mock_get_free_slots)
    monkeypatch.setattr(schedule_router, "create_calendar_events_for_scheduled_tasks", mock_create_events)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        suggest_res = await ac.post("/schedule/suggest", json={})
        confirm_res = await ac.post("/schedule/confirm")
        confirm_again_res = await ac.post("/schedule/confirm")

    assert suggest_res.status_code == status.HTTP_200_OK
    shown = suggest_res.json()["scheduled"]

    assert confirm_res.status_code == status.HTTP_200_OK
    assert confirm_res.json() == {"confirmed": [{"task_id": "manual:t1", "title": "任務一", "calendar_event_id": "event-1"}], "failed": []}
    assert [(w["task_id"], w["start"].isoformat().replace("+00:00", "Z")) for w in written] == \
        [(s["task_id"], s["start"]) for s in shown]

    assert confirm_again_res.status_code == status.HTTP_409_CONFLICT


@pytest.mark.asyncio
async def test_confirm_schedule_requires_login():
    """沒帶登入 token → 被擋在門外（401/403）。"""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post("/schedule/confirm", json={})

    assert res.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)


@pytest.mark.asyncio
async def test_list_schedulable_tasks_success(monkeypatch, logged_in_user):
    """GET /schedule/tasks：回傳手動任務 + 外部平台項目的統一清單。"""
    async def mock_get_items(user_id):
        return [{
            "id": "github:42", "source": "github", "title": "GitHub Issue", "status": "To Do",
            "priority": None, "duration": None, "due_date": None, "sort_order": None,
            "calendar_event_id": None, "url": "https://github.com/x/y/issues/42",
        }]

    monkeypatch.setattr(schedule_router, "get_all_schedulable_items", mock_get_items)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/schedule/tasks")

    assert res.status_code == status.HTTP_200_OK
    body = res.json()
    assert body[0]["id"] == "github:42"
    assert body[0]["source"] == "github"
    assert body[0]["url"] == "https://github.com/x/y/issues/42"


@pytest.mark.asyncio
async def test_list_schedulable_tasks_requires_login():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/schedule/tasks")

    assert res.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)


@pytest.mark.asyncio
async def test_reorder_schedule_tasks_success(monkeypatch, logged_in_user):
    """PUT /schedule/reorder：接受混著手動任務／外部平台項目的組合 id 清單。"""
    async def mock_reorder(user_id, items):
        pass

    async def mock_get_items(user_id):
        return [{
            "id": "manual:t1", "source": "manual", "title": "任務", "status": "To Do",
            "priority": "High", "duration": None, "due_date": None, "sort_order": 0,
            "calendar_event_id": None, "url": None,
        }]

    monkeypatch.setattr(schedule_router, "reorder_schedulable_items", mock_reorder)
    monkeypatch.setattr(schedule_router, "get_all_schedulable_items", mock_get_items)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.put(
            "/schedule/reorder",
            json={"items": [{"task_id": "manual:t1", "priority": "High"}]},
        )

    assert res.status_code == status.HTTP_200_OK
    assert res.json()[0]["id"] == "manual:t1"


@pytest.mark.asyncio
async def test_update_schedule_task_fields_success(monkeypatch, logged_in_user):
    """PATCH /schedule/tasks/fields：含斜線和問號的 Moodle id 放在 body 也能正確處理。"""
    captured = {}

    async def mock_update(user_id, task_id, data):
        captured["task_id"] = task_id
        captured["data"] = data

    monkeypatch.setattr(schedule_router, "update_scheduling_fields", mock_update)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.patch(
            "/schedule/tasks/fields",
            json={"task_id": "moodle:https://moodle.nccu.edu.tw/mod/assign/view.php?id=1", "duration": 60},
        )

    assert res.status_code == status.HTTP_200_OK
    assert captured["task_id"] == "moodle:https://moodle.nccu.edu.tw/mod/assign/view.php?id=1"
    assert captured["data"] == {"duration": 60}


@pytest.mark.asyncio
async def test_update_schedule_task_done_success(monkeypatch, logged_in_user):
    """PATCH /schedule/tasks/done：使用者手動標記完成／取消完成。"""
    captured = {}

    async def mock_set_done(user_id, task_id, done):
        captured["task_id"] = task_id
        captured["done"] = done

    monkeypatch.setattr(schedule_router, "set_done", mock_set_done)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.patch("/schedule/tasks/done", json={"task_id": "github:42", "done": True})

    assert res.status_code == status.HTTP_200_OK
    assert captured == {"task_id": "github:42", "done": True}
    assert res.json() == {"task_id": "github:42", "done": True}


# ---------- 外部 id 不存在、格式錯誤（AC8）----------
# 走真的 crud 與測試用的 mongomock，才看得出資料庫有沒有被改

from datetime import datetime, timezone

import httpx

from core import cache
from core.database import db

USER = "test_user_123"


async def _cleanup_schedule_data():
    for collection in (db.manual_tasks, db.github_issues, db.jira_issues, db.moodle_assignments):
        await collection.delete_many({"user_id": {"$in": [USER, "someone-else"]}})


async def _seed_reorder_data():
    await _cleanup_schedule_data()
    await db.manual_tasks.insert_many([
        {"_id": "t1", "user_id": USER, "title": "手動", "status": "To Do", "priority": "Low", "sort_order": 5},
        {"_id": "p1", "user_id": USER, "title": "主任務", "is_parent": True, "subtask_ids": ["s1", "s2"]},
        {"_id": "s1", "user_id": USER, "title": "階段一", "parent_id": "p1", "status": "To Do", "priority": "Medium", "sort_order": 6},
        {"_id": "s2", "user_id": USER, "title": "階段二", "parent_id": "p1", "status": "To Do", "priority": "Low", "sort_order": 7},
        {"_id": "other", "user_id": "someone-else", "title": "別人的", "status": "To Do", "priority": "Low", "sort_order": 8},
    ])
    await db.github_issues.insert_one({"id": 1, "user_id": USER, "title": "G", "status": "open", "priority": "Low", "sort_order": 9})
    await db.jira_issues.insert_one({"id": "100", "user_id": USER, "title": "J", "status": "To Do", "priority": "Low", "sort_order": 10})
    await db.github_issues.insert_one({"id": 2, "user_id": "someone-else", "title": "別人的 G", "status": "open", "sort_order": 11})


async def _snapshot_order():
    snapshot = {}
    for collection in (db.manual_tasks, db.github_issues, db.jira_issues):
        async for doc in collection.find({}):
            snapshot[(collection.name, str(doc.get("_id") if collection is db.manual_tasks else doc["id"]))] = (
                doc.get("sort_order"), doc.get("priority"), doc.get("updated"),
            )
    return snapshot


@pytest.mark.parametrize("bad_item", [
    {"task_id": "github:999", "priority": "High"},
    {"task_id": "github:2", "priority": "High"},
    {"task_id": "manual:missing", "priority": "High"},
    {"task_id": "manual:other", "priority": "High"},
    {"task_id": "github:not-a-number", "priority": "High"},
    {"task_id": "foo:1", "priority": "High"},
    {"task_id": "no-colon", "priority": "High"},
    {"task_id": "manual:p1", "priority": "High"},
    {"task_id": "manual:s2", "priority": "High"},
], ids=[
    "external-missing", "external-other-user", "manual-missing", "manual-other-user", "external-bad-format",
    "unknown-prefix", "no-colon", "parent-task", "stage-priority-rule",
])
@pytest.mark.asyncio
async def test_reorder_rejects_whole_batch_without_writing_anything(logged_in_user, bad_item):
    """AC8：reorder 任何一項會回 400 時，整批 400 INVALID_REQUEST，資料庫的順序完全沒變（合法的項目也不寫）。"""
    await _seed_reorder_data()
    try:
        before = await _snapshot_order()
        items = [
            {"task_id": "github:1", "priority": "High"},
            {"task_id": "jira:100", "priority": "High"},
            {"task_id": "manual:t1", "priority": "High"},
            bad_item,
        ]

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            res = await ac.put("/schedule/reorder", json={"items": items})

        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert res.json()["error_code"] == "INVALID_REQUEST"
        assert await _snapshot_order() == before
    finally:
        await _cleanup_schedule_data()


@pytest.mark.parametrize("missing_id", ["github:999", "github:2", "manual:missing", "manual:other"])
@pytest.mark.asyncio
async def test_reorder_unknown_id_uses_same_message_as_manual_task(logged_in_user, missing_id):
    """AC8、AC10：外部與手動的 id 不存在或屬於別人，都是同一個訊息，列出送出的組合 id，不透露資料是否存在。"""
    await _seed_reorder_data()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            res = await ac.put("/schedule/reorder", json={"items": [{"task_id": missing_id, "priority": "High"}]})

        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert res.json() == {"detail": f"包含不屬於你的任務 id: ['{missing_id}']", "error_code": "INVALID_REQUEST"}
    finally:
        await _cleanup_schedule_data()


@pytest.mark.asyncio
async def test_reorder_valid_batch_still_writes_all_sources(logged_in_user):
    """AC8：全部合法時照常寫入各來源，sort_order 是整份清單的索引。"""
    await _seed_reorder_data()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            res = await ac.put("/schedule/reorder", json={"items": [
                {"task_id": "jira:100", "priority": "High"},
                {"task_id": "manual:t1", "priority": "Medium"},
                {"task_id": "github:1", "priority": "Low"},
            ]})

        assert res.status_code == status.HTTP_200_OK
        assert (await db.jira_issues.find_one({"id": "100"}))["sort_order"] == 0
        manual = await db.manual_tasks.find_one({"_id": "t1"})
        assert (manual["sort_order"], manual["priority"]) == (1, "Medium")
        assert (await db.github_issues.find_one({"id": 1}))["sort_order"] == 2
    finally:
        await _cleanup_schedule_data()


@pytest.mark.parametrize("path, body", [
    ("/schedule/tasks/fields", {"duration": 30}),
    ("/schedule/tasks/done", {"done": True}),
])
@pytest.mark.parametrize("task_id", ["github:999", "github:2", "jira:missing"])
@pytest.mark.asyncio
async def test_fields_and_done_with_missing_external_id_is_404(logged_in_user, path, body, task_id):
    """AC8、AC10：fields、done 的外部 id 不存在或屬於別人 → 404 NOT_FOUND，訊息和手動任務不存在時相同，別人的資料也沒被改。"""
    await _seed_reorder_data()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            res = await ac.patch(path, json={"task_id": task_id, **body})
            manual_res = await ac.patch(path, json={"task_id": "manual:missing", **body})

        assert res.status_code == status.HTTP_404_NOT_FOUND
        assert res.json() == {"detail": "Task not found", "error_code": "NOT_FOUND"}
        assert res.json() == manual_res.json()
        other = await db.github_issues.find_one({"id": 2})
        assert "duration" not in other and "done" not in other
    finally:
        await _cleanup_schedule_data()


@pytest.mark.parametrize("method, path, body", [
    ("PATCH", "/schedule/tasks/fields", {"task_id": "foo:1", "duration": 30}),
    ("PATCH", "/schedule/tasks/done", {"task_id": "foo:1", "done": True}),
    ("PATCH", "/schedule/tasks/done", {"task_id": "no-colon", "done": True}),
    ("PUT", "/schedule/reorder", {"items": [{"task_id": "foo:1", "priority": "High"}]}),
])
@pytest.mark.asyncio
async def test_unknown_source_prefix_is_400_on_all_three_endpoints(logged_in_user, method, path, body):
    """AC8：來源前綴不認得（或沒有冒號）是組合 id 格式錯誤 → 三個 endpoint 都 400 INVALID_REQUEST。"""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.request(method, path, json=body)

    assert res.status_code == status.HTTP_400_BAD_REQUEST
    assert res.json()["error_code"] == "INVALID_REQUEST"


@pytest.mark.asyncio
async def test_fields_and_done_existing_external_item_still_updates(logged_in_user):
    """AC8：外部項目存在時 fields、done 照常寫入。"""
    await _seed_reorder_data()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            fields_res = await ac.patch("/schedule/tasks/fields", json={"task_id": "github:1", "duration": 30})
            done_res = await ac.patch("/schedule/tasks/done", json={"task_id": "jira:100", "done": True})

        assert fields_res.status_code == status.HTTP_200_OK
        assert done_res.status_code == status.HTTP_200_OK
        assert (await db.github_issues.find_one({"id": 1}))["duration"] == 30
        assert (await db.jira_issues.find_one({"id": "100"}))["done"] is True
    finally:
        await _cleanup_schedule_data()


# ---------- 確認排程（AC7、AC8）----------

GOOGLE_EVENTS_URL = "https://www.googleapis.com/calendar/v3/calendars/primary-cal/events"


def _google_error_response(status_code: int, reason: str | None = None) -> httpx.Response:
    body = {"error": {"code": status_code, "errors": [{"reason": reason}] if reason else []}}
    return httpx.Response(status_code, json=body, request=httpx.Request("POST", GOOGLE_EVENTS_URL))


async def _confirm_with_google_write_result(monkeypatch, write_result, tasks=None, scheduled=None):
    """建議快照裡有 manual:t1；寫入 Google 時照 write_result（回傳值或要丟的例外）。"""
    import services.google_calendar as google_calendar_service

    cache._memory_store.clear()
    tasks = tasks or [{"id": "manual:t1", "title": "任務一", "priority": "High", "status": "To Do",
                       "due_date": None, "calendar_event_id": None}]
    scheduled = scheduled or [{"task_id": "manual:t1", "title": "任務一", "priority": "High",
                               "start": "2030-01-01T09:00:00+00:00", "end": "2030-01-01T10:00:00+00:00"}]
    await cache.cache_set(schedule_router._suggestion_snapshot_key(USER), scheduled, 600)

    async def mock_get_tasks(user_id):
        return tasks

    async def mock_get_free_slots(user_id, use_cache=True):
        return [{"start": "2030-01-01T00:00:00Z", "end": "2030-01-02T00:00:00Z"}]

    async def mock_token_and_calendar(clerk_id):
        return "access-token", "primary-cal"

    async def mock_create_event(*args, **kwargs):
        if isinstance(write_result, BaseException):
            raise write_result
        return write_result

    monkeypatch.setattr(schedule_router, "get_all_schedulable_items", mock_get_tasks)
    monkeypatch.setattr(schedule_router, "get_free_slots_for_user", mock_get_free_slots)
    monkeypatch.setattr(google_calendar_service, "_get_access_token_and_primary_calendar_id", mock_token_and_calendar)
    monkeypatch.setattr(google_calendar_service, "create_calendar_event", mock_create_event)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        return await ac.post("/schedule/confirm")


def _status_error(status_code: int, reason: str | None = None) -> httpx.HTTPStatusError:
    response = _google_error_response(status_code, reason)
    return httpx.HTTPStatusError("error", request=response.request, response=response)


@pytest.mark.parametrize("error, error_code, reason", [
    (_status_error(401), "REAUTH_REQUIRED", "Google 授權已失效，請重新連接 Google Calendar"),
    (_status_error(403, "insufficientPermissions"), "REAUTH_REQUIRED", "Google 授權的權限不足，請重新連接 Google Calendar"),
    (_status_error(400), "INTERNAL_ERROR", "伺服器處理 Google 請求時發生錯誤，請稍後再試"),
    (_status_error(429), "UPSTREAM_RATE_LIMITED", "Google 請求太頻繁，請稍後再試"),
    (_status_error(403, "rateLimitExceeded"), "UPSTREAM_RATE_LIMITED", "Google 請求太頻繁，請稍後再試"),
    (_status_error(503), "UPSTREAM_ERROR", "Google 暫時無法處理請求，請稍後再試"),
    (httpx.ReadTimeout("timeout"), "UPSTREAM_TIMEOUT", "Google 回應逾時，請稍後再試"),
    (httpx.ConnectError("refused"), "UPSTREAM_ERROR", "無法連線至 Google，請稍後再試"),
], ids=["401", "403-permission", "400", "429", "403-rate-limit", "503", "timeout", "unreachable"])
@pytest.mark.asyncio
async def test_confirm_google_write_failure_carries_error_code_and_matching_reason(
    monkeypatch, logged_in_user, error, error_code, reason,
):
    """AC7：寫入 Google 失敗的 failed 項目帶依原因的 error_code，reason 是和原因一致的固定文字。"""
    res = await _confirm_with_google_write_result(monkeypatch, error)

    assert res.status_code == status.HTTP_200_OK
    assert res.json()["failed"] == [{"task_id": "manual:t1", "title": "任務一", "reason": reason, "error_code": error_code}]


@pytest.mark.asyncio
async def test_confirm_precheck_failure_and_previous_stage_have_null_error_code(monkeypatch, logged_in_user):
    """AC7：寫入前檢查不通過、前一個階段寫入失敗的項目 error_code 是 null，reason 不變。"""
    tasks = [
        {"id": "manual:done", "title": "已完成", "priority": "High", "status": "Done", "calendar_event_id": None},
        {"id": "manual:s1", "title": "階段一", "priority": "High", "status": "To Do", "calendar_event_id": None, "parent_id": "manual:p1"},
        {"id": "manual:s2", "title": "階段二", "priority": "High", "status": "To Do", "calendar_event_id": None, "parent_id": "manual:p1"},
    ]
    scheduled = [
        {"task_id": "manual:done", "title": "已完成", "priority": "High",
         "start": "2030-01-01T08:00:00+00:00", "end": "2030-01-01T09:00:00+00:00"},
        {"task_id": "manual:s1", "title": "階段一", "priority": "High", "parent_id": "manual:p1",
         "start": "2030-01-01T09:00:00+00:00", "end": "2030-01-01T10:00:00+00:00"},
        {"task_id": "manual:s2", "title": "階段二", "priority": "High", "parent_id": "manual:p1",
         "start": "2030-01-01T10:00:00+00:00", "end": "2030-01-01T11:00:00+00:00"},
    ]

    res = await _confirm_with_google_write_result(monkeypatch, _status_error(503), tasks=tasks, scheduled=scheduled)

    failed = {f["task_id"]: f for f in res.json()["failed"]}
    assert failed["manual:done"] == {"task_id": "manual:done", "title": "已完成", "reason": "任務已經完成", "error_code": None}
    assert failed["manual:s1"]["error_code"] == "UPSTREAM_ERROR"
    assert failed["manual:s2"] == {"task_id": "manual:s2", "title": "階段二", "reason": "前一個階段寫入失敗", "error_code": None}


@pytest.mark.asyncio
async def test_confirm_succeeds_when_external_item_was_deleted_meanwhile(monkeypatch, logged_in_user):
    """AC8：確認排程期間外部項目被刪除，寫回事件 id 時找不到也不丟錯，確認仍成功。"""
    await _cleanup_schedule_data()
    tasks = [{"id": "github:777", "title": "已刪除的 issue", "priority": "High", "status": "To Do", "calendar_event_id": None}]
    scheduled = [{"task_id": "github:777", "title": "已刪除的 issue", "priority": "High",
                  "start": "2030-01-01T09:00:00+00:00", "end": "2030-01-01T10:00:00+00:00"}]

    res = await _confirm_with_google_write_result(monkeypatch, {"id": "event-1"}, tasks=tasks, scheduled=scheduled)

    assert res.status_code == status.HTTP_200_OK
    assert res.json() == {
        "confirmed": [{"task_id": "github:777", "title": "已刪除的 issue", "calendar_event_id": "event-1"}],
        "failed": [],
    }
