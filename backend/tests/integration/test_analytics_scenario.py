"""
情境測試：透過 HTTP 標記任務完成後查詢工作效率統計，確認完成時間真的寫入、統計讀得到。
clerk_id 用這個檔案獨有的值，避免和其他測試共用的資料庫互相影響。
"""
import pytest
from fastapi import status
from httpx import AsyncClient
from httpx._transports.asgi import ASGITransport

from main import app
from core.database import db
from core.security import get_current_clerk_user

SCENARIO_USER = {"sub": "scenario_user_analytics"}


@pytest.fixture(autouse=True)
def _override_auth():
    async def mock_get_user():
        return SCENARIO_USER
    app.dependency_overrides[get_current_clerk_user] = mock_get_user
    yield
    app.dependency_overrides.pop(get_current_clerk_user, None)


@pytest.mark.asyncio
async def test_marking_task_done_shows_up_in_this_weeks_completions():
    """建立任務 → 標記完成 → 統計顯示完成 1、本週完成 1 → 取消完成 → 本週回到 0。"""
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            create_res = await ac.post("/manual-tasks/", json={
                "title": "情境測試：寫報告", "description": "d", "status": "To Do",
                "priority": "High", "duration": 45,
            })
            assert create_res.status_code == status.HTTP_201_CREATED, create_res.text
            task_id = create_res.json()["id"]

            done_res = await ac.patch("/schedule/tasks/done", json={"task_id": f"manual:{task_id}", "done": True})
            assert done_res.status_code == status.HTTP_200_OK, done_res.text

            summary = (await ac.get("/analytics/productivity", params={"timezone": "Asia/Taipei"})).json()
            assert (summary["total"], summary["done"]) == (1, 1)
            assert summary["untracked_done"] == 0
            assert summary["weekly"][-1]["completed"] == 1
            assert summary["weekly"][-1]["completed_minutes"] == 45

            await ac.patch("/schedule/tasks/done", json={"task_id": f"manual:{task_id}", "done": False})

            summary = (await ac.get("/analytics/productivity", params={"timezone": "Asia/Taipei"})).json()
            assert summary["done"] == 0
            assert summary["weekly"][-1]["completed"] == 0
    finally:
        await db.manual_tasks.delete_many({"user_id": SCENARIO_USER["sub"]})
