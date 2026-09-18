"""
端對端「情境」測試（跟 test_manual_task_scenario.py 同一個精神）：把使用者連結
GitHub 帳號的一整串操作串起來，透過真的 HTTP 呼叫 main.app，確認每一步寫進
mongomock 的資料，下一步真的讀得到、也真的反映了更新，而不是每個 endpoint
各自獨立 mock 掉資料庫。

真的會打外部 GitHub API 的 `fetch_github_userinfo` monkeypatch 掉，避免測試
依賴真的網路；其餘（加密、遮罩、mongomock 讀寫）全部走真的程式碼路徑。
"""
import pytest
from fastapi import status
from httpx import AsyncClient
from httpx._transports.asgi import ASGITransport

from main import app
from db.security import get_current_clerk_user
import crud.linkedAccount as linked_mod

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
    call_count = {"n": 0}

    async def mock_fetch_github_userinfo(token):
        call_count["n"] += 1
        # 回傳值隨呼叫次數變化，才能證明「更新」那一步真的重新驗證、
        # 重新寫入了新的值，而不是沿用建立當下的舊資料
        return {
            "username": f"mock_user_v{call_count['n']}",
            "avatar_url": f"https://mock.avatar/v{call_count['n']}",
        }

    monkeypatch.setattr(linked_mod, "fetch_github_userinfo", mock_fetch_github_userinfo)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. 連結 GitHub 帳號
        create_res = await ac.post(
            "/user/linked-accounts/create",
            json={
                "platform": "github",
                "status": "connected",
                "username": "",
                "apiKey": "token-v1",
            },
        )
        assert create_res.status_code == status.HTTP_200_OK, create_res.text
        assert create_res.json()["linkedAccounts"]["github"]["username"] == "mock_user_v1"

        # 2. 列表裡看得到，而且金鑰是遮罩過的，不是明文
        list_res = await ac.get("/user/linked-accounts/me")
        assert list_res.status_code == status.HTTP_200_OK
        accounts = list_res.json()
        assert len(accounts) == 1
        github_account = accounts[0]
        assert github_account["platform"] == "github"
        assert github_account["username"] == "mock_user_v1"
        assert github_account["apiKey"] != "token-v1"  # 絕不回傳明文
        assert github_account["apiKey"].endswith("v1")  # mask_secret 保留最後幾碼

        # 3. 更新金鑰（前端實際送出的形狀：{"platform", "data": {"payload": {...}}}）
        update_res = await ac.put(
            "/user/linked-accounts/",
            json={
                "platform": "github",
                "data": {"payload": {"apiKey": "token-v2"}},
            },
        )
        assert update_res.status_code == status.HTTP_200_OK, update_res.text
        assert update_res.json()["success"] is True
        assert call_count["n"] == 2  # 更新有重新驗證一次新 token

        # 4. 更新有真的落地：使用者名稱反映的是第二次驗證拿到的新值
        list_after_update = await ac.get("/user/linked-accounts/me")
        assert list_after_update.json()[0]["username"] == "mock_user_v2"

        # 5. 刪除
        delete_res = await ac.delete("/user/linked-accounts/github")
        assert delete_res.status_code == status.HTTP_200_OK
        assert delete_res.json()["deleted"] is True

        # 6. 刪除後沒有任何連結帳號 -> 是正常狀態，回 200 + 空陣列，不是 404
        list_after_delete = await ac.get("/user/linked-accounts/me")
        assert list_after_delete.status_code == status.HTTP_200_OK
        assert list_after_delete.json() == []


@pytest.mark.asyncio
async def test_moodle_linked_account_rejects_wrong_password_and_leaves_nothing_behind(monkeypatch):
    """
    Moodle 連結帳號會真的觸發 Selenium 登入驗證（見 crud/moodle.py）。
    這裡驗證帳密錯誤時：(a) API 回 401，(b) 完全沒有東西被寫進 DB——
    不會留下一筆「看起來已連結、其實密碼從沒驗證成功過」的殘影資料。
    """
    from crud.errors import NonRetryableError

    # verify_moodle_login 本身是同步函式（真正的實作用 Selenium，是阻塞的），
    # crud/linkedAccount.py 用 run_in_threadpool 呼叫它——mock 也要是同步的，
    # 不然 run_in_threadpool 只會拿到一個沒被 await 的 coroutine，不會真的拋出例外
    def mock_verify_login_fails(username, password):
        raise NonRetryableError(f"Moodle 登入失敗，使用者：{username}")

    monkeypatch.setattr(linked_mod, "verify_moodle_login", mock_verify_login_fails)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        create_res = await ac.post(
            "/user/linked-accounts/create",
            json={
                "platform": "moodle",
                "status": "connected",
                "username": "stu001",
                "password": "wrong-password",
            },
        )
        assert create_res.status_code == status.HTTP_401_UNAUTHORIZED

        # 驗證失敗不該留下任何殘影資料——沒有任何連結帳號，回 200 + 空陣列，不是 404
        list_res = await ac.get("/user/linked-accounts/me")
        assert list_res.status_code == status.HTTP_200_OK
        assert list_res.json() == []
