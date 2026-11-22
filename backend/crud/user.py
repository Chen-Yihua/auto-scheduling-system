from core.database import db
from schemas.schedule import SavedSchedulePreferences
from schemas.user import UserCreate, UserUpdate
from pymongo.errors import DuplicateKeyError
from core.errors import ConflictError, InvalidRequestError, NotFoundError
from platforms import PLATFORMS

async def create_user(user: UserCreate) -> dict:
    doc = user.model_dump()
    doc["_id"] = doc.pop("clerk_id")
    try:
        await db.users.insert_one(doc)
    except DuplicateKeyError:
        raise ConflictError("User already exists")

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
        raise InvalidRequestError("沒有可更新的欄位")

    result = await db.users.update_one({"_id": clerk_id}, {"$set": filtered_data})

    # 用 matched_count：值沒變時 modified_count 是 0，但使用者存在，不該回 404
    if result.matched_count == 0:
        raise NotFoundError("User not found or no changes made")

async def get_schedule_preferences(clerk_id: str) -> SavedSchedulePreferences:
    """沒存過偏好（舊文件沒有這個欄位）時回傳預設值。"""
    user = await db.users.find_one({"_id": clerk_id}, {"schedule_preferences": 1})
    if not user:
        raise NotFoundError("User not found")
    return SavedSchedulePreferences.model_validate(user.get("schedule_preferences") or {})

async def save_schedule_preferences(clerk_id: str, preferences: SavedSchedulePreferences) -> None:
    """整份換掉，只留最近一次。"""
    result = await db.users.update_one(
        {"_id": clerk_id},
        {"$set": {"schedule_preferences": preferences.model_dump()}},
    )
    # 用 matched_count：值沒變時 modified_count 是 0，但使用者存在
    if result.matched_count == 0:
        raise NotFoundError("User not found")

async def delete_user_by_clerk_id(clerk_id: str) -> bool:
    """刪除使用者和他名下的所有資料，回傳使用者是否存在。"""
    # users 最後才刪：中途失敗時使用者還在，可以重試
    await db.manual_tasks.delete_many({"user_id": clerk_id})
    await db.linkedAccounts.delete_many({"clerk_id": clerk_id})
    await db.googleCalendarTokens.delete_one({"_id": clerk_id})
    for platform in PLATFORMS.values():
        await platform.collection.delete_many({"user_id": clerk_id})

    result = await db.users.delete_one({"_id": clerk_id})
    return result.deleted_count > 0
