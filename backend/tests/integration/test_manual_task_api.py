# 透過 HTTP 確認路由、登入驗證、回應格式和錯誤狀態碼；細部邏輯由 unit 測試負責
import pytest
from fastapi import HTTPException
from httpx import AsyncClient
from httpx._transports.asgi import ASGITransport
from unittest.mock import AsyncMock, patch

from main import app  # 假設 FastAPI app 是定義在 main.py 裡
from schemas.manual_task import ManualTaskInput, ManualTaskOut


@pytest.fixture
def fake_task_input():
    return ManualTaskInput(
        title="Test Task",
        description="This is a test task.",
        due_date=None,
        status="To Do",
        priority="Low",
        duration=30,  # 兩個不確定欄位都填了，才不會觸發 LLM 推斷
    )

@pytest.fixture
def fake_task_out():
    return ManualTaskOut(
        id="task_id",
        user_id="test_user_123",
        title="Test Task",
        description="This is a test task.",
        due_date=None,
        created="2023-10-01T00:00:00Z",
        updated="2023-10-01T00:00:00Z",
        status="To Do",
        priority="Low"
    )

@pytest.fixture
def fake_task_out_updated():
    return ManualTaskOut(
        id="task_id",
        user_id="test_user_123",
        title="Test Task",
        description="This is a test task (updated).",
        due_date=None,
        created="2023-10-01T00:00:00Z",
        updated="2023-10-10T00:00:00Z",
        status="To Do",
        priority="Low"
    )

"""
測試建立任務
"""
@pytest.mark.asyncio
@patch("routers.manual_task.infer_missing_task_fields", new_callable=AsyncMock)
@patch("crud.manual_task.create_manual_task", new_callable=AsyncMock)
async def test_create_manual_task_success(mock_create_manual_task, mock_infer, fake_task_input, fake_task_out, logged_in_user):
    """POST /manual-tasks/：建立任務成功；priority 和 duration 都填了，就不該去問 LLM 推斷。"""
    mock_create_manual_task.return_value = fake_task_out

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/manual-tasks/", json=fake_task_input.model_dump())

    assert response.status_code == 201
    assert response.json()["id"] == "task_id"
    assert response.json()["created"] == "2023-10-01T00:00:00Z"
    # priority/duration 兩個都填了，不該去問 LLM
    mock_infer.assert_not_called()

@pytest.mark.asyncio
@patch("crud.manual_task.create_manual_task", new_callable=AsyncMock)
async def test_create_manual_task_ignores_client_supplied_user_id(mock_create_manual_task, fake_task_input, fake_task_out, logged_in_user):
    """建立任務時，就算請求裡帶了別人的 user_id，任務的擁有者仍是登入者本人。"""
    mock_create_manual_task.return_value = fake_task_out
    payload = fake_task_input.model_dump()
    payload["user_id"] = "someone_else"  # 冒充別人

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/manual-tasks/", json=payload)

    assert response.status_code == 201
    saved_task = mock_create_manual_task.call_args[0][0]
    assert saved_task.user_id == logged_in_user["sub"]


@pytest.mark.asyncio
async def test_create_manual_task_invalid_input(logged_in_user):
    """請求內容缺必填欄位 → 回 422。"""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/manual-tasks/", json={})
    assert response.status_code == 422  # FastAPI 的預設驗證


"""
測試取得帳號底下任務
"""
@pytest.mark.asyncio
@patch("crud.manual_task.get_manual_tasks_by_user_id", new_callable=AsyncMock)
async def test_get_user_tasks_success(mock_get_tasks, fake_task_out, logged_in_user):
    """GET /manual-tasks/me：回傳目前使用者的所有任務。"""
    mock_get_tasks.return_value = [fake_task_out, fake_task_out]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/manual-tasks/me")
    assert response.status_code == 200
    tasks = response.json()
    assert len(tasks) == 2
    assert tasks[0]["id"] == "task_id"

@pytest.mark.asyncio
@patch("crud.manual_task.get_manual_tasks_by_user_id", new_callable=AsyncMock)
async def test_get_user_tasks_empty(mock_get_tasks, logged_in_user):
    """沒有任何任務是正常狀態（新使用者、或剛清空清單）→ 回 200 加空陣列，不是 404；否則刪掉最後一個任務後，前端重新整理會誤判成錯誤。"""
    mock_get_tasks.return_value = []

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/manual-tasks/me")
    assert response.status_code == 200
    assert response.json() == []


"""
測試查詢單一任務
"""
@pytest.mark.asyncio
@patch("crud.manual_task.get_manual_task_by_id", new_callable=AsyncMock)
async def test_get_manual_task_success(mock_get_task, fake_task_out, logged_in_user):
    """GET /manual-tasks/{id}：查到任務就回傳它。"""
    mock_get_task.return_value = fake_task_out


    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/manual-tasks/task-id")

    assert response.status_code == 200
    task = response.json()
    assert task["id"] == "task_id"

@pytest.mark.asyncio
@patch("crud.manual_task.get_manual_task_by_id", new_callable=AsyncMock)
async def test_get_manual_task_not_found(mock_get_task, logged_in_user):
    """查無此任務 → 404 "Task not found"。"""
    mock_get_task.side_effect = HTTPException(status_code=404, detail="Task not found")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/manual-tasks/does-not-exist")

    assert response.status_code == 404
    assert response.json()["detail"] == "Task not found"


"""
測試更新任務
"""
@pytest.mark.asyncio
@patch("crud.manual_task.get_manual_task_by_id", new_callable=AsyncMock)
@patch("crud.manual_task.update_manual_task_by_id", new_callable=AsyncMock)
async def test_update_manual_task_success(mock_update_task, mock_get_task, fake_task_out, fake_task_out_updated, logged_in_user):
    """PUT /manual-tasks/{id}：更新成功，回傳更新後的任務（description、updated 都是新值）。"""
    mock_get_task.return_value = fake_task_out.model_dump()
    mock_update_task.return_value = fake_task_out_updated.model_dump()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.put("/manual-tasks/task-id", json=fake_task_out.model_dump(mode="json"))

    assert response.status_code == 200
    task = response.json()
    assert task["description"] == "This is a test task (updated)."
    assert task["updated"] == "2023-10-10T00:00:00Z"

@pytest.mark.asyncio
@patch("crud.manual_task.get_manual_task_by_id", new_callable=AsyncMock)
async def test_update_manual_task_not_found(mock_get_task, fake_task_out, logged_in_user):
    """更新不存在的任務 → 404 "Task not found"。"""
    mock_get_task.side_effect = HTTPException(status_code=404, detail="Task not found")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.put("/manual-tasks/does-not-exist", json=fake_task_out.model_dump(mode="json"))

    assert response.status_code == 404
    assert response.json()["detail"] == "Task not found"


"""
測試刪除任務
"""
@pytest.mark.asyncio
@patch("crud.manual_task.get_manual_task_by_id", new_callable=AsyncMock)
@patch("crud.manual_task.delete_manual_task_by_id", new_callable=AsyncMock)
async def test_delete_manual_task_success(mock_delete_task, mock_get_task, fake_task_out, logged_in_user):
    """DELETE /manual-tasks/{id}：刪除成功，回傳被刪的任務 ID 和 deleted 為 True。"""
    mock_get_task.return_value = fake_task_out.model_dump()
    mock_delete_task.return_value = True

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.delete("/manual-tasks/task-id")

    assert response.status_code == 200
    assert response.json() == {"task ID": "task-id", "deleted": True}

@pytest.mark.asyncio
@patch("crud.manual_task.get_manual_task_by_id", new_callable=AsyncMock)
async def test_delete_manual_task_not_found(mock_get_task, logged_in_user):
    """刪除不存在的任務 → 404 "Task not found"。"""
    mock_get_task.side_effect = HTTPException(status_code=404, detail="Task not found")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.delete("/manual-tasks/task-999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Task not found"


"""
測試沒登入
"""
@pytest.mark.asyncio
async def test_get_user_tasks_requires_login():
    """沒帶登入 token → 被擋在門外（401/403），不能進到函式裡。"""
    # 這個測試刻意不用 logged_in_user，所以請求是沒登入的
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/manual-tasks/me")

    assert response.status_code in (401, 403)


"""
階段任務（主任務拆成子任務）：用記憶體資料庫走真的 crud
"""
import pytest_asyncio
from core.database import db


@pytest_asyncio.fixture
async def stage_cleanup():
    yield
    await db.manual_tasks.delete_many({"user_id": "test_user_123", "title": {"$regex": "^階段API"}})


def _staged_payload(subtasks, **fields):
    payload = {"title": "階段API 主任務", "description": "", "subtasks": subtasks}
    payload.update(fields)
    return payload


def _api_sub(title, **fields):
    return {"title": f"階段API {title}", "priority": "Low", "duration": 30, **fields}


async def _count_stage_docs():
    return await db.manual_tasks.count_documents({"user_id": "test_user_123", "title": {"$regex": "^階段API"}})


@pytest.mark.asyncio
async def test_ac1_create_with_subtasks_returns_parent_and_stages(logged_in_user, stage_cleanup):
    """AC1：POST /manual-tasks/ 帶 subtasks → 201，回應是主任務並附上依填寫順序編號的子任務。"""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/manual-tasks/", json=_staged_payload([_api_sub("一"), _api_sub("二")]))

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["is_parent"] is True
    assert body["priority"] is None and body["duration"] is None
    assert body["progress"] == {"done": 0, "total": 2}
    assert [(s["title"], s["stage"], s["parent_id"]) for s in body["subtasks"]] == [
        ("階段API 一", 1, body["id"]), ("階段API 二", 2, body["id"]),
    ]


@pytest.mark.asyncio
@patch("routers.manual_task.infer_missing_task_fields", new_callable=AsyncMock)
async def test_ac2_create_without_subtasks_behaves_as_before(mock_infer, logged_in_user, stage_cleanup):
    """AC2：不帶 subtasks → 和現在一樣建立一般任務（status 仍是必填，缺欄位才問 AI），不是主任務。"""
    mock_infer.return_value = {"priority": "High", "duration": 45, "reason": "理由"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        missing_status = await ac.post("/manual-tasks/", json={"title": "階段API 一般", "description": ""})
        response = await ac.post("/manual-tasks/", json={"title": "階段API 一般", "description": "", "status": "To Do"})

    assert missing_status.status_code == 422
    assert response.status_code == 201, response.text
    body = response.json()
    assert (body["priority"], body["duration"], body["is_parent"], body["parent_id"]) == ("High", 45, False, None)
    mock_infer.assert_awaited_once_with("階段API 一般", "", None)


@pytest.mark.asyncio
@pytest.mark.parametrize("subtasks", [
    [_api_sub(str(i)) for i in range(11)],
    [],
    [{"priority": "Low", "duration": 30}],
    [_api_sub("有標題"), {"title": "   ", "priority": "Low", "duration": 30}],
])
async def test_ac3_invalid_subtasks_are_rejected_with_422_and_nothing_created(logged_in_user, stage_cleanup, subtasks):
    """AC3：超過 10 個、空的 subtasks、子任務沒有標題 → 422，不建立任何資料。"""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/manual-tasks/", json=_staged_payload(subtasks))

    assert response.status_code == 422
    assert any("subtasks" in error["loc"] for error in response.json()["detail"])
    assert await _count_stage_docs() == 0


@pytest.mark.asyncio
async def test_ac4_one_invalid_subtask_creates_nothing_and_explains_which_stage(logged_in_user, stage_cleanup):
    """AC4 / AC8：一筆子任務驗證失敗 → 400 且 detail 指出階段，主任務和子任務都不建立。"""
    payload = _staged_payload(
        [_api_sub("一"), _api_sub("二", due_date="2030-02-01T00:00:00Z")], due_date="2030-01-01T00:00:00Z",
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/manual-tasks/", json=payload)

    assert response.status_code == 400
    assert "階段 2" in response.json()["detail"]
    assert await _count_stage_docs() == 0


@pytest.mark.asyncio
async def test_ac9_create_with_subtasks_counts_as_one_request_for_rate_limit(logged_in_user, stage_cleanup):
    """AC9：一次建立主任務加子任務只算一次請求：20/分 內的第 20 次成功、第 21 次才 429。"""
    from core.rate_limit import limiter

    limiter.enabled = True
    limiter.reset()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            headers = {"Authorization": "Bearer ac9-token"}
            payload = _staged_payload([_api_sub("一"), _api_sub("二"), _api_sub("三")])
            statuses = [(await ac.post("/manual-tasks/", json=payload, headers=headers)).status_code for _ in range(21)]
    finally:
        limiter.enabled = False
        limiter.reset()

    assert statuses[:20] == [201] * 20
    assert statuses[20] == 429


@pytest.mark.asyncio
async def test_ac10_ac12_add_subtask_to_plain_task_converts_it(logged_in_user, stage_cleanup):
    """AC10 / AC12：POST /manual-tasks/{id}/subtasks 對一般任務新增第 1 個子任務 → 201，它變成主任務。"""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        plain = (await ac.post("/manual-tasks/", json={
            "title": "階段API 一般", "description": "", "status": "To Do", "priority": "High", "duration": 60,
        })).json()
        response = await ac.post(f"/manual-tasks/{plain['id']}/subtasks", json=_api_sub("第一階段", priority="High"))

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["id"] == plain["id"]
    assert body["is_parent"] is True and body["priority"] is None
    assert [s["stage"] for s in body["subtasks"]] == [1]


@pytest.mark.asyncio
async def test_ac11_ac14_add_subtask_errors_return_400(logged_in_user, stage_cleanup):
    """AC11 / AC14：已有 10 個子任務、或對子任務再新增 → 400 並帶說明。"""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        parent = (await ac.post("/manual-tasks/", json=_staged_payload([_api_sub(str(i)) for i in range(10)]))).json()
        too_many = await ac.post(f"/manual-tasks/{parent['id']}/subtasks", json=_api_sub("第 11 個"))
        nested = await ac.post(f"/manual-tasks/{parent['subtasks'][0]['id']}/subtasks", json=_api_sub("第三層"))

    assert too_many.status_code == 400 and too_many.json()["detail"]
    assert nested.status_code == 400 and nested.json()["detail"]


@pytest.mark.asyncio
async def test_ac13_add_subtask_to_done_task_returns_400(logged_in_user, stage_cleanup):
    """AC13：已完成的一般任務不能新增子任務 → 400 並說明原因。"""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        done = (await ac.post("/manual-tasks/", json={
            "title": "階段API 已完成", "description": "", "status": "Done", "priority": "Low", "duration": 30,
        })).json()
        response = await ac.post(f"/manual-tasks/{done['id']}/subtasks", json=_api_sub("階段"))

    assert response.status_code == 400
    assert "已完成" in response.json()["detail"]


@pytest.mark.asyncio
async def test_ac15_add_subtask_to_other_users_task_returns_404(logged_in_user):
    """AC15：別人的任務 id → 404，和查詢一致。"""
    await db.manual_tasks.insert_one({"_id": "api-alice-task", "user_id": "alice", "title": "Alice", "status": "To Do"})
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.post("/manual-tasks/api-alice-task/subtasks", json=_api_sub("偷塞"))
        assert response.status_code == 404
        assert response.json()["detail"] == "Task not found"
    finally:
        await db.manual_tasks.delete_many({"_id": "api-alice-task"})


@pytest.mark.asyncio
async def test_ac37_add_subtask_requires_login():
    """AC37：沒登入呼叫新增子任務的 API → 401，沿用現有的登入驗證。"""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/manual-tasks/any-id/subtasks", json=_api_sub("階段"))

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_ac38_put_ignores_parent_id_stage_and_is_parent(logged_in_user, stage_cleanup):
    """AC38：PUT 帶 parent_id、stage、is_parent → 這三個欄位不會被寫入，子任務不會被掛到別的主任務或改階段。"""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        parent = (await ac.post("/manual-tasks/", json=_staged_payload([_api_sub("一"), _api_sub("二")]))).json()
        stage1 = parent["subtasks"][0]
        response = await ac.put(f"/manual-tasks/{stage1['id']}", json={
            "title": "階段API 改名", "parent_id": "someone-elses-parent", "stage": 9, "is_parent": True,
            "subtask_ids": ["x"],
        })
        parent_put = await ac.put(f"/manual-tasks/{parent['id']}", json={"title": "階段API 主任務", "subtask_ids": []})
        stage1_after = (await ac.get(f"/manual-tasks/{stage1['id']}")).json()

    assert response.status_code == 200, response.text
    assert parent_put.status_code == 200, parent_put.text
    stored = await db.manual_tasks.find_one({"_id": stage1["id"]})
    assert (stored["title"], stored["parent_id"], stored.get("is_parent"), stored.get("subtask_ids")) == (
        "階段API 改名", parent["id"], None, None,
    )
    assert "stage" not in stored
    assert stage1_after["stage"] == 1
    assert (await db.manual_tasks.find_one({"_id": parent["id"]}))["subtask_ids"] == [s["id"] for s in parent["subtasks"]]


@pytest.mark.asyncio
async def test_ac40_add_subtask_retry_with_same_idempotency_key_returns_first_result(logged_in_user, stage_cleanup):
    """AC40：新增子任務帶相同 Idempotency-Key 重送 → 回傳第一次的結果，不會重複新增子任務。"""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        parent = (await ac.post("/manual-tasks/", json=_staged_payload([_api_sub("一")]))).json()
        headers = {"Idempotency-Key": "ac40-key"}
        first = await ac.post(f"/manual-tasks/{parent['id']}/subtasks", json=_api_sub("二"), headers=headers)
        second = await ac.post(f"/manual-tasks/{parent['id']}/subtasks", json=_api_sub("二"), headers=headers)

    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert [s["id"] for s in second.json()["subtasks"]] == [s["id"] for s in first.json()["subtasks"]]
    assert await db.manual_tasks.count_documents({"parent_id": parent["id"]}) == 2
