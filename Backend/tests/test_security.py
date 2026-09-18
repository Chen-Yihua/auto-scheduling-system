"""
db/security.py 的 get_current_clerk_user——整個系統的驗證守門員，理論上優先度
最高，但先前完全沒有專屬測試（模組載入當下缺環境變數會 RuntimeError 這件事，
已經由 test_ci_env_requirements.py 用乾淨的子行程驗證過，這裡只補函式本體）。
"""
import pytest
from fastapi import HTTPException
from fastapi_clerk_auth import HTTPAuthorizationCredentials

import db.security as security


@pytest.mark.asyncio
async def test_get_current_clerk_user_returns_decoded_payload_on_success():
    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer", credentials="valid-token", decoded={"sub": "uid123", "email": "a@b.com"}
    )

    result = await security.get_current_clerk_user(credentials=credentials)

    assert result == {"sub": "uid123", "email": "a@b.com"}


@pytest.mark.asyncio
async def test_get_current_clerk_user_raises_401_when_credentials_missing():
    with pytest.raises(HTTPException) as exc_info:
        await security.get_current_clerk_user(credentials=None)

    assert exc_info.value.status_code == 401
    assert exc_info.value.headers == {"WWW-Authenticate": "Bearer"}


@pytest.mark.asyncio
async def test_get_current_clerk_user_raises_401_when_token_fails_to_decode():
    # decoded 是 None 代表 ClerkHTTPBearer 驗證失敗（token 過期/簽章不對/JWKS
    # 抓不到...），但 auto_error 沒有在更上層就直接擋下來時的最後一道防線
    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer", credentials="bad-token", decoded=None
    )

    with pytest.raises(HTTPException) as exc_info:
        await security.get_current_clerk_user(credentials=credentials)

    assert exc_info.value.status_code == 401
