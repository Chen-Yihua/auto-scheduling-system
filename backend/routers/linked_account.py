from typing import List
from fastapi import APIRouter, HTTPException, Depends, Request
from crud import linked_account as linked_account_crud
from schemas.linked_account import LinkedAccountCreate, LinkedAccountOut, LinkedAccountUpdate
from core.security import get_current_clerk_user
from core.rate_limit import limiter

# 綁定帳號是「目前登入者」底下的資源，掛在 /users/me 底下，跟 routers/user.py 的 /users/me 一致
router = APIRouter(prefix="/users/me/linked-accounts", tags=["linked-accounts"])

# 查詢目前登入者綁定帳號
@router.get("/", response_model=List[LinkedAccountOut])
async def get_current_linked_accounts(
    clerk_user: dict = Depends(get_current_clerk_user)
):
    # 沒有任何綁定帳號是正常狀態（例如剛註冊、還沒連結任何平台），crud 會回空清單，
    # 這裡原樣回傳成 200 + 空陣列，不是 404
    return await linked_account_crud.get_linked_accounts_by_clerk_id(clerk_user["sub"])

# 註冊（新增）綁定帳號
# 平台是 GitHub/Jira 會真的打一次驗證 API，平台是 Moodle 會真的開一次 Selenium
# 登入驗證——成本跟 /moodle/assignments 同一個等級，一起限流。
@router.post("/")
@limiter.limit("10/minute")
async def create_linked_account(
    request: Request,
    account_data: LinkedAccountCreate,
    clerk_user: dict = Depends(get_current_clerk_user)
):
    clerk_id = clerk_user["sub"]

    new_account_response = await linked_account_crud.create_linked_account(
        clerk_id=clerk_id,
        account=account_data
    )
    return new_account_response


# 部分更新（只送要改的欄位，例如 {"apiKey": "..."}），所以是 PATCH；
# 更新 Moodle 密碼一樣會觸發 Selenium 驗證
@router.patch("/{platform}")
@limiter.limit("10/minute")
async def update_linked_account(
    request: Request,
    platform: str,
    data: LinkedAccountUpdate,
    clerk_user: dict = Depends(get_current_clerk_user)
):
    success = await linked_account_crud.update_linked_account_by_clerk_id(
        clerk_user['sub'],
        platform,
        data.model_dump(exclude_none=True)
    )
    if not success:
        raise HTTPException(status_code=404, detail="Linked account not found or no valid fields to update")
    return {"success": True}


# 刪除資料
@router.delete("/{platform}")
async def delete_linked_account(
    platform: str,
    clerk_user: dict = Depends(get_current_clerk_user)
):
    clerk_id = clerk_user["sub"]
    composite_id = f"{clerk_id}_{platform}"

    await linked_account_crud.delete_linked_account_by_id(composite_id) # 查無此帳號由 crud 直接 raise 404
    return {"deleted": True}

