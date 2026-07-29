import pytest
import crud.linkedAccount as linked_mod
import crud.moodle as moodle_mod
from crud.linkedAccount import (
    create_linked_account,
    get_linked_accounts_by_clerk_id,
    update_linked_account_by_clerk_id,
)
from crud.moodle import get_user_account
from db.crypto import encrypt_secret, decrypt_secret
from schemas.linkedAccount import LinkedAccountCreate


def _mock_update_one(stored: dict):
    async def _update_one(filter, update, upsert=False):
        stored.clear()
        stored.update(update["$set"])
        return type("Mock", (), {"modified_count": 1, "upserted_id": None})()
    return _update_one


# ========== 建立帳號時，密碼／apiKey 必須加密落地 ==========

@pytest.mark.asyncio
async def test_create_moodle_account_encrypts_password(monkeypatch):
    stored = {}
    monkeypatch.setattr(linked_mod.db.linkedAccounts, "update_one", _mock_update_one(stored))

    account = LinkedAccountCreate(platform="moodle", status="", username="stu123", password="my-real-password")
    await create_linked_account("uid123", account)

    assert stored["password"] != "my-real-password"
    assert decrypt_secret(stored["password"]) == "my-real-password"


@pytest.mark.asyncio
async def test_create_github_account_encrypts_apikey(monkeypatch):
    stored = {}

    async def mock_fetch_github_userinfo(token):
        assert token == "ghp_real_token"  # 呼叫 GitHub 驗證時必須拿到明文
        return {"username": "octocat", "avatar_url": "https://avatar"}

    monkeypatch.setattr(linked_mod.db.linkedAccounts, "update_one", _mock_update_one(stored))
    monkeypatch.setattr(linked_mod, "fetch_github_userinfo", mock_fetch_github_userinfo)

    account = LinkedAccountCreate(platform="github", status="", username="", apiKey="ghp_real_token")
    await create_linked_account("uid123", account)

    assert stored["apiKey"] != "ghp_real_token"
    assert decrypt_secret(stored["apiKey"]) == "ghp_real_token"


# ========== 查詢時絕不回傳可用的明文 ==========

@pytest.mark.asyncio
async def test_get_linked_accounts_never_returns_plaintext_or_ciphertext(monkeypatch):
    real_password = "super-secret-pw"
    encrypted = encrypt_secret(real_password)

    class MockCursor:
        def __aiter__(self):
            async def generator():
                yield {
                    "_id": "uid123_moodle",
                    "platform": "moodle",
                    "username": "stu123",
                    "password": encrypted,
                }
            return generator()

    monkeypatch.setattr(linked_mod.db.linkedAccounts, "find", lambda q: MockCursor())

    result = await get_linked_accounts_by_clerk_id("uid123")
    returned_password = result[0]["password"]

    assert returned_password != real_password          # 不是明文
    assert returned_password != encrypted               # 也不是密文原樣回傳
    assert returned_password.endswith(real_password[-4:])  # 但仍保留可辨識的後四碼給前端顯示
    assert real_password not in returned_password


# ========== 更新時也必須加密 ==========

@pytest.mark.asyncio
async def test_update_moodle_password_encrypts_before_save(monkeypatch):
    stored = {}
    monkeypatch.setattr(linked_mod.db.linkedAccounts, "update_one", _mock_update_one(stored))

    result = await update_linked_account_by_clerk_id(
        "uid123", "moodle", {"payload": {"password": "new-password"}}
    )

    assert result is True
    assert stored["password"] != "new-password"
    assert decrypt_secret(stored["password"]) == "new-password"


@pytest.mark.asyncio
async def test_update_jira_apikey_without_domain_still_encrypted(monkeypatch):
    # 只更新 apiKey、沒帶 domain 的邊界情況，過去會漏加密，這裡確保有修正
    stored = {}
    monkeypatch.setattr(linked_mod.db.linkedAccounts, "update_one", _mock_update_one(stored))

    result = await update_linked_account_by_clerk_id(
        "uid123", "jira", {"payload": {"apiKey": "new-jira-token"}}
    )

    assert result is True
    assert stored["apiKey"] != "new-jira-token"
    assert decrypt_secret(stored["apiKey"]) == "new-jira-token"


# ========== Moodle 爬蟲登入前，才在伺服器內部解密 ==========

@pytest.mark.asyncio
async def test_moodle_get_user_account_decrypts_for_internal_use(monkeypatch):
    real_password = "moodle-pw-123"

    async def mock_find_one(query):
        return {
            "platform": "moodle",
            "clerk_id": "uid123",
            "username": "stu123",
            "password": encrypt_secret(real_password),
        }

    monkeypatch.setattr(moodle_mod.db.linkedAccounts, "find_one", mock_find_one)

    user = await get_user_account("uid123")

    assert user["password"] == real_password
