import pytest
import mongomock
from db import mongodb

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
