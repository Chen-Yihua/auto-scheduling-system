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
