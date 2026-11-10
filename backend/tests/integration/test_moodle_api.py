# 透過 HTTP 確認路由、登入驗證、回應格式和錯誤狀態碼；細部邏輯由 unit 測試負責
from datetime import datetime, timezone

import pytest
from fastapi import status
from httpx import AsyncClient
from httpx._transports.asgi import ASGITransport

from core import cache
from main import app
from core.crypto import encrypt_secret
import platforms.router as platform_router
from core import database
from platforms.moodle import MOODLE


@pytest.fixture(autouse=True)
def clear_moodle_cache():
    """get_assignments 有 TTL 快取，清乾淨避免測試之間互相汙染。"""
    cache._memory_store.clear()
    yield
    cache._memory_store.clear()


class MockLinkedAccounts:
    """模擬 db.linkedAccounts.find_one：使用者有綁定 Moodle，密碼是真的加密過的。"""

    async def find_one(self, query):
        return {"username": "stu001", "password": encrypt_secret("decrypted_pw")}


class EmptyLinkedAccounts:
    """模擬 db.linkedAccounts.find_one：使用者還沒綁定 Moodle。"""

    async def find_one(self, query):
        return None


@pytest.mark.asyncio
async def test_get_moodle_assignments(monkeypatch, logged_in_user):
    """GET /moodle/assignments 成功 → 200，回傳作業清單並帶 X-Data-Stale、X-Synced-At。"""
    assignments = [
        {
            "id": "https://moodle.nccu.edu.tw/mod/assign/view.php?id=1",
            "course_name": "資料結構",
            "title": "HW1",
            "url": "https://moodle.nccu.edu.tw/mod/assign/view.php?id=1",
            "due_date": "2026-09-10",
        }
    ]

    async def mock_sync(user_id, fetch_fn):
        # (作業清單, 是不是舊資料, 同步時間, 登入是否失敗)
        return assignments, False, datetime(2026, 9, 1, tzinfo=timezone.utc), False

    monkeypatch.setattr(database.db, "linkedAccounts", MockLinkedAccounts())
    monkeypatch.setattr(MOODLE, "sync_items", mock_sync)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/moodle/assignments")

    assert res.status_code == status.HTTP_200_OK
    # 排程欄位都是預設值，不列出
    body = res.json()
    assert len(body) == 1
    for key, value in assignments[0].items():
        assert body[0][key] == value
    assert res.headers["X-Data-Stale"] == "false"
    assert res.headers["X-Synced-At"] == "2026-09-01T00:00:00+00:00"


@pytest.mark.asyncio
async def test_get_moodle_assignments_when_account_not_linked(monkeypatch, logged_in_user):
    """使用者還沒綁定 Moodle → 400 NOT_LINKED 加說明，前端才能顯示「請先設定帳號」。"""
    monkeypatch.setattr(database.db, "linkedAccounts", EmptyLinkedAccounts())

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/moodle/assignments")

    assert res.status_code == status.HTTP_400_BAD_REQUEST
    assert res.json() == {"detail": "No Moodle linked account", "error_code": "NOT_LINKED"}


@pytest.mark.asyncio
async def test_get_moodle_assignments_requires_login():
    """沒帶登入 token → 被擋在門外（401/403），不能進到函式裡。"""
    # 這個測試刻意不用 logged_in_user，所以請求是沒登入的
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/moodle/assignments")

    assert res.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)


# ---------- 需求 5：Moodle 登入結果與 Selenium 錯誤的分類 ----------
from unittest.mock import MagicMock

from selenium.common.exceptions import TimeoutException, WebDriverException

import platforms.moodle as moodle_platform
from tests.integration.platform_http_fakes import clean_platform_data, link_account, reset_items, skip_retry_delay  # noqa: F401

OLD_MOODLE_ITEM = {"id": "https://moodle.nccu.edu.tw/mod/assign/view.php?id=9", "course_name": "課",
                   "title": "舊作業", "url": "https://moodle.nccu.edu.tw/mod/assign/view.php?id=9", "due_date": "無截止日期"}


def _fake_browser(monkeypatch, final_url=None, error=None):
    """登入後停在 final_url；有 error 時等頁面元素就丟出。回傳記錄開了幾次瀏覽器的 list。"""
    opened = []

    def fake_chrome(**kwargs):
        driver = MagicMock()
        driver.current_url = final_url
        opened.append(driver)
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
    return opened


MOODLE_FETCH_CASES = [
    pytest.param({"final_url": "https://i.nccu.edu.tw/Login.aspx?ReturnUrl=%2fsso_app%2fMoodleSSO2.aspx&e=1"},
                 1, 401, "REAUTH_REQUIRED", True, id="stays-on-login-page"),
    pytest.param({"final_url": "https://i.nccu.edu.tw/sso_app/Error.aspx"}, 1, 401, "UPSTREAM_ERROR", False, id="redirected-elsewhere"),
    pytest.param({"error": TimeoutException("element not found")}, 2, 502, "UPSTREAM_TIMEOUT", False, id="selenium-timeout"),
    pytest.param({"error": WebDriverException("chrome crashed")}, 2, 502, "UPSTREAM_ERROR", False, id="webdriver-error"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("browser, attempts, status_code, error_code, _", MOODLE_FETCH_CASES)
async def test_moodle_fetch_error_without_cached_data(monkeypatch, logged_in_user, browser, attempts, status_code, error_code, _, clean_platform_data):
    """AC7、AC22：沒有舊資料時，只有停在登入頁才是 REAUTH_REQUIRED；導向別處、逾時不要求重新連結；detail 不帶 Moodle 帳號。"""
    await link_account("moodle", {"username": "stu-secret-name", "password": "pw"})
    await reset_items(database.db.moodle_assignments, None)
    skip_retry_delay(monkeypatch)
    opened = _fake_browser(monkeypatch, **browser)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/moodle/assignments")

    assert len(opened) == attempts
    assert res.status_code == status_code
    assert res.json()["error_code"] == error_code
    assert "stu-secret-name" not in res.text
    if error_code != "REAUTH_REQUIRED":
        assert "帳號密碼" not in res.json()["detail"]


@pytest.mark.asyncio
@pytest.mark.parametrize("browser, attempts, _, error_code, auth_error", MOODLE_FETCH_CASES)
async def test_moodle_fetch_error_with_cached_data(monkeypatch, logged_in_user, browser, attempts, _, error_code, auth_error, clean_platform_data):
    """AC7：有舊資料時只有停在登入頁設 X-Auth-Error。"""
    await link_account("moodle", {"username": "stu001", "password": "pw"})
    await reset_items(database.db.moodle_assignments, OLD_MOODLE_ITEM)
    skip_retry_delay(monkeypatch)
    opened = _fake_browser(monkeypatch, **browser)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/moodle/assignments")

    assert len(opened) == attempts
    assert res.status_code == status.HTTP_200_OK
    assert ("X-Auth-Error" in res.headers) is auth_error
