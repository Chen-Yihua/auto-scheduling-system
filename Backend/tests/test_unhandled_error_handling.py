# 兜底的錯誤處理（exception_handlers.py 的 UnhandledExceptionMiddleware，註冊在 main.py）：
# 程式出現沒預期的 bug 時，回 JSON 500 並帶 CORS 標頭，讓瀏覽器看得到真正的狀態碼。
import logging

import pytest
from fastapi import status
from httpx import AsyncClient
from httpx._transports.asgi import ASGITransport

from main import app
import crud.user as user_crud
from exception_handlers import UnhandledExceptionMiddleware

SECRET = "internal detail: mongodb://user:secret@10.0.0.5"


def _raise_bug(monkeypatch):
    async def buggy(*args, **kwargs):
        raise RuntimeError(SECRET)

    monkeypatch.setattr(user_crud, "get_user_by_clerk_id", buggy)


async def _get_me(headers=None):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        return await ac.get("/users/me", headers=headers)


@pytest.mark.asyncio
async def test_unexpected_exception_returns_json_500_without_leaking_details(monkeypatch, logged_in_user):
    """程式出現沒預期的 bug → 回 JSON 500 和固定的中文訊息；例外內容（可能含機密）不能回傳給前端。"""
    _raise_bug(monkeypatch)

    res = await _get_me()

    assert res.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert res.json() == {"detail": "伺服器發生未預期的錯誤，請稍後再試"}
    assert "secret" not in res.text


@pytest.mark.asyncio
async def test_unexpected_exception_response_carries_cors_headers(monkeypatch, logged_in_user):
    """500 的回應也要帶 CORS 標頭，瀏覽器才看得到真正的狀態碼，而不是被「CORS 錯誤」蓋掉。"""
    _raise_bug(monkeypatch)

    res = await _get_me(headers={"Origin": "http://localhost:3000"})

    assert res.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert res.headers["access-control-allow-origin"] == "http://localhost:3000"


@pytest.mark.asyncio
async def test_unexpected_exception_is_logged_with_traceback(monkeypatch, logged_in_user, caplog):
    """沒預期的例外要記進後端 log（含請求方法、路徑和 traceback），方便事後排查。"""
    _raise_bug(monkeypatch)

    with caplog.at_level(logging.ERROR, logger="exception_handlers"):
        await _get_me()

    assert any("GET /users/me" in r.getMessage() and r.exc_info and SECRET in str(r.exc_info[1]) for r in caplog.records)


@pytest.mark.asyncio
async def test_expected_http_errors_are_not_turned_into_500(monkeypatch, logged_in_user):
    """預期中的錯誤（例如查無使用者的 404）維持原本的狀態碼和訊息，不會被兜底成 500。"""
    async def no_user(clerk_id):
        return None

    monkeypatch.setattr(user_crud, "get_user_by_clerk_id", no_user)

    res = await _get_me()

    assert res.status_code == status.HTTP_404_NOT_FOUND
    assert res.json() == {"detail": "User not found"}


@pytest.mark.asyncio
async def test_error_after_response_already_started_is_not_swallowed():
    """回應已經開始送出（狀態碼和標頭都送了）之後才出錯 → 不能再改成 500，例外要照樣往外丟，讓連線中斷。"""
    async def half_sent_app(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        raise RuntimeError("boom")

    sent = []

    async def send(message):
        sent.append(message)

    async def receive():
        return {"type": "http.request"}

    middleware = UnhandledExceptionMiddleware(half_sent_app)

    with pytest.raises(RuntimeError):
        await middleware({"type": "http", "method": "GET", "path": "/x"}, receive, send)

    # 只送過原本那次開頭，沒有另外補送一個 500
    assert [m["type"] for m in sent] == ["http.response.start"]
