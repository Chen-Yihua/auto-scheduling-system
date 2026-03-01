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