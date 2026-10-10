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
