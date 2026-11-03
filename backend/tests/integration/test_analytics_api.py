# 透過 HTTP 確認路由、登入驗證、回應格式和錯誤狀態碼；統計規則由 unit/test_productivity.py 負責
import pytest
from fastapi import status
from httpx import AsyncClient
from httpx._transports.asgi import ASGITransport

from main import app
import routers.analytics as analytics_router


@pytest.mark.asyncio
async def test_get_productivity_summary(monkeypatch, logged_in_user):
    """GET /analytics/productivity → 200，統計的是登入者自己的項目，日期轉成字串送出。"""
    requested_users = []

    async def mock_get_items(user_id):
        requested_users.append(user_id)
        return [{"source": "manual", "status": "To Do", "priority": "High", "duration": 30, "due_date": None}]

    monkeypatch.setattr(analytics_router, "get_all_schedulable_items", mock_get_items)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/analytics/productivity", params={"timezone": "Asia/Taipei"})

    assert res.status_code == status.HTTP_200_OK, res.text
    body = res.json()
    assert requested_users == ["test_user_123"]
    assert body["total"] == 1
    assert body["remaining_minutes"] == 30
    assert body["by_source"] == [{"source": "manual", "total": 1, "done": 0}]
    assert len(body["weekly"]) == 8
    assert isinstance(body["weekly"][0]["week_start"], str)


@pytest.mark.asyncio
async def test_get_productivity_summary_rejects_unknown_timezone(logged_in_user):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/analytics/productivity", params={"timezone": "Mars/Olympus"})

    assert res.status_code == status.HTTP_400_BAD_REQUEST
    assert "Mars/Olympus" in res.json()["detail"]


@pytest.mark.asyncio
async def test_get_productivity_summary_requires_login():
    """AC11：未登入回 403（沿用 Clerk 驗證的既有行為）。"""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/analytics/productivity")

    assert res.status_code == status.HTTP_403_FORBIDDEN
