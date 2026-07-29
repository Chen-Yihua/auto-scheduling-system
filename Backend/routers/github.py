from fastapi import APIRouter, Depends, HTTPException
from db.mongodb import db
from db.security import get_current_clerk_user
from typing import List
from schemas.github import GitHubIssue, GitHubAPIRawItem
from crud.github import fetch_github_user_issues, transform_github_item

router = APIRouter(prefix="/github", tags=["github"])

# 從前端同步資料進資料庫
@router.post("/sync")
async def sync_github_issues(
    issues: List[GitHubIssue],
    clerk_user: dict = Depends(get_current_clerk_user),
):
    user_id = clerk_user["sub"]

    # 若為空資料，直接回傳成功但說明跳過
    if not issues:
        return {
            "status": "skipped",
            "reason": "Empty issue list",
            "user_id": user_id
        }

    # upsert 避免重複寫入
    inserted_count = 0

    for issue in issues:
        doc = issue.model_dump()
        doc["user_id"] = user_id

        result = await db.github_issues.update_one(
            {"id": doc["id"], "user_id": user_id},  # 唯一鍵條件
            {"$set": doc},                 # 只在找不到時插入
            upsert=True
        )

        if result.upserted_id:
            inserted_count += 1


    return {
        "status": "success",
        "inserted": inserted_count,
        "total": len(issues),
        "user_id": user_id
    }


# 後端直接從 GitHub API 抓資料並自動寫入 MongoDB
@router.get("/issues", response_model=List[GitHubIssue])
async def get_github_issues(clerk_user=Depends(get_current_clerk_user)):
    user_id = clerk_user["sub"]

    linked = await db.linkedAccounts.find_one({
        "clerk_id": user_id,
        "platform": "github"
    })

    if not linked or not linked.get("apiKey"):
        raise HTTPException(status_code=400, detail="No GitHub token linked")

    try:
        raw_items = await fetch_github_user_issues(token=linked["apiKey"])
        issues = [transform_github_item(item) for item in raw_items]

        # 自動同步到 DB
        for issue in issues:
            doc = issue
            doc["user_id"] = user_id
            await db.github_issues.update_one(
                {"id": doc["id"], "user_id": user_id},
                {"$set": doc},
                upsert=True
            )

        return issues

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
