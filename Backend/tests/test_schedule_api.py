# 透過 HTTP 測試 /schedule 這組 API：路由有註冊、登入驗證有掛上、
# 回傳的 JSON 格式（response_model）跟錯誤狀態碼真的送得出去。
# 排程規則本身（誰先排、塞哪個空檔）由 test_schedule_crud.py 負責，這裡不重複測。
import pytest
from fastapi import HTTPException, status
from httpx import AsyncClient
from httpx._transports.asgi import ASGITransport

from main import app
import routers.schedule as schedule_router


# 測試 GET /schedule/suggest —— 任務 + 空檔 -> 排程建議
@pytest.mark.asyncio
async def test_get_schedule_suggestion(monkeypatch, logged_in_user):
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


# 使用者還沒連接 Google Calendar：底層丟出 400，HTTP 回應要帶著中文說明，前端才能顯示
@pytest.mark.asyncio
async def test_get_schedule_suggestion_when_calendar_not_connected(monkeypatch, logged_in_user):
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


# 沒帶登入 token（這個測試沒有用 logged_in_user）-> 要被擋在門外，不能進到函式裡
@pytest.mark.asyncio
async def test_get_schedule_suggestion_requires_login():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/schedule/suggest")

    assert res.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)
