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
    auto_error=True, # 自動回 403 / 401，未傳或驗證失敗時
    # 容忍一點點時間誤差（開發機時鐘飄一兩秒、網路延遲）再判斷 token
    # 是否過期／尚未生效，避免因為極小的時間差就整支擋掉。這不是拿來
    # 掩蓋真正的系統時鐘問題——如果本機時間跟實際時間差了幾分鐘以上
    # （WSL2 常見：主機睡眠喚醒後子系統時鐘沒跟著校正），這裡的 leeway
    # 蓋不住，還是要修時鐘本身。
    leeway=10,
)

# 先前為了排查「所有 API 都 403」的問題，這裡曾經暫時打開 debug_mode=True，
# 讓 fastapi_clerk_auth 平常會吞掉的驗證例外重新丟出來（見 git 記錄）。
# 已經確認根本原因是 WSL2 系統時鐘漂移，導致 Clerk token 的 iat
# （簽發時間）看起來還在「未來」，驗證失敗——不是這裡的程式邏輯有問題，
# 所以已經改回預設的 debug_mode=False，避免正式環境把內部例外細節
# 洩漏在錯誤回應裡。
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
