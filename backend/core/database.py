from pymongo import AsyncMongoClient
import os

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME   = os.getenv("MONGO_DB",  "auto_scheduling_db")

client = AsyncMongoClient(MONGO_URI)
db = client[DB_NAME]


async def ensure_indexes() -> None:
    """替常用查詢欄位建立索引，避免資料量變大後全表掃描。"""
    # 不用 unique：_id 是 "{clerk_id}_{platform}"，已保證不重複
    await db.linkedAccounts.create_index([("clerk_id", 1), ("platform", 1)])

    await db.manual_tasks.create_index("user_id")

    # 不用 unique：已有重複資料時建立會失敗，伺服器會無法啟動
    # 在函式內 import 以避免循環 import
    from platforms import PLATFORMS
    for platform in PLATFORMS.values():
        await platform.collection.create_index([("user_id", 1), ("id", 1)])
