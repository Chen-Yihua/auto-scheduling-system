# 透過 HTTP 確認路由、登入驗證、回應格式和錯誤狀態碼；細部邏輯由 unit 測試負責
import pytest
from fastapi import status
from httpx import AsyncClient
from httpx._transports.asgi import ASGITransport

from main import app
from core import database
from platforms.moodle import MOODLE


class EmptyLinkedAccounts:
    """模擬 db.linkedAccounts.find_one：使用者還沒綁定 Moodle。"""

    async def find_one(self, query):
        return None


ASSIGNMENT = {
    "id": "https://moodle.nccu.edu.tw/mod/assign/view.php?id=1",
    "course_name": "資料結構",
    "title": "HW1",
    "url": "https://moodle.nccu.edu.tw/mod/assign/view.php?id=1",
    "due_date": "2026-09-10",
}


@pytest.mark.asyncio
async def test_sync_moodle_assignments(monkeypatch, logged_in_user, clean_platform_data):
    """AC24：POST /moodle/sync 即時抓作業、寫進資料庫，回 200 和作業清單，並帶 X-Data-Stale、X-Synced-At。"""
    await link_account("moodle", {"username": "stu001", "password": "pw"})
    await reset_items(database.db.moodle_assignments, None)

    async def mock_fetch(credentials):
        return [dict(ASSIGNMENT)]

    monkeypatch.setattr(MOODLE, "fetch_items", mock_fetch)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post("/moodle/sync")

    assert res.status_code == status.HTTP_200_OK
    body = res.json()
    assert len(body) == 1
    for key, value in ASSIGNMENT.items():
        assert body[0][key] == value
    assert res.headers["X-Data-Stale"] == "false"
    assert "X-Synced-At" in res.headers


@pytest.mark.asyncio
async def test_sync_moodle_twice_fetches_twice(monkeypatch, logged_in_user, clean_platform_data):
    """AC25：剛同步過（15 分鐘內）又按立即同步，仍要即時抓資料，不經過快取。"""
    await link_account("moodle", {"username": "stu001", "password": "pw"})
    await reset_items(database.db.moodle_assignments, None)
    calls = []

    async def mock_fetch(credentials):
        calls.append(credentials)
        return [dict(ASSIGNMENT)]

    monkeypatch.setattr(MOODLE, "fetch_items", mock_fetch)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        first = await ac.post("/moodle/sync")
        second = await ac.post("/moodle/sync")

    assert first.status_code == second.status_code == status.HTTP_200_OK
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_get_moodle_assignments_when_account_not_linked(monkeypatch, logged_in_user):
    """AC21：使用者還沒綁定 Moodle → GET 回 409 NOT_LINKED 加說明，前端才能顯示「請先設定帳號」。"""
    monkeypatch.setattr(database.db, "linkedAccounts", EmptyLinkedAccounts())

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/moodle/assignments")

    assert res.status_code == status.HTTP_409_CONFLICT
    assert res.json() == {"detail": "No Moodle linked account", "error_code": "NOT_LINKED"}


@pytest.mark.asyncio
@pytest.mark.parametrize("method, path", [("GET", "/moodle/assignments"), ("POST", "/moodle/sync")])
async def test_moodle_endpoints_require_login(method, path):
    """AC29：沒帶登入 token → GET 與 POST 都被擋在門外（401），不能進到函式裡。"""
    # 這個測試刻意不用 logged_in_user，所以請求是沒登入的
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.request(method, path)

    assert res.status_code == status.HTTP_401_UNAUTHORIZED
    assert res.json()["error_code"] == "UNAUTHENTICATED"


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
                 1, 409, "REAUTH_REQUIRED", True, id="stays-on-login-page"),
    pytest.param({"final_url": "https://i.nccu.edu.tw/sso_app/Error.aspx"}, 1, 502, "UPSTREAM_ERROR", False, id="redirected-elsewhere"),
    pytest.param({"error": TimeoutException("element not found")}, 2, 504, "UPSTREAM_TIMEOUT", False, id="selenium-timeout"),
    pytest.param({"error": WebDriverException("chrome crashed")}, 2, 502, "UPSTREAM_ERROR", False, id="webdriver-error"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("browser, attempts, status_code, error_code, _", MOODLE_FETCH_CASES)
async def test_moodle_fetch_error_without_cached_data(monkeypatch, logged_in_user, browser, attempts, status_code, error_code, _, clean_platform_data):
    """AC28：POST /moodle/sync 沒有舊資料時，只有停在登入頁才是 REAUTH_REQUIRED；導向別處、逾時不要求重新連結；detail 不帶 Moodle 帳號。"""
    await link_account("moodle", {"username": "stu-secret-name", "password": "pw"})
    await reset_items(database.db.moodle_assignments, None)
    skip_retry_delay(monkeypatch)
    opened = _fake_browser(monkeypatch, **browser)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post("/moodle/sync")

    assert len(opened) == attempts
    assert res.status_code == status_code
    assert res.json()["error_code"] == error_code
    assert "stu-secret-name" not in res.text
    if error_code != "REAUTH_REQUIRED":
        assert "帳號密碼" not in res.json()["detail"]


@pytest.mark.asyncio
@pytest.mark.parametrize("browser, attempts, _, error_code, auth_error", MOODLE_FETCH_CASES)
async def test_moodle_fetch_error_with_cached_data(monkeypatch, logged_in_user, browser, attempts, _, error_code, auth_error, clean_platform_data):
    """AC27：POST /moodle/sync 失敗但有舊資料時回舊資料，只有停在登入頁設 X-Auth-Error。"""
    await link_account("moodle", {"username": "stu001", "password": "pw"})
    await reset_items(database.db.moodle_assignments, OLD_MOODLE_ITEM)
    skip_retry_delay(monkeypatch)
    opened = _fake_browser(monkeypatch, **browser)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post("/moodle/sync")

    assert len(opened) == attempts
    assert res.status_code == status.HTTP_200_OK
    assert ("X-Auth-Error" in res.headers) is auth_error
