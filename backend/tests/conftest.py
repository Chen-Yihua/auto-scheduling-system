import os
import pytest
from mongomock_motor import AsyncMongoMockClient
from cryptography.fernet import Fernet
from core import database

# 測試環境用固定金鑰即可，不影響 production（production 由環境變數注入）
os.environ.setdefault("SECRET_ENCRYPTION_KEY", Fernet.generate_key().decode())

# routers.pr_review_webhook 在 import 時就會建立 genai.Client，沒有這個變數會直接噴錯
os.environ.setdefault("GEMINI_API_KEY", "test-gemini-key")

# 關掉全域限流，避免測試短時間內重複呼叫被擋；限流本身在 test_rate_limit.py 用獨立的 Limiter 測試
os.environ.setdefault("DISABLE_RATE_LIMIT", "true")

@pytest.fixture(scope="session", autouse=True)
def override_mongodb():
    # mongomock 是同步的，程式碼會 await 結果，所以要用 mongomock_motor
    mock_client = AsyncMongoMockClient()
    test_db = mock_client["auto_scheduling_db"]

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

    # mongomock 是 in-memory 的，不需要手動清除


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
