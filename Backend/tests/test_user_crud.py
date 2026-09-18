"""
crud/user.py——先前完全沒有專屬測試（test_user.py 把整個 crud 層 mock 掉，
只測 router），這裡直接測 crud 函式本身，包含 PyMongoError 分支。
"""
import pytest
from pymongo.errors import DuplicateKeyError, PyMongoError
from fastapi import HTTPException

import crud.user as user_crud
from schemas.user import UserCreate, UserUpdate


def _user_create():
    return UserCreate(clerk_id="uid123", name="Alice", email="alice@example.com")


# ---------- create_user ----------

@pytest.mark.asyncio
async def test_create_user_returns_created_user(monkeypatch):
    async def mock_insert_one(doc):
        return None

    monkeypatch.setattr(user_crud.db.users, "insert_one", mock_insert_one)

    result = await user_crud.create_user(_user_create())

    assert result == {"id": "uid123", "name": "Alice", "email": "alice@example.com"}


@pytest.mark.asyncio
async def test_create_user_raises_409_when_already_exists(monkeypatch):
    async def mock_insert_one(doc):
        raise DuplicateKeyError("duplicate")

    monkeypatch.setattr(user_crud.db.users, "insert_one", mock_insert_one)

    with pytest.raises(HTTPException) as exc_info:
        await user_crud.create_user(_user_create())

    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_create_user_raises_500_when_db_down(monkeypatch):
    async def mock_insert_one(doc):
        raise PyMongoError("connection lost")

    monkeypatch.setattr(user_crud.db.users, "insert_one", mock_insert_one)

    with pytest.raises(HTTPException) as exc_info:
        await user_crud.create_user(_user_create())

    assert exc_info.value.status_code == 500


# ---------- get_user_by_clerk_id ----------

@pytest.mark.asyncio
async def test_get_user_by_clerk_id_returns_user_with_id_field(monkeypatch):
    async def mock_find_one(query):
        return {"_id": "uid123", "name": "Alice", "email": "alice@example.com"}

    monkeypatch.setattr(user_crud.db.users, "find_one", mock_find_one)

    result = await user_crud.get_user_by_clerk_id("uid123")

    assert result == {"id": "uid123", "name": "Alice", "email": "alice@example.com"}
    assert "_id" not in result


@pytest.mark.asyncio
async def test_get_user_by_clerk_id_returns_none_when_not_found(monkeypatch):
    async def mock_find_one(query):
        return None

    monkeypatch.setattr(user_crud.db.users, "find_one", mock_find_one)

    result = await user_crud.get_user_by_clerk_id("uid123")

    assert result is None


@pytest.mark.asyncio
async def test_get_user_by_clerk_id_raises_500_when_db_down(monkeypatch):
    async def mock_find_one(query):
        raise PyMongoError("connection lost")

    monkeypatch.setattr(user_crud.db.users, "find_one", mock_find_one)

    with pytest.raises(HTTPException) as exc_info:
        await user_crud.get_user_by_clerk_id("uid123")

    assert exc_info.value.status_code == 500


# ---------- update_user_by_clerk_id ----------

@pytest.mark.asyncio
async def test_update_user_by_clerk_id_raises_404_when_no_fields_to_update():
    with pytest.raises(HTTPException) as exc_info:
        await user_crud.update_user_by_clerk_id("uid123", UserUpdate())

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_update_user_by_clerk_id_succeeds_when_user_matched(monkeypatch):
    async def mock_update_one(query, update):
        return type("Result", (), {"matched_count": 1, "modified_count": 0})()

    monkeypatch.setattr(user_crud.db.users, "update_one", mock_update_one)

    # 不會丟例外就代表成功——即使新值跟舊值一樣（modified_count=0），
    # 只要真的找到這個使用者（matched_count=1）就不該被當成 404
    await user_crud.update_user_by_clerk_id("uid123", UserUpdate(name="Alice"))


@pytest.mark.asyncio
async def test_update_user_by_clerk_id_raises_404_when_user_not_matched(monkeypatch):
    async def mock_update_one(query, update):
        return type("Result", (), {"matched_count": 0, "modified_count": 0})()

    monkeypatch.setattr(user_crud.db.users, "update_one", mock_update_one)

    with pytest.raises(HTTPException) as exc_info:
        await user_crud.update_user_by_clerk_id("uid123", UserUpdate(name="Alice"))

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_update_user_by_clerk_id_raises_500_when_db_down(monkeypatch):
    async def mock_update_one(query, update):
        raise PyMongoError("connection lost")

    monkeypatch.setattr(user_crud.db.users, "update_one", mock_update_one)

    with pytest.raises(HTTPException) as exc_info:
        await user_crud.update_user_by_clerk_id("uid123", UserUpdate(name="Alice"))

    assert exc_info.value.status_code == 500


# ---------- delete_user_by_clerk_id ----------

@pytest.mark.asyncio
async def test_delete_user_by_clerk_id_returns_true_when_deleted(monkeypatch):
    async def mock_delete_one(query):
        return type("Result", (), {"deleted_count": 1})()

    monkeypatch.setattr(user_crud.db.users, "delete_one", mock_delete_one)

    result = await user_crud.delete_user_by_clerk_id("uid123")

    assert result is True


@pytest.mark.asyncio
async def test_delete_user_by_clerk_id_returns_false_when_nothing_deleted(monkeypatch):
    async def mock_delete_one(query):
        return type("Result", (), {"deleted_count": 0})()

    monkeypatch.setattr(user_crud.db.users, "delete_one", mock_delete_one)

    result = await user_crud.delete_user_by_clerk_id("uid123")

    assert result is False


@pytest.mark.asyncio
async def test_delete_user_by_clerk_id_raises_500_when_db_down(monkeypatch):
    async def mock_delete_one(query):
        raise PyMongoError("connection lost")

    monkeypatch.setattr(user_crud.db.users, "delete_one", mock_delete_one)

    with pytest.raises(HTTPException) as exc_info:
        await user_crud.delete_user_by_clerk_id("uid123")

    assert exc_info.value.status_code == 500
