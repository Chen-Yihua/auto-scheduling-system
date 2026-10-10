"""
情境測試：透過 HTTP 依序操作連結帳號，用 mongomock 確認每一步的資料在下一步讀得到。
只 mock 呼叫外部平台的函式，加密、遮罩和 DB 讀寫都走真的程式碼。
"""
import pytest
from fastapi import status
from httpx import AsyncClient
from httpx._transports.asgi import ASGITransport

from main import app
from core.security import get_current_clerk_user
import crud.linked_account as linked_mod
import platforms.github as github_platform
import platforms.moodle as moodle_platform

SCENARIO_USER = {"sub": "scenario_user_linked_account"}


@pytest.fixture(autouse=True)
def _override_auth():
    async def mock_get_user():
        return SCENARIO_USER
    app.dependency_overrides[get_current_clerk_user] = mock_get_user
    yield
    app.dependency_overrides.pop(get_current_clerk_user, None)


@pytest.mark.asyncio
async def test_github_linked_account_full_lifecycle(monkeypatch):
    """GitHub 帳號完整流程：連結 → 列表（金鑰已遮罩）→ 更新金鑰 → 刪除 → 列表為空。"""
    call_count = {"n": 0}

    async def mock_fetch_github_userinfo(token):
        call_count["n"] += 1
        # 每次呼叫回傳不同值，才能證明更新時有重新驗證
        return {
            "username": f"mock_user_v{call_count['n']}",
            "avatar_url": f"https://mock.avatar/v{call_count['n']}",
        }

    monkeypatch.setattr(github_platform, "fetch_github_userinfo", mock_fetch_github_userinfo)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. 連結 GitHub 帳號
        create_res = await ac.post(
            "/users/me/linked-accounts/",
            json={
                "platform": "github",
                "status": "connected",
                "username": "",
                "apiKey": "token-v1",
            },
        )
        assert create_res.status_code == status.HTTP_201_CREATED, create_res.text
        created = create_res.json()
        assert created["username"] == "mock_user_v1"
        assert "token-v1" not in created["apiKey"]
        assert "clerk_id" not in created  # response_model 只回傳 LinkedAccountOut 定義的欄位

        # 2. 列表裡看得到，而且金鑰是遮罩過的，不是明文
        list_res = await ac.get("/users/me/linked-accounts/")
        assert list_res.status_code == status.HTTP_200_OK
        accounts = list_res.json()
        assert len(accounts) == 1
        github_account = accounts[0]
        assert github_account["platform"] == "github"
        assert github_account["username"] == "mock_user_v1"
        assert github_account["apiKey"] != "token-v1"  # 絕不回傳明文
        assert github_account["apiKey"].endswith("v1")  # mask_secret 保留最後幾碼

        # 3. 更新金鑰（PATCH，body 直接放要改的欄位）
        update_res = await ac.patch(
            "/users/me/linked-accounts/github",
            json={"apiKey": "token-v2"},
        )
        assert update_res.status_code == status.HTTP_200_OK, update_res.text
        assert update_res.json()["success"] is True
        assert call_count["n"] == 2  # 更新有重新驗證一次新 token

        # 4. 更新有真的落地：使用者名稱反映的是第二次驗證拿到的新值
        list_after_update = await ac.get("/users/me/linked-accounts/")
        assert list_after_update.json()[0]["username"] == "mock_user_v2"

        # 5. 刪除
        delete_res = await ac.delete("/users/me/linked-accounts/github")
        assert delete_res.status_code == status.HTTP_200_OK
        assert delete_res.json()["deleted"] is True

        # 6. 刪除後沒有任何連結帳號 -> 是正常狀態，回 200 + 空陣列，不是 404
        list_after_delete = await ac.get("/users/me/linked-accounts/")
        assert list_after_delete.status_code == status.HTTP_200_OK
        assert list_after_delete.json() == []


@pytest.mark.asyncio
async def test_moodle_linked_account_rejects_wrong_password_and_leaves_nothing_behind(monkeypatch):
    """Moodle 帳密錯誤 → 401，且沒有寫入任何資料。"""
    from platforms.sync import NonRetryableError

    # 原函式是同步的（透過 run_in_threadpool 呼叫），mock 也要是同步的
    def mock_verify_login_fails(username, password):
        raise NonRetryableError(f"Moodle 登入失敗，使用者：{username}")

    monkeypatch.setattr(moodle_platform, "verify_moodle_login", mock_verify_login_fails)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        create_res = await ac.post(
            "/users/me/linked-accounts/",
            json={
                "platform": "moodle",
                "status": "connected",
                "username": "stu001",
                "password": "wrong-password",
            },
        )
        assert create_res.status_code == status.HTTP_401_UNAUTHORIZED

        # 驗證失敗不該留下任何殘影資料——沒有任何連結帳號，回 200 + 空陣列，不是 404
        list_res = await ac.get("/users/me/linked-accounts/")
        assert list_res.status_code == status.HTTP_200_OK
        assert list_res.json() == []


@pytest.mark.asyncio
async def test_update_linked_account_with_unchanged_values_still_succeeds(monkeypatch):
    """送出的值和資料庫相同 → 200，不能因為沒有欄位被修改就回 404。"""
    async def mock_fetch_github_userinfo(token):
        return {"username": "mock_user", "avatar_url": "https://mock.avatar"}

    monkeypatch.setattr(github_platform, "fetch_github_userinfo", mock_fetch_github_userinfo)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        create_res = await ac.post(
            "/users/me/linked-accounts/",
            json={"platform": "github", "status": "connected", "username": "", "apiKey": "token"},
        )
        assert create_res.status_code == status.HTTP_201_CREATED, create_res.text

        update_res = await ac.patch("/users/me/linked-accounts/github", json={"status": "connected"})
        assert update_res.status_code == status.HTTP_200_OK, update_res.text

        await ac.delete("/users/me/linked-accounts/github")


@pytest.mark.asyncio
async def test_update_nonexistent_linked_account_returns_404_without_creating_record():
    """更新沒連結過的平台 → 404，且不能建立出只有部分欄位的紀錄。"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        update_res = await ac.patch("/users/me/linked-accounts/jira", json={"domain": "foo.atlassian.net"})
        assert update_res.status_code == status.HTTP_404_NOT_FOUND

        list_res = await ac.get("/users/me/linked-accounts/")
        assert list_res.json() == []
