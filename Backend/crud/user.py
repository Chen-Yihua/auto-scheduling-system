import logging

from db.mongodb import db
from schemas.user import UserCreate, UserUpdate
from pymongo.errors import DuplicateKeyError, PyMongoError
from fastapi import HTTPException

logger = logging.getLogger(__name__)

# 建立使用者並回報重複使用者錯誤
async def create_user(user: UserCreate) -> dict:
    doc = user.model_dump()
    doc["_id"] = doc.pop("clerk_id")  # 直接用 Clerk id 當 _id
    try:
        await db.users.insert_one(doc)
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail="User already exists")
    except PyMongoError:
        logger.exception("Failed to create user, clerk_id=%s", doc["_id"])
        raise HTTPException(status_code=500, detail="建立使用者失敗，請稍後再試")

    return {
        "id": doc["_id"],
        "name": doc.get("name"),
        "email": doc.get("email"),
    }

# 透過 clerk_id 取得使用者
async def get_user_by_clerk_id(clerk_id: str):
    try:
        user = await db.users.find_one({"_id": clerk_id})  # 直接查 _id，不轉 ObjectId
    except PyMongoError:
        logger.exception("Failed to fetch user, clerk_id=%s", clerk_id)
        raise HTTPException(status_code=500, detail="查詢使用者失敗，請稍後再試")

    if not user:
        return None
    user["id"] = user["_id"]  # 保留一個 id 欄位給前端用
    del user["_id"]
    return user

# 更新使用者
# 可更新欄位限制交給 UserUpdate 這個 Pydantic model 把關（避免 mass assignment，
# 例如竄改 clerk_id 或未來新增的敏感欄位），這裡只需把「沒填的欄位」過濾掉，
# 讓部分更新不會被 None 覆蓋掉原本的值
async def update_user_by_clerk_id(clerk_id: str, data: UserUpdate) -> bool:
    filtered_data = data.model_dump(exclude_unset=True)
    if not filtered_data:
        return False

    try:
        result = await db.users.update_one({"_id": clerk_id}, {"$set": filtered_data})
    except PyMongoError:
        logger.exception("Failed to update user, clerk_id=%s", clerk_id)
        raise HTTPException(status_code=500, detail="更新使用者失敗，請稍後再試")

    # 用 matched_count（有沒有找到這筆文件）而不是 modified_count（值是否真的變了）——
    # 如果新值跟舊值一樣，MongoDB 會判定沒有實際變更、modified_count 是 0，
    # 但這種情況使用者明明存在，不該被當成「找不到」回 404
    return result.matched_count > 0

# 刪除使用者
async def delete_user_by_clerk_id(clerk_id: str) -> bool:
    try:
        result = await db.users.delete_one({"_id": clerk_id})
    except PyMongoError:
        logger.exception("Failed to delete user, clerk_id=%s", clerk_id)
        raise HTTPException(status_code=500, detail="刪除使用者失敗，請稍後再試")

    return result.deleted_count > 0
