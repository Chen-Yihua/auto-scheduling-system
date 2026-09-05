import json
import logging
import os

from fastapi.concurrency import run_in_threadpool
from google import genai

from constants.task_inference_prompt import TASK_FIELD_INFERENCE_PROMPT

logger = logging.getLogger(__name__)

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

DEFAULT_PRIORITY = "Medium"
DEFAULT_DURATION_MINUTES = 60
DEFAULT_REASON = "AI 無法判斷，套用預設值"

MIN_DURATION_MINUTES = 15
MAX_DURATION_MINUTES = 480
VALID_PRIORITIES = {"High", "Medium", "Low"}


async def infer_missing_task_fields(title: str, description: str) -> dict:
    """
    使用者建立任務時沒填 priority/duration，用 LLM 從標題/描述推斷合理值並附理由。

    這裡 LLM 的影響範圍鎖死在兩個純量欄位（不牽涉時段分配），
    所以驗證很單純：priority 是不是合法的三選一、duration 是不是落在合理範圍。
    不管是 LLM 呼叫失敗、回傳格式錯誤、還是驗證沒過，都直接退回固定預設值，
    絕不讓「建立任務」這個動作因為 LLM 出狀況而失敗。
    """
    try:
        prompt = TASK_FIELD_INFERENCE_PROMPT.format(
            title=title,
            description=description or "（無描述）",
        )
        response = await run_in_threadpool(
            client.models.generate_content,
            model="gemini-2.0-flash",
            contents=prompt,
            config={"response_mime_type": "application/json"},
        )
        parsed = json.loads(response.text)

        priority = parsed.get("priority")
        duration = parsed.get("duration_minutes")
        reason = parsed.get("reason") or ""

        if priority not in VALID_PRIORITIES:
            raise ValueError(f"LLM 回傳不合法的 priority: {priority!r}")
        if not isinstance(duration, (int, float)) or isinstance(duration, bool):
            raise ValueError(f"LLM 回傳不合法的 duration_minutes: {duration!r}")
        if not (MIN_DURATION_MINUTES <= duration <= MAX_DURATION_MINUTES):
            raise ValueError(f"LLM 回傳的 duration_minutes 超出合理範圍: {duration!r}")

        return {"priority": priority, "duration": int(duration), "reason": reason}

    except Exception:
        logger.warning(
            "LLM task field inference failed for title=%r, falling back to defaults",
            title,
            exc_info=True,
        )
        return {
            "priority": DEFAULT_PRIORITY,
            "duration": DEFAULT_DURATION_MINUTES,
            "reason": DEFAULT_REASON,
        }
