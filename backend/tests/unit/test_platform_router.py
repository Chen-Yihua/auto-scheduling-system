# platforms/router.py：GET 讀資料庫的 header，以及立即同步的每種結果對應到什麼回應；sync_account 多數換成假的
import asyncio
from datetime import datetime, timezone

import logging

import httpx
import pytest
import pytest_asyncio
from fastapi import Response
from pymongo.errors import OperationFailure, ServerSelectionTimeoutError

import platforms.account_sync as account_sync
import platforms.router as platform_router
from core.database import db
from core.errors import AppError
from platforms.account_sync import SyncOutcome, SyncResult
from platforms.github import GITHUB
from platforms.jira import JIRA
from platforms.moodle import MOODLE
from platforms.sync import InvalidResponseError, NonRetryableError, UpstreamError
from tests.unit.sync_fakes import (
    ACCOUNT_ID,
    PAST,
    USER,
    ControlledFetch,
    PausingCollection,
    account,
    cleanup,
    item,
    link_github,
)

SYNCED_AT = datetime(2026, 9, 1, tzinfo=timezone.utc)
ITEM = {"id": "item-1", "title": "項目"}


@pytest_asyncio.fixture(autouse=True)
async def clean():
    await cleanup()
    yield
    await cleanup()


def _sync_returning(result: SyncResult, calls: list | None = None):
    async def fake_sync(platform, user_id):
        if calls is not None:
            calls.append((platform, user_id))
        return result
    return fake_sync


def _sync_raising(error: Exception):
    async def fake_sync(platform, user_id):
        raise error
    return fake_sync


def _failed(error: Exception, error_code: str) -> SyncResult:
    return SyncResult(SyncOutcome.FAILED, error=error, error_code=error_code)


# ---------- 成功 ----------

@pytest.mark.asyncio
@pytest.mark.parametrize("platform", [GITHUB, JIRA, MOODLE], ids=lambda p: p.name)
async def test_sync_success_returns_fetched_items_and_headers(monkeypatch, platform):
    """AC24：立即同步成功 → 回傳這次抓到的項目，X-Data-Stale 為 false，X-Synced-At 是這次的時間。"""
    calls = []
    monkeypatch.setattr(platform_router, "sync_account", _sync_returning(
        SyncResult(SyncOutcome.SUCCEEDED, items=[ITEM], synced_at=SYNCED_AT), calls,
    ))

    response = Response()
    result = await platform_router.sync_platform_items_now(platform, USER, response)

    assert result == [ITEM]
    assert calls == [(platform, USER)]
    assert response.headers["X-Data-Stale"] == "false"
    assert response.headers["X-Synced-At"] == SYNCED_AT.isoformat()
    assert "X-Auth-Error" not in response.headers


# ---------- 抓取失敗、沒有舊資料：照原因回錯誤（AC28） ----------

@pytest.mark.asyncio
@pytest.mark.parametrize("platform", [GITHUB, JIRA, MOODLE], ids=lambda p: p.name)
async def test_reauth_failure_without_old_data(monkeypatch, platform):
    """AC28：平台拒絕憑證而且沒有舊資料 → REAUTH_REQUIRED 和該平台「請重新連結」的說明。"""
    await link_github()
    monkeypatch.setattr(platform_router, "sync_account", _sync_returning(_failed(NonRetryableError("401"), "REAUTH_REQUIRED")))

    with pytest.raises(AppError) as exc_info:
        await platform_router.sync_platform_items_now(platform, USER, Response())

    assert exc_info.value.error_code == "REAUTH_REQUIRED"
    assert exc_info.value.detail == platform.auth_failed_detail


@pytest.mark.asyncio
@pytest.mark.parametrize("error_code", ["UPSTREAM_RATE_LIMITED", "INTERNAL_ERROR", "UPSTREAM_ERROR"])
async def test_non_retryable_errors_other_than_reauth_keep_their_error_code(monkeypatch, error_code):
    """AC28：不重試的限流、400、404 沒有舊資料時 error_code 照原因，detail 不說授權已失效、不帶平台原文。"""
    await link_github()
    error = NonRetryableError("GitHub API failed: 403 secret-upstream-text", error_code=error_code)
    monkeypatch.setattr(platform_router, "sync_account", _sync_returning(_failed(error, error_code)))

    with pytest.raises(AppError) as exc_info:
        await platform_router.sync_platform_items_now(GITHUB, USER, Response())

    assert exc_info.value.error_code == error_code
    assert "授權已失效" not in exc_info.value.detail
    assert "secret-upstream-text" not in exc_info.value.detail


@pytest.mark.asyncio
@pytest.mark.parametrize("error, error_code", [
    (UpstreamError("503 Service Unavailable"), "UPSTREAM_ERROR"),
    (UpstreamError("429", error_code="UPSTREAM_RATE_LIMITED"), "UPSTREAM_RATE_LIMITED"),
    (httpx.ConnectError("連不上"), "UPSTREAM_ERROR"),
    (httpx.ReadTimeout("逾時"), "UPSTREAM_TIMEOUT"),
    (InvalidResponseError("not json"), "UPSTREAM_ERROR"),
    (RuntimeError("unexpected bug"), "INTERNAL_ERROR"),
], ids=["5xx", "429", "connect-error", "timeout", "unparsable", "unexpected"])
async def test_temporary_failure_without_old_data(monkeypatch, error, error_code):
    """AC28：平台故障、限流、連不上、逾時或我們自己的 bug，而且沒有舊資料 → error_code 照原因；未預期的錯誤只回固定訊息。"""
    await link_github()
    monkeypatch.setattr(platform_router, "sync_account", _sync_returning(_failed(error, error_code)))

    with pytest.raises(AppError) as exc_info:
        await platform_router.sync_platform_items_now(GITHUB, USER, Response())

    assert exc_info.value.error_code == error_code
    if error_code == "INTERNAL_ERROR":
        assert exc_info.value.detail == GITHUB.fetch_failed_detail


# ---------- 抓取失敗、有舊資料：退回舊資料（AC27） ----------

@pytest.mark.asyncio
@pytest.mark.parametrize("error_code, auth_error", [("REAUTH_REQUIRED", True), ("UPSTREAM_ERROR", False)])
async def test_failure_with_old_data_returns_stale_items(monkeypatch, error_code, auth_error):
    """AC27：抓取失敗但有舊資料 → 回舊資料，帶 X-Data-Stale: true；只有憑證失效另外帶 X-Auth-Error。"""
    await link_github(last_synced_at=SYNCED_AT)
    await db.github_issues.insert_one({"id": 1, "title": "舊資料", "user_id": USER})
    monkeypatch.setattr(platform_router, "sync_account", _sync_returning(_failed(NonRetryableError("x", error_code=error_code), error_code)))

    response = Response()
    result = await platform_router.sync_platform_items_now(GITHUB, USER, response)

    assert [i["title"] for i in result] == ["舊資料"]
    assert response.headers["X-Data-Stale"] == "true"
    assert response.headers["X-Synced-At"] == SYNCED_AT.isoformat()
    assert ("X-Auth-Error" in response.headers) is auth_error


# ---------- 憑證、帳號、鎖 ----------

@pytest.mark.asyncio
async def test_undecryptable_credentials_is_reauth_required(monkeypatch, caplog):
    """AC60：憑證解不開 → REAUTH_REQUIRED，記 warning。"""
    monkeypatch.setattr(platform_router, "sync_account", _sync_returning(SyncResult(SyncOutcome.UNDECRYPTABLE)))

    with caplog.at_level(logging.WARNING), pytest.raises(AppError) as exc_info:
        await platform_router.sync_platform_items_now(GITHUB, USER, Response())

    assert exc_info.value.error_code == "REAUTH_REQUIRED"
    assert any(r.levelno == logging.WARNING for r in caplog.records)


@pytest.mark.asyncio
async def test_incomplete_credentials_is_not_linked(monkeypatch):
    """AC62：憑證資料不完整 → NOT_LINKED 和該平台的說明。"""
    monkeypatch.setattr(platform_router, "sync_account", _sync_returning(SyncResult(SyncOutcome.INCOMPLETE_CREDENTIALS)))

    with pytest.raises(AppError) as exc_info:
        await platform_router.sync_platform_items_now(GITHUB, USER, Response())

    assert exc_info.value.error_code == "NOT_LINKED"
    assert exc_info.value.detail == GITHUB.not_linked_detail


@pytest.mark.asyncio
async def test_other_credential_errors_are_internal_error_not_reauth(monkeypatch):
    """解密以外的例外（例如伺服器沒設加密金鑰）→ INTERNAL_ERROR，不標成要重新連結。"""
    await link_github()
    monkeypatch.delenv("SECRET_ENCRYPTION_KEY")

    with pytest.raises(AppError) as exc_info:
        await platform_router.sync_platform_items_now(GITHUB, USER, Response())

    assert exc_info.value.error_code == "INTERNAL_ERROR"


@pytest.mark.asyncio
@pytest.mark.parametrize("error, error_code", [
    (ServerSelectionTimeoutError("down"), "SERVICE_UNAVAILABLE"),
    (OperationFailure("bad"), "INTERNAL_ERROR"),
], ids=["db-unavailable", "db-error"])
async def test_database_error_during_sync(monkeypatch, error, error_code):
    """同步途中資料庫出錯：連不上是 SERVICE_UNAVAILABLE，其他 INTERNAL_ERROR。"""
    monkeypatch.setattr(platform_router, "sync_account", _sync_raising(error))

    with pytest.raises(AppError) as exc_info:
        await platform_router.sync_platform_items_now(GITHUB, USER, Response())

    assert exc_info.value.error_code == error_code


@pytest.mark.asyncio
@pytest.mark.parametrize("outcome", [SyncOutcome.SUPERSEDED, SyncOutcome.LOCK_LOST, SyncOutcome.ACCOUNT_CHANGED])
async def test_results_replaced_by_another_sync_return_db_items(monkeypatch, outcome):
    """AC57、AC63、AC65：被取代、鎖被拿走、換成另一次連結 → 回資料庫目前的項目與資料庫裡的同步時間、授權狀態。"""
    await link_github(last_synced_at=SYNCED_AT, last_sync_error_code="REAUTH_REQUIRED")
    await db.github_issues.insert_one({"id": 1, "title": "資料庫", "user_id": USER})
    monkeypatch.setattr(platform_router, "sync_account", _sync_returning(SyncResult(outcome)))

    response = Response()
    result = await platform_router.sync_platform_items_now(GITHUB, USER, response)

    assert [i["title"] for i in result] == ["資料庫"]
    assert response.headers["X-Synced-At"] == SYNCED_AT.isoformat()
    assert response.headers["X-Auth-Error"] == "true"


@pytest.mark.asyncio
async def test_account_changed_and_removed_is_not_linked(monkeypatch):
    """AC64：帳號已變更而且已經不存在 → NOT_LINKED。"""
    monkeypatch.setattr(platform_router, "sync_account", _sync_returning(SyncResult(SyncOutcome.ACCOUNT_CHANGED)))

    with pytest.raises(AppError) as exc_info:
        await platform_router.sync_platform_items_now(GITHUB, USER, Response())

    assert exc_info.value.error_code == "NOT_LINKED"


@pytest.mark.asyncio
@pytest.mark.parametrize("has_old_data", [True, False], ids=["with-old-data", "without-old-data"])
async def test_lock_timeout(monkeypatch, has_old_data):
    """AC58、AC59：等不到鎖 → 有舊資料回舊資料與 X-Data-Stale；沒有就 SERVICE_UNAVAILABLE。"""
    await link_github()
    if has_old_data:
        await db.github_issues.insert_one({"id": 1, "title": "舊資料", "user_id": USER})
    monkeypatch.setattr(platform_router, "sync_account", _sync_returning(
        SyncResult(SyncOutcome.LOCK_TIMEOUT, error_code="SERVICE_UNAVAILABLE"),
    ))

    response = Response()
    if has_old_data:
        result = await platform_router.sync_platform_items_now(GITHUB, USER, response)
        assert [i["title"] for i in result] == ["舊資料"]
        assert response.headers["X-Data-Stale"] == "true"
    else:
        with pytest.raises(AppError) as exc_info:
            await platform_router.sync_platform_items_now(GITHUB, USER, response)
        assert exc_info.value.error_code == "SERVICE_UNAVAILABLE"


# ---------- 寫入途中被打斷（真的同步流程） ----------

@pytest.fixture
def paused_write(monkeypatch):
    """抓到的項目「這次抓到」寫入時暫停；回傳 (reached, release)。"""
    monkeypatch.setattr(account_sync, "LOCK_POLL_SECONDS", 0.01)
    fetch = ControlledFetch()
    monkeypatch.setattr(GITHUB, "fetch_items", fetch)
    _, gate = fetch.plan([item(1, "這次抓到")])
    gate.set()
    items = PausingCollection(db.github_issues)
    monkeypatch.setattr(db, "github_issues", items)
    return items.pause_on("這次抓到")


@pytest.mark.asyncio
async def test_lock_taken_while_writing_returns_db_items(paused_write):
    """AC63：寫入途中發現鎖已經不是自己的 → 回資料庫目前的項目（含這次抓不到的那筆）與資料庫的 X-Synced-At，同步結果不變。"""
    reached, release = paused_write
    await link_github(last_synced_at=PAST)
    await db.github_issues.insert_one({"id": 9, "title": "這次抓不到", "user_id": USER})

    response = Response()
    task = asyncio.create_task(platform_router.sync_platform_items_now(GITHUB, USER, response))
    await reached.wait()
    await db.linkedAccounts.update_one({"_id": ACCOUNT_ID}, {"$set": {"sync_lock_owner": "someone-else"}})
    release.set()
    result = await task

    assert "這次抓不到" in [i["title"] for i in result]
    assert response.headers["X-Synced-At"] == PAST.isoformat()
    doc = await account()
    assert doc is not None
    assert doc["last_synced_at"] == PAST
    assert "last_sync_error_code" not in doc


@pytest.mark.asyncio
async def test_account_deleted_while_writing_is_not_linked(paused_write):
    """AC64：寫入項目期間帳號連結被刪除 → NOT_LINKED。"""
    reached, release = paused_write
    await link_github()

    task = asyncio.create_task(platform_router.sync_platform_items_now(GITHUB, USER, Response()))
    await reached.wait()
    await db.linkedAccounts.delete_one({"_id": ACCOUNT_ID})
    release.set()

    with pytest.raises(AppError) as exc_info:
        await task
    assert exc_info.value.error_code == "NOT_LINKED"


# ---------- GET ----------

@pytest.mark.asyncio
async def test_get_does_not_decrypt_or_fetch(monkeypatch):
    """AC16：GET 只讀資料庫：憑證壞掉也照樣回項目，不抓資料。"""
    await link_github(apiKey="not-actually-encrypted")
    await db.github_issues.insert_one({"id": 1, "title": "資料庫", "user_id": USER})

    async def fail(*args, **kwargs):
        raise AssertionError("GET 不能同步")

    monkeypatch.setattr(platform_router, "sync_account", fail)

    response = Response()
    result = await platform_router.get_platform_items(GITHUB, USER, response)

    assert [i["title"] for i in result] == ["資料庫"]


@pytest.mark.asyncio
async def test_get_not_linked():
    """AC21：沒有連結該平台 → NOT_LINKED 和該平台的說明。"""
    with pytest.raises(AppError) as exc_info:
        await platform_router.get_platform_items(GITHUB, USER, Response())

    assert exc_info.value.error_code == "NOT_LINKED"
    assert exc_info.value.detail == GITHUB.not_linked_detail


def test_each_platform_sync_endpoint_has_its_own_rate_limit_entry():
    """AC26：只有 POST 限流；各平台函式名稱不同，各自登記自己的限流規則，計數不會共用。"""
    from core.rate_limit import limiter

    registered = {name: [str(l.limit) for l in limits]
                  for name, limits in limiter._route_limits.items() if name.startswith("platforms.router.")}

    assert registered == {
        "platforms.router.sync_github_items": ["10 per 1 minute"],
        "platforms.router.sync_jira_items": ["30 per 1 minute"],
        "platforms.router.sync_moodle_items": ["5 per 1 minute"],
    }
