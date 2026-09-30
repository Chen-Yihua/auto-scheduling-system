# 透過 HTTP 測試 /schedule 這組 API：路由有註冊、登入驗證有掛上、
# 回傳的 JSON 格式（response_model）跟錯誤狀態碼真的送得出去。
# 排程規則本身（誰先排、塞哪個空檔）由 test_schedule_crud.py 負責，這裡不重複測。
import pytest
from fastapi import HTTPException, status
from httpx import AsyncClient
from httpx._transports.asgi import ASGITransport

from main import app
import routers.schedule as schedule_router


@pytest.mark.asyncio
async def test_get_schedule_suggestion(monkeypatch, logged_in_user):
    """POST /schedule/suggest 成功（不帶 preferences）：200，回傳 scheduled / unscheduled 兩份清單，datetime 被轉成字串。"""
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
    """POST /schedule/suggest 帶 preferences：不工作時段會先把空檔挖掉，塞不進去的任務要出現在 unscheduled。"""
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
    """曾經是真的會炸的 bug：套用不工作時段後，回傳的 scheduled start/end 弄丟了 UTC
    時區標記，前端 new Date(...) 會當成瀏覽器本地時間解讀，讓排程建議看起來排到
    已經過去的時間。這裡只擋掉空檔的一小段（12:00-13:00），任務仍然排得進去，
    確認回傳的時間字串真的是帶時區資訊的（不是被誤判成本地時間的裸字串）。"""
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
async def test_confirm_schedule_success(monkeypatch, logged_in_user):
    """POST /schedule/confirm 成功：200，回傳 confirmed／failed 兩份清單。"""
    async def mock_get_tasks(user_id):
        return [{"id": "t1", "title": "任務一", "priority": "High", "status": "To Do", "due_date": None}]

    async def mock_get_free_slots(user_id):
        return [{"start": "2026-09-10T09:00:00Z", "end": "2026-09-10T10:00:00Z"}]

    async def mock_create_events(user_id, scheduled):
        return {"confirmed": [{"task_id": "t1", "title": "任務一", "calendar_event_id": "event-1"}], "failed": []}

    monkeypatch.setattr(schedule_router, "get_all_schedulable_items", mock_get_tasks)
    monkeypatch.setattr(schedule_router, "get_free_slots_for_user", mock_get_free_slots)
    monkeypatch.setattr(schedule_router, "create_calendar_events_for_scheduled_tasks", mock_create_events)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post("/schedule/confirm", json={})

    assert res.status_code == status.HTTP_200_OK
    body = res.json()
    assert body["confirmed"] == [{"task_id": "t1", "title": "任務一", "calendar_event_id": "event-1"}]
    assert body["failed"] == []


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
    """PUT /schedule/tasks/fields：task_id 放 body，Moodle 那種帶斜線/問號的組合 id 也不會被 URL 解析搞壞。"""
    captured = {}

    async def mock_update(user_id, task_id, data):
        captured["task_id"] = task_id
        captured["data"] = data

    monkeypatch.setattr(schedule_router, "update_scheduling_fields", mock_update)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.put(
            "/schedule/tasks/fields",
            json={"task_id": "moodle:https://moodle.nccu.edu.tw/mod/assign/view.php?id=1", "duration": 60},
        )

    assert res.status_code == status.HTTP_200_OK
    assert captured["task_id"] == "moodle:https://moodle.nccu.edu.tw/mod/assign/view.php?id=1"
    assert captured["data"] == {"duration": 60}


@pytest.mark.asyncio
async def test_update_schedule_task_done_success(monkeypatch, logged_in_user):
    """PUT /schedule/tasks/done：使用者手動標記完成／取消完成。"""
    captured = {}

    async def mock_set_done(user_id, task_id, done):
        captured["task_id"] = task_id
        captured["done"] = done

    monkeypatch.setattr(schedule_router, "set_done", mock_set_done)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.put("/schedule/tasks/done", json={"task_id": "github:42", "done": True})

    assert res.status_code == status.HTTP_200_OK
    assert captured == {"task_id": "github:42", "done": True}
    assert res.json() == {"task_id": "github:42", "done": True}
