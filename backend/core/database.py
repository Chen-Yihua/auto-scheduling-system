import os
from typing import Any

from pymongo import AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME   = os.getenv("MONGO_DB",  "auto_scheduling_db")

# 連線在 app 啟動（main.py 的 lifespan）時才建立、關閉時釋放；import 時不連線，測試才不會連到真的 MongoDB
client: AsyncMongoClient | None = None
db: Any = None
_owns_client = False


def get_db() -> AsyncDatabase:
    """目前的資料庫。測試會把 db 換成記憶體資料庫，所以每次呼叫都重新讀 db，不能在 import 時存起來。"""
    if db is None:
        raise RuntimeError("資料庫還沒連線：要在 app 啟動後才能使用")
    return db


async def open_database() -> None:
    global client, db, _owns_client
    # 測試已經換成記憶體資料庫時保留它，不另外連線
    if db is not None:
        return
    # MongoDB 的日期只存 UTC、不存時區；不設 tz_aware 讀出的 datetime 不帶時區，回應序列化時就沒有 Z
    client = AsyncMongoClient(MONGO_URI, tz_aware=True)
    db = client[DB_NAME]
    _owns_client = True


async def close_database() -> None:
    """只關自己建立的連線；測試換進來的記憶體資料庫由測試自己關。"""
    global client, db, _owns_client
    if client is not None and _owns_client:
        await client.close()
        client = None
        db = None
        _owns_client = False


async def ensure_indexes() -> None:
    """替常用查詢欄位建立索引，避免資料量變大後全表掃描。"""
    database = get_db()
    # 查單筆帳號用 _id（"{clerk_id}_{platform}"），這個索引給「列出使用者所有帳號」用
    await database.linkedAccounts.create_index("clerk_id")

    await database.manual_tasks.create_index("user_id")
    # 防止同一次建立請求重送時產生重複任務；沒帶 key 的任務不受限制
    await database.manual_tasks.create_index(
        [("user_id", 1), ("idempotency_key", 1)],
        unique=True,
        partialFilterExpression={"idempotency_key": {"$type": "string"}},
    )
    # 查主任務底下的子任務
    await database.manual_tasks.create_index([("user_id", 1), ("parent_id", 1)])

    # unique：同一使用者同時同步兩次時，資料庫才會擋下重複的項目
    # 在函式內 import 以避免循環 import
    from platforms import PLATFORMS
    for platform in PLATFORMS.values():
        await platform.collection.create_index([("user_id", 1), ("id", 1)], unique=True)
