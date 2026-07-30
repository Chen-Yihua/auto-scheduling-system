from fastapi import APIRouter, Depends, HTTPException
from db.mongodb import db
from db.security import get_current_clerk_user
from db.crypto import decrypt_secret
from typing import List
from schemas.github import GitHubIssue
from crud.github import fetch_github_user_issues, transform_github_item

router = APIRouter(prefix="/github", tags=["github"])

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
        token = decrypt_secret(linked["apiKey"])
        raw_items = await fetch_github_user_issues(token=token)
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
