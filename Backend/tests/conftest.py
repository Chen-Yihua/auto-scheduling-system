import os
import pytest
import mongomock
from cryptography.fernet import Fernet
from db import mongodb

# 測試環境用固定金鑰即可，不影響 production（production 由環境變數注入）
os.environ.setdefault("SECRET_ENCRYPTION_KEY", Fernet.generate_key().decode())

# routers.webhook 在 import 時就會建立 genai.Client，沒有這個變數會直接噴錯
os.environ.setdefault("GEMINI_API_KEY", "test-gemini-key")

# 測試會在短時間內對同個 endpoint 打很多次請求，關掉全域限流避免測試互相干擾、
# 被自己的流量限制誤傷。rate_limit.py 自己的行為由 tests/test_rate_limit.py
# 直接用獨立的 Limiter 實例測試，不受這個影響。
os.environ.setdefault("DISABLE_RATE_LIMIT", "true")

@pytest.fixture(scope="session", autouse=True)
def override_mongodb():
    mock_client = mongomock.MongoClient()
    test_db = mock_client["auto_scheduling_db"]

    # 覆蓋你要用到的 collection
    mongodb.db.linkedAccounts = test_db["linkedAccounts"]
    mongodb.db.users = test_db["users"]
    mongodb.db.manual_tasks = test_db["manual_tasks"]
    mongodb.db.googleCalendarTokens = test_db["googleCalendarTokens"]
    mongodb.db.github_issues = test_db["github_issues"]
    mongodb.db.jira_issues = test_db["jira_issues"]
    mongodb.db.moodle_assignments = test_db["moodle_assignments"]
    # 加更多 collection 如有需要...

    yield  # 測試期間使用 mock db

    # mongomock 是 in-memory 的，不需要手動清除
