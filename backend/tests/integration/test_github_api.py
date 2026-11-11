# 透過 HTTP 確認路由、登入驗證、回應格式和錯誤狀態碼；細部邏輯由 unit 測試負責
import pytest
from fastapi import status
from httpx import AsyncClient
from httpx._transports.asgi import ASGITransport
from datetime import datetime, timezone

from main import app
from core.crypto import encrypt_secret
import platforms.router as platform_router
from core import database
import platforms.github as github_platform

@pytest.mark.asyncio
async def test_get_github_issues(monkeypatch, logged_in_user):
    """GET /github/issues 成功：GitHub 原始資料被轉成統一格式，用 200 和 JSON 清單回傳。"""
    async def mock_find_one(*args, **kwargs):
        return {"apiKey": encrypt_secret("fake_token"), "clerk_id": logged_in_user["sub"]}

    async def mock_fetch(token):
        return [
            {
                "id": 9000999,
                "number": 999,
                "title": "Fix bug",
                "state": "open",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "html_url": "https://github.com/user/repo/issues/999",
                "user": {"login": "mock_user", "avatar_url": "https://mock.avatar"},
                "labels": [{"name": "bug"}],
                "comments": 2,
                "pull_request": {}
            }
        ]

    class MockUpdateResult:
        def __init__(self, upserted_id="mock_id"):
            self._upserted_id = upserted_id

        @property
        def upserted_id(self):
            return self._upserted_id

    class MockCollection:
        async def find_one(self, *args, **kwargs):
            return await mock_find_one(*args, **kwargs)

        async def update_one(self, *args, **kwargs):
            return MockUpdateResult()

        async def delete_many(self, *args, **kwargs):
            return MockUpdateResult()

    monkeypatch.setattr(database.db, "linkedAccounts", MockCollection())
    monkeypatch.setattr(database.db, "github_issues", MockCollection())
    monkeypatch.setattr(github_platform, "fetch_github_user_issues", mock_fetch)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/github/issues")

    assert res.status_code == status.HTTP_200_OK
    assert any(issue["title"] == "Fix bug" for issue in res.json())


@pytest.mark.asyncio
async def test_get_github_issues_when_account_not_linked(monkeypatch, logged_in_user):
    """使用者還沒綁定 GitHub → 409 NOT_LINKED 加說明，前端才能顯示「請先設定帳號」。"""
    class EmptyLinkedAccounts:
        async def find_one(self, *args, **kwargs):
            return None

    monkeypatch.setattr(database.db, "linkedAccounts", EmptyLinkedAccounts())

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/github/issues")

    assert res.status_code == status.HTTP_409_CONFLICT
    assert res.json() == {"detail": "No GitHub token linked", "error_code": "NOT_LINKED"}


@pytest.mark.asyncio
async def test_get_github_issues_requires_login():
    """沒帶登入 token → 被擋在門外（401/403），不能進到函式裡。"""
    # 這個測試刻意不用 logged_in_user，所以請求是沒登入的
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/github/issues")

    assert res.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)


# ---------- 需求 5：GitHub 每種錯誤回應的重試、狀態碼、error_code、X-Auth-Error ----------
import httpx as _httpx

from tests.integration.platform_http_fakes import (  # noqa: F401  clean_platform_data 是 fixture
    clean_platform_data,
    UPSTREAM_SECRET_TEXT,
    link_account,
    reset_items,
    response,
    skip_retry_delay,
    use_fake_http,
)

OLD_GITHUB_ITEM = github_platform.transform_github_item({
    "id": 1, "number": 1, "title": "舊資料", "state": "open",
    "created_at": "2026-01-01T00:00:00Z", "updated_at": "2026-01-01T00:00:00Z",
    "html_url": "https://github.com/o/r/issues/1", "user": {"login": "u", "avatar_url": ""},
    "labels": [], "comments": 0,
})

# (GitHub 的回應, 嘗試次數, 沒有舊資料時的狀態碼, error_code, 有舊資料時是否設 X-Auth-Error)
GITHUB_FETCH_CASES = [
    pytest.param(response(403, {"x-ratelimit-remaining": "0"}), 1, 503, "UPSTREAM_RATE_LIMITED", False, id="403-remaining-0"),
    pytest.param(response(403, {"retry-after": "30"}), 1, 503, "UPSTREAM_RATE_LIMITED", False, id="403-retry-after"),
    pytest.param(response(403, json_body={"message": f"You have exceeded a secondary rate limit {UPSTREAM_SECRET_TEXT}"}),
                 1, 503, "UPSTREAM_RATE_LIMITED", False, id="403-secondary-rate-limit"),
    pytest.param(response(429), 2, 503, "UPSTREAM_RATE_LIMITED", False, id="429"),
    pytest.param(response(401), 1, 409, "REAUTH_REQUIRED", True, id="401"),
    pytest.param(response(403, {"x-ratelimit-remaining": "10"}), 1, 409, "REAUTH_REQUIRED", True, id="403-no-rate-limit"),
    pytest.param(response(400), 1, 500, "INTERNAL_ERROR", False, id="400"),
    pytest.param(response(404), 1, 502, "UPSTREAM_ERROR", False, id="404"),
    pytest.param(response(503), 2, 502, "UPSTREAM_ERROR", False, id="5xx"),
    pytest.param(response(418), 2, 502, "UPSTREAM_ERROR", False, id="other-4xx"),
    pytest.param(response(304), 2, 502, "UPSTREAM_ERROR", False, id="3xx"),
    pytest.param(response(200, content=f"<html>{UPSTREAM_SECRET_TEXT}</html>".encode()), 2, 502, "UPSTREAM_ERROR", False, id="not-json"),
    pytest.param(_httpx.ConnectError("connection refused"), 2, 502, "UPSTREAM_ERROR", False, id="connect-error"),
    pytest.param(_httpx.ReadTimeout("timed out"), 2, 504, "UPSTREAM_TIMEOUT", False, id="timeout"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("outcome, attempts, status_code, error_code, _", GITHUB_FETCH_CASES)
async def test_github_fetch_error_without_cached_data(monkeypatch, logged_in_user, outcome, attempts, status_code, error_code, _, clean_platform_data):
    """AC1、AC9、AC10：沒有舊資料時，每種 GitHub 錯誤的重試次數不變，狀態碼照 error_code 查表；detail 不帶 GitHub 回應原文。"""
    await link_account("github", {"apiKey": "gh-token"})
    await reset_items(database.db.github_issues, None)
    skip_retry_delay(monkeypatch)
    client = use_fake_http(monkeypatch, github_platform, outcome)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/github/issues")

    assert client.calls == attempts
    assert res.status_code == status_code
    assert res.json()["error_code"] == error_code
    assert UPSTREAM_SECRET_TEXT not in res.text
    if error_code != "REAUTH_REQUIRED":
        assert "授權已失效" not in res.json()["detail"]


@pytest.mark.asyncio
@pytest.mark.parametrize("outcome, attempts, _, error_code, auth_error", GITHUB_FETCH_CASES)
async def test_github_fetch_error_with_cached_data(monkeypatch, logged_in_user, outcome, attempts, _, error_code, auth_error, clean_platform_data):
    """AC5、AC6：有舊資料時回舊資料；只有憑證失效設 X-Auth-Error（GitHub 用 403 限流不設），重試次數照需求 5。"""
    await link_account("github", {"apiKey": "gh-token"})
    await reset_items(database.db.github_issues, OLD_GITHUB_ITEM)
    skip_retry_delay(monkeypatch)
    client = use_fake_http(monkeypatch, github_platform, outcome)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/github/issues")

    assert client.calls == attempts
    assert res.status_code == status.HTTP_200_OK
    assert res.headers["X-Data-Stale"] == "true"
    assert ("X-Auth-Error" in res.headers) is auth_error


@pytest.mark.asyncio
async def test_github_fetch_when_credentials_cannot_be_decrypted(monkeypatch, logged_in_user, caplog, clean_platform_data):
    """已存的 GitHub 憑證解不開 → 409 REAUTH_REQUIRED；記 warning、不刪憑證。"""
    import logging
    await link_account("github", {"apiKey": "gh-token"})
    await database.db.linkedAccounts.update_one({"_id": "test_user_123_github"}, {"$set": {"apiKey": "broken-cipher"}})

    with caplog.at_level(logging.WARNING):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            res = await ac.get("/github/issues")

    assert res.status_code == 409
    assert res.json()["error_code"] == "REAUTH_REQUIRED"
    assert await database.db.linkedAccounts.find_one({"_id": "test_user_123_github"}) is not None
    assert any(r.levelno == logging.WARNING for r in caplog.records)


# ---------- 外部限流帶 Retry-After（AC5）----------

@pytest.mark.asyncio
@pytest.mark.parametrize("outcome, retry_after", [
    pytest.param(response(403, {"retry-after": "30"}), "30", id="403-secondary-seconds"),
    pytest.param(response(429, {"Retry-After": "60"}), "60", id="429-seconds"),
    pytest.param(response(429, {"Retry-After": "0"}), "0", id="429-zero"),
    pytest.param(response(429), None, id="429-without"),
    pytest.param(response(429, {"Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT"}), None, id="429-http-date"),
    pytest.param(response(429, {"Retry-After": "-5"}), None, id="429-negative"),
    pytest.param(response(403, {"x-ratelimit-remaining": "0", "x-ratelimit-reset": "1999999999"}), None, id="403-reset-not-converted"),
])
async def test_github_fetch_rate_limited_forwards_retry_after_seconds(monkeypatch, logged_in_user, outcome, retry_after, clean_platform_data):
    """AC5：GitHub 限流 → 503 UPSTREAM_RATE_LIMITED；GitHub 帶秒數的 Retry-After 時原樣帶上，沒帶、日期格式不帶，也不從 x-ratelimit-reset 換算。"""
    await link_account("github", {"apiKey": "gh-token"})
    await reset_items(database.db.github_issues, None)
    skip_retry_delay(monkeypatch)
    use_fake_http(monkeypatch, github_platform, outcome)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/github/issues")

    assert res.status_code == 503
    assert res.json()["error_code"] == "UPSTREAM_RATE_LIMITED"
    assert res.headers.get("Retry-After") == retry_after
