import pytest
from datetime import datetime

import routers.schedule as schedule_router

mock_user = {"sub": "test_user_123"}


@pytest.mark.asyncio
async def test_suggest_schedule_combines_tasks_and_free_slots(monkeypatch):
    async def mock_get_tasks(user_id):
        return [
            {"id": "t1", "title": "任務一", "priority": "High", "status": "To Do", "due_date": None},
            {"id": "t2", "title": "任務二", "priority": "Low", "status": "To Do", "due_date": None},
        ]

    async def mock_get_free_slots(user_id):
        return [{"start": "2026-09-10T09:00:00Z", "end": "2026-09-10T10:00:00Z"}]

    monkeypatch.setattr(schedule_router, "get_manual_tasks_by_user_id", mock_get_tasks)
    monkeypatch.setattr(schedule_router, "get_free_slots_for_user", mock_get_free_slots)

    result = await schedule_router.suggest_schedule(clerk_user=mock_user)

    assert len(result["scheduled"]) == 1
    assert result["scheduled"][0]["task_id"] == "t1"  # 高優先權先排
    assert len(result["unscheduled"]) == 1
    assert result["unscheduled"][0]["task_id"] == "t2"


@pytest.mark.asyncio
async def test_suggest_schedule_handles_no_tasks(monkeypatch):
    async def mock_get_tasks(user_id):
        return None  # get_manual_tasks_by_user_id 沒有任務時回傳 None

    async def mock_get_free_slots(user_id):
        return [{"start": "2026-09-10T09:00:00Z", "end": "2026-09-10T10:00:00Z"}]

    monkeypatch.setattr(schedule_router, "get_manual_tasks_by_user_id", mock_get_tasks)
    monkeypatch.setattr(schedule_router, "get_free_slots_for_user", mock_get_free_slots)

    result = await schedule_router.suggest_schedule(clerk_user=mock_user)

    assert result["scheduled"] == []
    assert result["unscheduled"] == []
