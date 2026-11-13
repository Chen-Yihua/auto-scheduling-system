"""三個平台共用的 GET（只讀資料庫）與 POST /{platform}/sync（立即同步）：header、限流、跨網域，以及同步的特殊結果。"""
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from httpx._transports.asgi import ASGITransport

import platforms.account_sync as account_sync
from core.database import db
from core.rate_limit import limiter
from main import app
from platforms.github import GITHUB, transform_github_item
from platforms.jira import JIRA, transform_jira_item
from platforms.moodle import MOODLE
from tests.integration.platform_http_fakes import (  # noqa: F401  clean_platform_data 是 fixture
    USER_ID,
    clean_platform_data,
    link_account,
    reset_items,
)

SYNCED_AT = datetime(2026, 11, 1, 4, 0, tzinfo=timezone.utc)

def _github_item(item_id: int, title: str) -> dict:
    return transform_github_item({
        "id": item_id, "number": item_id, "title": title, "state": "open", "created_at": "2026-01-01T00:00:00Z",
        "html_url": f"https://github.com/o/r/issues/{item_id}", "user": {"login": "u", "avatar_url": ""},
    })


def _jira_item(item_id: str, title: str) -> dict:
    return transform_jira_item({"id": item_id, "key": f"P-{item_id}", "fields": {"summary": title}})


def _moodle_item(item_id: str, title: str) -> dict:
    return {"id": item_id, "course_name": "課", "title": title, "url": item_id, "due_date": "無截止日期"}


# (平台, 帳號欄位, 資料庫裡的舊項目, 這次抓到的項目)
PLATFORM_CASES = [
    pytest.param(GITHUB, {"apiKey": "gh-token"}, _github_item(1, "資料庫"), _github_item(2, "這次抓到"), id="github"),
    pytest.param(JIRA, {"apiKey": "jira-key", "domain": "team.atlassian.net"},
                 _jira_item("1", "資料庫"), _jira_item("2", "這次抓到"), id="jira"),
    pytest.param(MOODLE, {"username": "stu001", "password": "pw"},
                 _moodle_item("https://m/1", "資料庫"), _moodle_item("https://m/2", "這次抓到"), id="moodle"),
]


async def _set_account(platform, fields: dict) -> None:
    await db.linkedAccounts.update_one({"_id": f"{USER_ID}_{platform.name}"}, {"$set": fields})


async def _account(platform) -> dict | None:
    return await db.linkedAccounts.find_one({"_id": f"{USER_ID}_{platform.name}"})


async def _request(method: str, path: str, **kwargs):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        return await ac.request(method, path, **kwargs)


def _fetch_must_not_be_called(monkeypatch, platform):
    async def fail(credentials):
        raise AssertionError("不能向平台抓資料")

    monkeypatch.setattr(platform, "fetch_items", fail)


def _fetch_returns(monkeypatch, platform, items, *, during=None):
    async def fetch(credentials):
        if during is not None:
            await during()
        return [dict(i) for i in items]

    monkeypatch.setattr(platform, "fetch_items", fetch)


# ---------- GET：只讀資料庫 ----------

@pytest.mark.asyncio
@pytest.mark.parametrize("platform, fields, db_item, _", PLATFORM_CASES)
async def test_get_returns_db_items_without_fetching(monkeypatch, logged_in_user, clean_platform_data, platform, fields, db_item, _):
    """AC16：GET 回資料庫裡的項目，不向平台抓資料。"""
    await link_account(platform.name, fields)
    await reset_items(platform.collection, db_item)
    _fetch_must_not_be_called(monkeypatch, platform)

    res = await _request("GET", platform.route_path)

    assert res.status_code == 200
    assert [i["title"] for i in res.json()] == ["資料庫"]


@pytest.mark.asyncio
@pytest.mark.parametrize("platform, fields, db_item, _", PLATFORM_CASES)
async def test_get_sets_synced_at_from_last_successful_sync(monkeypatch, logged_in_user, clean_platform_data, platform, fields, db_item, _):
    """AC17：帳號有成功同步過時，GET 帶 X-Synced-At，值是最近一次成功同步的時間。"""
    await link_account(platform.name, fields)
    await _set_account(platform, {"last_synced_at": SYNCED_AT})
    await reset_items(platform.collection, db_item)

    res = await _request("GET", platform.route_path)

    assert res.headers["X-Synced-At"] == SYNCED_AT.isoformat()


@pytest.mark.asyncio
@pytest.mark.parametrize("platform, fields, db_item, _", PLATFORM_CASES)
async def test_get_without_sync_record_has_no_synced_at(monkeypatch, logged_in_user, clean_platform_data, platform, fields, db_item, _):
    """AC18：帳號從來沒有成功同步過時，GET 不帶 X-Synced-At（項目上的舊時間也不算）。"""
    await link_account(platform.name, fields)
    await reset_items(platform.collection, {**db_item, "synced_at": SYNCED_AT})

    res = await _request("GET", platform.route_path)

    assert "X-Synced-At" not in res.headers


@pytest.mark.asyncio
@pytest.mark.parametrize("platform, fields, db_item, _", PLATFORM_CASES)
@pytest.mark.parametrize("error_code, auth_error", [
    ("REAUTH_REQUIRED", True), ("UPSTREAM_ERROR", False), (None, False),
], ids=["reauth", "temporary-failure", "success"])
async def test_get_auth_error_follows_last_sync_result(
    monkeypatch, logged_in_user, clean_platform_data, platform, fields, db_item, _, error_code, auth_error,
):
    """AC19、AC20：最近一次同步因 REAUTH_REQUIRED 失敗時 GET 帶 X-Auth-Error: true；暫時性失敗或成功時不帶。"""
    await link_account(platform.name, fields)
    await _set_account(platform, {"last_sync_error_code": error_code})
    await reset_items(platform.collection, db_item)

    res = await _request("GET", platform.route_path)

    assert res.status_code == 200
    assert (res.headers.get("X-Auth-Error") == "true") is auth_error
    assert ("X-Auth-Error" in res.headers) is auth_error


# ---------- POST：限流 ----------

@pytest.fixture
def enabled_rate_limit():
    limiter.reset()
    limiter.enabled = True
    yield
    limiter.enabled = False
    limiter.reset()


@pytest.mark.asyncio
@pytest.mark.parametrize("platform, limit", [(GITHUB, 10), (JIRA, 30), (MOODLE, 5)], ids=["github", "jira", "moodle"])
async def test_sync_over_rate_limit_returns_429(monkeypatch, logged_in_user, enabled_rate_limit, platform, limit):
    """AC26：同一個使用者一分鐘內超過次數限制（GitHub 10、Jira 30、Moodle 5）時 POST 回 429。"""
    async def fake_sync_now(platform_arg, user_id, response):
        return []

    import platforms.router as platform_router
    monkeypatch.setattr(platform_router, "sync_platform_items_now", fake_sync_now)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        statuses = [(await ac.post(platform.sync_route_path)).status_code for _ in range(limit + 1)]

    assert statuses[:limit] == [200] * limit
    assert statuses[limit] == 429


@pytest.mark.asyncio
async def test_get_is_not_rate_limited(monkeypatch, logged_in_user, enabled_rate_limit, clean_platform_data):
    """GET 只讀資料庫，和其他讀取的 endpoint 一樣不限流。"""
    await link_account("moodle", {"username": "stu001", "password": "pw"})

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        statuses = [(await ac.get("/moodle/assignments")).status_code for _ in range(7)]

    assert statuses == [200] * 7


# ---------- 跨網域 ----------

@pytest.mark.asyncio
@pytest.mark.parametrize("method, path", [("GET", "/github/issues"), ("POST", "/github/sync")])
async def test_cross_origin_response_exposes_sync_headers(monkeypatch, logged_in_user, clean_platform_data, method, path):
    """AC56：帶 Origin 呼叫平台 GET 與 POST 時，Access-Control-Expose-Headers 包含三個同步狀態的 header。"""
    await link_account("github", {"apiKey": "gh-token"})
    _fetch_returns(monkeypatch, GITHUB, [])

    res = await _request(method, path, headers={"Origin": "http://localhost:3000"})

    exposed = {h.strip().lower() for h in res.headers["Access-Control-Expose-Headers"].split(",")}
    assert {"x-synced-at", "x-auth-error", "x-data-stale"} <= exposed


# ---------- POST：同步的特殊結果 ----------

@pytest.mark.asyncio
@pytest.mark.parametrize("platform, fields, db_item, fetched", PLATFORM_CASES)
async def test_superseded_sync_returns_db_items(monkeypatch, logged_in_user, clean_platform_data, platform, fields, db_item, fetched):
    """AC57：這次同步被比較晚開始的同步取代時，回資料庫目前的項目與資料庫裡的 X-Synced-At，不是這次抓到的。"""
    await link_account(platform.name, fields)
    await _set_account(platform, {
        "sync_started_at": datetime.now(timezone.utc) + timedelta(hours=1), "last_synced_at": SYNCED_AT,
    })
    await reset_items(platform.collection, db_item)
    _fetch_returns(monkeypatch, platform, [fetched])

    res = await _request("POST", platform.sync_route_path)

    assert res.status_code == 200
    assert [i["title"] for i in res.json()] == ["資料庫"]
    assert res.headers["X-Synced-At"] == SYNCED_AT.isoformat()


@pytest.mark.asyncio
@pytest.mark.parametrize("has_old_data", [True, False], ids=["with-old-data", "without-old-data"])
async def test_lock_wait_timeout(monkeypatch, logged_in_user, clean_platform_data, has_old_data):
    """AC58、AC59：等不到寫入鎖時，有舊資料回舊資料並帶 X-Data-Stale: true；沒有舊資料回 503 SERVICE_UNAVAILABLE。"""
    case = PLATFORM_CASES[0].values
    platform, fields, db_item, fetched = case[0], case[1], case[2], case[3]
    monkeypatch.setattr(account_sync, "LOCK_WAIT_SECONDS", 0.05)
    monkeypatch.setattr(account_sync, "LOCK_POLL_SECONDS", 0.01)
    await link_account(platform.name, fields)
    await _set_account(platform, {
        "sync_lock_owner": "someone-else", "sync_lock_until": datetime.now(timezone.utc) + timedelta(minutes=5),
    })
    await reset_items(platform.collection, db_item if has_old_data else None)
    _fetch_returns(monkeypatch, platform, [fetched])

    res = await _request("POST", platform.sync_route_path)

    if has_old_data:
        assert res.status_code == 200
        assert res.headers["X-Data-Stale"] == "true"
        assert [i["title"] for i in res.json()] == ["資料庫"]
    else:
        assert res.status_code == 503
        assert res.json()["error_code"] == "SERVICE_UNAVAILABLE"


@pytest.mark.asyncio
@pytest.mark.parametrize("platform, fields, _, __", PLATFORM_CASES)
async def test_undecryptable_credentials_keep_sync_result(monkeypatch, logged_in_user, clean_platform_data, platform, fields, _, __):
    """AC60：POST 解不開憑證時回 REAUTH_REQUIRED，不改這個帳號的同步結果與 sync_started_at。"""
    await link_account(platform.name, fields)
    started_at = datetime(2026, 10, 1, tzinfo=timezone.utc)
    await _set_account(platform, {
        platform.secret_field: "encrypted-with-another-key", "last_sync_error_code": "UPSTREAM_ERROR",
        "sync_started_at": started_at,
    })
    _fetch_must_not_be_called(monkeypatch, platform)

    res = await _request("POST", platform.sync_route_path)

    assert res.status_code == 409
    assert res.json()["error_code"] == "REAUTH_REQUIRED"
    doc = await _account(platform)
    assert doc is not None
    assert doc["last_sync_error_code"] == "UPSTREAM_ERROR"
    assert doc["sync_started_at"] == started_at


@pytest.mark.asyncio
@pytest.mark.parametrize("platform, fields, _, __", PLATFORM_CASES)
async def test_incomplete_credentials_is_not_linked(monkeypatch, logged_in_user, clean_platform_data, platform, fields, _, __):
    """AC62：帳號文件缺少憑證欄位時，POST 回 409 NOT_LINKED。"""
    await link_account(platform.name, fields)
    await db.linkedAccounts.update_one({"_id": f"{USER_ID}_{platform.name}"}, {"$unset": {platform.secret_field: ""}})
    _fetch_must_not_be_called(monkeypatch, platform)

    res = await _request("POST", platform.sync_route_path)

    assert res.status_code == 409
    assert res.json()["error_code"] == "NOT_LINKED"


@pytest.mark.asyncio
@pytest.mark.parametrize("platform, fields, _, fetched", PLATFORM_CASES)
async def test_account_deleted_during_sync_is_not_linked(monkeypatch, logged_in_user, clean_platform_data, platform, fields, _, fetched):
    """AC64：同步途中帳號連結被刪除時，POST 回 409 NOT_LINKED。"""
    await link_account(platform.name, fields)

    async def unlink():
        await db.linkedAccounts.delete_one({"_id": f"{USER_ID}_{platform.name}"})

    _fetch_returns(monkeypatch, platform, [fetched], during=unlink)

    res = await _request("POST", platform.sync_route_path)

    assert res.status_code == 409
    assert res.json()["error_code"] == "NOT_LINKED"


@pytest.mark.asyncio
@pytest.mark.parametrize("platform, fields, db_item, fetched", PLATFORM_CASES)
async def test_relinked_during_sync_returns_db_items(monkeypatch, logged_in_user, clean_platform_data, platform, fields, db_item, fetched):
    """AC65：同步途中帳號換成另一次連結時，回資料庫目前的項目與資料庫裡的 X-Synced-At。"""
    await link_account(platform.name, fields)
    await _set_account(platform, {"last_synced_at": SYNCED_AT})
    await reset_items(platform.collection, db_item)

    async def relink():
        await _set_account(platform, {"link_id": "another-link"})

    _fetch_returns(monkeypatch, platform, [fetched], during=relink)

    res = await _request("POST", platform.sync_route_path)

    assert res.status_code == 200
    assert [i["title"] for i in res.json()] == ["資料庫"]
    assert res.headers["X-Synced-At"] == SYNCED_AT.isoformat()
