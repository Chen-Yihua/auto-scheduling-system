from fastapi import APIRouter, Request
import os
import requests
from google import genai
from constants.webhook_prompt import GEMINI_MR_SUMMARY_PROMPT
from schemas.review import ReviewSummary

router = APIRouter()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1367067918235340811/-Fap87RJ3peFhC-3I7jT9GiNNtHUtH4A3wEeCCr4qYou01Qa4waUb_AG647p25Ylakx5"
MAIN_WEBHOOK_URL = "https://discord.com/api/webhooks/1367070901400764446/DgoC4ookwtHJTiMg7XWAWi6nGUlDTf9YEqmxyYE-647LEm1l_Pt4OI8i6gPWVaCM6e1G"

@router.post("/webhook")
async def gitlab_webhook(request: Request):
    payload = await request.json()

    if payload.get("object_kind") == "merge_request" and payload["object_attributes"]["action"] == "open":
        title = payload["object_attributes"]["title"]
        description = payload["object_attributes"]["description"]
        project_id = payload["project"]["id"]
        mr_iid = payload["object_attributes"]["iid"]

        GITLAB_TOKEN = os.getenv("GITLAB_TOKEN")

        try:
            change_url = f"https://gitlab.com/api/v4/projects/{project_id}/merge_requests/{mr_iid}/changes"
            headers = {"PRIVATE-TOKEN": GITLAB_TOKEN}
            res = requests.get(change_url, headers=headers)
            changes = res.json().get("changes", [])
            file_tree = "\n".join(f"- {f['new_path']}" for f in changes)
        except Exception:
            file_tree = "（無法取得變更檔案）"

        prompt = GEMINI_MR_SUMMARY_PROMPT.format(
            title=title,
            description=description,
            file_tree=file_tree
        )

        try:
            response = client.models.generate_content(
                contents=prompt,
                model="gemini-2.0-flash",
                config={
                    "response_mime_type": "application/json",
                    "response_schema": ReviewSummary,
                }
            )
            import json
            parsed = json.loads(response.text)
            
            body = f"""
### ✅ 摘要：
{parsed.get('summary', '（無法取得摘要）')}

### 🧩 前端改動：
{parsed.get('frontend', '（無）')}

### 🧠 後端改動：
{parsed.get('backend', '（無）')}

### 🧹 重構建議：
{parsed.get('refactor', '（無）')}
            """

             # === 發送 Discord Embed ===
            embed = {
                "title": f"Merge Request !{mr_iid} 摘要",
                "description": parsed.get("summary", "（無法取得摘要）"),
                "fields": [
                    {"name": "🧩 前端建議", "value": parsed.get("frontend") or "（無）", "inline": False},
                    {"name": "🧠 後端建議", "value": parsed.get("backend") or "（無）", "inline": False},
                    {"name": "🧹 重構建議", "value": parsed.get("refactor") or "（無）", "inline": False},
                ],
                "color": 0x1E90FF,
            }
            requests.post(DISCORD_WEBHOOK_URL, json={"embeds": [embed]})

        except Exception as e:
            body = f"❌ Gemini 回傳失敗：{str(e)}"

        comment_url = f"https://gitlab.com/api/v4/projects/{project_id}/merge_requests/{mr_iid}/notes"
        requests.post(
            comment_url,
            headers=headers,
            json={"body": body}
        )

    if payload.get("object_kind") == "merge_request":
        action = payload["object_attributes"]["action"]
        target_branch = payload["object_attributes"]["target_branch"]

        if action == "merge" and target_branch == "main":
            mr_title = payload["object_attributes"]["title"]
            mr_url = payload["object_attributes"]["url"]
            author_name = payload["user"]["name"]
            commit_count = payload["object_attributes"].get("commits_count", "未知")
            merged_at = payload["object_attributes"]["updated_at"]

            embed = {
                "title": "✅ Merge to `main` 完成",
                "description": f"**{mr_title}**",
                "url": mr_url,
                "color": 0x00C853,
                "fields": [
                    {"name": "🧑‍💻 作者", "value": author_name, "inline": True},
                    {"name": "🧾 Commit 數量", "value": str(commit_count), "inline": True},
                    {"name": "🕒 時間", "value": merged_at.replace("T", " ").replace("Z", ""), "inline": False},
                ],
                "footer": {"text": "Gemini Bot - 自動合併通知"}
            }

            message = {"embeds": [embed]}
            requests.post(MAIN_WEBHOOK_URL, json=message)


    return {"status": "ok"}