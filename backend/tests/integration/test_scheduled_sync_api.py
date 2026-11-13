"""POST /internal/scheduled-sync：密鑰驗證、所有帳號逐一同步、失敗不影響其他帳號、回應只有筆數。"""
import logging
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import AsyncClient
from httpx._transports.asgi import ASGITransport

import platforms.account_sync as account_sync
import routers.scheduled_sync as scheduled_sync_router
from core.crypto import encrypt_secret
from core.database import db
from main import app
from platforms.github import GITHUB
from platforms.jira import JIRA
from platforms.moodle import MOODLE
from platforms.sync import NonRetryableError
from tests.integration.platform_http_fakes import skip_retry_delay

SECRET = "scheduler-test-secret"
AUTH = {"Authorization": f"Bearer {SECRET}"}
USERS = ["sched-u1", "sched-u2", "sched-u3"]
CATEGORY_USERS = ["ok", "fails", "superseded", "unlinked", "incomplete", "locked"]
PAST = datetime(2026, 1, 1, tzinfo=timezone.utc)

# 每個平台用憑證認出是哪個使用者，抓到的項目 id 帶上使用者，才看得出寫到誰身上
PLATFORM_FIELDS = {
    "github": lambda uid: {"apiKey": f"token-{uid}"},
    "jira": lambda uid: {"apiKey": f"token-{uid}", "domain": "team.atlassian.net"},
    "moodle": lambda uid: {"username": uid, "password": f"token-{uid}"},
}
SECRET_FIELD = {"github": "apiKey", "jira": "apiKey", "moodle": "password"}


def _user_of(credentials: dict) -> str:
    secret = credentials.get("token") or credentials.get("api_key") or credentials.get("password") or ""
    return secret.removeprefix("token-")


@pytest_asyncio.fixture(autouse=True)
async def isolated_accounts(monkeypatch):
    # 定時同步會處理資料庫裡所有帳號，先清掉其他測試留下的帳號
    monkeypatch.setattr(scheduled_sync_router, "SCHEDULED_SYNC_SECRET", SECRET)
    skip_retry_delay(monkeypatch)
    await db.linkedAccounts.delete_many({})
    yield
    await db.linkedAccounts.delete_many({})
    for collection in (db.github_issues, db.jira_issues, db.moodle_assignments):
        await collection.delete_many({"user_id": {"$in": USERS + CATEGORY_USERS}})


async def _link(uid: str, platform: str, **extra) -> None:
    fields = PLATFORM_FIELDS[platform](uid)
    secret_field = SECRET_FIELD[platform]
    fields[secret_field] = encrypt_secret(fields[secret_field])
    await db.linkedAccounts.insert_one({
        "_id": f"{uid}_{platform}", "clerk_id": uid, "platform": platform, "status": "connected",
        "username": uid, "link_id": f"link-{uid}-{platform}", **fields, **extra,
    })


def _fetch_by_user(monkeypatch, platform, behaviours: dict | None = None, calls: list | None = None):
    """依使用者決定回傳的項目或丟出的例外；沒列的使用者回一筆 id 為 "<uid>-<平台>" 的項目。"""
    behaviours = behaviours or {}

    async def fetch(credentials):
        uid = _user_of(credentials)
        if calls is not None:
            calls.append(uid)
        behaviour = behaviours.get(uid)
        if isinstance(behaviour, Exception):
            raise behaviour
        if callable(behaviour):
            return await behaviour()
        return [{"id": f"{uid}-{platform.name}", "title": f"{uid} 的項目", "number": 1, "status": "open",
                 "url": "https://example.com", "key": "K-1", "course_name": "課", "due_date": "無截止日期"}]

    monkeypatch.setattr(platform, "fetch_items", fetch)


async def _post(headers: dict | None = None):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        return await ac.post("/internal/scheduled-sync", headers=headers or {})


# ---------- 密鑰驗證 ----------

@pytest.mark.asyncio
@pytest.mark.parametrize("headers", [
    {},
    {"Authorization": "Bearer wrong-secret"},
    {"Authorization": SECRET},
    {"Authorization": f"Token {SECRET}"},
    {"Authorization": "Bearer "},
    {"Authorization": "Bearer"},
], ids=["missing", "wrong-secret", "no-scheme", "other-scheme", "empty-after-bearer", "bearer-only"])
async def test_rejects_bad_authorization_without_syncing(monkeypatch, headers):
    """AC6：沒帶 Authorization、密鑰錯誤、格式不是 Bearer <值>、Bearer 後面是空的 → 401，而且不同步任何帳號。"""
    await _link("sched-u1", "github")
    calls = []
    _fetch_by_user(monkeypatch, GITHUB, calls=calls)

    res = await _post(headers)

    assert res.status_code == 401
    assert res.json()["error_code"] == "INVALID_SCHEDULER_TOKEN"
    assert calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize("server_secret", [None, ""], ids=["unset", "empty-string"])
@pytest.mark.parametrize("headers", [{"Authorization": "Bearer "}, {"Authorization": "Bearer anything"}, {}],
                         ids=["empty-bearer", "some-value", "missing"])
async def test_rejects_everything_when_server_secret_not_configured(monkeypatch, server_secret, headers):
    """AC7：後端沒設定 SCHEDULED_SYNC_SECRET 或是空字串時，不論帶什麼都回 401，也不同步。"""
    monkeypatch.setattr(scheduled_sync_router, "SCHEDULED_SYNC_SECRET", server_secret)
    await _link("sched-u1", "github")
    calls = []
    _fetch_by_user(monkeypatch, GITHUB, calls=calls)

    res = await _post(headers)

    assert res.status_code == 401
    assert calls == []


# ---------- 同步所有帳號 ----------

@pytest.mark.asyncio
async def test_syncs_every_linked_platform_of_every_user(monkeypatch):
    """AC5、AC14、AC70：帶正確密鑰時，每個使用者的每個已連結平台都同步並寫進資料庫；回應只有三個筆數。"""
    for uid in USERS[:2]:
        for platform in ("github", "jira", "moodle"):
            await _link(uid, platform)
    for platform in (GITHUB, JIRA, MOODLE):
        _fetch_by_user(monkeypatch, platform)

    res = await _post(AUTH)

    assert res.status_code == 200
    assert res.json() == {"succeeded": 6, "failed": 0, "skipped": 0}
    for uid in USERS[:2]:
        for platform in (GITHUB, JIRA, MOODLE):
            assert await platform.collection.find_one({"user_id": uid, "id": f"{uid}-{platform.name}"}) is not None
            account = await db.linkedAccounts.find_one({"_id": f"{uid}_{platform.name}"})
            assert account is not None and account["last_synced_at"] is not None


@pytest.mark.asyncio
async def test_failed_accounts_do_not_stop_others_and_keep_their_items(monkeypatch, caplog):
    """AC8、AC9、AC10、AC11、AC12：一個帳號憑證失效、一個未預期的例外，第三個仍同步；失敗帳號的項目不變、
    連結保留、log 記下使用者 id、平台與 error_code，整個過程的 log 不含明文或密文憑證。"""
    for uid in USERS:
        await _link(uid, "github")
        await db.github_issues.insert_one({"id": f"old-{uid}", "title": "舊資料", "user_id": uid})
    _fetch_by_user(monkeypatch, GITHUB, {
        "sched-u1": NonRetryableError("401 Unauthorized", error_code="REAUTH_REQUIRED"),
        "sched-u2": RuntimeError("unexpected bug"),
    })
    ciphertexts = [doc["apiKey"] async for doc in db.linkedAccounts.find({})]

    with caplog.at_level(logging.DEBUG):
        res = await _post(AUTH)

    assert res.json() == {"succeeded": 1, "failed": 2, "skipped": 0}
    assert await db.github_issues.find_one({"user_id": "sched-u3", "id": "sched-u3-github"}) is not None
    for uid in ("sched-u1", "sched-u2"):
        assert [d["id"] async for d in db.github_issues.find({"user_id": uid})] == [f"old-{uid}"]
    assert await db.linkedAccounts.find_one({"_id": "sched-u1_github"}) is not None
    failure_logs = [r.getMessage() for r in caplog.records if "sched-u1" in r.getMessage()]
    assert any("github" in m and "REAUTH_REQUIRED" in m for m in failure_logs)
    assert any("sched-u2" in r.getMessage() and "INTERNAL_ERROR" in r.getMessage() for r in caplog.records)
    for uid in USERS:
        assert f"token-{uid}" not in caplog.text
    for ciphertext in ciphertexts:
        assert ciphertext not in caplog.text


@pytest.mark.asyncio
async def test_undecryptable_account_is_skipped_and_others_continue(monkeypatch):
    """AC15：解密某個帳號的憑證失敗 → 算進 skipped、不改它的同步結果，並繼續處理其他帳號。"""
    await _link("sched-u1", "github", apiKey="encrypted-with-another-key", last_sync_error_code="UPSTREAM_ERROR",
                last_synced_at=PAST)
    await _link("sched-u2", "github")
    _fetch_by_user(monkeypatch, GITHUB)
    before = await db.linkedAccounts.find_one({"_id": "sched-u1_github"})

    res = await _post(AUTH)

    assert res.json() == {"succeeded": 1, "failed": 0, "skipped": 1}
    assert await db.linkedAccounts.find_one({"_id": "sched-u1_github"}) == before
    assert await db.github_issues.find_one({"user_id": "sched-u2"}) is not None


@pytest.mark.asyncio
async def test_syncing_one_user_does_not_touch_another_users_data(monkeypatch):
    """AC50：同步一個使用者時，另一個使用者的項目（即使 id 相同）與 linkedAccounts 欄位不變。"""
    await _link("sched-u1", "github")
    await _link("sched-u2", "github", apiKey="encrypted-with-another-key", last_synced_at=PAST)
    await db.github_issues.insert_one({"id": "shared-id", "title": "u2 的項目", "user_id": "sched-u2"})
    await db.github_issues.insert_one({"id": "u2-only", "title": "u2 獨有", "user_id": "sched-u2"})

    async def u1_items():
        return [{"id": "shared-id", "title": "u1 的項目", "number": 1, "status": "open", "url": "https://example.com"}]

    _fetch_by_user(monkeypatch, GITHUB, {"sched-u1": u1_items})
    u2_account_before = await db.linkedAccounts.find_one({"_id": "sched-u2_github"})
    u2_items_before = [d async for d in db.github_issues.find({"user_id": "sched-u2"})]

    await _post(AUTH)

    assert await db.linkedAccounts.find_one({"_id": "sched-u2_github"}) == u2_account_before
    assert [d async for d in db.github_issues.find({"user_id": "sched-u2"})] == u2_items_before


@pytest.mark.asyncio
async def test_each_result_is_counted_in_its_category(monkeypatch):
    """AC66、AC67、AC70：成功算 succeeded；抓取失敗（有舊資料）、等不到鎖算 failed；被取代、帳號已變更、憑證資料不完整算 skipped。"""
    monkeypatch.setattr(account_sync, "LOCK_WAIT_SECONDS", 0.05)
    monkeypatch.setattr(account_sync, "LOCK_POLL_SECONDS", 0.01)
    future = datetime.now(timezone.utc) + timedelta(hours=1)
    await _link("ok", "github")
    await _link("fails", "github")
    await db.github_issues.insert_one({"id": "old", "title": "舊資料", "user_id": "fails"})
    await _link("superseded", "github", sync_started_at=future)
    await _link("unlinked", "github")
    await _link("incomplete", "github", apiKey="")
    await _link("locked", "github", sync_lock_owner="someone-else", sync_lock_until=future)

    async def unlink():
        await db.linkedAccounts.delete_one({"_id": "unlinked_github"})
        return []

    _fetch_by_user(monkeypatch, GITHUB, {
        "fails": NonRetryableError("401", error_code="REAUTH_REQUIRED"),
        "unlinked": unlink,
    })

    res = await _post(AUTH)

    assert res.json() == {"succeeded": 1, "failed": 2, "skipped": 3}
