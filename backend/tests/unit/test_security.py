"""core/security.py：Clerk JWT 驗證失敗時的狀態碼與 error_code，以及 get_current_clerk_user。"""
import http.client
import io
import json
import logging
import time
from email.message import Message
from urllib.error import HTTPError, URLError

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi_clerk_auth import HTTPAuthorizationCredentials
from jwt.algorithms import RSAAlgorithm
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.requests import Request

import core.security as security
from core.errors import AppError
from core.exception_handlers import app_error_handler, http_exception_handler

ISSUER = security.CLERK_ISSUER
SECRET_TEXT = "jwks-internal-detail-10.0.0.5"


def _rsa_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


SIGNING_KEY = _rsa_key()
OTHER_KEY = _rsa_key()


def _jwk(private_key, kid: str) -> dict:
    jwk = RSAAlgorithm.to_jwk(private_key.public_key(), as_dict=True)
    return {**jwk, "kid": kid, "use": "sig", "alg": "RS256"}


def _jwks(*kids: str) -> bytes:
    return json.dumps({"keys": [_jwk(SIGNING_KEY, kid) for kid in kids]}).encode()


def _token(kid: str = "k1", *, key=SIGNING_KEY, exp_offset: int = 300, issuer: str | None = None) -> str:
    now = int(time.time())
    payload = {"sub": "user_1", "iss": issuer or ISSUER, "iat": now - 10, "exp": now + exp_offset}
    return jwt.encode(payload, key, algorithm="RS256", headers={"kid": kid})


class _Response(io.BytesIO):
    """urllib 回應的替身；read_error 模擬讀回應時才發生的錯誤。"""

    def __init__(self, body: bytes = b"", read_error: BaseException | None = None):
        super().__init__(body)
        self._read_error = read_error

    def read(self, *args):
        if self._read_error is not None:
            raise self._read_error
        return super().read(*args)


class FakeOpener:
    """
    取代 urllib.request.build_opener 回傳的 opener：PyJWKClient.fetch_data 用 opener.open 抓 JWKS，
    只 patch urlopen 會真的連到 Clerk。outcomes 依序是每次抓取的結果（bytes、_Response 或要丟的例外）。
    """

    def __init__(self, *outcomes):
        self.outcomes = list(outcomes)
        self.calls = 0

    def __call__(self, *handlers):
        return self

    def open(self, request, timeout=None):
        self.calls += 1
        outcome = self.outcomes.pop(0) if len(self.outcomes) > 1 else self.outcomes[0]
        if callable(outcome) and not isinstance(outcome, (bytes, _Response)):
            outcome = outcome()
        if isinstance(outcome, BaseException):
            raise outcome
        if isinstance(outcome, bytes):
            return _Response(outcome)
        return outcome


@pytest.fixture
def opener(monkeypatch):
    def install(*outcomes) -> FakeOpener:
        fake = FakeOpener(*outcomes)
        monkeypatch.setattr("jwt.jwks_client.urllib.request.build_opener", fake)
        return fake
    return install


def _bearer():
    # 每個測試自己建 instance：JWKS 快取與上次成功抓取的時間不能跨測試共用
    return security.ClerkJWTBearer(config=security.clerk_config, auto_error=True)


def _request(authorization: str | None) -> Request:
    headers = [(b"authorization", authorization.encode())] if authorization is not None else []
    return Request({"type": "http", "method": "GET", "path": "/users/me", "headers": headers, "query_string": b""})


async def _authenticate(bearer, authorization: str | None):
    """跑一次驗證，丟出的 AppError、HTTPException 照全域 handler 轉成回應；回 (狀態碼, body)。"""
    request = _request(authorization)
    try:
        credentials = await bearer(request)
    except AppError as e:
        response = await app_error_handler(request, e)
    except StarletteHTTPException as e:
        response = await http_exception_handler(request, e)
    else:
        return 200, credentials.decoded
    return response.status_code, json.loads(response.body)


def _connect_timeout():
    # 連線時逾時：URLError(reason=TimeoutError)，TimeoutError 同時在 __context__
    try:
        raise TimeoutError("timed out")
    except TimeoutError as e:
        raise URLError(e)


def _raise_connect_timeout():
    try:
        _connect_timeout()
    except URLError as e:
        return e


def _http_error(status: int) -> HTTPError:
    return HTTPError("https://test.clerk.invalid/.well-known/jwks.json", status, "error", Message(), io.BytesIO(b""))


# ---------- 模組設定 ----------

def test_module_auth_uses_wrapped_bearer():
    """AC4：全站用的 clerk_auth 是包裝後的子類別，失敗回應才會照下面的規則。"""
    assert isinstance(security.clerk_auth, security.ClerkJWTBearer)


# ---------- 401 UNAUTHENTICATED ----------

@pytest.mark.parametrize("authorization", [None, "Basic dXNlcjpwdw==", "Bearer"])
@pytest.mark.asyncio
async def test_missing_token_or_wrong_scheme_is_401(opener, authorization):
    """AC4：沒帶 token、scheme 不是 Bearer → 401 UNAUTHENTICATED，不用抓 JWKS。"""
    fake = opener(_jwks("k1"))

    status, body = await _authenticate(_bearer(), authorization)

    assert status == 401
    assert body["error_code"] == "UNAUTHENTICATED"
    assert fake.calls == 0


@pytest.mark.parametrize("token", ["not-a-jwt", "a.b.c"])
@pytest.mark.asyncio
async def test_malformed_token_is_401_even_when_clerk_is_down(opener, token):
    """AC4：token 格式錯誤 → 401；先解析 header 再抓 keys，所以 Clerk 故障時也是 401。"""
    fake = opener(URLError(ConnectionRefusedError(111, "refused")))

    status, body = await _authenticate(_bearer(), f"Bearer {token}")

    assert status == 401
    assert body["error_code"] == "UNAUTHENTICATED"
    assert fake.calls == 0


@pytest.mark.asyncio
async def test_valid_token_is_accepted_with_real_jwks_client(opener):
    """AC4：用真的 PyJWKClient、只模擬 urllib：簽章正確、沒過期的 token 通過驗證。"""
    opener(_jwks("k1"))

    status, decoded = await _authenticate(_bearer(), f"Bearer {_token('k1')}")

    assert status == 200
    assert decoded["sub"] == "user_1"


@pytest.mark.parametrize("token_factory", [
    lambda: _token("k1", key=OTHER_KEY),
    lambda: _token("k1", exp_offset=-3600),
    lambda: _token("k1", issuer="https://evil.example.com"),
], ids=["bad-signature", "expired", "wrong-issuer"])
@pytest.mark.asyncio
async def test_invalid_signature_expired_or_wrong_claims_is_401(opener, token_factory):
    """AC4：簽章無效、過期、claims 不符 → 401 UNAUTHENTICATED。"""
    opener(_jwks("k1"))

    status, body = await _authenticate(_bearer(), f"Bearer {token_factory()}")

    assert status == 401
    assert body["error_code"] == "UNAUTHENTICATED"


@pytest.mark.asyncio
async def test_unknown_kid_within_cooldown_is_401_without_refetch(opener):
    """AC4：kid 找不到、離上次成功抓取不到 30 秒 → 不重新抓 JWKS，401。"""
    fake = opener(_jwks("k1"))

    status, body = await _authenticate(_bearer(), f"Bearer {_token('unknown')}")

    assert status == 401
    assert body["error_code"] == "UNAUTHENTICATED"
    assert fake.calls == 1


@pytest.mark.asyncio
async def test_random_kids_after_successful_fetch_do_not_refetch(opener):
    """AC4：上次成功抓取後 30 秒內，帶任意 kid 的 token 都不會再向 Clerk 抓 JWKS。"""
    fake = opener(_jwks("k1"))
    bearer = _bearer()

    assert (await _authenticate(bearer, f"Bearer {_token('k1')}"))[0] == 200
    for i in range(5):
        status, _ = await _authenticate(bearer, f"Bearer {_token(f'random-{i}')}")
        assert status == 401

    assert fake.calls == 1


@pytest.mark.asyncio
async def test_unknown_kid_after_cooldown_refetches_and_finds_rotated_key(opener):
    """AC4：cooldown 過後 kid 找不到會重新抓一次；抓到輪替後的新 key 就通過。"""
    fake = opener(_jwks("k1"), _jwks("k1", "k2"))
    bearer = _bearer()
    await _authenticate(bearer, f"Bearer {_token('k1')}")
    bearer.jwks_client._last_successful_fetch = time.monotonic() - 31

    status, decoded = await _authenticate(bearer, f"Bearer {_token('k2')}")

    assert status == 200
    assert decoded["sub"] == "user_1"
    assert fake.calls == 2


@pytest.mark.asyncio
async def test_unknown_kid_still_missing_after_refetch_is_401(opener):
    """AC4：重新抓之後仍找不到 kid → 401（可能是 token 用了不存在的金鑰）。"""
    fake = opener(_jwks("k1"))
    bearer = _bearer()
    await _authenticate(bearer, f"Bearer {_token('k1')}")
    bearer.jwks_client._last_successful_fetch = time.monotonic() - 31

    status, body = await _authenticate(bearer, f"Bearer {_token('unknown')}")

    assert status == 401
    assert body["error_code"] == "UNAUTHENTICATED"
    assert fake.calls == 2


@pytest.mark.parametrize("refetch_error, status, error_code", [
    (URLError(ConnectionRefusedError(111, "refused")), 502, "UPSTREAM_ERROR"),
    (_raise_connect_timeout, 504, "UPSTREAM_TIMEOUT"),
])
@pytest.mark.asyncio
async def test_refetch_failure_after_cooldown_is_upstream_error(opener, refetch_error, status, error_code):
    """AC4：cooldown 過後重新抓 JWKS 失敗算 Clerk 的錯誤（502／504），不是 401。"""
    opener(_jwks("k1"), refetch_error)
    bearer = _bearer()
    await _authenticate(bearer, f"Bearer {_token('k1')}")
    bearer.jwks_client._last_successful_fetch = time.monotonic() - 31

    result_status, body = await _authenticate(bearer, f"Bearer {_token('k2')}")

    assert result_status == status
    assert body["error_code"] == error_code


# ---------- 抓 JWKS 失敗：502／504 ----------

def _read_timeout():
    return _Response(read_error=TimeoutError("read timed out"))


@pytest.mark.parametrize("outcome, status, error_code", [
    (_raise_connect_timeout, 504, "UPSTREAM_TIMEOUT"),
    (_read_timeout, 504, "UPSTREAM_TIMEOUT"),
    (lambda: URLError(ConnectionRefusedError(111, SECRET_TEXT)), 502, "UPSTREAM_ERROR"),
    (lambda: _http_error(503), 502, "UPSTREAM_ERROR"),
    (lambda: _Response(read_error=http.client.RemoteDisconnected(SECRET_TEXT)), 502, "UPSTREAM_ERROR"),
    (lambda: _Response(read_error=http.client.IncompleteRead(b"{")), 502, "UPSTREAM_ERROR"),
    (lambda: _Response(SECRET_TEXT.encode()), 502, "UPSTREAM_ERROR"),
    (lambda: _Response(b'{"keys": []}'), 502, "UPSTREAM_ERROR"),
    (lambda: _Response(b"{}"), 502, "UPSTREAM_ERROR"),
    (lambda: _Response(b"[1, 2]"), 502, "UPSTREAM_ERROR"),
    (lambda: _Response(json.dumps({"keys": [{**_jwk(SIGNING_KEY, "k1"), "use": "enc"}]}).encode()), 502, "UPSTREAM_ERROR"),
    (lambda: _Response(b'{"keys": ["x"]}'), 502, "UPSTREAM_ERROR"),
    (lambda: _Response(b'{"keys": [{"kty": "RSA", "kid": "k1", "n": 1, "e": 2}]}'), 502, "UPSTREAM_ERROR"),
], ids=[
    "connect-timeout", "read-timeout", "connection-refused", "http-503", "remote-disconnected",
    "incomplete-read", "not-json", "empty-keys", "no-keys", "json-not-object", "no-signing-key",
    "key-not-object", "key-field-wrong-type",
])
@pytest.mark.asyncio
async def test_jwks_fetch_failure_is_upstream_error(opener, caplog, outcome, status, error_code):
    """AC4：抓 Clerk JWKS 連不上、中斷、不是 JSON、沒有 key、key 格式錯 → 502；逾時 → 504。detail 不帶例外內容，log 有例外。"""
    opener(outcome)

    with caplog.at_level(logging.WARNING, logger="core.security"):
        result_status, body = await _authenticate(_bearer(), f"Bearer {_token('k1')}")

    assert result_status == status
    assert body["error_code"] == error_code
    assert SECRET_TEXT not in json.dumps(body, ensure_ascii=False)
    assert any(r.exc_info for r in caplog.records)


@pytest.mark.asyncio
async def test_unexpected_exception_outside_jwks_fetch_is_not_converted(opener, monkeypatch):
    """AC4：取得 keys 以外丟的 AttributeError 是程式的 bug，不轉成 401 或 502，照未處理的例外回 500。"""
    opener(_jwks("k1"))
    bearer = _bearer()

    def broken_match_kid(*args):
        raise AttributeError("bug")

    monkeypatch.setattr(bearer.jwks_client, "match_kid", broken_match_kid)

    with pytest.raises(AttributeError):
        await bearer(_request(f"Bearer {_token('k1')}"))


# ---------- get_current_clerk_user ----------

@pytest.mark.asyncio
async def test_get_current_clerk_user_returns_decoded_payload_on_success():
    """驗證成功 → 原樣回傳解碼後的 token 內容（含 sub、email）。"""
    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer", credentials="valid-token", decoded={"sub": "uid123", "email": "a@b.com"}
    )

    result = await security.get_current_clerk_user(credentials=credentials)

    assert result == {"sub": "uid123", "email": "a@b.com"}


@pytest.mark.asyncio
async def test_get_current_clerk_user_raises_401_when_credentials_missing():
    """AC5：完全沒有 credentials → 401 UNAUTHENTICATED，並帶 WWW-Authenticate: Bearer 標頭。"""
    with pytest.raises(AppError) as exc_info:
        await security.get_current_clerk_user(credentials=None)

    assert exc_info.value.error_code == "UNAUTHENTICATED"
    assert exc_info.value.detail == "Invalid authentication credentials"
    assert exc_info.value.headers == {"WWW-Authenticate": "Bearer"}
