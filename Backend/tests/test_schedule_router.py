import pytest
from datetime import datetime

from fastapi import HTTPException

import routers.schedule as schedule_router

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

    monkeypatch.setattr(schedule_router, "get_manual_tasks_by_user_id", mock_get_tasks)
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
        return []  # get_manual_tasks_by_user_id 沒有任務時回傳空清單

    async def mock_get_free_slots(user_id):
        return [{"start": "2026-09-10T09:00:00Z", "end": "2026-09-10T10:00:00Z"}]

    monkeypatch.setattr(schedule_router, "get_manual_tasks_by_user_id", mock_get_tasks)
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

    def mock_build_schedule_suggestion(tasks, free_slots):
        raise KeyError("unexpected")

    monkeypatch.setattr(schedule_router, "get_manual_tasks_by_user_id", mock_get_tasks)
    monkeypatch.setattr(schedule_router, "get_free_slots_for_user", mock_get_free_slots)
    monkeypatch.setattr(schedule_router, "build_schedule_suggestion", mock_build_schedule_suggestion)

    with pytest.raises(HTTPException) as exc_info:
        await schedule_router.suggest_schedule(clerk_user=mock_user)

    assert exc_info.value.status_code == 500
