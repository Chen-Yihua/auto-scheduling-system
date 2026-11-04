"""
情境測試：透過 HTTP 依序操作任務，用 mongomock 確認跨步驟的資料一致性。
clerk_id 用這個檔案獨有的值，避免和其他測試共用的資料庫互相影響。
"""
import pytest
from fastapi import status
from httpx import AsyncClient
from httpx._transports.asgi import ASGITransport

from main import app
from core.security import get_current_clerk_user

SCENARIO_USER = {"sub": "scenario_user_manual_task"}


@pytest.fixture(autouse=True)
def _override_auth():
    async def mock_get_user():
        return SCENARIO_USER
    app.dependency_overrides[get_current_clerk_user] = mock_get_user
    yield
    app.dependency_overrides.pop(get_current_clerk_user, None)


@pytest.mark.asyncio
async def test_manual_task_full_lifecycle():
    """任務完整流程：建立 → 列表 → 查詢 → 編輯 → 刪除 → 查詢 404 → 列表為空（200）。"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. 建立任務（有填 priority/duration，不觸發 AI 推斷）
        create_res = await ac.post(
            "/manual-tasks/",
            json={
                "user_id": SCENARIO_USER["sub"],
                "title": "情境測試：期末報告",
                "description": "整理資料並簡報",
                "status": "To Do",
                "priority": "Medium",
                "duration": 90,
                "due_date": "2026-12-31T00:00:00Z",
            },
        )
        assert create_res.status_code == status.HTTP_201_CREATED, create_res.text
        created = create_res.json()
        task_id = created["id"]
        assert created["title"] == "情境測試：期末報告"
        assert created["inferred_fields"] == []  # 都有填，不該有任何欄位是 AI 推斷的

        # 2. 列表裡看得到剛建立的任務
        list_res = await ac.get("/manual-tasks/me")
        assert list_res.status_code == status.HTTP_200_OK
        titles = [t["title"] for t in list_res.json()]
        assert "情境測試：期末報告" in titles

        # 3. 用 id 單獨查詢，資料要跟建立時一致
        get_res = await ac.get(f"/manual-tasks/{task_id}")
        assert get_res.status_code == status.HTTP_200_OK
        assert get_res.json()["priority"] == "Medium"

        # 4. 編輯：改標題跟優先度
        update_res = await ac.put(
            f"/manual-tasks/{task_id}",
            json={
                "user_id": SCENARIO_USER["sub"],
                "title": "情境測試：期末報告（已延期）",
                "description": "整理資料並簡報",
                "status": "To Do",
                "priority": "High",
                "duration": 90,
                "due_date": "2027-01-15T00:00:00Z",
            },
        )
        assert update_res.status_code == status.HTTP_200_OK, update_res.text
        assert update_res.json()["title"] == "情境測試：期末報告（已延期）"
        assert update_res.json()["priority"] == "High"

        # 5. 更新有真的落地：列表裡看到的是新標題，不是舊的
        list_after_update = await ac.get("/manual-tasks/me")
        titles_after_update = [t["title"] for t in list_after_update.json()]
        assert "情境測試：期末報告（已延期）" in titles_after_update
        assert "情境測試：期末報告" not in titles_after_update

        # 6. 刪除
        delete_res = await ac.delete(f"/manual-tasks/{task_id}")
        assert delete_res.status_code == status.HTTP_200_OK
        assert delete_res.json()["deleted"] is True

        # 7. 刪除後查不到了（單筆查詢回 404）
        get_after_delete = await ac.get(f"/manual-tasks/{task_id}")
        assert get_after_delete.status_code == status.HTTP_404_NOT_FOUND

        # 8. 沒有任務時回 200 和空陣列，不是 404
        list_after_delete = await ac.get("/manual-tasks/me")
        assert list_after_delete.status_code == status.HTTP_200_OK
        assert list_after_delete.json() == []


@pytest.mark.asyncio
async def test_manual_task_ai_inference_fills_missing_fields_and_survives_full_lifecycle():
    """沒填 priority/duration → AI 推斷的值在列表、查詢、編輯後都要保留。"""
    from unittest.mock import AsyncMock, patch

    with patch(
        "routers.manual_task.infer_missing_task_fields",
        new=AsyncMock(return_value={
            "priority": "Low",
            "duration": 30,
            "reason": "情境測試假造的推斷理由",
        }),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            create_res = await ac.post(
                "/manual-tasks/",
                json={
                    "user_id": SCENARIO_USER["sub"],
                    "title": "情境測試：AI 推斷任務",
                    "description": "沒填優先度跟時長",
                    "status": "To Do",
                    "due_date": "2026-12-31T00:00:00Z",
                },
            )
            assert create_res.status_code == status.HTTP_201_CREATED, create_res.text
            created = create_res.json()
            task_id = created["id"]
            assert created["priority"] == "Low"
            assert created["duration"] == 30
            assert set(created["inferred_fields"]) == {"priority", "duration"}

            # 推斷出來的值要真的存進去、查得到，不是只有建立當下的回應裡有
            get_res = await ac.get(f"/manual-tasks/{task_id}")
            assert get_res.json()["priority"] == "Low"
            assert get_res.json()["duration"] == 30

            # 清理，避免留在 mongomock 裡影響其他測試
            await ac.delete(f"/manual-tasks/{task_id}")


@pytest.mark.asyncio
async def test_staged_task_delete_parent_fails_midway_then_retry_succeeds(monkeypatch):
    """
    AC28 / AC31 / AC33：建立主任務加兩個階段 → 兩個階段都排入行事曆 → 刪除主任務時第二個事件刪失敗（502），
    任務全部保留 → 重試時第一個事件已經不存在（404）當作成功，主任務和子任務都刪掉。
    """
    import httpx
    from core.crypto import encrypt_secret
    from core.database import db
    import services.google_calendar as calendar_service

    await db.googleCalendarTokens.update_one(
        {"_id": SCENARIO_USER["sub"]},
        {"$set": {"access_token": encrypt_secret("token")}},
        upsert=True,
    )

    async def fake_calendar_list(access_token):
        return [{"id": "primary", "primary": True}]

    remaining_events = {"ev-1", "ev-2"}
    fail_next_delete_of = {"ev-2"}

    def _error(status):
        request = httpx.Request("GET", "https://example.com")
        return httpx.HTTPStatusError("error", request=request, response=httpx.Response(status, request=request))

    async def fake_get_event(access_token, calendar_id, event_id):
        if event_id not in remaining_events:
            raise _error(404)
        return {"status": "confirmed", "start": {"dateTime": "2099-01-01T09:00:00Z"}, "end": {"dateTime": "2099-01-01T10:00:00Z"}}

    async def fake_delete_event(access_token, calendar_id, event_id):
        if event_id in fail_next_delete_of:
            fail_next_delete_of.discard(event_id)
            raise _error(503)
        remaining_events.discard(event_id)

    monkeypatch.setattr(calendar_service, "fetch_google_calendar_list", fake_calendar_list)
    monkeypatch.setattr(calendar_service, "get_calendar_event", fake_get_event)
    monkeypatch.setattr(calendar_service, "delete_calendar_event", fake_delete_event)

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            created = (await ac.post("/manual-tasks/", json={
                "title": "情境測試：分階段報告", "description": "",
                "subtasks": [
                    {"title": "階段一", "priority": "High", "duration": 60},
                    {"title": "階段二", "priority": "High", "duration": 60},
                ],
            })).json()
            parent_id = created["id"]
            for subtask, event_id in zip(created["subtasks"], ["ev-1", "ev-2"]):
                await db.manual_tasks.update_one({"_id": subtask["id"]}, {"$set": {"calendar_event_id": event_id}})

            # 主任務出現在列表，排程頁的資料帶主任務名稱和階段
            listed = (await ac.get("/schedule/tasks")).json()
            stage_rows = [t for t in listed if t.get("parent_id") == f"manual:{parent_id}"]
            assert [(t["stage"], t["stage_count"], t["parent_title"]) for t in stage_rows] == [
                (1, 2, "情境測試：分階段報告"), (2, 2, "情境測試：分階段報告"),
            ]

            first_try = await ac.delete(f"/manual-tasks/{parent_id}")
            assert first_try.status_code == 502
            assert "重試" in first_try.json()["detail"]
            assert remaining_events == {"ev-2"}
            assert len((await ac.get("/manual-tasks/me")).json()) == 3

            retry = await ac.delete(f"/manual-tasks/{parent_id}")
            assert retry.status_code == 200, retry.text
            assert remaining_events == set()
            assert (await ac.get("/manual-tasks/me")).json() == []
    finally:
        await db.googleCalendarTokens.delete_many({"_id": SCENARIO_USER["sub"]})
        await db.manual_tasks.delete_many({"user_id": SCENARIO_USER["sub"]})
