# 直接呼叫 router 函式（await github_router.get_github_issues(...)）測試它自己的判斷分支：
# 查不到帳號、解密失敗、同步失敗各回什麼狀態碼，以及有沒有設定回應 header。
# 同步流程（重試、退回舊資料、寫入資料庫）由 test_external_sync.py 負責，這裡直接把它換成假的。
# 不經過 HTTP，所以不涉及路由註冊、登入驗證、response_model —— 那些由 test_github_api.py 負責。
import pytest
from datetime import datetime, timezone
from fastapi import HTTPException, Response
import routers.github as github_router
from db.crypto import encrypt_secret
from crud.errors import NonRetryableError

mock_user = {"sub": "test_user_123"}


@pytest.mark.asyncio
async def test_get_github_issues_success(monkeypatch):
    """成功流程：查到帳號 → 解密 token → 抓 GitHub → 轉成統一格式後回傳清單，X-Data-Stale 為 false；抓資料時用的是解密後的明文 token，不是資料庫裡的密文。"""
    fetch_calls = []

    class MockLinkedAccounts:
        async def find_one(self, query):
            return {"apiKey": encrypt_secret("fake_token")}

    async def mock_fetch_github_user_issues(token):
        fetch_calls.append(token)
        return [
            {
                "number": 999,
                "title": "Fix bug",
                "state": "open",
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-02T00:00:00Z",
                "html_url": "https://github.com/example/repo/issues/999",
                "user": {"login": "tester", "avatar_url": "https://avatar"},
                "labels": [{"name": "bug"}],
                "comments": 2,
            }
        ]

    async def mock_sync(user_id, fetch_fn):
        # 真的執行 router 交給 sync 的 fetch_fn，才測得到「解密 → 抓資料 → 轉格式」這段
        return (await fetch_fn(), False, None, False)

    monkeypatch.setattr(github_router.db, "linkedAccounts", MockLinkedAccounts())
    monkeypatch.setattr(github_router, "fetch_github_user_issues", mock_fetch_github_user_issues)
    monkeypatch.setattr(github_router, "sync_github_issues", mock_sync)

    response = Response()
    result = await github_router.get_github_issues(response=response, clerk_user=mock_user)

    assert result == [
        {
            "id": 999,
            "title": "Fix bug",
            "status": "open",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-02T00:00:00Z",
            "url": "https://github.com/example/repo/issues/999",
            "isPR": False,
            "author": {"username": "tester", "avatar": "https://avatar"},
            "labels": ["bug"],
            "comments": 2,
        }
    ]
    assert response.headers["X-Data-Stale"] == "false"
    assert fetch_calls == ["fake_token"]


@pytest.mark.asyncio
async def test_get_github_issues_raises_400_when_token_missing(monkeypatch):
    """綁定帳號存在但沒有 apiKey（等於還沒設定 token）→ 回 400 "No GitHub token linked"。"""
    class MockLinkedAccounts:
        async def find_one(self, query):
            return {}  # 沒有 apiKey

    monkeypatch.setattr(github_router.db, "linkedAccounts", MockLinkedAccounts())

    with pytest.raises(HTTPException) as exc_info:
        await github_router.get_github_issues(clerk_user=mock_user)

    assert exc_info.value.status_code == 400
    assert "No GitHub token linked" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_get_github_issues_raises_500_when_decrypt_fails(monkeypatch):
    """token 解密失敗（資料壞掉或金鑰不對）→ 回 500。"""
    class MockLinkedAccounts:
        async def find_one(self, query):
            return {"apiKey": "not-actually-encrypted"}

    monkeypatch.setattr(github_router.db, "linkedAccounts", MockLinkedAccounts())

    with pytest.raises(HTTPException) as exc_info:
        await github_router.get_github_issues(clerk_user=mock_user)

    assert exc_info.value.status_code == 500


@pytest.mark.asyncio
async def test_get_github_issues_raises_500_on_unexpected_sync_error(monkeypatch):
    """同步時出現未預期的錯誤 → 回 500 和固定中文訊息；內部錯誤原因只寫進 log，不回傳給前端。"""
    class MockLinkedAccounts:
        async def find_one(self, query):
            return {"apiKey": encrypt_secret("fake_token")}

    async def mock_sync(user_id, fetch_fn):
        raise Exception("GitHub API down")

    monkeypatch.setattr(github_router.db, "linkedAccounts", MockLinkedAccounts())
    monkeypatch.setattr(github_router, "sync_github_issues", mock_sync)

    with pytest.raises(HTTPException) as exc_info:
        await github_router.get_github_issues(clerk_user=mock_user)

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == "無法取得 GitHub 資料，請稍後再試"


@pytest.mark.asyncio
async def test_get_github_issues_token_expired_raises_401(monkeypatch):
    """token 失效（NonRetryableError）要回 401，跟一般暫時性失敗（500）分開——重試也沒用，使用者要重新連結帳號才能解決。"""
    class MockLinkedAccounts:
        async def find_one(self, query):
            return {"apiKey": encrypt_secret("fake_token")}

    async def mock_sync(user_id, fetch_fn):
        raise NonRetryableError("GitHub API failed: 401 Unauthorized")

    monkeypatch.setattr(github_router.db, "linkedAccounts", MockLinkedAccounts())
    monkeypatch.setattr(github_router, "sync_github_issues", mock_sync)

    with pytest.raises(HTTPException) as exc_info:
        await github_router.get_github_issues(clerk_user=mock_user)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "GitHub 授權已失效，請重新連結帳號"


@pytest.mark.asyncio
async def test_get_github_issues_sets_auth_error_header(monkeypatch):
    """token 已失效但還有舊資料可退回時：回舊資料，並設定 X-Auth-Error、X-Data-Stale、X-Synced-At，前端才知道要顯示「請重新連結」和「資料可能過期」。"""
    class MockLinkedAccounts:
        async def find_one(self, query):
            return {"apiKey": encrypt_secret("fake_token")}

    synced_at = datetime(2026, 9, 10, tzinfo=timezone.utc)

    async def mock_sync(user_id, fetch_fn):
        # stale=True、auth_error=True：token 失效但還有快取可以退回顯示
        return ([{"id": 1}], True, synced_at, True)

    monkeypatch.setattr(github_router.db, "linkedAccounts", MockLinkedAccounts())
    monkeypatch.setattr(github_router, "sync_github_issues", mock_sync)

    response = Response()
    result = await github_router.get_github_issues(response=response, clerk_user=mock_user)

    assert result == [{"id": 1}]
    assert response.headers["X-Auth-Error"] == "true"
    assert response.headers["X-Data-Stale"] == "true"
    assert response.headers["X-Synced-At"] == synced_at.isoformat()
