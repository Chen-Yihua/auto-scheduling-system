# 透過 HTTP 確認路由、登入驗證、回應格式和錯誤狀態碼；細部邏輯由 unit 測試負責
import pytest
from fastapi import HTTPException, status
from httpx import AsyncClient
from httpx._transports.asgi import ASGITransport

from main import app
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
    """使用者還沒連接 Google Calendar → 400，HTTP 回應要帶著中文說明，前端才能顯示。"""
    async def mock_get_tasks(user_id):
        return []

    async def mock_get_free_slots(user_id):
        raise HTTPException(status_code=400, detail="尚未連接 Google Calendar")

    monkeypatch.setattr(schedule_router, "get_all_schedulable_items", mock_get_tasks)
    monkeypatch.setattr(schedule_router, "get_free_slots_for_user", mock_get_free_slots)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post("/schedule/suggest", json={})

    assert res.status_code == status.HTTP_400_BAD_REQUEST
    assert res.json() == {"detail": "尚未連接 Google Calendar"}


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
