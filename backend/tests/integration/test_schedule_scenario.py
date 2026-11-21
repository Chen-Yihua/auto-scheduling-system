"""
情境測試：透過 HTTP 讀出可排程項目、再把排程精靈的修改送回，用 mongomock 確認截止日的時區與資料一致性。
clerk_id 用這個檔案獨有的值，避免和其他測試共用的資料庫互相影響。
"""
from datetime import datetime, timezone

import pytest
from fastapi import status
from httpx import AsyncClient
from httpx._transports.asgi import ASGITransport

from main import app
from core.database import db
from core.datetimes import to_utc_datetime
from core.security import get_current_clerk_user

SCENARIO_USER = {"sub": "scenario_user_schedule"}
MANUAL_DUE = datetime(2030, 1, 9, 16, 0, tzinfo=timezone.utc)
GITHUB_DUE = datetime(2030, 1, 10, 20, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def _override_auth():
    async def mock_get_user():
        return SCENARIO_USER
    app.dependency_overrides[get_current_clerk_user] = mock_get_user
    yield
    app.dependency_overrides.pop(get_current_clerk_user, None)


def _assert_utc_string(value, expected: datetime):
    """回應的時間字串要明確標示 UTC（Z 或 +00:00），而且和資料庫存的是同一個時間點。"""
    assert isinstance(value, str)
    assert value.endswith("Z") or value.endswith("+00:00"), value
    assert to_utc_datetime(value) == expected


async def _seed(ac: AsyncClient) -> str:
    create_res = await ac.post("/manual-tasks/", json={
        "title": "情境測試：排程截止日", "description": "", "status": "To Do",
        "priority": "Medium", "duration": 30, "due_date": "2030-01-09T16:00:00Z",
    })
    assert create_res.status_code == status.HTTP_201_CREATED, create_res.text
    await db.github_issues.insert_one({
        "id": 77, "user_id": SCENARIO_USER["sub"], "title": "GitHub issue", "status": "open",
        "scheduling_due_date": GITHUB_DUE,
    })
    return create_res.json()["id"]


async def _cleanup():
    await db.manual_tasks.delete_many({"user_id": SCENARIO_USER["sub"]})
    await db.github_issues.delete_many({"user_id": SCENARIO_USER["sub"]})


@pytest.mark.asyncio
async def test_schedulable_tasks_due_dates_read_from_db_are_utc():
    """AC4：GET /schedule/tasks（SchedulableTaskOut）的 due_date 從資料庫讀出後帶 UTC 時區，手動任務和外部平台項目都是，時間值和存的相同。"""
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            task_id = await _seed(ac)
            res = await ac.get("/schedule/tasks")
        assert res.status_code == status.HTTP_200_OK, res.text

        items = {item["id"]: item for item in res.json()}
        _assert_utc_string(items[f"manual:{task_id}"]["due_date"], MANUAL_DUE)
        _assert_utc_string(items["github:77"]["due_date"], GITHUB_DUE)
    finally:
        await _cleanup()


@pytest.mark.asyncio
async def test_schedule_wizard_sending_due_date_back_unchanged_keeps_due_date():
    """AC8：排程精靈把 GET /schedule/tasks 回應的 due_date 原樣 PATCH 回去 → 資料庫裡的截止日不變。"""
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            task_id = await _seed(ac)
            items = {item["id"]: item for item in (await ac.get("/schedule/tasks")).json()}

            for composite_id, expected in ((f"manual:{task_id}", MANUAL_DUE), ("github:77", GITHUB_DUE)):
                due = items[composite_id]["due_date"]
                _assert_utc_string(due, expected)
                patch_res = await ac.patch("/schedule/tasks/fields", json={
                    "task_id": composite_id, "due_date": due, "duration": 45,
                })
                assert patch_res.status_code == status.HTTP_200_OK, patch_res.text

        manual = await db.manual_tasks.find_one({"_id": task_id})
        github = await db.github_issues.find_one({"user_id": SCENARIO_USER["sub"], "id": 77})
        assert manual is not None and github is not None
        assert to_utc_datetime(manual["due_date"]) == MANUAL_DUE
        assert to_utc_datetime(github["scheduling_due_date"]) == GITHUB_DUE
    finally:
        await _cleanup()


# ---------- issue-42：處理在 Google 日曆上被刪除的事件，再產生排程 ----------

import routers.schedule as schedule_router

FREE_DAY = [{"start": "2030-01-01T09:00:00Z", "end": "2030-01-01T18:00:00Z"}]


@pytest.fixture
def fake_google(monkeypatch):
    """假的 Google 日曆：gone 是已被刪除的事件 id；deleted 記錄被刪掉的事件。"""
    state = {"gone": set(), "deleted": []}

    async def find_removed(user_id, event_ids):
        return {event_id for event_id in event_ids if event_id in state["gone"]}

    async def delete_events(user_id, event_ids):
        state["deleted"].extend(event_ids)

    async def free_slots(user_id, use_cache=True):
        return FREE_DAY

    async def event_ends(user_id, event_ids):
        raise AssertionError("處理後不該還有在等前一個階段事件的子任務")

    monkeypatch.setattr(schedule_router, "find_removed_calendar_events", find_removed)
    monkeypatch.setattr(schedule_router, "delete_calendar_events", delete_events)
    monkeypatch.setattr(schedule_router, "get_free_slots_for_user", free_slots)
    monkeypatch.setattr(schedule_router, "get_calendar_event_ends", event_ends)
    return state


async def _create_staged(ac: AsyncClient, event_ids: list[str | None]) -> list[str]:
    """建立一個主任務與階段，依序寫入事件 id；回傳子任務 id（依階段順序）。"""
    res = await ac.post("/manual-tasks/", json={
        "title": "期末報告", "description": "",
        "subtasks": [
            {"title": f"階段{n}", "description": "", "status": "To Do", "priority": "High", "duration": 60}
            for n in range(1, len(event_ids) + 1)
        ],
    })
    assert res.status_code == status.HTTP_201_CREATED, res.text
    subtask_ids = [s["id"] for s in res.json()["subtasks"]]
    for subtask_id, event_id in zip(subtask_ids, event_ids):
        await db.manual_tasks.update_one({"_id": subtask_id}, {"$set": {"calendar_event_id": event_id}})
    return subtask_ids


@pytest.mark.asyncio
async def test_issue42_ac1_ac10_task_with_deleted_event_can_be_rescheduled(fake_google):
    """AC1、AC10：重現步驟——任務的事件在 Google 上被刪掉 → 列在 removed-events；勾選重新排程後沒有事件編號，出現在待排清單，產生排程時照常排入。"""
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            task_id = await _seed(ac)
            await db.manual_tasks.update_one({"_id": task_id}, {"$set": {"calendar_event_id": "ev-gone"}})
            fake_google["gone"] = {"ev-gone"}
            composite_id = f"manual:{task_id}"

            removed = (await ac.get("/schedule/removed-events")).json()
            assert [item["id"] for item in removed] == [composite_id]

            res = await ac.post("/schedule/removed-events/resolve", json={"reschedule": [composite_id], "delete": []})
            assert res.status_code == status.HTTP_200_OK, res.text
            assert res.json()["succeeded"] == [composite_id]

            items = {item["id"]: item for item in (await ac.get("/schedule/tasks")).json()}
            assert items[composite_id]["calendar_event_id"] is None

            suggestion = (await ac.post("/schedule/suggest", json={})).json()
            assert composite_id in [item["task_id"] for item in suggestion["scheduled"]]
    finally:
        await _cleanup()


@pytest.mark.asyncio
async def test_issue42_ac29_rescheduled_previous_stage_and_later_stage_are_scheduled_in_order(fake_google):
    """AC29：前一個階段的事件被刪除、勾選重新排程 → 後面已排入的階段一起回到待排；產生排程時依序排入，後面的在前一個之後。"""
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            first, second = await _create_staged(ac, ["ev-1", "ev-2"])
            fake_google["gone"] = {"ev-1"}

            res = await ac.post("/schedule/removed-events/resolve", json={"reschedule": [f"manual:{first}"], "delete": []})
            assert res.status_code == status.HTTP_200_OK, res.text
            assert fake_google["deleted"] == ["ev-2"]

            scheduled = {item["task_id"]: item for item in (await ac.post("/schedule/suggest", json={})).json()["scheduled"]}
            assert to_utc_datetime(scheduled[f"manual:{second}"]["start"]) >= to_utc_datetime(scheduled[f"manual:{first}"]["end"])
    finally:
        await _cleanup()


@pytest.mark.asyncio
async def test_issue42_ac30_deleted_previous_stage_renumbers_later_stages_and_schedule_follows(fake_google):
    """AC30：前一個階段沒勾（被刪除）→ 後面的階段編號往前遞補，產生排程時照遞補後的順序。"""
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            first, second, third = await _create_staged(ac, ["ev-1", None, None])
            fake_google["gone"] = {"ev-1"}

            res = await ac.post("/schedule/removed-events/resolve", json={"reschedule": [], "delete": [f"manual:{first}"]})
            assert res.status_code == status.HTTP_200_OK, res.text

            items = {item["id"]: item for item in (await ac.get("/schedule/tasks")).json()}
            assert f"manual:{first}" not in items
            assert (items[f"manual:{second}"]["stage"], items[f"manual:{third}"]["stage"]) == (1, 2)

            scheduled = {item["task_id"]: item for item in (await ac.post("/schedule/suggest", json={})).json()["scheduled"]}
            assert to_utc_datetime(scheduled[f"manual:{third}"]["start"]) >= to_utc_datetime(scheduled[f"manual:{second}"]["end"])
    finally:
        await _cleanup()


@pytest.mark.asyncio
async def test_schedule_wizard_empty_ac28_scheduled_task_rescheduled_returns_to_wizard_filter(fake_google):
    """AC28：確認排程後的任務經 POST /schedule/tasks/reschedule → 事件已刪、三個欄位都是 null，符合排程精靈的篩選（不是主任務、沒完成、沒有事件編號）。"""
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            task_id = await _seed(ac)
            composite_id = f"manual:{task_id}"
            scheduled_at = datetime(2030, 1, 1, 9, 0, tzinfo=timezone.utc)
            await db.manual_tasks.update_one({"_id": task_id}, {"$set": {
                "calendar_event_id": "ev-1", "scheduled_start": scheduled_at, "scheduled_end": scheduled_at,
            }})

            before = {item["id"]: item for item in (await ac.get("/schedule/tasks")).json()}
            assert before[composite_id]["scheduled_start"] is not None

            res = await ac.post("/schedule/tasks/reschedule", json={"task_ids": [composite_id]})
            assert res.status_code == status.HTTP_200_OK, res.text
            assert res.json() == {"succeeded": [composite_id], "failed": []}

            item = {i["id"]: i for i in (await ac.get("/schedule/tasks")).json()}[composite_id]
            assert fake_google["deleted"] == ["ev-1"]
            assert item["calendar_event_id"] is None
            assert item["scheduled_start"] is None and item["scheduled_end"] is None
            assert not item["is_parent"] and item["status"] != "Done"
    finally:
        await _cleanup()
