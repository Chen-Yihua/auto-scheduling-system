import pytest
from fastapi import HTTPException
from routers import linkedAccount as router
import crud.linkedAccount as crud_mod
from schemas.linkedAccount import LinkedAccountCreate

mock_user = {"sub": "test_user_123"}


@pytest.mark.asyncio
async def test_get_current_linked_accounts(monkeypatch):
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
    async def mock_get_accounts(clerk_id):
        return []

    monkeypatch.setattr(crud_mod, "get_linked_accounts_by_clerk_id", mock_get_accounts)

    with pytest.raises(HTTPException) as exc_info:
        await router.get_current_linked_accounts(clerk_user=mock_user)
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_create_linked_account(monkeypatch):
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

    result = await router.create_linked_account(account_data=account, clerk_user=mock_user)
    assert result["linkedAccounts"]["github"]["status"] == "connected"


@pytest.mark.asyncio
async def test_update_linked_account(monkeypatch):
    async def mock_update(clerk_id, platform, data):
        return True

    monkeypatch.setattr(crud_mod, "update_linked_account_by_clerk_id", mock_update)

    result = await router.update_linked_account(
        platform="github",
        data={"status": "connected"},
        clerk_user=mock_user
    )
    assert result["success"] is True


@pytest.mark.asyncio
async def test_update_linked_account_fail(monkeypatch):
    async def mock_update(clerk_id, platform, data):
        return False

    monkeypatch.setattr(crud_mod, "update_linked_account_by_clerk_id", mock_update)

    with pytest.raises(HTTPException) as exc_info:
        await router.update_linked_account(
            platform="github",
            data={"status": "connected"},
            clerk_user=mock_user
        )
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_delete_linked_account(monkeypatch):
    async def mock_delete(composite_id):
        return True

    monkeypatch.setattr(crud_mod, "delete_linked_account_by_id", mock_delete)

    result = await router.delete_linked_account(
        platform="github",
        clerk_user=mock_user
    )
    assert result["deleted"] is True


@pytest.mark.asyncio
async def test_delete_linked_account_fail(monkeypatch):
    async def mock_delete(composite_id):
        return False

    monkeypatch.setattr(crud_mod, "delete_linked_account_by_id", mock_delete)

    with pytest.raises(HTTPException) as exc_info:
        await router.delete_linked_account(
            platform="github",
            clerk_user=mock_user
        )
    assert exc_info.value.status_code == 404