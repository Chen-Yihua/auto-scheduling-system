# 透過 HTTP 確認路由、登入驗證、回應格式和錯誤狀態碼；細部邏輯由 unit 測試負責
import pytest
from fastapi import status
from httpx import AsyncClient
from httpx._transports.asgi import ASGITransport

from main import app
import platforms.router as platform_router
from core import database
from platforms.jira import JIRA


class MockLinkedAccounts:
    """模擬 db.linkedAccounts.find_one：使用者有綁定 Jira。"""

    async def find_one(self, query):
        return {"apiKey": "unused-because-sync-is-mocked", "domain": "fake.atlassian.net"}


class EmptyLinkedAccounts:
    """模擬 db.linkedAccounts.find_one：使用者還沒綁定 Jira。"""

    async def find_one(self, query):
        return None


@pytest.mark.asyncio
async def test_get_jira_issues(monkeypatch, logged_in_user):
    """GET /jira/issues 成功 → 200，回傳統一格式的 issue 清單，並用 X-Data-Stale 標示資料是最新的。"""
    # 解密、抓資料、同步各自有 router/crud 測試，這裡只確認 HTTP 這一層，所以直接讓 sync 回傳結果
    issue = {
        "id": "1",
        "key": "JIRA-1",
        "title": "Test Issue 1",
        "status": "In Progress",
        "updated_at": "2024-01-01T00:00:00.000+0000",
        "assignee": "User One",
        "avatar": "",
        "type": "Task",
        "iconUrl": "",
    }

    async def mock_sync(user_id, fetch_fn):
        return [issue], False, None, False

    monkeypatch.setattr(database.db, "linkedAccounts", MockLinkedAccounts())
    monkeypatch.setattr(platform_router, "decrypt_secret", lambda value: "fake_api_key")
    monkeypatch.setattr(JIRA, "sync_items", mock_sync)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/jira/issues")

    assert res.status_code == status.HTTP_200_OK
    # 排程欄位都是預設值，不列出
    body = res.json()
    assert len(body) == 1
    assert body[0]["id"] == issue["id"]
    assert body[0]["status_category"] == ""
    for key, value in issue.items():
        if key != "updated_at":
            assert body[0][key] == value
    # AC19：資料庫裡舊的字串時間照樣讀得出來，回應統一成 UTC
    assert body[0]["updated_at"] == "2024-01-01T00:00:00Z"
    assert res.headers["X-Data-Stale"] == "false"


@pytest.mark.asyncio
async def test_get_jira_issues_when_account_not_linked(monkeypatch, logged_in_user):
    """使用者還沒綁定 Jira → 409 NOT_LINKED 加說明，前端才能顯示「請先設定帳號」。"""
    monkeypatch.setattr(database.db, "linkedAccounts", EmptyLinkedAccounts())

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/jira/issues")

    assert res.status_code == status.HTTP_409_CONFLICT
    assert res.json() == {"detail": "No Jira linked account", "error_code": "NOT_LINKED"}


@pytest.mark.asyncio
async def test_get_jira_issues_requires_login():
    """沒帶登入 token → 被擋在門外（401/403），不能進到函式裡。"""
    # 這個測試刻意不用 logged_in_user，所以請求是沒登入的
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/jira/issues")

    assert res.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)


# ---------- 需求 5：Jira 每種錯誤回應的重試、狀態碼、error_code、X-Auth-Error ----------
import httpx as _httpx

import platforms.jira as jira_platform
from tests.integration.platform_http_fakes import (  # noqa: F401  clean_platform_data 是 fixture
    clean_platform_data,
    UPSTREAM_SECRET_TEXT,
    link_account,
    reset_items,
    response,
    skip_retry_delay,
    use_fake_http,
)

OLD_JIRA_ITEM = jira_platform.transform_jira_item({"id": "10001", "key": "P-1", "fields": {"summary": "舊資料"}})

JIRA_FETCH_CASES = [
    pytest.param(response(429), 2, 503, "UPSTREAM_RATE_LIMITED", False, id="429"),
    pytest.param(response(401), 1, 409, "REAUTH_REQUIRED", True, id="401"),
    pytest.param(response(403), 1, 409, "REAUTH_REQUIRED", True, id="403"),
    pytest.param(response(404), 1, 409, "REAUTH_REQUIRED", True, id="404"),
    pytest.param(response(400), 1, 500, "INTERNAL_ERROR", False, id="400"),
    pytest.param(response(500), 2, 502, "UPSTREAM_ERROR", False, id="5xx"),
    pytest.param(response(409), 2, 502, "UPSTREAM_ERROR", False, id="other-4xx"),
    pytest.param(response(302), 2, 502, "UPSTREAM_ERROR", False, id="3xx"),
    pytest.param(response(200, content=f"<html>{UPSTREAM_SECRET_TEXT}</html>".encode()), 2, 502, "UPSTREAM_ERROR", False, id="not-json"),
    pytest.param(_httpx.ConnectError("connection refused"), 2, 502, "UPSTREAM_ERROR", False, id="connect-error"),
    pytest.param(_httpx.ReadTimeout("timed out"), 2, 504, "UPSTREAM_TIMEOUT", False, id="timeout"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("outcome, attempts, status_code, error_code, _", JIRA_FETCH_CASES)
async def test_jira_fetch_error_without_cached_data(monkeypatch, logged_in_user, outcome, attempts, status_code, error_code, _, clean_platform_data):
    """AC1、AC9、AC10：沒有舊資料時，每種 Jira 錯誤的重試次數不變，狀態碼照 error_code 查表；detail 不帶 Jira 回應原文。"""
    await link_account("jira", {"apiKey": "jira-key", "domain": "team.atlassian.net"})
    await reset_items(database.db.jira_issues, None)
    skip_retry_delay(monkeypatch)
    client = use_fake_http(monkeypatch, jira_platform, outcome)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/jira/issues")

    assert client.calls == attempts
    assert res.status_code == status_code
    assert res.json()["error_code"] == error_code
    assert UPSTREAM_SECRET_TEXT not in res.text


@pytest.mark.asyncio
async def test_jira_fetch_404_asks_to_check_domain(monkeypatch, logged_in_user, clean_platform_data):
    """AC16：Jira 404 是 REAUTH_REQUIRED，detail 請使用者確認網域或重新連結。"""
    await link_account("jira", {"apiKey": "jira-key", "domain": "team.atlassian.net"})
    await reset_items(database.db.jira_issues, None)
    use_fake_http(monkeypatch, jira_platform, response(404))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/jira/issues")

    assert res.json() == {"detail": "Jira 網域可能已失效，請到設定確認或重新連結", "error_code": "REAUTH_REQUIRED"}


@pytest.mark.asyncio
@pytest.mark.parametrize("outcome, attempts, _, error_code, auth_error", JIRA_FETCH_CASES)
async def test_jira_fetch_error_with_cached_data(monkeypatch, logged_in_user, outcome, attempts, _, error_code, auth_error, clean_platform_data):
    """AC6：有舊資料時回舊資料；只有 401、403、404 設 X-Auth-Error。"""
    await link_account("jira", {"apiKey": "jira-key", "domain": "team.atlassian.net"})
    await reset_items(database.db.jira_issues, OLD_JIRA_ITEM)
    skip_retry_delay(monkeypatch)
    client = use_fake_http(monkeypatch, jira_platform, outcome)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/jira/issues")

    assert client.calls == attempts
    assert res.status_code == status.HTTP_200_OK
    assert res.headers["X-Data-Stale"] == "true"
    assert ("X-Auth-Error" in res.headers) is auth_error


# ---------- 外部限流帶 Retry-After（AC5）----------

@pytest.mark.asyncio
@pytest.mark.parametrize("outcome, retry_after", [
    pytest.param(response(429, {"Retry-After": "15"}), "15", id="seconds"),
    pytest.param(response(429), None, id="without"),
    pytest.param(response(429, {"Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT"}), None, id="http-date"),
])
async def test_jira_fetch_rate_limited_forwards_retry_after_seconds(monkeypatch, logged_in_user, outcome, retry_after, clean_platform_data):
    """AC5：Jira 抓項目限流 → 503 UPSTREAM_RATE_LIMITED；帶秒數的 Retry-After 原樣帶上，沒帶或日期格式不帶。"""
    await link_account("jira", {"apiKey": "jira-key", "domain": "team.atlassian.net"})
    await reset_items(database.db.jira_issues, None)
    skip_retry_delay(monkeypatch)
    use_fake_http(monkeypatch, jira_platform, outcome)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/jira/issues")

    assert res.status_code == 503
    assert res.json()["error_code"] == "UPSTREAM_RATE_LIMITED"
    assert res.headers.get("Retry-After") == retry_after
