import os
import pytest
import pytest_asyncio
from cryptography.fernet import Fernet

# 測試一律用下面的假值，不沿用本機 .env 或 shell 的設定，測試才不會碰到真的服務
# 加密用的金鑰每次測試隨機產生即可，不影響 production（production 由環境變數注入）
os.environ["SECRET_ENCRYPTION_KEY"] = Fernet.generate_key().decode()

# Gemini client 由下面的 fixture 建立；測試會替換模型呼叫，不會真的打 Gemini
os.environ["GEMINI_API_KEY"] = "test-gemini-key"

# core.security 在 import 時就檢查這兩個變數；測試不會真的打 Clerk，給假值即可
os.environ["CLERK_JWKS_URL"] = "https://test.clerk.invalid/.well-known/jwks.json"
os.environ["CLERK_ISSUER"] = "https://test.clerk.invalid"

# 關掉全域限流，避免測試短時間內重複呼叫被擋；限流本身在 test_rate_limit.py 用獨立的 Limiter 測試
os.environ["DISABLE_RATE_LIMIT"] = "true"
# 空字串代表不用 Redis，改用記憶體快取
os.environ["REDIS_URL"] = ""

from mongomock_motor import AsyncMongoMockClient
from core import database
from services import task_inference
from routers import pr_review_webhook

# 在收集測試檔之前就換成記憶體資料庫：測試檔裡的 `from core.database import db` 在 import 時就會讀取 db
# mongomock 是同步的，程式碼會 await 結果，所以要用 mongomock_motor；和正式環境一樣設 tz_aware，讀出的 datetime 才帶 UTC 時區
mock_client = AsyncMongoMockClient(tz_aware=True)
test_db = mock_client["auto_scheduling_db"]
database.client = mock_client
database.db = test_db

@pytest_asyncio.fixture(scope="session", autouse=True)
async def override_mongodb():
    # 測試不經過 app 的 lifespan，Gemini client 要在這裡建立
    task_inference.open_client()
    pr_review_webhook.open_client()

    # 覆蓋你要用到的 collection
    database.db.linkedAccounts = test_db["linkedAccounts"]
    database.db.users = test_db["users"]
    database.db.manual_tasks = test_db["manual_tasks"]
    database.db.googleCalendarTokens = test_db["googleCalendarTokens"]
    database.db.github_issues = test_db["github_issues"]
    database.db.jira_issues = test_db["jira_issues"]
    database.db.moodle_assignments = test_db["moodle_assignments"]
    # 加更多 collection 如有需要...

    yield  # 測試期間使用 mock db

    if pr_review_webhook.client is not None:
        await pr_review_webhook.close_client()
    task_inference.close_client()
    mock_client.close()
    database.client = None
    database.db = None


@pytest_asyncio.fixture(autouse=True)
async def isolate_mock_database(override_mongodb):
    """整個測試共用一個記憶體資料庫；每個測試開始前清空，測試結果才不會受執行順序影響。"""
    for name in await database.db.list_collection_names():
        await database.db[name].delete_many({})


@pytest.fixture
def logged_in_user():
    """
    用 dependency_overrides 假裝已登入。
    寫成 fixture 才能保證測試失敗時也會清掉，否則會影響後面驗證「未登入被擋」的測試。
    """
    from main import app
    from core.security import get_current_clerk_user

    user = {"sub": "test_user_123"}

    async def fake_get_current_clerk_user():
        return user

    app.dependency_overrides[get_current_clerk_user] = fake_get_current_clerk_user
    yield user
    app.dependency_overrides.clear()
