# 資料庫例外的集中處理（exception_handlers.py，註冊在 main.py）：
# crud / router 遇到資料庫錯誤時不各自轉成 HTTPException，直接往外丟，
# 由全域 handler 統一回應。這裡走 HTTP 確認各個模組真的都被涵蓋、回應格式正確。
import logging

import pytest
from fastapi import status
from httpx import AsyncClient
from httpx._transports.asgi import ASGITransport
from pymongo.errors import (
    AutoReconnect,
    NetworkTimeout,
    NotPrimaryError,
    OperationFailure,
    ServerSelectionTimeoutError,
)

from main import app
from db.mongodb import db

DB_UNAVAILABLE_DETAIL = "資料庫暫時無法使用，請稍後再試"


def _failing(error):
    async def _raise(*args, **kwargs):
        raise error
    return _raise


class _FailingCursor:
    """find(...) 回傳的游標：讀取資料時才出錯。"""

    def __init__(self, error):
        self._error = error

    async def to_list(self, *args, **kwargs):
        raise self._error

    def __aiter__(self):
        return self

    async def __anext__(self):
        raise self._error


# (路徑, 讓該 endpoint 第一次碰資料庫就出錯的設定方式)
ENDPOINTS = {
    "users": ("/users/me", lambda mp, err: mp.setattr(db.users, "find_one", _failing(err))),
    "manual_tasks": ("/manual_tasks/me", lambda mp, err: mp.setattr(db.manual_tasks, "find", lambda q: _FailingCursor(err))),
    "linked_accounts": ("/user/linked-accounts/me", lambda mp, err: mp.setattr(db.linkedAccounts, "find", lambda q: _FailingCursor(err))),
    "github": ("/github/issues", lambda mp, err: mp.setattr(db.linkedAccounts, "find_one", _failing(err))),
    "jira": ("/jira/issues", lambda mp, err: mp.setattr(db.linkedAccounts, "find_one", _failing(err))),
    "moodle": ("/moodle/assignments", lambda mp, err: mp.setattr(db.linkedAccounts, "find_one", _failing(err))),
    "oauth": ("/oauth/status", lambda mp, err: mp.setattr(db.googleCalendarTokens, "find_one", _failing(err))),
}


async def _get(path, headers=None):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        return await ac.get(path, headers=headers)


@pytest.mark.asyncio
@pytest.mark.parametrize("module", list(ENDPOINTS))
async def test_database_connection_failure_returns_503_in_every_module(monkeypatch, logged_in_user, module):
    """資料庫連不上 → 每個用到資料庫的模組都回 503 和固定的中文訊息（例外沒有被中途吞掉或轉成別的狀態碼）。"""
    path, make_db_fail = ENDPOINTS[module]
    make_db_fail(monkeypatch, ServerSelectionTimeoutError("connection lost"))

    res = await _get(path)

    assert res.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert res.json() == {"detail": DB_UNAVAILABLE_DETAIL}


@pytest.mark.asyncio
@pytest.mark.parametrize("error", [
    ServerSelectionTimeoutError("no server"),
    AutoReconnect("reconnecting"),
    NetworkTimeout("timed out"),
    NotPrimaryError("failover in progress"),
])
async def test_every_connection_type_error_returns_503(monkeypatch, logged_in_user, error):
    """連線類的資料庫錯誤（找不到伺服器、重新連線中、網路逾時、主節點切換中）都屬於暫時性問題 → 503。"""
    path, make_db_fail = ENDPOINTS["users"]
    make_db_fail(monkeypatch, error)

    res = await _get(path)

    assert res.status_code == status.HTTP_503_SERVICE_UNAVAILABLE


@pytest.mark.asyncio
async def test_non_connection_database_error_returns_500_without_leaking_details(monkeypatch, logged_in_user):
    """非連線類的資料庫錯誤（例如查詢寫錯）多半是程式問題，重試也沒用 → 500；例外內容（可能含連線字串）不能回傳給前端。"""
    path, make_db_fail = ENDPOINTS["users"]
    make_db_fail(monkeypatch, OperationFailure("bad query on mongodb://user:secret@10.0.0.5"))

    res = await _get(path)

    assert res.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert res.json() == {"detail": "伺服器發生錯誤，請稍後再試"}
    assert "secret" not in res.text


@pytest.mark.asyncio
async def test_database_error_response_still_carries_cors_headers(monkeypatch, logged_in_user):
    """資料庫錯誤的回應也要帶 CORS 標頭，瀏覽器才看得到真正的狀態碼，而不是被「CORS 錯誤」蓋掉。"""
    path, make_db_fail = ENDPOINTS["users"]
    make_db_fail(monkeypatch, ServerSelectionTimeoutError("connection lost"))

    res = await _get(path, headers={"Origin": "http://localhost:3000"})

    assert res.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert res.headers["access-control-allow-origin"] == "http://localhost:3000"


@pytest.mark.asyncio
async def test_database_error_is_logged_with_request_path(monkeypatch, logged_in_user, caplog):
    """資料庫錯誤要記進後端 log（含請求的方法和路徑），方便事後排查；前端只看得到固定訊息。"""
    path, make_db_fail = ENDPOINTS["users"]
    make_db_fail(monkeypatch, ServerSelectionTimeoutError("connection lost"))

    with caplog.at_level(logging.ERROR, logger="exception_handlers"):
        await _get(path)

    assert any("GET /users/me" in record.getMessage() and record.exc_info for record in caplog.records)
