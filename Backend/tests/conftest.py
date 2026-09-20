import os
import pytest
from mongomock_motor import AsyncMongoMockClient
from cryptography.fernet import Fernet
from db import mongodb

# 測試環境用固定金鑰即可，不影響 production（production 由環境變數注入）
os.environ.setdefault("SECRET_ENCRYPTION_KEY", Fernet.generate_key().decode())

# routers.webhook 在 import 時就會建立 genai.Client，沒有這個變數會直接噴錯
os.environ.setdefault("GEMINI_API_KEY", "test-gemini-key")

# 測試會在短時間內對同個 endpoint 打很多次請求，關掉全域限流避免測試互相干擾、
# 被自己的流量限制誤傷。rate_limit.py 自己的行為由 tests/integration/test_rate_limit.py
# 直接用獨立的 Limiter 實例測試，不受這個影響。
os.environ.setdefault("DISABLE_RATE_LIMIT", "true")

@pytest.fixture(scope="session", autouse=True)
def override_mongodb():
    # mongomock 本身是同步的（模仿 pymongo，不是 motor），如果直接拿它的
    # collection 給會 `await` 結果的程式碼用，會噴「XxxResult can't be used
    # in await expression」。mongomock_motor 是專門包一層讓它可以配合
    # async/await 使用的版本，真正需要對這個假資料庫做非 mock 的讀寫時要用這個。
    mock_client = AsyncMongoMockClient()
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


@pytest.fixture
def logged_in_user():
    """API 測試（tests/integration/test_*_api.py）用：假裝已經用 Clerk 登入的使用者。

    走 HTTP 打 API 時，每個受保護的 endpoint 都會先跑 get_current_clerk_user 去驗
    Bearer token。測試裡沒有真的 token，所以用 FastAPI 的 dependency_overrides
    把這個驗證換成「直接回傳一個假使用者」。

    寫成 fixture 而不是每個測試自己設定/清掉，是因為 fixture 的收尾（yield 之後）
    不管測試是通過還是 assert 失敗都一定會執行——如果測試中途失敗、清除那行沒跑到，
    假登入會殘留在共用的 app 上，讓後面「應該要被擋掉」的測試莫名其妙通過。
    """
    from main import app
    from db.security import get_current_clerk_user

    user = {"sub": "test_user_123"}

    async def fake_get_current_clerk_user():
        return user

    app.dependency_overrides[get_current_clerk_user] = fake_get_current_clerk_user
    yield user
    app.dependency_overrides.clear()
