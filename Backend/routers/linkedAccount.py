from fastapi import APIRouter, HTTPException, Depends, Body, Request
from crud import linkedAccount as linkedAccount_crud
from schemas.linkedAccount import LinkedAccountCreate, LinkedAccountOut
from db.security import get_current_clerk_user
from rate_limit import limiter

router = APIRouter(prefix="/user/linked-accounts", tags=["linked-accounts"])

# 查詢目前登入者綁定帳號
@router.get("/me")
async def get_current_linked_accounts(
    clerk_user: dict = Depends(get_current_clerk_user)
):
    accounts = await linkedAccount_crud.get_linked_accounts_by_clerk_id(clerk_user["sub"])
    if not accounts:
        raise HTTPException(status_code=404, detail="No linked accounts found")
    return accounts

# 註冊（新增）綁定帳號
# 平台是 GitHub/Jira 會真的打一次驗證 API，平台是 Moodle 會真的開一次 Selenium
# 登入驗證——成本跟 /moodle/assignments 同一個等級，一起限流。
@router.post("/create")
@limiter.limit("10/minute")
async def create_linked_account(
    request: Request,
    account_data: LinkedAccountCreate,
    clerk_user: dict = Depends(get_current_clerk_user)
):
    clerk_id = clerk_user["sub"]

    new_account_response = await linkedAccount_crud.create_linked_account(
        clerk_id=clerk_id,
        account=account_data
    )
    return new_account_response


# 更新（同上，更新 Moodle 密碼一樣會觸發 Selenium 驗證）
@router.put("/")
@limiter.limit("10/minute")
async def update_linked_account(
    request: Request,
    platform: str = Body(..., embed=True),
    data: dict = Body(...),
    clerk_user: dict = Depends(get_current_clerk_user)
):
    success = await linkedAccount_crud.update_linked_account_by_clerk_id(
        clerk_user['sub'],
        platform,
        data
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

    success = await linkedAccount_crud.delete_linked_account_by_id(composite_id)
    if not success:
        raise HTTPException(status_code=404, detail="Linked account not found")
    return {"deleted": True}

