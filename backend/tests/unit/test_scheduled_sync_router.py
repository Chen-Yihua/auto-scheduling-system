"""routers/scheduled_sync.py 的 run_scheduled_sync：依序處理帳號，以及每種同步結果算進哪個筆數。"""
import asyncio
import logging

import pytest
import pytest_asyncio

import routers.scheduled_sync as scheduled_sync_router
from core.crypto import encrypt_secret
from core.database import db
from platforms.account_sync import SyncOutcome, SyncResult
from platforms.github import GITHUB

USERS = [f"seq-u{i}" for i in range(4)]


@pytest_asyncio.fixture(autouse=True)
async def accounts():
    await db.linkedAccounts.delete_many({})
    for uid in USERS:
        await db.linkedAccounts.insert_one({
            "_id": f"{uid}_github", "clerk_id": uid, "platform": "github", "status": "connected",
            "username": uid, "apiKey": encrypt_secret(f"token-{uid}"), "link_id": f"link-{uid}",
        })
    yield
    await db.linkedAccounts.delete_many({})
    await db.github_issues.delete_many({"user_id": {"$in": USERS}})


@pytest.mark.asyncio
async def test_processes_one_account_at_a_time(monkeypatch):
    """AC13：一次定時同步處理多個帳號時，同一時間只能有一個帳號在抓資料。"""
    running = 0
    peak = 0

    async def fetch(credentials):
        nonlocal running, peak
        running += 1
        peak = max(peak, running)
        await asyncio.sleep(0.01)
        running -= 1
        return []

    monkeypatch.setattr(GITHUB, "fetch_items", fetch)

    counts = await scheduled_sync_router.run_scheduled_sync()

    assert counts == {"succeeded": len(USERS), "failed": 0, "skipped": 0}
    assert peak == 1


@pytest.mark.asyncio
async def test_each_outcome_is_counted_in_its_category(monkeypatch):
    """AC66、AC67、AC70：被取代、帳號已變更、憑證解不開、憑證資料不完整算 skipped；等不到鎖、鎖被拿走、失敗算 failed；成功算 succeeded。"""
    outcomes = iter([
        SyncResult(SyncOutcome.SUCCEEDED),
        SyncResult(SyncOutcome.FAILED, error_code="UPSTREAM_ERROR"),
        SyncResult(SyncOutcome.LOCK_TIMEOUT, error_code="SERVICE_UNAVAILABLE"),
        SyncResult(SyncOutcome.LOCK_LOST),
        SyncResult(SyncOutcome.SUPERSEDED),
        SyncResult(SyncOutcome.ACCOUNT_CHANGED),
        SyncResult(SyncOutcome.UNDECRYPTABLE),
        SyncResult(SyncOutcome.INCOMPLETE_CREDENTIALS),
    ])
    for i in range(4, 8):
        await db.linkedAccounts.insert_one({"_id": f"extra-{i}_github", "clerk_id": f"extra-{i}", "platform": "github"})

    async def fake_sync(platform, user_id):
        return next(outcomes)

    monkeypatch.setattr(scheduled_sync_router, "sync_account", fake_sync)

    counts = await scheduled_sync_router.run_scheduled_sync()

    assert counts == {"succeeded": 1, "failed": 3, "skipped": 4}


@pytest.mark.asyncio
async def test_unexpected_exception_is_failed_and_logs_class_name_only(monkeypatch, caplog):
    """AC8、AC10：同步本身丟出未預期的例外 → 算 failed、記下使用者 id、平台與例外類別名稱（不記訊息），繼續處理下一個帳號。"""
    calls = []

    async def fake_sync(platform, user_id):
        calls.append(user_id)
        if user_id == USERS[0]:
            raise RuntimeError("message-that-may-contain-secrets")
        return SyncResult(SyncOutcome.SUCCEEDED)

    monkeypatch.setattr(scheduled_sync_router, "sync_account", fake_sync)

    with caplog.at_level(logging.INFO):
        counts = await scheduled_sync_router.run_scheduled_sync()

    assert counts == {"succeeded": len(USERS) - 1, "failed": 1, "skipped": 0}
    assert sorted(calls) == sorted(USERS)
    assert any(USERS[0] in r.getMessage() and "github" in r.getMessage() and "RuntimeError" in r.getMessage()
               for r in caplog.records)
    assert "message-that-may-contain-secrets" not in caplog.text


def test_scheduled_sync_endpoint_is_rate_limited():
    """密鑰外洩時降低濫用：endpoint 限流 5/hour。"""
    from core.rate_limit import limiter

    assert [str(l.limit) for l in limiter._route_limits["routers.scheduled_sync.scheduled_sync"]] == ["5 per 1 hour"]
