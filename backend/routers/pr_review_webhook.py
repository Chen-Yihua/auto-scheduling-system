import hashlib
import hmac
import json
import logging
from fastapi import APIRouter, Header, HTTPException, Request
import os
import httpx
from google import genai
from prompts.pr_review import GEMINI_PR_SUMMARY_PROMPT
from platforms.github import GITHUB_API_VERSION
from schemas.review import ReviewSummary
from core.rate_limit import limiter

logger = logging.getLogger(__name__)

router = APIRouter()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# PR 摘要用的 webhook（貼在 open PR 的當下）、merge 到 main 通知用的 webhook，
# 兩組都不該寫死在程式碼裡——沒設定就直接跳過發送，不影響其餘邏輯。
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_MR_WEBHOOK_URL")
MAIN_WEBHOOK_URL = os.getenv("DISCORD_MAIN_WEBHOOK_URL")

# 呼叫 GitHub REST API（讀 PR 變更檔案、貼留言）用的機器人帳號 token，
# 跟使用者自己連結 GitHub 帳號用的 apiKey（crud/linked_account.py）是不同東西，
# 這個是伺服器自己的、專門給這支 bot 用的 token。
GITHUB_BOT_TOKEN = os.getenv("GITHUB_BOT_TOKEN")

# GitHub 呼叫 webhook 時會用這組密鑰對整個 request body 做 HMAC-SHA256 簽章，
# 簽章結果放在 X-Hub-Signature-256 header，用來確認請求真的是 GitHub 發的。
GITHUB_WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET")

LLM_TIMEOUT_MS = 30_000

# Discord embed 的長度上限：超過的話 Discord 會整筆拒收（回 400），不是自動截斷
DISCORD_DESCRIPTION_LIMIT = 4096
DISCORD_FIELD_LIMIT = 1024
DISCORD_TIMEOUT_SECONDS = 10
GITHUB_TIMEOUT_SECONDS = 10


def _truncate(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


async def _send_discord(url: str, message: dict) -> None:
    """
    Discord 通知只是附加功能，失敗不影響 webhook 其餘流程，但一定要留下 log——
    之前沒檢查回應，Discord 回 400 時會完全無聲地失敗。
    """
    try:
        async with httpx.AsyncClient(timeout=DISCORD_TIMEOUT_SECONDS) as http:
            res = await http.post(url, json=message)
        res.raise_for_status()
    except httpx.HTTPError:
        logger.exception("Failed to send Discord notification")


def _verify_github_signature(raw_body: bytes, signature: str | None) -> None:
    """
    沒設定密鑰就直接全部拒絕——避免忘記設定時，變成完全沒有保護。
    用 hmac.compare_digest 而不是 == 比對，避免 timing attack。
    """
    if not GITHUB_WEBHOOK_SECRET or not signature:
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    expected = "sha256=" + hmac.new(
        GITHUB_WEBHOOK_SECRET.encode(), raw_body, hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")


# 簽章驗證擋掉了非 GitHub 的請求，但簽章正確的請求短時間內狂送還是會一直觸發
# Gemini 呼叫，這裡再加一層頻率限制當第二道防線
@router.post("/webhook")
@limiter.limit("30/minute")
async def github_webhook(
    request: Request,
    x_hub_signature_256: str | None = Header(default=None, alias="X-Hub-Signature-256"),
    x_github_event: str | None = Header(default=None, alias="X-GitHub-Event"),
):
    raw_body = await request.body()
    _verify_github_signature(raw_body, x_hub_signature_256)
    payload = json.loads(raw_body)

    if x_github_event != "pull_request":
        # 不是 PR 事件（例如 GitHub 設定 webhook 當下送的 ping）就不用處理
        return {"status": "ok"}

    pr = payload["pull_request"]
    action = payload.get("action")
    repo = payload["repository"]["full_name"]
    pr_number = pr["number"]
    headers = {
        "Authorization": f"Bearer {GITHUB_BOT_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": GITHUB_API_VERSION,
    }

    if action == "opened":
        title = pr["title"]
        description = pr.get("body") or ""

        try:
            files_url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}/files"
            async with httpx.AsyncClient(timeout=GITHUB_TIMEOUT_SECONDS) as http:
                res = await http.get(files_url, headers=headers)
            res.raise_for_status()
            files = res.json()
            file_tree = "\n".join(f"- {f['filename']}" for f in files)
        except Exception:
            file_tree = "（無法取得變更檔案）"

        prompt = GEMINI_PR_SUMMARY_PROMPT.format(
            title=title,
            description=description,
            file_tree=file_tree
        )

        summary = None
        try:
            response = await client.aio.models.generate_content(
                contents=prompt,
                model="gemini-2.0-flash",
                config={
                    "response_mime_type": "application/json",
                    "response_schema": ReviewSummary,
                    "http_options": {"timeout": LLM_TIMEOUT_MS},
                }
            )
            # 用 ReviewSummary 再驗證一次：少了 summary、欄位型別不對都會在這裡拋例外
            summary = ReviewSummary.model_validate_json(response.text)
        except Exception:
            # 例外細節（可能含內部路徑、API 回應內容）只寫進 log，絕不貼到公開的 PR 留言
            logger.exception("Gemini PR summary generation failed for repo=%s pr_number=%s", repo, pr_number)

        if summary is None:
            body = "⚠️ 自動摘要產生失敗，請人工確認此次變更內容。"
        else:
            body = f"""
### 摘要：
{summary.summary or '（無法取得摘要）'}

### 🧩 前端改動：
{summary.frontend or '（無）'}

### 🧠 後端改動：
{summary.backend or '（無）'}

### 🧹 重構建議：
{summary.refactor or '（無）'}
            """

            # Discord 發送失敗只影響 Discord 通知，不能連帶讓 PR 留言變成「摘要產生失敗」
            if DISCORD_WEBHOOK_URL:
                embed = {
                    "title": f"Pull Request #{pr_number} 摘要",
                    "description": _truncate(summary.summary or "（無法取得摘要）", DISCORD_DESCRIPTION_LIMIT),
                    "fields": [
                        {"name": "🧩 前端建議", "value": _truncate(summary.frontend or "（無）", DISCORD_FIELD_LIMIT), "inline": False},
                        {"name": "🧠 後端建議", "value": _truncate(summary.backend or "（無）", DISCORD_FIELD_LIMIT), "inline": False},
                        {"name": "🧹 重構建議", "value": _truncate(summary.refactor or "（無）", DISCORD_FIELD_LIMIT), "inline": False},
                    ],
                    "color": 0x1E90FF,
                }
                await _send_discord(DISCORD_WEBHOOK_URL, {"embeds": [embed]})

        comment_url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
        async with httpx.AsyncClient(timeout=GITHUB_TIMEOUT_SECONDS) as http:
            await http.post(
                comment_url,
                headers=headers,
                json={"body": body}
            )

    if action == "closed" and pr.get("merged") and pr["base"]["ref"] == "main":
        pr_title = pr["title"]
        pr_url = pr["html_url"]
        author_name = pr["user"]["login"]
        commit_count = pr.get("commits", "未知")
        merged_at = pr.get("merged_at") or ""

        embed = {
            "title": "✅ Merge to `main` 完成",
            "description": f"**{pr_title}**",
            "url": pr_url,
            "color": 0x00C853,
            "fields": [
                {"name": "🧑‍💻 作者", "value": author_name, "inline": True},
                {"name": "🧾 Commit 數量", "value": str(commit_count), "inline": True},
                {"name": "🕒 時間", "value": merged_at.replace("T", " ").replace("Z", ""), "inline": False},
            ],
            "footer": {"text": "Gemini Bot - 自動合併通知"}
        }

        if MAIN_WEBHOOK_URL:
            await _send_discord(MAIN_WEBHOOK_URL, {"embeds": [embed]})

    return {"status": "ok"}
