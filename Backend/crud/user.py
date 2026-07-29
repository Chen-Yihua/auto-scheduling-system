from db.mongodb import db
from schemas.user import UserCreate
from pymongo.errors import DuplicateKeyError
from fastapi import HTTPException

# 建立使用者並回報重複使用者錯誤
async def create_user(user: UserCreate) -> str:
    doc = user.dict()
    doc["_id"] = doc.pop("clerk_id")  # 直接用 Clerk id 當 _id
    try:
        await db.users.insert_one(doc)
        return {
        "id": doc["_id"],
        "name": doc.get("name"),
        "email": doc.get("email"),
    }
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail="User already exists")

# 透過 clerk_id 取得使用者
async def get_user_by_clerk_id(clerk_id: str):
    user = await db.users.find_one({"_id": clerk_id})  # 直接查 _id，不轉 ObjectId
    if not user:
        return None
    user["id"] = user["_id"]  # 保留一個 id 欄位給前端用
    del user["_id"]
    return user

# 更新使用者
async def update_user_by_clerk_id(clerk_id: str, data: dict):
    result = await db.users.update_one({"_id": clerk_id}, {"$set": data})
    return result.modified_count > 0

# 刪除使用者
async def delete_user_by_clerk_id(clerk_id: str):
    result = await db.users.delete_one({"_id": clerk_id})
    return result.deleted_count > 0
