"""連結或更新帳號後馬上同步一次；同步失敗不影響連結的結果。帳號清單只回同步時間，不回同步用的內部欄位。"""
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from httpx import AsyncClient
from httpx._transports.asgi import ASGITransport

import platforms.account_sync as account_sync
import platforms.github as github_platform
from core.crypto import SecretDecryptError, encrypt_secret
from core.database import db
from main import app
from platforms.sync import NonRetryableError
from tests.integration.platform_http_fakes import skip_retry_delay

USER_ID = "test_user_123"
ACCOUNT_ID = f"{USER_ID}_github"
GITHUB_PAYLOAD = {"platform": "github", "status": "connected", "username": "me", "apiKey": "ghp_new_token"}
RAW_ISSUE = {
    "id": 4242, "number": 1, "title": "連結後同步", "state": "open", "created_at": "2026-11-01T00:00:00Z",
    "html_url": "https://github.com/o/r/issues/1", "user": {"login": "me", "avatar_url": ""},
}
SYNC_FIELDS = ("last_synced_at", "last_sync_error_code", "sync_started_at", "sync_lock_owner", "sync_lock_until")


@pytest_asyncio.fixture(autouse=True)
async def clean(monkeypatch):
    skip_retry_delay(monkeypatch)

    async def userinfo(token):
        return {"username": "me", "avatar_url": ""}

    monkeypatch.setattr(github_platform, "fetch_github_userinfo", userinfo)
    await db.linkedAccounts.delete_many({"clerk_id": USER_ID})
    await db.github_issues.delete_many({"user_id": USER_ID})
    yield
    await db.linkedAccounts.delete_many({"clerk_id": USER_ID})
    await db.github_issues.delete_many({"user_id": USER_ID})


def _github_fetch(monkeypatch, outcome) -> list:
    calls = []

    async def fetch(token):
        calls.append(token)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr(github_platform, "fetch_github_user_issues", fetch)
    return calls


async def _insert_account(**extra) -> None:
    await db.linkedAccounts.insert_one({
        "_id": ACCOUNT_ID, "clerk_id": USER_ID, "platform": "github", "status": "connected",
        "username": "me", "apiKey": encrypt_secret("old-token"), "link_id": "link-old", **extra,
    })


async def _request(method: str, path: str, **kwargs):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        return await ac.request(method, path, **kwargs)


# ---------- 連結 ----------

@pytest.mark.asyncio
async def test_link_syncs_platform_once(monkeypatch, logged_in_user):
    """AC40：連結帳號成功時同步該平台一次，資料庫有該平台的項目，也記下同步時間。"""
    calls = _github_fetch(monkeypatch, [RAW_ISSUE])

    res = await _request("POST", "/users/me/linked-accounts/", json=GITHUB_PAYLOAD)

    assert res.status_code == 201
    assert calls == ["ghp_new_token"]
    assert await db.github_issues.find_one({"user_id": USER_ID, "id": 4242}) is not None
    account = await db.linkedAccounts.find_one({"_id": ACCOUNT_ID})
    assert account is not None
    assert account["last_synced_at"] is not None
    assert account["link_id"]


@pytest.mark.asyncio
async def test_link_still_succeeds_when_sync_fails(monkeypatch, logged_in_user):
    """AC41：連結後的同步失敗時，POST 仍回 201，帳號存進資料庫。"""
    _github_fetch(monkeypatch, RuntimeError("GitHub down"))

    res = await _request("POST", "/users/me/linked-accounts/", json=GITHUB_PAYLOAD)

    assert res.status_code == 201
    assert await db.linkedAccounts.find_one({"_id": ACCOUNT_ID}) is not None


@pytest.mark.asyncio
async def test_link_sync_with_undecryptable_credentials_records_nothing(monkeypatch, logged_in_user):
    """AC61：連結帳號後的同步解不開憑證時，不改這個帳號的同步結果。"""
    calls = _github_fetch(monkeypatch, [RAW_ISSUE])

    def fail_decrypt(value):
        raise SecretDecryptError("encrypted with another key")

    monkeypatch.setattr(account_sync, "decrypt_secret", fail_decrypt)

    res = await _request("POST", "/users/me/linked-accounts/", json=GITHUB_PAYLOAD)

    assert res.status_code == 201
    assert calls == []
    account = await db.linkedAccounts.find_one({"_id": ACCOUNT_ID})
    assert account is not None
    for field in SYNC_FIELDS:
        assert field not in account


# ---------- 更新憑證 ----------

@pytest.mark.asyncio
async def test_update_credentials_syncs_and_clears_reauth_error(monkeypatch, logged_in_user):
    """AC42、AC43：更新憑證而且重新驗證成功時同步一次；同步成功後清掉之前的「憑證失效」結果，並換一個新的 link_id。"""
    await _insert_account(last_sync_error_code="REAUTH_REQUIRED")
    calls = _github_fetch(monkeypatch, [RAW_ISSUE])

    res = await _request("PATCH", "/users/me/linked-accounts/github", json={"apiKey": "ghp_rotated"})

    assert res.status_code == 200
    assert calls == ["ghp_rotated"]
    account = await db.linkedAccounts.find_one({"_id": ACCOUNT_ID})
    assert account is not None
    assert account["last_sync_error_code"] is None
    assert account["last_synced_at"] is not None
    assert account["link_id"] not in (None, "link-old")
    assert await db.github_issues.find_one({"user_id": USER_ID, "id": 4242}) is not None


@pytest.mark.asyncio
async def test_update_credentials_still_succeeds_when_sync_fails(monkeypatch, logged_in_user):
    """AC44：更新憑證後的同步失敗時，PATCH 仍回成功。"""
    await _insert_account()
    _github_fetch(monkeypatch, NonRetryableError("401", error_code="REAUTH_REQUIRED"))

    res = await _request("PATCH", "/users/me/linked-accounts/github", json={"apiKey": "ghp_rotated"})

    assert res.status_code == 200
    assert res.json() == {"success": True}


@pytest.mark.asyncio
async def test_update_without_reverify_does_not_sync(monkeypatch, logged_in_user):
    """AC45：更新的欄位不需要重新驗證（只改 status）時不同步，link_id 也不換。"""
    await _insert_account()
    calls = _github_fetch(monkeypatch, [RAW_ISSUE])

    res = await _request("PATCH", "/users/me/linked-accounts/github", json={"status": "connected"})

    assert res.status_code == 200
    assert calls == []
    account = await db.linkedAccounts.find_one({"_id": ACCOUNT_ID})
    assert account is not None and account["link_id"] == "link-old"


# ---------- 帳號清單 ----------

@pytest.mark.asyncio
async def test_linked_accounts_list_has_last_synced_at_only(logged_in_user):
    """AC22、AC23：帳號清單每個帳號帶 last_synced_at（沒有同步紀錄是 null），不出現鎖、開始時間等內部欄位。"""
    synced_at = datetime(2026, 11, 1, 4, 0, tzinfo=timezone.utc)
    await _insert_account(
        last_synced_at=synced_at, last_sync_error_code="UPSTREAM_ERROR", sync_started_at=synced_at,
        sync_lock_owner="owner", sync_lock_until=synced_at,
    )
    await db.linkedAccounts.insert_one({
        "_id": f"{USER_ID}_moodle", "clerk_id": USER_ID, "platform": "moodle", "status": "connected",
        "username": "stu", "password": encrypt_secret("pw"),
    })

    res = await _request("GET", "/users/me/linked-accounts/")

    assert res.status_code == 200
    by_platform = {a["platform"]: a for a in res.json()}
    assert by_platform["github"]["last_synced_at"] == "2026-11-01T04:00:00Z"
    assert by_platform["moodle"]["last_synced_at"] is None
    for account in by_platform.values():
        for field in ("sync_started_at", "sync_lock_owner", "sync_lock_until", "last_sync_error_code", "link_id"):
            assert field not in account
