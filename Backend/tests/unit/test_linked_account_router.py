import pytest
from unittest.mock import MagicMock
from fastapi import HTTPException
from routers import linkedAccount as router
import crud.linkedAccount as crud_mod
from schemas.linkedAccount import LinkedAccountCreate

mock_user = {"sub": "test_user_123"}


@pytest.mark.asyncio
async def test_get_current_linked_accounts(monkeypatch):
    """回傳 crud 查到的綁定帳號清單（router 只是轉手）。"""
    async def mock_get_accounts(clerk_id):
        return [
            {
                "platform": "github",
                "username": "tester",
                "status": "connected",
                "avatar_url": "https://avatar"
            }
        ]

    monkeypatch.setattr(crud_mod, "get_linked_accounts_by_clerk_id", mock_get_accounts)

    result = await router.get_current_linked_accounts(clerk_user=mock_user)
    assert result[0]["platform"] == "github"


@pytest.mark.asyncio
async def test_get_current_linked_accounts_empty(monkeypatch):
    """沒有任何綁定帳號是正常狀態 → 回空清單，不是 404。"""
    async def mock_get_accounts(clerk_id):
        return []

    monkeypatch.setattr(crud_mod, "get_linked_accounts_by_clerk_id", mock_get_accounts)

    result = await router.get_current_linked_accounts(clerk_user=mock_user)
    assert result == []


@pytest.mark.asyncio
async def test_create_linked_account(monkeypatch):
    """建立綁定帳號成功 → 回傳 crud 建立的結果（GitHub 的 status 為 connected）。"""
    account = LinkedAccountCreate(
        platform="github",
        username="",
        status="",
        apiKey="token123",
        domain=None,
    )

    async def mock_create(clerk_id, account):
        return {
            "linkedAccounts": {
                "github": {
                    "username": "tester",
                    "avatar_url": "https://avatar",
                    "status": "connected",
                }
            }
        }

    monkeypatch.setattr(crud_mod, "create_linked_account", mock_create)

    result = await router.create_linked_account(request=MagicMock(), account_data=account, clerk_user=mock_user)
    assert result["linkedAccounts"]["github"]["status"] == "connected"


@pytest.mark.asyncio
async def test_update_linked_account(monkeypatch):
    """更新成功（crud 回傳 True）→ 回 {"success": True}。"""
    async def mock_update(clerk_id, platform, data):
        return True

    monkeypatch.setattr(crud_mod, "update_linked_account_by_clerk_id", mock_update)

    result = await router.update_linked_account(
        request=MagicMock(),
        platform="github",
        data={"status": "connected"},
        clerk_user=mock_user
    )
    assert result["success"] is True


@pytest.mark.asyncio
async def test_update_linked_account_fail(monkeypatch):
    """crud 回傳 False（找不到帳號，或沒有合法欄位可更新）→ 404。"""
    async def mock_update(clerk_id, platform, data):
        return False

    monkeypatch.setattr(crud_mod, "update_linked_account_by_clerk_id", mock_update)

    with pytest.raises(HTTPException) as exc_info:
        await router.update_linked_account(
            request=MagicMock(),
            platform="github",
            data={"status": "connected"},
            clerk_user=mock_user
        )
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_delete_linked_account(monkeypatch):
    """刪除成功 → 回 {"deleted": True}。"""
    async def mock_delete(composite_id):
        return None  # 成功時 crud 不回傳東西，沒 raise 就代表成功

    monkeypatch.setattr(crud_mod, "delete_linked_account_by_id", mock_delete)

    result = await router.delete_linked_account(
        platform="github",
        clerk_user=mock_user
    )
    assert result["deleted"] is True


@pytest.mark.asyncio
async def test_delete_linked_account_fail(monkeypatch):
    """查無此帳號 → 404。"""
    # 這個 404 是 crud 丟出來的，router 沒有另外判斷
    async def mock_delete(composite_id):
        raise HTTPException(status_code=404, detail="Linked account not found")

    monkeypatch.setattr(crud_mod, "delete_linked_account_by_id", mock_delete)

    with pytest.raises(HTTPException) as exc_info:
        await router.delete_linked_account(
            platform="github",
            clerk_user=mock_user
        )
    assert exc_info.value.status_code == 404