from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
import os

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME   = os.getenv("MONGO_DB",  "auto_scheduling_db")

client = AsyncIOMotorClient(MONGO_URI)

# 指定使用哪個資料庫
db = client[DB_NAME]

#取得資料庫連線
async def get_db():
    return db


async def ensure_indexes() -> None:
    """
    替常用查詢欄位建立索引，避免資料量變大後全表掃描。
    users / googleCalendarTokens 用 clerk_id 當 _id，MongoDB 本身就會索引，不需要額外處理。
    """
    # linkedAccounts._id 已經是 "{clerk_id}_{platform}" 組成，天然唯一，
    # 這裡不用 unique=True，純粹加速 clerk_id / (clerk_id, platform) 查詢
    await db.linkedAccounts.create_index([("clerk_id", 1), ("platform", 1)])

    # manual_tasks 用應用層自產的 uuid4 字串 `id` 當實際查詢鍵（不是 Mongo 原生 _id），
    # 要自己補 unique index 才能保證唯一性、也才不用每次查詢都全表掃描
    await db.manual_tasks.create_index("id", unique=True)
    await db.manual_tasks.create_index("user_id")

    # github_issues / jira_issues / moodle_assignments 都用 (user_id, id) 當
    # sync_platform_items()（crud/external_sync.py）upsert 的唯一鍵條件，
    # 這裡不設 unique=True——避免萬一舊資料已經有重複值時，建立索引直接讓啟動失敗
    await db.github_issues.create_index([("user_id", 1), ("id", 1)])
    await db.jira_issues.create_index([("user_id", 1), ("id", 1)])
    await db.moodle_assignments.create_index([("user_id", 1), ("id", 1)])