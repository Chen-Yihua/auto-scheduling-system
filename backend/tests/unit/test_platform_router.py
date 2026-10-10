# 所有外部平台共用的「取得項目」流程（platforms/router.py 的 get_platform_items）：
# 查不到帳號、解密失敗、抓取失敗各回什麼狀態碼、有沒有設定回應 header，以及快取。
# 每種行為對 GitHub／Jira／Moodle 各跑一次，確認每個平台都接上了同一套流程、錯誤訊息也是各自的。
# 同步流程本身（重試、退回舊資料、寫入資料庫）由 test_platform_sync.py 負責，這裡直接換成假的；
# 各平台怎麼抓資料、怎麼轉格式，由 test_github_crud.py 等各平台自己的測試負責。
from datetime import datetime, timezone

import pytest
from fastapi import HTTPException, Response

from core import cache
import platforms.router as platform_router
import httpx
from platforms.sync import NonRetryableError, UpstreamError
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
    monkeypatch.setattr(platform_router.db, "linkedAccounts", accounts)
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
    """成功流程：用使用者 id + 平台名稱查到帳號 → 解密 → 用明文憑證抓資料 → 回傳項目，
    X-Data-Stale 為 false。抓資料拿到的是解密後的明文，不是資料庫裡的密文。"""
    accounts = _use_account(monkeypatch, account)
    received = []

    async def fake_fetch_items(credentials):
        received.append(credentials)
        return [ITEM]

    async def fake_sync(user_id, fetch_fn):
        # 真的執行交給 sync 的 fetch_fn，才測得到「解密 → 抓資料」這段
        return await fetch_fn(), False, SYNCED_AT, False

    monkeypatch.setattr(platform, "fetch_items", fake_fetch_items)
    monkeypatch.setattr(platform, "sync", fake_sync)

    response = Response()
    result = await platform_router.get_platform_items(platform, USER_ID, response)

    assert result == [ITEM]
    assert received == [expected_credentials]
    assert accounts.queries == [{"clerk_id": USER_ID, "platform": platform.name}]
    assert response.headers["X-Data-Stale"] == "false"
    assert response.headers["X-Synced-At"] == SYNCED_AT.isoformat()


@pytest.mark.asyncio
@pytest.mark.parametrize("platform", [GITHUB, JIRA, MOODLE], ids=lambda p: p.name)
@pytest.mark.parametrize("account", [None, {}], ids=["no-account", "account-without-credentials"])
async def test_raises_400_when_account_not_linked(monkeypatch, platform, account):
    """還沒綁定這個平台、或帳號資料裡沒有憑證 → 400 加上這個平台自己的說明，
    前端才能顯示「請先設定帳號」。"""
    _use_account(monkeypatch, account)

    with pytest.raises(HTTPException) as exc_info:
        await platform_router.get_platform_items(platform, USER_ID, Response())

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == platform.not_linked_detail


@pytest.mark.asyncio
@pytest.mark.parametrize("platform, account, _", PLATFORM_CASES)
async def test_raises_500_when_decrypt_fails(monkeypatch, platform, account, _):
    """憑證解密失敗（資料壞掉或金鑰不對）→ 500，不能把壞掉的密文拿去打平台。"""
    broken = {key: ("not-actually-encrypted" if key in ("apiKey", "password") else value) for key, value in account.items()}
    _use_account(monkeypatch, broken)

    with pytest.raises(HTTPException) as exc_info:
        await platform_router.get_platform_items(platform, USER_ID, Response())

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == platform.fetch_failed_detail


@pytest.mark.asyncio
@pytest.mark.parametrize("platform, account, _", PLATFORM_CASES)
async def test_raises_401_when_credentials_rejected_and_no_cached_data(monkeypatch, platform, account, _):
    """平台拒絕憑證（token 過期、密碼改了）而且沒有舊資料可退 → 401，提示使用者重新連結。"""
    _use_account(monkeypatch, account)

    async def fake_sync(user_id, fetch_fn):
        raise NonRetryableError("401 Unauthorized")

    monkeypatch.setattr(platform, "sync", fake_sync)

    with pytest.raises(HTTPException) as exc_info:
        await platform_router.get_platform_items(platform, USER_ID, Response())

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == platform.auth_failed_detail


@pytest.mark.asyncio
@pytest.mark.parametrize("platform, account, _", PLATFORM_CASES)
@pytest.mark.parametrize("error", [UpstreamError("503 Service Unavailable"), httpx.ConnectError("連不上")])
async def test_raises_502_when_platform_unavailable_and_no_cached_data(monkeypatch, platform, account, _, error):
    """平台暫時掛掉或連不上，而且沒有舊資料可退 → 502，跟我們自己的 bug（500）區分。"""
    _use_account(monkeypatch, account)

    async def fake_sync(user_id, fetch_fn):
        raise error

    monkeypatch.setattr(platform, "sync", fake_sync)

    with pytest.raises(HTTPException) as exc_info:
        await platform_router.get_platform_items(platform, USER_ID, Response())

    assert exc_info.value.status_code == 502
    assert exc_info.value.detail == platform.fetch_failed_detail


@pytest.mark.asyncio
@pytest.mark.parametrize("platform, account, _", PLATFORM_CASES)
async def test_raises_500_on_unexpected_sync_error(monkeypatch, platform, account, _):
    """同步時出現未預期的錯誤 → 500 和固定中文訊息；內部錯誤原因只寫進 log，不回傳給前端。"""
    _use_account(monkeypatch, account)

    async def fake_sync(user_id, fetch_fn):
        raise RuntimeError("unexpected bug")

    monkeypatch.setattr(platform, "sync", fake_sync)

    with pytest.raises(HTTPException) as exc_info:
        await platform_router.get_platform_items(platform, USER_ID, Response())

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == platform.fetch_failed_detail


@pytest.mark.asyncio
async def test_stale_data_with_auth_error_sets_both_headers(monkeypatch):
    """憑證已失效、但有舊資料可顯示 → 回舊資料，X-Data-Stale 標示是舊的、
    X-Auth-Error 告訴前端要請使用者重新連結。"""
    _use_account(monkeypatch, {"apiKey": encrypt_secret("gh-token")})
    monkeypatch.setattr(GITHUB, "sync", _sync_returning([ITEM], stale=True, auth_error=True))

    response = Response()
    result = await platform_router.get_platform_items(GITHUB, USER_ID, response)

    assert result == [ITEM]
    assert response.headers["X-Data-Stale"] == "true"
    assert response.headers["X-Auth-Error"] == "true"


@pytest.mark.asyncio
async def test_stale_data_without_auth_error_omits_auth_header(monkeypatch):
    """平台暫時連不上、退回舊資料（不是憑證問題）→ X-Data-Stale 為 true，
    但不設 X-Auth-Error，不能叫使用者去重新連結一個其實沒問題的帳號。"""
    _use_account(monkeypatch, {"apiKey": encrypt_secret("gh-token")})
    monkeypatch.setattr(GITHUB, "sync", _sync_returning([ITEM], stale=True, auth_error=False))

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
    monkeypatch.setattr(MOODLE, "sync", _sync_returning([ITEM], calls=calls))

    first = await platform_router.get_platform_items(MOODLE, USER_ID, Response())
    second_response = Response()
    second = await platform_router.get_platform_items(MOODLE, USER_ID, second_response)

    assert first == second == [ITEM]
    assert len(calls) == 1
    assert second_response.headers["X-Data-Stale"] == "false"
    assert second_response.headers["X-Synced-At"] == SYNCED_AT.isoformat()


@pytest.mark.asyncio
async def test_cached_platform_does_not_cache_stale_fallback(monkeypatch):
    """抓取失敗、只能退回舊資料時，這份舊資料不能被快取——否則下一次請求會直接讀到
    「已知是舊的」快取，錯過重新嘗試抓取的機會。"""
    _use_account(monkeypatch, MOODLE_ACCOUNT)
    calls = []
    monkeypatch.setattr(MOODLE, "sync", _sync_returning([ITEM], stale=True, calls=calls))

    await platform_router.get_platform_items(MOODLE, USER_ID, Response())
    await platform_router.get_platform_items(MOODLE, USER_ID, Response())

    assert len(calls) == 2


@pytest.mark.asyncio
async def test_platform_without_cache_ttl_always_fetches_live(monkeypatch):
    """沒設快取的平台（GitHub）每次都即時抓，使用者剛關掉的 issue 重新整理就看得到。"""
    _use_account(monkeypatch, {"apiKey": encrypt_secret("gh-token")})
    calls = []
    monkeypatch.setattr(GITHUB, "sync", _sync_returning([ITEM], calls=calls))

    await platform_router.get_platform_items(GITHUB, USER_ID, Response())
    await platform_router.get_platform_items(GITHUB, USER_ID, Response())

    assert len(calls) == 2


def test_each_platform_endpoint_has_its_own_rate_limit_entry():
    """每個平台的 endpoint 都是同一個內部函式產生的；slowapi 用函式名稱登記限流規則，
    名稱沒分開的話，兩個有限流的平台會共用同一組規則跟計數。只有設了 rate_limit 的平台才會被登記。"""
    from core.rate_limit import limiter

    registered = {name: [str(l.limit) for l in limits]
                  for name, limits in limiter._route_limits.items() if name.startswith("platforms.router.")}

    assert registered == {"platforms.router.get_moodle_items": ["5 per 1 minute"]}
