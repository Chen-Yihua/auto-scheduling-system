import pytest
from fastapi import HTTPException
import crud.linkedAccount as linked_mod
from crud.linkedAccount import (
    create_linked_account,
    get_linked_accounts_by_clerk_id,
    update_linked_account_by_clerk_id,
)
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
    """建立 Moodle 帳號時，密碼存進資料庫前要加密，不能存明文；解密後要等於原本的密碼。"""
    stored = {}
    monkeypatch.setattr(linked_mod.db.linkedAccounts, "update_one", _mock_update_one(stored))
    monkeypatch.setattr(linked_mod, "verify_moodle_login", lambda username, password: True)

    account = LinkedAccountCreate(platform="moodle", status="", username="stu123", password="my-real-password")
    await create_linked_account("uid123", account)

    assert stored["password"] != "my-real-password"
    assert decrypt_secret(stored["password"]) == "my-real-password"


@pytest.mark.asyncio
async def test_create_moodle_account_rejects_wrong_credentials(monkeypatch):
    """Moodle 帳密驗證失敗 → 401，而且完全不能寫進資料庫。"""
    from crud.errors import NonRetryableError

    stored = {}
    monkeypatch.setattr(linked_mod.db.linkedAccounts, "update_one", _mock_update_one(stored))

    def fake_verify(username, password):
        raise NonRetryableError("Moodle 登入失敗，使用者：stu123")

    monkeypatch.setattr(linked_mod, "verify_moodle_login", fake_verify)

    account = LinkedAccountCreate(platform="moodle", status="", username="stu123", password="wrong-password")

    with pytest.raises(HTTPException) as exc_info:
        await create_linked_account("uid123", account)

    assert exc_info.value.status_code == 401
    assert stored == {}  # 驗證失敗，完全不該寫進 DB


@pytest.mark.asyncio
async def test_create_github_account_encrypts_apikey(monkeypatch):
    """建立 GitHub 帳號時，apiKey 存進資料庫前要加密；但向 GitHub 驗證 token 時用的必須是明文。"""
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
    """查詢綁定帳號時，回傳的密碼既不是明文、也不是原樣的密文，只保留最後 4 碼讓前端辨識。"""
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
    """更新 Moodle 密碼時，存進資料庫前也要加密。"""
    stored = {}
    monkeypatch.setattr(linked_mod.db.linkedAccounts, "update_one", _mock_update_one(stored))
    monkeypatch.setattr(linked_mod, "verify_moodle_login", lambda username, password: True)

    async def mock_find_one(query):
        return {"username": "stu123"}  # 密碼單獨更新時，拿現有帳號一起驗證

    monkeypatch.setattr(linked_mod.db.linkedAccounts, "find_one", mock_find_one)

    result = await update_linked_account_by_clerk_id(
        "uid123", "moodle", {"payload": {"password": "new-password"}}
    )

    assert result is True
    assert stored["password"] != "new-password"
    assert decrypt_secret(stored["password"]) == "new-password"


@pytest.mark.asyncio
async def test_update_jira_apikey_without_domain_still_encrypted(monkeypatch):
    """只更新 Jira 的 apiKey、沒帶 domain 時也要加密（這個情境過去漏加密過）。"""
    stored = {}
    monkeypatch.setattr(linked_mod.db.linkedAccounts, "update_one", _mock_update_one(stored))

    result = await update_linked_account_by_clerk_id(
        "uid123", "jira", {"payload": {"apiKey": "new-jira-token"}}
    )

    assert result is True
    assert stored["apiKey"] != "new-jira-token"
    assert decrypt_secret(stored["apiKey"]) == "new-jira-token"
