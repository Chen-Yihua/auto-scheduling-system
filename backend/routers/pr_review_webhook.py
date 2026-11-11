import hashlib
import hmac
import json
import logging
from fastapi import APIRouter, Header, Request
import os
import httpx
from google import genai
from prompts.pr_review import GEMINI_PR_SUMMARY_PROMPT
from platforms.github import GITHUB_API_VERSION
from schemas.review import ReviewSummary
from core.rate_limit import limiter
from core.errors import AppError, ExternalServiceError, InvalidRequestError

logger = logging.getLogger(__name__)

router = APIRouter()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# 沒設定就略過對應的 Discord 通知
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_MR_WEBHOOK_URL")
MAIN_WEBHOOK_URL = os.getenv("DISCORD_MAIN_WEBHOOK_URL")

# bot 自己的 token，用來讀 PR 變更檔案和貼留言；跟使用者連結的 GitHub apiKey 無關
GITHUB_BOT_TOKEN = os.getenv("GITHUB_BOT_TOKEN")

# 驗證 X-Hub-Signature-256（request body 的 HMAC-SHA256），確認請求來自 GitHub
GITHUB_WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET")
if not GITHUB_WEBHOOK_SECRET:
    # 啟動時記一次就好，請求時不再記，否則每個 webhook 請求都會多一筆 error
    logger.error("GITHUB_WEBHOOK_SECRET 未設定，GitHub webhook 會一律拒絕")

LLM_TIMEOUT_MS = 30_000

# Discord embed 長度上限：超過會整筆被拒收（400），不會自動截斷
DISCORD_DESCRIPTION_LIMIT = 4096
DISCORD_FIELD_LIMIT = 1024
DISCORD_TIMEOUT_SECONDS = 10
GITHUB_TIMEOUT_SECONDS = 10


def _truncate(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


async def _send_discord(url: str, message: dict) -> None:
    """發送失敗只記 log，不影響 webhook 其餘流程。"""
    try:
        async with httpx.AsyncClient(timeout=DISCORD_TIMEOUT_SECONDS) as http:
            res = await http.post(url, json=message)
        res.raise_for_status()
    except httpx.HTTPError:
        logger.exception("Failed to send Discord notification")


def _invalid_signature() -> AppError:
    # 沒設定密鑰也用這個 code（對照表 401，ADR 0011「例外」）：回 500 會讓外部知道伺服器漏了設定
    return AppError("Invalid webhook signature", error_code="INVALID_WEBHOOK_SIGNATURE")


def _invalid_payload() -> InvalidRequestError:
    return InvalidRequestError("webhook payload 格式錯誤")


def _verify_github_signature(raw_body: bytes, signature: str | None) -> None:
    """沒設定密鑰時一律拒絕，避免漏設時完全沒有保護；用 compare_digest 防 timing attack。"""
    if not GITHUB_WEBHOOK_SECRET or not signature:
        raise _invalid_signature()

    expected = "sha256=" + hmac.new(
        GITHUB_WEBHOOK_SECRET.encode(), raw_body, hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise _invalid_signature()


# 簽章正確的請求大量送來仍會一直呼叫 Gemini，所以再加限流
@router.post("/webhook")
@limiter.limit("30/minute")
async def github_webhook(
    request: Request,
    x_hub_signature_256: str | None = Header(default=None, alias="X-Hub-Signature-256"),
    x_github_event: str | None = Header(default=None, alias="X-GitHub-Event"),
):
    raw_body = await request.body()
    _verify_github_signature(raw_body, x_hub_signature_256)
    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        raise _invalid_payload()

    if x_github_event != "pull_request":
        # 例如設定 webhook 時 GitHub 送的 ping
        return {"status": "ok"}

    try:
        pr = payload["pull_request"]
        action = payload.get("action")
        repo = payload["repository"]["full_name"]
        pr_number = pr["number"]
    except (KeyError, TypeError, AttributeError):
        raise _invalid_payload()
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
            if not response.text:
                raise ValueError("Gemini 回傳空內容")
            summary = ReviewSummary.model_validate_json(response.text)
        except Exception:
            # 例外細節只寫進 log，不能出現在公開的 PR 留言
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

            # Discord 失敗不能讓 PR 留言變成「摘要產生失敗」
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
        try:
            async with httpx.AsyncClient(timeout=GITHUB_TIMEOUT_SECONDS) as http:
                await http.post(
                    comment_url,
                    headers=headers,
                    json={"body": body}
                )
        except httpx.TimeoutException:
            logger.exception("貼 PR 留言逾時 repo=%s pr_number=%s", repo, pr_number)
            raise ExternalServiceError("GitHub 回應逾時", error_code="UPSTREAM_TIMEOUT")
        except httpx.RequestError:
            logger.exception("貼 PR 留言時連不上 GitHub repo=%s pr_number=%s", repo, pr_number)
            raise ExternalServiceError("無法連線至 GitHub")

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
