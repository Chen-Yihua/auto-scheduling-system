"""
用 Clerk 的 JWKS 驗證 Authorization header 的 JWT。

失敗分兩步（ADR 0011）：向 Clerk 取得 signing keys 失敗是外部服務的問題（502／504），
token 本身無效是 401；兩步以外的例外是程式的 bug，照未處理的例外回 500。
"""
import http.client
import logging
import os
import time
from urllib.error import URLError

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.encoders import jsonable_encoder
from fastapi_clerk_auth import ClerkConfig, ClerkHTTPBearer, HTTPAuthorizationCredentials

from core.errors import ExternalServiceError

logger = logging.getLogger(__name__)

CLERK_JWKS_URL = os.getenv("CLERK_JWKS_URL")
CLERK_ISSUER = os.getenv("CLERK_ISSUER")

if not CLERK_JWKS_URL or not CLERK_ISSUER:
    raise RuntimeError("Missing environment variable")

JWKS_UNAVAILABLE_DETAIL = "暫時無法驗證登入狀態，請稍後再試"

# 實測 PyJWT 2.14.0 取得 JWKS 時會丟的例外：PyJWKClientConnectionError（連不上、HTTP 錯誤、逾時）、
# 讀回應時原樣丟出的 http.client.HTTPException 與 OSError、回應不是 JSON 的 ValueError、
# JWKS 結構錯誤的 PyJWKSetError 與 PyJWKClientError。
# AttributeError、TypeError：keys 裡有元素不是 object、或 key 欄位型別錯誤時 PyJWK 會丟；只在取得 keys 這一個呼叫內接
_JWKS_FETCH_ERRORS = (
    jwt.PyJWKClientError,
    jwt.PyJWKSetError,
    http.client.HTTPException,
    OSError,
    ValueError,
    AttributeError,
    TypeError,
)


def _caused_by_timeout(exc: BaseException) -> bool:
    """連線逾時是 URLError(reason=TimeoutError)，讀回應逾時是 PyJWKClientConnectionError → TimeoutError。"""
    seen = set()
    pending: list[BaseException] = [exc]
    while pending:
        current = pending.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        if isinstance(current, TimeoutError):
            return True
        if isinstance(current, URLError) and isinstance(current.reason, BaseException):
            pending.append(current.reason)
        pending.extend(e for e in (current.__cause__, current.__context__) if e is not None)
    return False


class ClerkJWTBearer(ClerkHTTPBearer):
    """
    覆寫 ClerkHTTPBearer 的解碼：原本用 except Exception 吞掉所有例外，分不出 Clerk 故障和 token 無效。

    依賴 fastapi-clerk-auth 0.0.9 的 _decode_token，以及 PyJWT 2.14.0 PyJWKClient 的 _client_lock、
    _last_successful_fetch（requirements.txt 鎖定版本）；升級時要重新確認例外形式與這些私有成員。
    回 None 時 ClerkHTTPBearer 丟 403，由 core/exception_handlers.py 補成 UNAUTHENTICATED（401）。
    """

    def _get_signing_keys(self, refresh: bool = False) -> list[jwt.PyJWK]:
        try:
            return self.jwks_client.get_signing_keys(refresh=refresh)
        except _JWKS_FETCH_ERRORS as e:
            error_code = "UPSTREAM_TIMEOUT" if _caused_by_timeout(e) else "UPSTREAM_ERROR"
            logger.error("取得 Clerk JWKS 失敗 error_code=%s", error_code, exc_info=True)
            raise ExternalServiceError(JWKS_UNAVAILABLE_DETAIL, error_code=error_code) from e

    def _find_signing_key(self, kid) -> jwt.PyJWK | None:
        """照 PyJWKClient.get_signing_key 的流程，但取得 keys 的錯誤和 kid 找不到分開處理。"""
        client = self.jwks_client
        with client._client_lock:
            signing_key = client.match_kid(self._get_signing_keys(), kid)
            if signing_key is not None:
                return signing_key
            # 保留 cooldown：否則帶任意 kid 的請求每次都會向 Clerk 同步抓一次 JWKS
            cooling_down = (
                client.jwk_set_cache is not None
                and client._last_successful_fetch is not None
                and time.monotonic() - client._last_successful_fetch < client.cooldown_duration
            )
            if cooling_down:
                return None
            signing_keys = self._get_signing_keys(refresh=True)
            client._last_successful_fetch = time.monotonic()
            return client.match_kid(signing_keys, kid)

    def _decode_token(self, token: str) -> dict | None:
        # 先解析 header 再抓 keys：Clerk 故障時，格式錯誤的 token 仍是 401
        try:
            header = jwt.get_unverified_header(token)
        except jwt.InvalidTokenError:
            return None

        signing_key = self._find_signing_key(header.get("kid"))
        if signing_key is None:
            return None

        try:
            decoded_token = jwt.decode(
                token,
                key=signing_key.key,
                audience=self.audience,
                issuer=self.issuer,
                algorithms=["RS256"],
                options={
                    "verify_exp": self.config.verify_exp,
                    "verify_aud": self.config.verify_aud,
                    "verify_iss": self.config.verify_iss,
                    "verify_iat": self.config.verify_iat,
                },
                leeway=self.config.leeway,
            )
        except jwt.PyJWTError:
            return None
        return dict(jsonable_encoder(decoded_token))


clerk_config = ClerkConfig(
    jwks_url=CLERK_JWKS_URL,
    issuer=CLERK_ISSUER,
    verify_iss=True,
    leeway=10,  # 容許的時鐘誤差（秒）
)

clerk_auth = ClerkJWTBearer(config=clerk_config, auto_error=True)


async def get_current_clerk_user(
    credentials: HTTPAuthorizationCredentials = Depends(clerk_auth)
):
    """回傳解碼後的 JWT payload，"sub" 是 Clerk 使用者 id。"""
    if not credentials or not credentials.decoded :
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials.decoded
