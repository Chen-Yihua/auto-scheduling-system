from fastapi import APIRouter, Depends, HTTPException
from db.security import get_current_clerk_user
from crud.moodle import get_user_account,fetch_assignments
from fastapi.concurrency import run_in_threadpool

router = APIRouter(prefix="/moodle", tags=["moodle"])

@router.get("/assignments")
async def get_assignments(clerk_user: dict = Depends(get_current_clerk_user)):
    """
    Get the assignments for the user.
    """
    user = await get_user_account(clerk_user["sub"])
    get_assignments = await run_in_threadpool(
        fetch_assignments, user["username"], user["password"]
    )    
    return get_assignments
    