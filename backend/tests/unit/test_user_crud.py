"""crud/user.py 的函式。"""
import pytest
from core.errors import ConflictError, NotFoundError
from pymongo.errors import DuplicateKeyError

import crud.user as user_crud
from schemas.user import UserCreate, UserUpdate


def _user_create():
    return UserCreate(clerk_id="uid123", name="Alice", email="alice@example.com")


# ---------- create_user ----------

@pytest.mark.asyncio
async def test_create_user_returns_created_user(monkeypatch):
    """建立成功 → 回傳新使用者資料（id 用 clerk_id，含 name 和 email）。"""
    async def mock_insert_one(doc):
        return None

    monkeypatch.setattr(user_crud.db.users, "insert_one", mock_insert_one)

    result = await user_crud.create_user(_user_create())

    assert result == {"id": "uid123", "name": "Alice", "email": "alice@example.com"}


@pytest.mark.asyncio
async def test_create_user_raises_409_when_already_exists(monkeypatch):
    """使用者已經存在 → 409。"""
    async def mock_insert_one(doc):
        raise DuplicateKeyError("duplicate")

    monkeypatch.setattr(user_crud.db.users, "insert_one", mock_insert_one)

    with pytest.raises(ConflictError) as exc_info:
        await user_crud.create_user(_user_create())



# ---------- get_user_by_clerk_id ----------

@pytest.mark.asyncio
async def test_get_user_by_clerk_id_returns_user_with_id_field(monkeypatch):
    """查到使用者 → 回傳的資料用 id 欄位識別，不含資料庫內部的 _id。"""
    async def mock_find_one(query):
        return {"_id": "uid123", "name": "Alice", "email": "alice@example.com"}

    monkeypatch.setattr(user_crud.db.users, "find_one", mock_find_one)

    result = await user_crud.get_user_by_clerk_id("uid123")

    assert result == {"id": "uid123", "name": "Alice", "email": "alice@example.com"}
    assert "_id" not in result


@pytest.mark.asyncio
async def test_get_user_by_clerk_id_returns_none_when_not_found(monkeypatch):
    """查不到使用者 → 回傳 None（要不要回 404 由呼叫端決定）。"""
    async def mock_find_one(query):
        return None

    monkeypatch.setattr(user_crud.db.users, "find_one", mock_find_one)

    result = await user_crud.get_user_by_clerk_id("uid123")

    assert result is None


# ---------- update_user_by_clerk_id ----------

@pytest.mark.asyncio
async def test_update_user_by_clerk_id_raises_404_when_no_fields_to_update():
    """沒有任何要更新的欄位 → 404。"""
    with pytest.raises(NotFoundError) as exc_info:
        await user_crud.update_user_by_clerk_id("uid123", UserUpdate())



@pytest.mark.asyncio
async def test_update_user_by_clerk_id_succeeds_when_user_matched(monkeypatch):
    """更新成功：就算新值跟舊值一樣（沒有實際變動），只要使用者存在，就不該被當成 404。"""
    async def mock_update_one(query, update):
        return type("Result", (), {"matched_count": 1, "modified_count": 0})()

    monkeypatch.setattr(user_crud.db.users, "update_one", mock_update_one)

    await user_crud.update_user_by_clerk_id("uid123", UserUpdate(name="Alice"))


@pytest.mark.asyncio
async def test_update_user_by_clerk_id_raises_404_when_user_not_matched(monkeypatch):
    """找不到這個使用者 → 404。"""
    async def mock_update_one(query, update):
        return type("Result", (), {"matched_count": 0, "modified_count": 0})()

    monkeypatch.setattr(user_crud.db.users, "update_one", mock_update_one)

    with pytest.raises(NotFoundError) as exc_info:
        await user_crud.update_user_by_clerk_id("uid123", UserUpdate(name="Alice"))



# ---------- delete_user_by_clerk_id ----------

@pytest.mark.asyncio
async def test_delete_user_by_clerk_id_returns_true_when_deleted(monkeypatch):
    """刪除成功 → 回傳 True。"""
    async def mock_delete_one(query):
        return type("Result", (), {"deleted_count": 1})()

    monkeypatch.setattr(user_crud.db.users, "delete_one", mock_delete_one)

    result = await user_crud.delete_user_by_clerk_id("uid123")

    assert result is True


@pytest.mark.asyncio
async def test_delete_user_by_clerk_id_returns_false_when_nothing_deleted(monkeypatch):
    """沒有任何使用者被刪除 → 回傳 False（由 router 轉成 404）。"""
    async def mock_delete_one(query):
        return type("Result", (), {"deleted_count": 0})()

    monkeypatch.setattr(user_crud.db.users, "delete_one", mock_delete_one)

    result = await user_crud.delete_user_by_clerk_id("uid123")

    assert result is False


@pytest.mark.asyncio
async def test_delete_user_by_clerk_id_removes_all_data_of_that_user_only():
    """刪除使用者 → 他的任務、綁定帳號、Google token、平台項目都要刪掉，其他使用者的資料不受影響。"""
    db = user_crud.db
    collections = {
        "manual_tasks": "user_id",
        "linkedAccounts": "clerk_id",
        "github_issues": "user_id",
        "jira_issues": "user_id",
        "moodle_assignments": "user_id",
    }
    for owner in ("del_alice", "del_bob"):
        await db.users.insert_one({"_id": owner, "email": f"{owner}@example.com", "name": owner})
        await db.googleCalendarTokens.insert_one({"_id": owner, "access_token": "x"})
        for name, owner_field in collections.items():
            await getattr(db, name).insert_one({"_id": f"{owner}_{name}", owner_field: owner})

    assert await user_crud.delete_user_by_clerk_id("del_alice") is True

    assert await db.users.find_one({"_id": "del_alice"}) is None
    assert await db.googleCalendarTokens.find_one({"_id": "del_alice"}) is None
    assert await db.googleCalendarTokens.find_one({"_id": "del_bob"}) is not None
    for name, owner_field in collections.items():
        assert await getattr(db, name).count_documents({owner_field: "del_alice"}) == 0
        assert await getattr(db, name).count_documents({owner_field: "del_bob"}) == 1
