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
    """GET /schedule/suggest 成功：200，回傳 scheduled / unscheduled 兩份清單，datetime 被轉成字串。"""
    async def mock_get_tasks(user_id):
        return [{"id": "t1", "title": "任務一", "priority": "High", "status": "To Do", "due_date": None}]

    async def mock_get_free_slots(user_id):
        return [{"start": "2026-09-10T09:00:00Z", "end": "2026-09-10T10:00:00Z"}]

    monkeypatch.setattr(schedule_router, "get_manual_tasks_by_user_id", mock_get_tasks)
    monkeypatch.setattr(schedule_router, "get_free_slots_for_user", mock_get_free_slots)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/schedule/suggest")

    assert res.status_code == status.HTTP_200_OK
    body = res.json()
    assert body["scheduled"][0]["task_id"] == "t1"
    assert body["scheduled"][0]["start"].startswith("2026-09-10T09:00:00")  # datetime 被轉成字串送出
    assert body["unscheduled"] == []


@pytest.mark.asyncio
async def test_get_schedule_suggestion_when_calendar_not_connected(monkeypatch, logged_in_user):
    """使用者還沒連接 Google Calendar → 400，HTTP 回應要帶著中文說明，前端才能顯示。"""
    async def mock_get_tasks(user_id):
        return []

    async def mock_get_free_slots(user_id):
        raise HTTPException(status_code=400, detail="尚未連接 Google Calendar")

    monkeypatch.setattr(schedule_router, "get_manual_tasks_by_user_id", mock_get_tasks)
    monkeypatch.setattr(schedule_router, "get_free_slots_for_user", mock_get_free_slots)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/schedule/suggest")

    assert res.status_code == status.HTTP_400_BAD_REQUEST
    assert res.json() == {"detail": "尚未連接 Google Calendar"}


@pytest.mark.asyncio
async def test_get_schedule_suggestion_requires_login():
    """沒帶登入 token → 被擋在門外（401/403），不能進到函式裡。"""
    # 這個測試刻意不用 logged_in_user，所以請求是沒登入的
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/schedule/suggest")

    assert res.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)
