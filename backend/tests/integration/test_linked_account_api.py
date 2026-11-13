# 透過 HTTP 確認路由、登入驗證、回應格式和錯誤狀態碼；細部邏輯由 unit 測試負責
import pytest
from fastapi import status
from httpx import AsyncClient
from httpx._transports.asgi import ASGITransport

from main import app
from crud import linked_account as linked_mod
import platforms.github as github_platform
from schemas.linked_account import LinkedAccountCreate

test_account = LinkedAccountCreate(
    platform="github",
    status="connected",
    username="mock_user",
    apiKey="fake_token"
)


@pytest.mark.asyncio
async def test_create_linked_account(monkeypatch, logged_in_user):
    """POST /users/me/linked-accounts/：建立 GitHub 綁定帳號成功，回 201。"""
    async def mock_fetch(token):
        return {"username": "mock_user", "avatar_url": "https://mock.avatar"}

    monkeypatch.setattr(github_platform, "fetch_github_userinfo", mock_fetch)

    async def mock_insert_one(doc):
        return type("Mock", (), {"inserted_id": "test_user_123_github"})()

    monkeypatch.setattr(linked_mod.db.linkedAccounts, "insert_one", mock_insert_one)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post("/users/me/linked-accounts/", json=test_account.model_dump())

    assert res.status_code == status.HTTP_201_CREATED


@pytest.mark.asyncio
async def test_get_linked_accounts(monkeypatch, logged_in_user):
    """GET /users/me/linked-accounts/：回傳目前使用者綁定的帳號清單。"""
    # 定義 MockCursor 支援 async for
    class MockCursor:
        def __aiter__(self):
            async def generator():
                yield {
                    "_id": "test_user_123_github",
                    "platform": "github",
                    "status": "connected",
                    "username": "mock_user",
                    "avatar_url": "https://mock.avatar"
                }
            return generator()

    monkeypatch.setattr(linked_mod.db.linkedAccounts, "find", lambda q: MockCursor())

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/users/me/linked-accounts/")

    assert res.status_code == status.HTTP_200_OK
    assert res.json()[0]["platform"] == "github"


@pytest.mark.asyncio
async def test_update_linked_account(monkeypatch, logged_in_user):
    """PATCH /users/me/linked-accounts/{platform}：更新綁定帳號成功，回 200。"""
    async def mock_update(clerk_id, platform, data):
        return True

    monkeypatch.setattr(linked_mod, "update_linked_account_by_clerk_id", mock_update)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.patch("/users/me/linked-accounts/github", json={"status": "connected"})

    assert res.status_code == status.HTTP_200_OK


@pytest.mark.asyncio
async def test_delete_linked_account(monkeypatch, logged_in_user):
    """DELETE /users/me/linked-accounts/{platform}：刪除綁定帳號成功，回 200。"""
    async def mock_delete(composite_id):
        return True

    monkeypatch.setattr(linked_mod, "delete_linked_account_by_id", mock_delete)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.delete("/users/me/linked-accounts/github")

    assert res.status_code == status.HTTP_200_OK


@pytest.mark.asyncio
async def test_update_linked_account_not_found(monkeypatch, logged_in_user):
    """AC3：要更新的綁定帳號不存在 → 404 NOT_FOUND 加說明。"""
    async def mock_update(clerk_id, platform, data):
        return False

    monkeypatch.setattr(linked_mod, "update_linked_account_by_clerk_id", mock_update)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.patch("/users/me/linked-accounts/github", json={"status": "connected"})

    assert res.status_code == status.HTTP_404_NOT_FOUND
    assert res.json() == {"detail": "Linked account not found", "error_code": "NOT_FOUND"}


@pytest.mark.asyncio
async def test_update_linked_account_rejects_non_object_body(monkeypatch, logged_in_user):
    """body 不是 JSON 物件（例如字串）→ FastAPI 驗證直接擋下回 422，不會進到 crud。"""
    async def mock_update(clerk_id, platform, data):
        raise AssertionError("不該呼叫到 crud")

    monkeypatch.setattr(linked_mod, "update_linked_account_by_clerk_id", mock_update)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.patch("/users/me/linked-accounts/github", json="not-an-object")

    assert res.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


@pytest.mark.asyncio
async def test_get_linked_accounts_requires_login():
    """沒帶登入 token → 被擋在門外（401/403），不能進到函式裡。"""
    # 這個測試刻意不用 logged_in_user，所以請求是沒登入的
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/users/me/linked-accounts/")

    assert res.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)


@pytest.mark.asyncio
async def test_update_linked_account_passes_only_known_fields_to_crud(monkeypatch, logged_in_user):
    """PATCH 只把有送、且 schema 裡有的欄位交給 crud；未知欄位和 null 都不會傳下去。"""
    received = {}

    async def mock_update(clerk_id, platform, data):
        received.update(data)
        return True

    monkeypatch.setattr(linked_mod, "update_linked_account_by_clerk_id", mock_update)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.patch(
            "/users/me/linked-accounts/github",
            json={"apiKey": "new-token", "domain": None, "clerk_id": "someone_else"},
        )

    assert res.status_code == status.HTTP_200_OK
    assert received == {"apiKey": "new-token"}


@pytest.mark.asyncio
async def test_update_linked_account_rejects_wrong_field_type(monkeypatch, logged_in_user):
    """欄位型別錯誤（apiKey 不是字串）→ 422，不會進到 crud。"""
    async def mock_update(clerk_id, platform, data):
        raise AssertionError("不該呼叫到 crud")

    monkeypatch.setattr(linked_mod, "update_linked_account_by_clerk_id", mock_update)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.patch("/users/me/linked-accounts/github", json={"apiKey": 123})

    assert res.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


# ---------- 連結與更新帳號：依原因的 error_code，狀態碼照對照表 ----------
import logging
import socket

import httpx
import pytest_asyncio

import platforms.jira as jira_platform
import platforms.moodle as moodle_platform
from core.database import db
from tests.integration.platform_http_fakes import UPSTREAM_SECRET_TEXT, clean_platform_data, link_account, response, use_fake_http  # noqa: F401


def _dns_error() -> httpx.ConnectError:
    try:
        try:
            raise socket.gaierror(socket.EAI_NONAME, "Name or service not known")
        except socket.gaierror as e:
            raise httpx.ConnectError("[Errno -2] Name or service not known") from e
    except httpx.ConnectError as e:
        return e


@pytest_asyncio.fixture
async def no_linked_accounts():
    await db.linkedAccounts.delete_many({"clerk_id": "test_user_123"})
    yield
    await db.linkedAccounts.delete_many({"clerk_id": "test_user_123"})


GITHUB_PAYLOAD = {"platform": "github", "status": "connected", "username": "me", "apiKey": "ghp_new_token"}
JIRA_PAYLOAD = {"platform": "jira", "status": "connected", "username": "me", "apiKey": "jira-key", "domain": "team.atlassian.net"}

# (平台模組, 送出的內容, 平台的回應, 狀態碼, error_code)
LINK_CASES = [
    pytest.param(github_platform, GITHUB_PAYLOAD, response(401), 400, "INVALID_CREDENTIALS", id="github-401"),
    pytest.param(jira_platform, JIRA_PAYLOAD, response(401), 400, "INVALID_CREDENTIALS", id="jira-401"),
    pytest.param(github_platform, GITHUB_PAYLOAD, response(403), 400, "INVALID_CREDENTIALS", id="github-403-no-rate-limit"),
    pytest.param(jira_platform, JIRA_PAYLOAD, response(404), 400, "INVALID_PLATFORM_DOMAIN", id="jira-404"),
    pytest.param(jira_platform, JIRA_PAYLOAD, _dns_error(), 400, "INVALID_PLATFORM_DOMAIN", id="jira-dns-not-found"),
    pytest.param(jira_platform, JIRA_PAYLOAD, httpx.ConnectError("connection refused"), 502, "UPSTREAM_ERROR", id="jira-connect-error"),
    pytest.param(github_platform, GITHUB_PAYLOAD, httpx.ConnectError("connection refused"), 502, "UPSTREAM_ERROR", id="github-connect-error"),
    pytest.param(github_platform, GITHUB_PAYLOAD, httpx.ReadTimeout("timed out"), 504, "UPSTREAM_TIMEOUT", id="github-timeout"),
    pytest.param(github_platform, GITHUB_PAYLOAD, response(503), 502, "UPSTREAM_ERROR", id="github-5xx"),
    pytest.param(jira_platform, JIRA_PAYLOAD, response(500), 502, "UPSTREAM_ERROR", id="jira-5xx"),
    pytest.param(github_platform, GITHUB_PAYLOAD, response(429), 503, "UPSTREAM_RATE_LIMITED", id="github-429"),
    pytest.param(jira_platform, JIRA_PAYLOAD, response(429), 503, "UPSTREAM_RATE_LIMITED", id="jira-429"),
    pytest.param(github_platform, GITHUB_PAYLOAD, response(403, {"x-ratelimit-remaining": "0"}), 503, "UPSTREAM_RATE_LIMITED", id="github-403-rate-limit"),
    pytest.param(github_platform, GITHUB_PAYLOAD, response(400), 500, "INTERNAL_ERROR", id="github-400"),
    pytest.param(jira_platform, JIRA_PAYLOAD, response(400), 500, "INTERNAL_ERROR", id="jira-400"),
    pytest.param(github_platform, GITHUB_PAYLOAD, response(404), 502, "UPSTREAM_ERROR", id="github-404"),
    pytest.param(github_platform, GITHUB_PAYLOAD, response(302), 502, "UPSTREAM_ERROR", id="github-3xx"),
    pytest.param(github_platform, GITHUB_PAYLOAD, response(200, content=f"<html>{UPSTREAM_SECRET_TEXT}".encode()), 502, "UPSTREAM_ERROR", id="github-not-json"),
]

# 不是 REAUTH_REQUIRED、INVALID_CREDENTIALS 的列，detail 不能有這些說法
CREDENTIAL_WORDS = ("授權已失效", "帳號或密碼錯誤", "token 無效", "權限不足")


@pytest.mark.asyncio
@pytest.mark.parametrize("module, payload, outcome, status_code, error_code", LINK_CASES)
async def test_link_account_error_codes(monkeypatch, logged_in_user, no_linked_accounts, module, payload, outcome, status_code, error_code, clean_platform_data):
    """AC1、AC10：連結帳號時每種平台回應的 error_code 不同，狀態碼照 error_code 查表；detail 不帶平台回應原文。"""
    use_fake_http(monkeypatch, module, outcome)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post("/users/me/linked-accounts/", json=payload)

    body = res.json()
    assert res.status_code == status_code
    assert body["error_code"] == error_code
    assert UPSTREAM_SECRET_TEXT not in res.text
    if error_code != "INVALID_CREDENTIALS":
        assert not any(word in body["detail"] for word in CREDENTIAL_WORDS)


@pytest.mark.asyncio
async def test_link_github_403_without_rate_limit_explains_missing_permission(monkeypatch, logged_in_user, no_linked_accounts, clean_platform_data):
    """AC16：連結時沒有限流特徵的 403，detail 說明 token 權限不足、請換有權限的 token。"""
    use_fake_http(monkeypatch, github_platform, response(403))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post("/users/me/linked-accounts/", json=GITHUB_PAYLOAD)

    assert "權限不足" in res.json()["detail"]
    assert "有權限的 token" in res.json()["detail"]


def _fake_moodle_browser(monkeypatch, final_url=None, error=None):
    from unittest.mock import MagicMock

    def fake_chrome(**kwargs):
        driver = MagicMock()
        driver.current_url = final_url
        return driver

    def fake_wait(driver, timeout):
        def until(condition):
            if error is not None:
                raise error
            return MagicMock()
        return MagicMock(until=until)

    monkeypatch.setattr(moodle_platform.webdriver, "Chrome", fake_chrome)
    monkeypatch.setattr(moodle_platform, "WebDriverWait", fake_wait)
    monkeypatch.setattr(moodle_platform.time, "sleep", lambda seconds: None)


MOODLE_PAYLOAD = {"platform": "moodle", "status": "connected", "username": "stu-secret-name", "password": "pw"}


@pytest.mark.asyncio
@pytest.mark.parametrize("browser, status_code, error_code", [
    pytest.param({"final_url": "https://i.nccu.edu.tw/Login.aspx?x=1"}, 400, "INVALID_CREDENTIALS", id="wrong-password"),
    pytest.param({"final_url": "https://i.nccu.edu.tw/sso_app/Error.aspx"}, 502, "UPSTREAM_ERROR", id="redirected-elsewhere"),
    pytest.param({"error": "timeout"}, 504, "UPSTREAM_TIMEOUT", id="selenium-timeout"),
    pytest.param({"error": "webdriver"}, 502, "UPSTREAM_ERROR", id="webdriver-error"),
])
async def test_link_moodle_error_codes(monkeypatch, logged_in_user, no_linked_accounts, browser, status_code, error_code, clean_platform_data):
    """AC8、AC16、AC22：連結 Moodle 時帳密錯、導向別處、逾時、WebDriver 錯誤的 error_code 不同；detail 不帶 Moodle 帳號。"""
    from selenium.common.exceptions import TimeoutException, WebDriverException
    if browser.get("error") == "timeout":
        browser = {"error": TimeoutException("wait")}
    elif browser.get("error") == "webdriver":
        browser = {"error": WebDriverException("crash")}
    _fake_moodle_browser(monkeypatch, **browser)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post("/users/me/linked-accounts/", json=MOODLE_PAYLOAD)

    body = res.json()
    assert res.status_code == status_code
    assert body["error_code"] == error_code
    assert "stu-secret-name" not in res.text
    if error_code != "INVALID_CREDENTIALS":
        assert not any(word in body["detail"] for word in CREDENTIAL_WORDS)


@pytest.mark.asyncio
async def test_patch_jira_domain_only_rejected_with_stored_key_is_invalid_credentials(monkeypatch, logged_in_user, no_linked_accounts, clean_platform_data):
    """只改 Jira 網域、用已存的 API key 驗證被拒（401）→ 400 INVALID_CREDENTIALS。"""
    await link_account("jira", {"apiKey": "stored-key", "domain": "old.atlassian.net"})
    use_fake_http(monkeypatch, jira_platform, response(401))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.patch("/users/me/linked-accounts/jira", json={"domain": "new.atlassian.net"})

    assert res.status_code == 400
    assert res.json()["error_code"] == "INVALID_CREDENTIALS"


@pytest.mark.asyncio
async def test_patch_moodle_username_only_rejected_is_invalid_credentials(monkeypatch, logged_in_user, no_linked_accounts, clean_platform_data):
    """只改 Moodle 帳號、用已存的密碼驗證停在登入頁 → 400 INVALID_CREDENTIALS。"""
    await link_account("moodle", {"username": "old", "password": "stored-pw"})
    _fake_moodle_browser(monkeypatch, final_url="https://i.nccu.edu.tw/Login.aspx")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.patch("/users/me/linked-accounts/moodle", json={"username": "new"})

    assert res.status_code == 400
    assert res.json()["error_code"] == "INVALID_CREDENTIALS"


@pytest.mark.asyncio
async def test_patch_with_undecryptable_stored_credentials_is_reauth_required(monkeypatch, logged_in_user, no_linked_accounts, caplog, clean_platform_data):
    """PATCH 用已存的憑證驗證但解不開 → 409 REAUTH_REQUIRED；記 warning、不刪憑證。"""
    await link_account("jira", {"apiKey": "stored-key", "domain": "old.atlassian.net"})
    await db.linkedAccounts.update_one({"_id": "test_user_123_jira"}, {"$set": {"apiKey": "broken-cipher"}})

    with caplog.at_level(logging.WARNING):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            res = await ac.patch("/users/me/linked-accounts/jira", json={"domain": "new.atlassian.net"})

    assert res.status_code == 409
    assert res.json()["error_code"] == "REAUTH_REQUIRED"
    assert (await db.linkedAccounts.find_one({"_id": "test_user_123_jira"}))["apiKey"] == "broken-cipher"
    assert any(r.levelno == logging.WARNING for r in caplog.records)


@pytest.mark.asyncio
async def test_patch_without_fields_is_invalid_request(logged_in_user, no_linked_accounts, clean_platform_data):
    """AC1：沒有可更新的欄位 → 400 INVALID_REQUEST，和「帳號不存在」（404 NOT_FOUND）分得出來。"""
    await link_account("github", {"apiKey": "tok"})

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        no_fields = await ac.patch("/users/me/linked-accounts/github", json={})
        missing = await ac.patch("/users/me/linked-accounts/jira", json={"status": "connected"})

    assert no_fields.status_code == 400
    assert no_fields.json()["error_code"] == "INVALID_REQUEST"
    assert missing.status_code == 404
    assert missing.json()["error_code"] == "NOT_FOUND"


# ---------- 422：不帶回送出的憑證 ----------

@pytest.mark.asyncio
async def test_link_account_missing_field_does_not_echo_credentials(logged_in_user):
    """AC4：連結帳號時少送欄位 → 422 VALIDATION_ERROR，回應裡沒有送出的 apiKey、password，每一項沒有 input、ctx。"""
    payload = {"platform": "moodle", "username": "me", "apiKey": "ghp_echo_secret", "password": "pw_echo_secret"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post("/users/me/linked-accounts/", json=payload)

    body = res.json()
    assert res.status_code == 422
    assert body["error_code"] == "VALIDATION_ERROR"
    assert "ghp_echo_secret" not in res.text
    assert "pw_echo_secret" not in res.text
    assert all("input" not in item and "ctx" not in item for item in body["detail"])


# ---------- 帳號列表：解不開的帳號標 needs_reauth ----------

@pytest.mark.asyncio
async def test_list_marks_undecryptable_account_and_reauth_by_patch(monkeypatch, logged_in_user, no_linked_accounts, caplog, clean_platform_data):
    """AC9、AC10：一個帳號解不開時列表照常 200，該帳號 needs_reauth 且沒有憑證欄位、其他帳號照常；填完整憑證 PATCH 後恢復。"""
    await link_account("jira", {"apiKey": "jira-key", "domain": "team.atlassian.net"})
    await db.linkedAccounts.insert_one({
        "_id": "test_user_123_github", "clerk_id": "test_user_123", "platform": "github",
        "status": "connected", "username": "me", "apiKey": "cipher-from-another-key",
    })

    with caplog.at_level(logging.WARNING):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            res = await ac.get("/users/me/linked-accounts/")

    assert res.status_code == 200
    by_platform = {a["platform"]: a for a in res.json()}
    assert by_platform["github"]["needs_reauth"] is True
    assert by_platform["github"].get("apiKey") is None
    assert by_platform["github"].get("password") is None
    assert by_platform["jira"]["needs_reauth"] is False
    assert by_platform["jira"]["apiKey"].endswith("-key")
    assert any(r.levelno == logging.WARNING for r in caplog.records)
    assert (await db.linkedAccounts.find_one({"_id": "test_user_123_github"}))["apiKey"] == "cipher-from-another-key"

    use_fake_http(monkeypatch, github_platform, response(200, json_body={"login": "me", "avatar_url": ""}))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        patched = await ac.patch("/users/me/linked-accounts/github", json={"apiKey": "ghp_fresh"})
        after = await ac.get("/users/me/linked-accounts/")

    assert patched.status_code == 200
    assert {a["platform"]: a for a in after.json()}["github"]["needs_reauth"] is False


@pytest.mark.asyncio
async def test_list_returns_500_when_encryption_key_missing(monkeypatch, logged_in_user, no_linked_accounts, clean_platform_data):
    """AC18：伺服器沒設加密金鑰等其他例外 → 500 INTERNAL_ERROR，帳號不被標成要重新連結。"""
    await link_account("github", {"apiKey": "tok"})
    monkeypatch.delenv("SECRET_ENCRYPTION_KEY")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/users/me/linked-accounts/")

    assert res.status_code == 500
    assert res.json()["error_code"] == "INTERNAL_ERROR"


# ---------- 外部限流帶 Retry-After（AC5）----------

@pytest.mark.asyncio
@pytest.mark.parametrize("module, payload, outcome, retry_after", [
    pytest.param(github_platform, GITHUB_PAYLOAD, response(429, {"Retry-After": "12"}), "12", id="github-429-seconds"),
    pytest.param(github_platform, GITHUB_PAYLOAD, response(403, {"retry-after": "7"}), "7", id="github-403-secondary-seconds"),
    pytest.param(jira_platform, JIRA_PAYLOAD, response(429, {"Retry-After": "20"}), "20", id="jira-429-seconds"),
    pytest.param(jira_platform, JIRA_PAYLOAD, response(429), None, id="jira-429-without"),
    pytest.param(github_platform, GITHUB_PAYLOAD, response(429, {"Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT"}), None, id="github-429-http-date"),
])
async def test_link_account_rate_limited_forwards_retry_after_seconds(monkeypatch, logged_in_user, no_linked_accounts, module, payload, outcome, retry_after, clean_platform_data):
    """AC5：連結帳號時平台限流 → 503 UPSTREAM_RATE_LIMITED；帶秒數的 Retry-After 原樣帶上，沒帶或日期格式不帶。"""
    use_fake_http(monkeypatch, module, outcome)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post("/users/me/linked-accounts/", json=payload)

    assert res.status_code == 503
    assert res.json()["error_code"] == "UPSTREAM_RATE_LIMITED"
    assert res.headers.get("Retry-After") == retry_after
