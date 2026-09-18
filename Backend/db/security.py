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

# 暫時性診斷開關：fastapi_clerk_auth 預設會把驗證過程中的任何例外
# （JWKS 抓不到、token 過期、issuer 不符、簽章錯誤…）都吞掉，一律回覆
# 同一句「403 Forbidden」，完全看不出真正原因。開了 debug_mode 之後，
# 這個例外會被重新丟出來（會變成 500，但後端終端機會印出完整 traceback），
# 幫助我們找到 403 backlog 的根本原因。問題排除後記得改回 False，
# 避免正式環境把內部例外細節洩漏在錯誤回應裡。
clerk_auth = ClerkHTTPBearer(config=clerk_config, debug_mode=True)



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
