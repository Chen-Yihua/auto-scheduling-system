from pymongo import AsyncMongoClient
import os

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME   = os.getenv("MONGO_DB",  "auto_scheduling_db")

client = AsyncMongoClient(MONGO_URI)
db = client[DB_NAME]


async def ensure_indexes() -> None:
    """替常用查詢欄位建立索引，避免資料量變大後全表掃描。"""
    # 不用設 unique，因為_id 是 "{clerk_id}_{platform}"，已經保證同一組不會重複
    await db.linkedAccounts.create_index([("clerk_id", 1), ("platform", 1)])

    await db.manual_tasks.create_index("user_id")

    # 不用設 unique，因為舊資料如果已經有重複，建立唯一索引會失敗，伺服器就啟動不了
    # 在函式裡才 import，因為 platforms 也會 import 這個檔案，放在開頭會循環 import
    from platforms import PLATFORMS
    for platform in PLATFORMS.values():
        await platform.collection.create_index([("user_id", 1), ("id", 1)])
