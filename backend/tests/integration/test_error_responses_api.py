# 走 HTTP 確認全域的錯誤回應都帶 error_code：未知路由、不支援的方法、沒登入、資料庫、Redis、未處理的例外
import pytest
import redis.exceptions
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from httpx import AsyncClient
from httpx._transports.asgi import ASGITransport
from pymongo.errors import OperationFailure, ServerSelectionTimeoutError
from slowapi import Limiter

from main import app
from core import cache
from core.database import db
from core.exception_handlers import redis_error_handler


async def _request(method, path, **kwargs):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        return await ac.request(method, path, **kwargs)


@pytest.mark.asyncio
async def test_unknown_route_returns_not_found_code():
    """AC2：未知路由的 404 帶 NOT_FOUND。"""
    res = await _request("GET", "/no-such-route")

    assert res.status_code == 404
    assert res.json()["error_code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_unsupported_method_returns_method_not_allowed_and_keeps_allow_header():
    """AC2、AC19：不支援的方法回 405 METHOD_NOT_ALLOWED，保留 Allow header。"""
    res = await _request("DELETE", "/health")

    assert res.status_code == 405
    assert res.json()["error_code"] == "METHOD_NOT_ALLOWED"
    assert "GET" in res.headers["allow"]


@pytest.mark.asyncio
@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer not-a-jwt"}], ids=["no-jwt", "invalid-jwt"])
async def test_missing_or_invalid_jwt_returns_unauthenticated(headers):
    """AC1、AC4：沒帶或格式錯誤的 JWT → 401 UNAUTHENTICATED。"""
    res = await _request("GET", "/users/me", headers=headers)

    assert res.status_code == 401
    assert res.json() == {"detail": "Forbidden", "error_code": "UNAUTHENTICATED"}


@pytest.mark.asyncio
async def test_database_unavailable_returns_service_unavailable_code(monkeypatch, logged_in_user):
    """AC1：資料庫連不上 → 503 SERVICE_UNAVAILABLE。"""
    async def fail(*args, **kwargs):
        raise ServerSelectionTimeoutError("connection lost")

    monkeypatch.setattr(db.users, "find_one", fail)

    res = await _request("GET", "/users/me")

    assert res.status_code == 503
    assert res.json()["error_code"] == "SERVICE_UNAVAILABLE"


@pytest.mark.asyncio
async def test_other_database_error_returns_internal_error_code(monkeypatch, logged_in_user):
    """AC1：其他資料庫錯誤 → 500 INTERNAL_ERROR。"""
    async def fail(*args, **kwargs):
        raise OperationFailure("bad query")

    monkeypatch.setattr(db.users, "find_one", fail)

    res = await _request("GET", "/users/me")

    assert res.status_code == 500
    assert res.json()["error_code"] == "INTERNAL_ERROR"


@pytest.mark.asyncio
async def test_unhandled_exception_returns_internal_error_code(monkeypatch, logged_in_user):
    """AC2：未處理的例外回 500 INTERNAL_ERROR。"""
    async def boom(*args, **kwargs):
        raise RuntimeError("bug")

    monkeypatch.setattr(db.users, "find_one", boom)

    res = await _request("GET", "/users/me")

    assert res.status_code == 500
    assert res.json()["error_code"] == "INTERNAL_ERROR"


class _BrokenRedis:
    async def get(self, *args, **kwargs):
        raise redis.exceptions.ConnectionError("redis down")

    async def set(self, *args, **kwargs):
        raise redis.exceptions.ConnectionError("redis down")

    async def delete(self, *args, **kwargs):
        raise redis.exceptions.ConnectionError("redis down")


@pytest.mark.asyncio
async def test_redis_failure_returns_service_unavailable(monkeypatch, logged_in_user):
    """AC1：Redis 讀取失敗 → 503 SERVICE_UNAVAILABLE（和資料庫連不上一樣）。"""
    monkeypatch.setattr(cache, "_redis_client", _BrokenRedis())

    res = await _request("POST", "/schedule/confirm")

    assert res.status_code == 503
    assert res.json()["error_code"] == "SERVICE_UNAVAILABLE"


def test_rate_limit_storage_failure_returns_service_unavailable(monkeypatch):
    """AC1：限流計數的 Redis 失敗 → 503 SERVICE_UNAVAILABLE。"""
    mini_app = FastAPI()
    limiter = Limiter(key_func=lambda request: "fixed", storage_uri="memory://", enabled=True)
    mini_app.state.limiter = limiter
    mini_app.add_exception_handler(redis.exceptions.RedisError, redis_error_handler)  # pyright: ignore[reportArgumentType]

    def broken_hit(*args, **kwargs):
        raise redis.exceptions.ConnectionError("redis down")

    monkeypatch.setattr(limiter._limiter, "hit", broken_hit)

    @mini_app.get("/ping")
    @limiter.limit("5/minute")
    async def ping(request: Request):
        return {"status": "ok"}

    res = TestClient(mini_app, raise_server_exceptions=False).get("/ping")

    assert res.status_code == 503
    assert res.json()["error_code"] == "SERVICE_UNAVAILABLE"


def test_main_app_registers_redis_error_handler():
    """限流與快取共用同一個 Redis handler，要掛在 main 的 app 上。"""
    assert app.exception_handlers.get(redis.exceptions.RedisError) is redis_error_handler


@pytest.mark.asyncio
async def test_unknown_error_code_returns_fixed_internal_error(monkeypatch, logged_in_user, caplog):
    """AC3：對照表沒有的 error_code 走 HTTP 也是 500 INTERNAL_ERROR 與固定 detail，log 有原始 error_code 與 trace header。"""
    import logging

    import crud.user as user_crud
    from core.errors import AppError

    async def raise_unknown(*args, **kwargs):
        raise AppError("內部說明", error_code="NOT_IN_TABLE")

    monkeypatch.setattr(user_crud, "get_user_by_clerk_id", raise_unknown)

    with caplog.at_level(logging.ERROR, logger="core.exception_handlers"):
        res = await _request("GET", "/users/me", headers={"X-Cloud-Trace-Context": "abc123/1;o=1"})

    assert res.status_code == 500
    assert res.json() == {"detail": "伺服器發生未預期的錯誤，請稍後再試", "error_code": "INTERNAL_ERROR"}
    assert any("NOT_IN_TABLE" in r.getMessage() and "GET /users/me" in r.getMessage() and "abc123/1;o=1" in r.getMessage()
               for r in caplog.records)
