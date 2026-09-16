# Backend/db/security.py
from fastapi import Depends, HTTPException, status
from fastapi_clerk_auth import ClerkConfig, ClerkHTTPBearer, HTTPAuthorizationCredentials
import os


"""
此程式的核心邏輯：從 header 抓 token後，拿JWKs驗證，回傳decoded後的payload
"""




CLERK_JWKS_URL = os.getenv("CLERK_JWKS_URL")
CLERK_ISSUER = os.getenv("CLERK_ISSUER")

# 確認你有沒有設定這些環境變數
if not CLERK_JWKS_URL or not CLERK_ISSUER:
    raise RuntimeError("Missing environment variable")


# 建立 ClerkConfig
clerk_config = ClerkConfig(
    jwks_url=CLERK_JWKS_URL,
    issuer=CLERK_ISSUER,
    verify_iss=True,
    auto_error=True # 自動回 403 / 401，未傳或驗證失敗時
)

# 產生一個 HTTP Bearer 依賴性
clerk_auth = ClerkHTTPBearer(config=clerk_config)



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
    credentials: HTTPAuthorizationCredentials = Depends(clerk_auth)
):

    if not credentials or not credentials.decoded :
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials.decoded
