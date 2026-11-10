"""core/errors.py 的 error_code 與狀態碼預設值，以及 core/exception_handlers.py 各 handler 回的格式。"""
import json
import logging

import pytest
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.requests import Request

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
    validation_error_handler,
)


def _request() -> Request:
    return Request({"type": "http", "method": "POST", "path": "/test", "headers": [], "query_string": b""})


def _body(response) -> dict:
    return json.loads(response.body)


@pytest.mark.parametrize("error_cls, error_code, status", [
    (InvalidRequestError, "INVALID_REQUEST", 400),
    (ReauthRequiredError, "REAUTH_REQUIRED", 401),
    (AccessDeniedError, "INVALID_CREDENTIALS", 403),
    (NotFoundError, "NOT_FOUND", 404),
    (ConflictError, "ALREADY_EXISTS", 409),
    (ConfigurationError, "INTERNAL_ERROR", 500),
    (ExternalServiceError, "UPSTREAM_ERROR", 502),
    (AppError, "INTERNAL_ERROR", 500),
])
@pytest.mark.asyncio
async def test_app_error_without_overrides_uses_class_defaults(error_cls, error_code, status):
    """AC21：沒有指定時用類別預設的 error_code 與狀態碼（預設狀態碼是改之前的值；AccessDeniedError 是 INVALID_CREDENTIALS／403）。"""
    response = await app_error_handler(_request(), error_cls("說明"))

    assert response.status_code == status
    assert _body(response) == {"detail": "說明", "error_code": error_code}


@pytest.mark.asyncio
async def test_app_error_with_only_error_code_keeps_class_status():
    """AC21：只指定 error_code 時狀態碼和類別預設相同，例如逾時仍是 502。"""
    response = await app_error_handler(_request(), ExternalServiceError("逾時", error_code="UPSTREAM_TIMEOUT"))

    assert response.status_code == 502
    assert _body(response) == {"detail": "逾時", "error_code": "UPSTREAM_TIMEOUT"}


@pytest.mark.asyncio
async def test_app_error_with_explicit_status_uses_it():
    """AC21：明確指定狀態碼時用指定的值，例如 PATCH 解密失敗帶 REAUTH_REQUIRED 但維持 500。"""
    response = await app_error_handler(_request(), ReauthRequiredError("憑證無法讀取", status_code=500))

    assert response.status_code == 500
    assert _body(response) == {"detail": "憑證無法讀取", "error_code": "REAUTH_REQUIRED"}


@pytest.mark.parametrize("status, error_code", [
    (400, "INVALID_REQUEST"),
    (401, "UNAUTHENTICATED"),
    (403, "UNAUTHENTICATED"),
    (404, "NOT_FOUND"),
    (405, "METHOD_NOT_ALLOWED"),
    (409, "ALREADY_EXISTS"),
    (500, "INTERNAL_ERROR"),
    (502, "UPSTREAM_ERROR"),
    (418, "INVALID_REQUEST"),
    (503, "INTERNAL_ERROR"),
])
@pytest.mark.asyncio
async def test_http_exception_gets_default_error_code_by_status(status, error_code):
    """AC2、AC19：HTTPException 依狀態碼補預設的 error_code；沒列到的 4xx 是 INVALID_REQUEST、5xx 是 INTERNAL_ERROR。"""
    response = await http_exception_handler(_request(), StarletteHTTPException(status_code=status, detail="原本的說明"))

    assert response.status_code == status
    assert _body(response) == {"detail": "原本的說明", "error_code": error_code}


@pytest.mark.asyncio
async def test_http_exception_keeps_original_headers():
    """AC19：保留 HTTPException 原本的 header，例如 core/security.py 401 的 WWW-Authenticate。"""
    exc = StarletteHTTPException(status_code=401, detail="Invalid authentication credentials", headers={"WWW-Authenticate": "Bearer"})

    response = await http_exception_handler(_request(), exc)

    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert _body(response) == {"detail": "Invalid authentication credentials", "error_code": "UNAUTHENTICATED"}


@pytest.mark.asyncio
async def test_validation_error_drops_input_and_ctx(caplog):
    """AC4、AC13：422 帶 VALIDATION_ERROR，每一項不帶 input、ctx，也不把 request body 寫進 log。"""
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
