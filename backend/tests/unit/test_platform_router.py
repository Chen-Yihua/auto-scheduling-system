# get_platform_items 的狀態碼、header 和快取；每個案例對三個平台各跑一次。sync 在這裡換成假的
from datetime import datetime, timezone

import logging

import pytest
from fastapi import Response
from pymongo.errors import OperationFailure, ServerSelectionTimeoutError

from core import cache
import platforms.router as platform_router
from core import database
import httpx
from platforms.sync import InvalidResponseError, NonRetryableError, UpstreamError
from core.errors import AppError
from core.crypto import encrypt_secret
from platforms.github import GITHUB
from platforms.jira import JIRA
from platforms.moodle import MOODLE

USER_ID = "test_user_123"
SYNCED_AT = datetime(2026, 9, 1, tzinfo=timezone.utc)
ITEM = {"id": "item-1", "title": "項目"}

# 每個平台存在 linkedAccounts 的帳號資料（密文是真的加密過的），以及解密後應該拿去抓資料的憑證
PLATFORM_CASES = [
    pytest.param(GITHUB, {"apiKey": encrypt_secret("gh-token")}, {"token": "gh-token"}, id="github"),
    pytest.param(
        JIRA,
        {"apiKey": encrypt_secret("jira-key"), "domain": "team.atlassian.net"},
        {"api_key": "jira-key", "domain": "team.atlassian.net"},
        id="jira",
    ),
    pytest.param(
        MOODLE,
        {"username": "stu001", "password": encrypt_secret("moodle-pw")},
        {"username": "stu001", "password": "moodle-pw"},
        id="moodle",
    ),
]


class FakeLinkedAccounts:
    def __init__(self, account):
        self.account = account
        self.queries = []

    async def find_one(self, query):
        self.queries.append(query)
        return self.account


@pytest.fixture(autouse=True)
def clear_cache():
    """有些平台（Moodle）有快取，清乾淨避免測試之間互相汙染。"""
    cache._memory_store.clear()
    yield
    cache._memory_store.clear()


def _use_account(monkeypatch, account):
    accounts = FakeLinkedAccounts(account)
    monkeypatch.setattr(database.db, "linkedAccounts", accounts)
    return accounts


def _sync_returning(items, stale=False, synced_at=SYNCED_AT, auth_error=False, calls=None):
    async def fake_sync(user_id, fetch_fn):
        if calls is not None:
            calls.append(user_id)
        return items, stale, synced_at, auth_error
    return fake_sync


@pytest.mark.asyncio
@pytest.mark.parametrize("platform, account, expected_credentials", PLATFORM_CASES)
async def test_fetches_with_decrypted_credentials_and_returns_items(monkeypatch, platform, account, expected_credentials):
    """成功流程：用解密後的憑證抓資料並回傳，X-Data-Stale 為 false。"""
    accounts = _use_account(monkeypatch, account)
    received = []

    async def fake_fetch_items(credentials):
        received.append(credentials)
        return [ITEM]

    async def fake_sync(user_id, fetch_fn):
        # 真的執行交給 sync 的 fetch_fn，才測得到「解密 → 抓資料」這段
        return await fetch_fn(), False, SYNCED_AT, False

    monkeypatch.setattr(platform, "fetch_items", fake_fetch_items)
    monkeypatch.setattr(platform, "sync_items", fake_sync)

    response = Response()
    result = await platform_router.get_platform_items(platform, USER_ID, response)

    assert result == [ITEM]
    assert received == [expected_credentials]
    assert accounts.queries == [{"_id": f"{USER_ID}_{platform.name}"}]
    assert response.headers["X-Data-Stale"] == "false"
    assert response.headers["X-Synced-At"] == SYNCED_AT.isoformat()


@pytest.mark.asyncio
@pytest.mark.parametrize("platform", [GITHUB, JIRA, MOODLE], ids=lambda p: p.name)
@pytest.mark.parametrize("account", [None, {}], ids=["no-account", "account-without-credentials"])
async def test_raises_400_not_linked_when_account_not_linked(monkeypatch, platform, account):
    """還沒綁定或沒有憑證 → 400 NOT_LINKED 和該平台的說明。"""
    _use_account(monkeypatch, account)

    with pytest.raises(AppError) as exc_info:
        await platform_router.get_platform_items(platform, USER_ID, Response())

    assert exc_info.value.status_code == 400
    assert exc_info.value.error_code == "NOT_LINKED"
    assert exc_info.value.detail == platform.not_linked_detail


@pytest.mark.asyncio
@pytest.mark.parametrize("platform, account, _", PLATFORM_CASES)
async def test_raises_500_reauth_required_when_decrypt_fails(monkeypatch, platform, account, _, caplog):
    """AC10：憑證解不開 → 維持 500，error_code 是 REAUTH_REQUIRED，記 warning；不能把壞掉的密文拿去打平台。"""
    broken = {key: ("not-actually-encrypted" if key in ("apiKey", "password") else value) for key, value in account.items()}
    _use_account(monkeypatch, broken)

    with caplog.at_level(logging.WARNING), pytest.raises(AppError) as exc_info:
        await platform_router.get_platform_items(platform, USER_ID, Response())

    assert exc_info.value.status_code == 500
    assert exc_info.value.error_code == "REAUTH_REQUIRED"
    assert any(r.levelno == logging.WARNING for r in caplog.records)


@pytest.mark.asyncio
async def test_other_credential_errors_are_internal_error_not_reauth(monkeypatch):
    """AC18：解密以外的例外（例如伺服器沒設加密金鑰）→ 500 INTERNAL_ERROR，不標成要重新連結。"""
    _use_account(monkeypatch, {"apiKey": encrypt_secret("gh-token")})
    monkeypatch.delenv("SECRET_ENCRYPTION_KEY")

    with pytest.raises(AppError) as exc_info:
        await platform_router.get_platform_items(GITHUB, USER_ID, Response())

    assert exc_info.value.status_code == 500
    assert exc_info.value.error_code == "INTERNAL_ERROR"


@pytest.mark.asyncio
@pytest.mark.parametrize("platform, account, _", PLATFORM_CASES)
async def test_raises_401_reauth_when_credentials_rejected_and_no_cached_data(monkeypatch, platform, account, _):
    """平台拒絕憑證（token 過期、密碼改了）而且沒有舊資料可退 → 401 REAUTH_REQUIRED，提示使用者重新連結。"""
    _use_account(monkeypatch, account)

    async def fake_sync(user_id, fetch_fn):
        raise NonRetryableError("401 Unauthorized")

    monkeypatch.setattr(platform, "sync_items", fake_sync)

    with pytest.raises(AppError) as exc_info:
        await platform_router.get_platform_items(platform, USER_ID, Response())

    assert exc_info.value.status_code == 401
    assert exc_info.value.error_code == "REAUTH_REQUIRED"
    assert exc_info.value.detail == platform.auth_failed_detail


@pytest.mark.asyncio
@pytest.mark.parametrize("error_code", ["UPSTREAM_RATE_LIMITED", "INTERNAL_ERROR", "UPSTREAM_ERROR"])
async def test_non_retryable_errors_other_than_reauth_keep_401_with_their_error_code(monkeypatch, error_code):
    """AC5、AC6：不重試的限流、400、404 沒有舊資料時仍是 401，但 error_code 照原因，detail 不說授權已失效。"""
    _use_account(monkeypatch, {"apiKey": encrypt_secret("gh-token")})

    async def fake_sync(user_id, fetch_fn):
        raise NonRetryableError("GitHub API failed: 403 secret-upstream-text", error_code=error_code)

    monkeypatch.setattr(GITHUB, "sync_items", fake_sync)

    with pytest.raises(AppError) as exc_info:
        await platform_router.get_platform_items(GITHUB, USER_ID, Response())

    assert exc_info.value.status_code == 401
    assert exc_info.value.error_code == error_code
    assert "授權已失效" not in exc_info.value.detail
    assert "secret-upstream-text" not in exc_info.value.detail


@pytest.mark.asyncio
@pytest.mark.parametrize("platform, account, _", PLATFORM_CASES)
@pytest.mark.parametrize("error, error_code", [
    (UpstreamError("503 Service Unavailable"), "UPSTREAM_ERROR"),
    (UpstreamError("429", error_code="UPSTREAM_RATE_LIMITED"), "UPSTREAM_RATE_LIMITED"),
    (httpx.ConnectError("連不上"), "UPSTREAM_ERROR"),
    (httpx.ReadTimeout("逾時"), "UPSTREAM_TIMEOUT"),
], ids=["5xx", "429", "connect-error", "timeout"])
async def test_raises_502_when_platform_unavailable_and_no_cached_data(monkeypatch, platform, account, _, error, error_code):
    """平台暫時掛掉、限流或連不上，而且沒有舊資料可退 → 502，error_code 照原因，跟我們自己的 bug（500）區分。"""
    _use_account(monkeypatch, account)

    async def fake_sync(user_id, fetch_fn):
        raise error

    monkeypatch.setattr(platform, "sync_items", fake_sync)

    with pytest.raises(AppError) as exc_info:
        await platform_router.get_platform_items(platform, USER_ID, Response())

    assert exc_info.value.status_code == 502
    assert exc_info.value.error_code == error_code


@pytest.mark.asyncio
async def test_raises_500_upstream_error_when_response_unparsable(monkeypatch):
    """AC6：回應無法解析而且沒有舊資料 → 維持 500，error_code 是 UPSTREAM_ERROR。"""
    _use_account(monkeypatch, {"apiKey": encrypt_secret("gh-token")})

    async def fake_sync(user_id, fetch_fn):
        raise InvalidResponseError("not json")

    monkeypatch.setattr(GITHUB, "sync_items", fake_sync)

    with pytest.raises(AppError) as exc_info:
        await platform_router.get_platform_items(GITHUB, USER_ID, Response())

    assert exc_info.value.status_code == 500
    assert exc_info.value.error_code == "UPSTREAM_ERROR"


@pytest.mark.asyncio
@pytest.mark.parametrize("error, error_code", [
    (ServerSelectionTimeoutError("down"), "SERVICE_UNAVAILABLE"),
    (OperationFailure("bad"), "INTERNAL_ERROR"),
], ids=["db-unavailable", "db-error"])
async def test_database_error_during_sync_keeps_500(monkeypatch, error, error_code):
    """AC6：同步途中資料庫出錯維持 500；連不上是 SERVICE_UNAVAILABLE，其他 INTERNAL_ERROR。"""
    _use_account(monkeypatch, {"apiKey": encrypt_secret("gh-token")})

    async def fake_sync(user_id, fetch_fn):
        raise error

    monkeypatch.setattr(GITHUB, "sync_items", fake_sync)

    with pytest.raises(AppError) as exc_info:
        await platform_router.get_platform_items(GITHUB, USER_ID, Response())

    assert exc_info.value.status_code == 500
    assert exc_info.value.error_code == error_code


@pytest.mark.asyncio
@pytest.mark.parametrize("platform, account, _", PLATFORM_CASES)
async def test_raises_500_on_unexpected_sync_error(monkeypatch, platform, account, _):
    """同步時出現未預期的錯誤 → 500 INTERNAL_ERROR 和固定中文訊息；內部錯誤原因只寫進 log，不回傳給前端。"""
    _use_account(monkeypatch, account)

    async def fake_sync(user_id, fetch_fn):
        raise RuntimeError("unexpected bug")

    monkeypatch.setattr(platform, "sync_items", fake_sync)

    with pytest.raises(AppError) as exc_info:
        await platform_router.get_platform_items(platform, USER_ID, Response())

    assert exc_info.value.status_code == 500
    assert exc_info.value.error_code == "INTERNAL_ERROR"
    assert exc_info.value.detail == platform.fetch_failed_detail


@pytest.mark.asyncio
async def test_stale_data_with_auth_error_sets_both_headers(monkeypatch):
    """憑證失效但有舊資料 → 回舊資料，設 X-Data-Stale 和 X-Auth-Error。"""
    _use_account(monkeypatch, {"apiKey": encrypt_secret("gh-token")})
    monkeypatch.setattr(GITHUB, "sync_items", _sync_returning([ITEM], stale=True, auth_error=True))

    response = Response()
    result = await platform_router.get_platform_items(GITHUB, USER_ID, response)

    assert result == [ITEM]
    assert response.headers["X-Data-Stale"] == "true"
    assert response.headers["X-Auth-Error"] == "true"


@pytest.mark.asyncio
async def test_stale_data_without_auth_error_omits_auth_header(monkeypatch):
    """平台暫時連不上而退回舊資料 → 設 X-Data-Stale，不設 X-Auth-Error。"""
    _use_account(monkeypatch, {"apiKey": encrypt_secret("gh-token")})
    monkeypatch.setattr(GITHUB, "sync_items", _sync_returning([ITEM], stale=True, auth_error=False))

    response = Response()
    await platform_router.get_platform_items(GITHUB, USER_ID, response)

    assert response.headers["X-Data-Stale"] == "true"
    assert "X-Auth-Error" not in response.headers


# ---------- 快取：只有抓取成本高、有設 cache_ttl_seconds 的平台（Moodle 爬蟲）才有 ----------

MOODLE_ACCOUNT = {"username": "stu001", "password": encrypt_secret("moodle-pw")}


@pytest.mark.asyncio
async def test_cached_platform_second_call_within_ttl_skips_fetch_entirely(monkeypatch):
    """短時間內重複整理：第二次直接用快取，不再重新爬 Moodle（每次都要開瀏覽器，成本高）。"""
    _use_account(monkeypatch, MOODLE_ACCOUNT)
    calls = []
    monkeypatch.setattr(MOODLE, "sync_items", _sync_returning([ITEM], calls=calls))

    first = await platform_router.get_platform_items(MOODLE, USER_ID, Response())
    second_response = Response()
    second = await platform_router.get_platform_items(MOODLE, USER_ID, second_response)

    assert first == second == [ITEM]
    assert len(calls) == 1
    assert second_response.headers["X-Data-Stale"] == "false"
    assert second_response.headers["X-Synced-At"] == SYNCED_AT.isoformat()


@pytest.mark.asyncio
async def test_cached_platform_does_not_cache_stale_fallback(monkeypatch):
    """退回的舊資料不快取，下次請求才會重新抓取。"""
    _use_account(monkeypatch, MOODLE_ACCOUNT)
    calls = []
    monkeypatch.setattr(MOODLE, "sync_items", _sync_returning([ITEM], stale=True, calls=calls))

    await platform_router.get_platform_items(MOODLE, USER_ID, Response())
    await platform_router.get_platform_items(MOODLE, USER_ID, Response())

    assert len(calls) == 2


@pytest.mark.asyncio
async def test_platform_without_cache_ttl_always_fetches_live(monkeypatch):
    """沒設快取的平台（GitHub）每次都即時抓，使用者剛關掉的 issue 重新整理就看得到。"""
    _use_account(monkeypatch, {"apiKey": encrypt_secret("gh-token")})
    calls = []
    monkeypatch.setattr(GITHUB, "sync_items", _sync_returning([ITEM], calls=calls))

    await platform_router.get_platform_items(GITHUB, USER_ID, Response())
    await platform_router.get_platform_items(GITHUB, USER_ID, Response())

    assert len(calls) == 2


def test_each_platform_endpoint_has_its_own_rate_limit_entry():
    """各平台 endpoint 的函式名稱不同，各自登記自己的限流規則，計數不會共用。"""
    from core.rate_limit import limiter

    registered = {name: [str(l.limit) for l in limits]
                  for name, limits in limiter._route_limits.items() if name.startswith("platforms.router.")}

    assert registered == {
        "platforms.router.get_github_items": ["10 per 1 minute"],
        "platforms.router.get_jira_items": ["30 per 1 minute"],
        "platforms.router.get_moodle_items": ["5 per 1 minute"],
    }
