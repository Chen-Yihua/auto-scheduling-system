from core.database import db
from schemas.user import UserCreate, UserUpdate
from pymongo.errors import DuplicateKeyError
from fastapi import HTTPException

async def create_user(user: UserCreate) -> dict:
    doc = user.model_dump()
    doc["_id"] = doc.pop("clerk_id")
    try:
        await db.users.insert_one(doc)
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail="User already exists")

    return {
        "id": doc["_id"],
        "name": doc.get("name"),
        "email": doc.get("email"),
    }

async def get_user_by_clerk_id(clerk_id: str):
    user = await db.users.find_one({"_id": clerk_id})
    if not user:
        return None
    user["id"] = user["_id"]
    del user["_id"]
    return user

# 可更新的欄位由 UserUpdate 限制；exclude_unset 讓沒帶的欄位保留原值
async def update_user_by_clerk_id(clerk_id: str, data: UserUpdate) -> None:
    filtered_data = data.model_dump(exclude_unset=True)
    if not filtered_data:
        raise HTTPException(status_code=404, detail="User not found or no changes made")

    result = await db.users.update_one({"_id": clerk_id}, {"$set": filtered_data})

    # 用 matched_count：值沒變時 modified_count 是 0，但使用者存在，不該回 404
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found or no changes made")

async def delete_user_by_clerk_id(clerk_id: str) -> bool:
    result = await db.users.delete_one({"_id": clerk_id})
    return result.deleted_count > 0
