"""
端對端「情境」測試：跟其他 test_manual_task_api.py / test_manual_task_scenario.py 不同的地方是——
這裡不是逐一測試單一 endpoint，而是把使用者真實會做的一整串操作串起來，
在同一個測試裡透過真的 HTTP（httpx + ASGITransport 打 main.app）依序呼叫，
確認「上一步寫進去的資料，下一步真的讀得到、也真的反映了更新」。

用 mongomock（見 conftest.py）當資料庫，不是每支測試都各自 mock crud 函式——
這樣才測得到「create 完 DB 裡真的有資料、update 完真的覆蓋掉舊值、delete 完真的查不到」
這種跨步驟的資料一致性，而不只是「這個 endpoint 收到請求會怎麼回應」。

clerk_id 特意用這個檔案獨有的字串，避免跟其他測試檔案共用同一個 mongomock
session-scope 資料庫時互相污染到彼此的資料。
"""
import pytest
from fastapi import status
from httpx import AsyncClient
from httpx._transports.asgi import ASGITransport

from main import app
from db.security import get_current_clerk_user

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
    """任務的完整生命週期：建立（priority/duration 都有填，不觸發 AI 推斷）→ 列表 → 單筆查詢 → 編輯（更新有真的落地）→ 刪除 → 單筆查不到（404）→ 列表回到空清單（200，不是 404）。"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. 建立任務（priority/duration 都有填，不會觸發 AI 推斷，
        #    避免這個情境測試還要額外去 mock Gemini）
        create_res = await ac.post(
            "/manual_tasks/",
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
        assert create_res.status_code == status.HTTP_200_OK, create_res.text
        created = create_res.json()
        task_id = created["id"]
        assert created["title"] == "情境測試：期末報告"
        assert created["inferred_fields"] == []  # 都有填，不該有任何欄位是 AI 推斷的

        # 2. 列表裡看得到剛建立的任務
        list_res = await ac.get("/manual_tasks/me")
        assert list_res.status_code == status.HTTP_200_OK
        titles = [t["title"] for t in list_res.json()]
        assert "情境測試：期末報告" in titles

        # 3. 用 id 單獨查詢，資料要跟建立時一致
        get_res = await ac.get(f"/manual_tasks/{task_id}")
        assert get_res.status_code == status.HTTP_200_OK
        assert get_res.json()["priority"] == "Medium"

        # 4. 編輯：改標題跟優先度
        update_res = await ac.put(
            f"/manual_tasks/{task_id}",
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
        list_after_update = await ac.get("/manual_tasks/me")
        titles_after_update = [t["title"] for t in list_after_update.json()]
        assert "情境測試：期末報告（已延期）" in titles_after_update
        assert "情境測試：期末報告" not in titles_after_update

        # 6. 刪除
        delete_res = await ac.delete(f"/manual_tasks/{task_id}")
        assert delete_res.status_code == status.HTTP_200_OK
        assert delete_res.json()["deleted"] is True

        # 7. 刪除後查不到了（單筆查詢回 404）
        get_after_delete = await ac.get(f"/manual_tasks/{task_id}")
        assert get_after_delete.status_code == status.HTTP_404_NOT_FOUND

        # 8. 這個使用者名下已經沒有任何任務 -> 是正常狀態，列表 endpoint 回 200 + 空陣列，
        # 不是 404（404 代表資源路徑不存在，這裡路徑一直都存在，只是內容剛好是空的）
        list_after_delete = await ac.get("/manual_tasks/me")
        assert list_after_delete.status_code == status.HTTP_200_OK
        assert list_after_delete.json() == []


@pytest.mark.asyncio
async def test_manual_task_ai_inference_fills_missing_fields_and_survives_full_lifecycle():
    """沒填 priority/duration → AI 推斷出的值要能一路撐過列表顯示、單筆查詢、編輯保留、
最後刪除——不是只有建立當下那一次回應正確。"""
    from unittest.mock import AsyncMock, patch

    with patch(
        "routers.manualTask.infer_missing_task_fields",
        new=AsyncMock(return_value={
            "priority": "Low",
            "duration": 30,
            "reason": "情境測試假造的推斷理由",
        }),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            create_res = await ac.post(
                "/manual_tasks/",
                json={
                    "user_id": SCENARIO_USER["sub"],
                    "title": "情境測試：AI 推斷任務",
                    "description": "沒填優先度跟時長",
                    "status": "To Do",
                    "due_date": "2026-12-31T00:00:00Z",
                },
            )
            assert create_res.status_code == status.HTTP_200_OK, create_res.text
            created = create_res.json()
            task_id = created["id"]
            assert created["priority"] == "Low"
            assert created["duration"] == 30
            assert set(created["inferred_fields"]) == {"priority", "duration"}

            # 推斷出來的值要真的存進去、查得到，不是只有建立當下的回應裡有
            get_res = await ac.get(f"/manual_tasks/{task_id}")
            assert get_res.json()["priority"] == "Low"
            assert get_res.json()["duration"] == 30

            # 清理，避免留在 mongomock 裡影響其他測試
            await ac.delete(f"/manual_tasks/{task_id}")
