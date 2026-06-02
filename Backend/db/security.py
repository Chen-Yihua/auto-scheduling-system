from fastapi import Depends, HTTPException, status, Request
from fastapi_clerk_auth import ClerkConfig, ClerkHTTPBearer, HTTPAuthorizationCredentials
from cryptography.fernet import Fernet, InvalidToken
import os


"""
此程式的核心邏輯：從 header 抓 token後，拿JWKs驗證，回傳decoded後的payload
"""


def _get_fernet_cipher() -> Fernet:
    encryption_key = os.getenv("ENCRYPTION_KEY")
    if not encryption_key:
        raise RuntimeError("Missing environment variable: ENCRYPTION_KEY")
    return Fernet(encryption_key.encode())


def encrypt_secret(secret: str) -> str:
    """Encrypt sensitive credential values before storing them in DB."""
    return _get_fernet_cipher().encrypt(secret.encode()).decode()


def decrypt_secret(encrypted_secret: str) -> str:
    """Decrypt sensitive credential values before using them."""
    try:
        return _get_fernet_cipher().decrypt(encrypted_secret.encode()).decode()
    except InvalidToken:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Invalid encrypted credential",
        )


def _get_clerk_auth() -> ClerkHTTPBearer:
    clerk_jwks_url = os.getenv("CLERK_JWKS_URL")
    clerk_issuer = os.getenv("CLERK_ISSUER")

    if not clerk_jwks_url or not clerk_issuer:
        raise RuntimeError("Missing environment variable")

    clerk_config = ClerkConfig(
        jwks_url=clerk_jwks_url,
        issuer=clerk_issuer,
        verify_iss=True,
        auto_error=True
    )
    return ClerkHTTPBearer(config=clerk_config)

async def _get_clerk_credentials(request: Request) -> HTTPAuthorizationCredentials:
    return await _get_clerk_auth()(request)


"""
    此函式即可在路由中拿到解碼後的 token payload
    payload 內容可能會像：
    {
        "sub": "user_abc123",
        "email": "you@example.com",
        ...
    }
"""
async def get_current_clerk_user(
    credentials: HTTPAuthorizationCredentials = Depends(_get_clerk_credentials)
):
    if not credentials or not credentials.decoded:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials.decoded
