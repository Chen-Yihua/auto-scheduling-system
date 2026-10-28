from pymongo import AsyncMongoClient
import os

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME   = os.getenv("MONGO_DB",  "auto_scheduling_db")

client = AsyncMongoClient(MONGO_URI)
db = client[DB_NAME]


async def ensure_indexes() -> None:
    """替常用查詢欄位建立索引，避免資料量變大後全表掃描。"""
    # 查單筆帳號用 _id（"{clerk_id}_{platform}"），這個索引給「列出使用者所有帳號」用
    await db.linkedAccounts.create_index("clerk_id")

    await db.manual_tasks.create_index("user_id")
    # 防止同一次建立請求重送時產生重複任務；沒帶 key 的任務不受限制
    await db.manual_tasks.create_index(
        [("user_id", 1), ("idempotency_key", 1)],
        unique=True,
        partialFilterExpression={"idempotency_key": {"$type": "string"}},
    )

    # unique：同一使用者同時同步兩次時，資料庫才會擋下重複的項目
    # 在函式內 import 以避免循環 import
    from platforms import PLATFORMS
    for platform in PLATFORMS.values():
        await platform.collection.create_index([("user_id", 1), ("id", 1)], unique=True)
