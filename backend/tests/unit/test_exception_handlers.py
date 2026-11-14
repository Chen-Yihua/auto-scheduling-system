"""core/error_codes.py 的對照表、core/errors.py 的 error_code 預設值，以及 core/exception_handlers.py 各 handler 回的格式。"""
import inspect
import json
import logging

import pytest
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.requests import Request

from core.error_codes import STATUS_BY_ERROR_CODE, status_for_error_code
from core.errors import (
    AccessDeniedError,
    AppError,
    ConfigurationError,
    ConflictError,
    ExternalServiceError,
    InvalidRequestError,
    NotFoundError,
    ReauthRequiredError,
)
from core.exception_handlers import (
    app_error_handler,
    http_exception_handler,
    redis_error_handler,
    validation_error_handler,
)

# ADR 0011「對照表」逐列抄寫
ADR_0011_TABLE = {
    "INVALID_REQUEST": 400,
    "INVALID_CREDENTIALS": 400,
    "INVALID_PLATFORM_DOMAIN": 400,
    "INVALID_AUTHORIZATION_CODE": 400,
    "UNAUTHENTICATED": 401,
    "INVALID_WEBHOOK_SIGNATURE": 401,
    "INVALID_SCHEDULER_TOKEN": 401,
    "NOT_FOUND": 404,
    "METHOD_NOT_ALLOWED": 405,
    "NOT_LINKED": 409,
    "REAUTH_REQUIRED": 409,
    "ALREADY_EXISTS": 409,
    "SUGGESTION_EXPIRED": 409,
    "IDEMPOTENCY_KEY_REUSED": 409,
    "REQUEST_IN_PROGRESS": 409,
    "NO_PRIMARY_CALENDAR": 409,
    "VALIDATION_ERROR": 422,
    "RATE_LIMITED": 429,
    "INTERNAL_ERROR": 500,
    "UPSTREAM_ERROR": 502,
    "UPSTREAM_RATE_LIMITED": 503,
    "SERVICE_UNAVAILABLE": 503,
    "UPSTREAM_TIMEOUT": 504,
}

UNEXPECTED_DETAIL = "伺服器發生未預期的錯誤，請稍後再試"


def _request(headers: list[tuple[bytes, bytes]] | None = None) -> Request:
    return Request({"type": "http", "method": "POST", "path": "/test", "headers": headers or [], "query_string": b""})


def _body(response) -> dict:
    return json.loads(response.body)


def test_error_code_table_matches_adr_0011():
    """AC1：後端的對照表和 ADR 0011 的對照表逐列相同，沒有多也沒有少。"""
    assert STATUS_BY_ERROR_CODE == ADR_0011_TABLE


def test_unknown_error_code_has_no_status():
    """AC3：對照表沒有的 error_code 查不到狀態碼，由 handler 決定怎麼回。"""
    assert status_for_error_code("SOMETHING_NEW") is None


@pytest.mark.parametrize("error_cls, error_code, status", [
    (InvalidRequestError, "INVALID_REQUEST", 400),
    (ReauthRequiredError, "REAUTH_REQUIRED", 409),
    (AccessDeniedError, "INVALID_CREDENTIALS", 400),
    (NotFoundError, "NOT_FOUND", 404),
    (ConflictError, "ALREADY_EXISTS", 409),
    (ConfigurationError, "INTERNAL_ERROR", 500),
    (ExternalServiceError, "UPSTREAM_ERROR", 502),
    (AppError, "INTERNAL_ERROR", 500),
])
@pytest.mark.asyncio
async def test_app_error_status_comes_from_table_by_class_default_error_code(error_cls, error_code, status):
    """AC1、AC2：子類別只有預設的 error_code，狀態碼由對照表決定。"""
    response = await app_error_handler(_request(), error_cls("說明"))

    assert response.status_code == status
    assert _body(response) == {"detail": "說明", "error_code": error_code}


@pytest.mark.parametrize("error_code, status", list(ADR_0011_TABLE.items()))
@pytest.mark.asyncio
async def test_app_error_status_follows_error_code_not_class(error_code, status):
    """AC1：指定 error_code 時狀態碼照它查表，和例外類別無關（例如 ExternalServiceError 帶 UPSTREAM_TIMEOUT 是 504）。"""
    response = await app_error_handler(_request(), ExternalServiceError("說明", error_code=error_code))

    assert response.status_code == status
    assert _body(response)["error_code"] == error_code


def test_app_error_has_no_status_code_parameter_or_attribute():
    """AC2：AppError 與子類別沒有指定狀態碼的參數或屬性。"""
    for cls in (AppError, InvalidRequestError, ReauthRequiredError, AccessDeniedError, NotFoundError,
                ConflictError, ConfigurationError, ExternalServiceError):
        assert "status_code" not in inspect.signature(cls).parameters
        assert not hasattr(cls, "default_status_code")
        assert not hasattr(cls("x"), "status_code")


@pytest.mark.asyncio
async def test_app_error_headers_are_sent():
    """AC5：AppError 帶的 header（例如 Retry-After）會放進回應。"""
    exc = ExternalServiceError("限流", error_code="UPSTREAM_RATE_LIMITED", headers={"Retry-After": "30"})

    response = await app_error_handler(_request(), exc)

    assert response.status_code == 503
    assert response.headers["Retry-After"] == "30"


@pytest.mark.asyncio
async def test_unknown_error_code_returns_fixed_500_and_logs_original(caplog):
    """AC3：對照表沒有的 error_code → 500 INTERNAL_ERROR 與固定 detail，不回原始的 error_code 與 detail；log 有原始 error_code、例外、方法與路徑、trace header。"""
    try:
        raise AppError("內部的原因說明", error_code="SOMETHING_NEW")
    except AppError as e:
        exc = e
    request = _request([(b"x-cloud-trace-context", b"105445aa7843bc8bf206b12000100000/1;o=1")])

    with caplog.at_level(logging.ERROR, logger="core.exception_handlers"):
        response = await app_error_handler(request, exc)

    assert response.status_code == 500
    assert _body(response) == {"detail": UNEXPECTED_DETAIL, "error_code": "INTERNAL_ERROR"}
    assert b"SOMETHING_NEW" not in response.body
    assert "內部的原因說明".encode() not in response.body
    record = next(r for r in caplog.records if "SOMETHING_NEW" in r.getMessage())
    assert record.levelno == logging.ERROR
    assert "POST /test" in record.getMessage()
    assert "105445aa7843bc8bf206b12000100000/1;o=1" in record.getMessage()
    assert record.exc_info and record.exc_info[1] is exc and record.exc_info[2] is not None


@pytest.mark.asyncio
async def test_unknown_error_code_log_without_trace_header(caplog):
    """AC3：沒有 X-Cloud-Trace-Context 時照樣記 log 與回固定的 500。"""
    with caplog.at_level(logging.ERROR, logger="core.exception_handlers"):
        response = await app_error_handler(_request(), AppError("x", error_code="SOMETHING_NEW"))

    assert response.status_code == 500
    assert any("SOMETHING_NEW" in r.getMessage() for r in caplog.records)


@pytest.mark.parametrize("status, error_code, response_status", [
    (400, "INVALID_REQUEST", 400),
    (401, "UNAUTHENTICATED", 401),
    (403, "UNAUTHENTICATED", 401),
    (404, "NOT_FOUND", 404),
    (405, "METHOD_NOT_ALLOWED", 405),
    (409, "ALREADY_EXISTS", 409),
    (500, "INTERNAL_ERROR", 500),
    (502, "UPSTREAM_ERROR", 502),
    (418, "INVALID_REQUEST", 400),
    (503, "INTERNAL_ERROR", 500),
])
@pytest.mark.asyncio
async def test_http_exception_error_code_by_status_then_status_by_table(status, error_code, response_status):
    """AC1、AC4：HTTPException 先依狀態碼補 error_code，再依 error_code 查表；Clerk library 的 403 變成 401 UNAUTHENTICATED。"""
    response = await http_exception_handler(_request(), StarletteHTTPException(status_code=status, detail="原本的說明"))

    assert response.status_code == response_status
    assert _body(response) == {"detail": "原本的說明", "error_code": error_code}


@pytest.mark.asyncio
async def test_http_exception_keeps_original_headers():
    """保留 HTTPException 原本的 header，例如 WWW-Authenticate。"""
    exc = StarletteHTTPException(status_code=401, detail="Invalid authentication credentials", headers={"WWW-Authenticate": "Bearer"})

    response = await http_exception_handler(_request(), exc)

    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert _body(response) == {"detail": "Invalid authentication credentials", "error_code": "UNAUTHENTICATED"}


@pytest.mark.asyncio
async def test_redis_error_is_503_service_unavailable():
    """AC1：Redis 故障是本系統依賴暫時不能用，503 SERVICE_UNAVAILABLE。"""
    from redis.exceptions import ConnectionError as RedisConnectionError

    response = await redis_error_handler(_request(), RedisConnectionError("down"))

    assert response.status_code == 503
    assert _body(response)["error_code"] == "SERVICE_UNAVAILABLE"


@pytest.mark.asyncio
async def test_validation_error_drops_input_and_ctx(caplog):
    """422 帶 VALIDATION_ERROR，每一項不帶 input、ctx，也不把 request body 寫進 log。"""
    exc = RequestValidationError([
        {"type": "missing", "loc": ("body", "status"), "msg": "Field required",
         "input": {"apiKey": "ghp_secret_value", "password": "pw-secret"}},
        {"type": "string_too_short", "loc": ("body", "username"), "msg": "too short",
         "input": "pw-secret", "ctx": {"min_length": 3, "value": "pw-secret"}},
    ], body={"apiKey": "ghp_secret_value", "password": "pw-secret"})

    with caplog.at_level(logging.DEBUG):
        response = await validation_error_handler(_request(), exc)

    body = _body(response)
    assert response.status_code == 422
    assert body["error_code"] == "VALIDATION_ERROR"
    assert body["detail"] == [
        {"type": "missing", "loc": ["body", "status"], "msg": "Field required"},
        {"type": "string_too_short", "loc": ["body", "username"], "msg": "too short"},
    ]
    assert "ghp_secret_value" not in response.body.decode()
    assert "ghp_secret_value" not in caplog.text
    assert "pw-secret" not in caplog.text
