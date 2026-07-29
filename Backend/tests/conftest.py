import os
import pytest
import mongomock
from cryptography.fernet import Fernet
from db import mongodb

# 測試環境用固定金鑰即可，不影響 production（production 由環境變數注入）
os.environ.setdefault("SECRET_ENCRYPTION_KEY", Fernet.generate_key().decode())

@pytest.fixture(scope="session", autouse=True)
def override_mongodb():
    mock_client = mongomock.MongoClient()
    test_db = mock_client["auto_scheduling_db"]

    # 覆蓋你要用到的 collection
    mongodb.db.linkedAccounts = test_db["linkedAccounts"]
    mongodb.db.users = test_db["users"]
    mongodb.db.manual_tasks = test_db["manual_tasks"]
    # 加更多 collection 如有需要...

    yield  # 測試期間使用 mock db

    # mongomock 是 in-memory 的，不需要手動清除
