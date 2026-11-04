import json
import logging
import os

from fastapi.concurrency import run_in_threadpool
from google import genai

from prompts.task_inference import SUBTASK_FIELD_INFERENCE_PROMPT, SUBTASK_LINE, TASK_FIELD_INFERENCE_PROMPT
from schemas.task_inference import TaskFieldInference

logger = logging.getLogger(__name__)

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

DEFAULT_PRIORITY = "Medium"
DEFAULT_DURATION_MINUTES = 60
DEFAULT_REASON = "AI 無法判斷，套用預設值"

MIN_DURATION_MINUTES = 15
MAX_DURATION_MINUTES = 480
VALID_PRIORITIES = {"High", "Medium", "Low"}

# 建立任務會等這個呼叫，逾時就用預設值
LLM_TIMEOUT_MS = 10_000


async def infer_missing_task_fields(title: str, description: str, hint: str | None = None) -> dict:
    """
    用 LLM 從標題、描述和使用者的提醒推斷 priority 和 duration，並附上理由。
    任何失敗（呼叫失敗、格式錯誤、值不合法）都回傳預設值，不讓建立任務失敗。
    """
    try:
        prompt = TASK_FIELD_INFERENCE_PROMPT.format(
            title=title,
            description=description or "（無描述）",
            hint=hint or "（無）",
        )
        response = await run_in_threadpool(
            client.models.generate_content,
            model="gemini-2.0-flash",
            contents=prompt,
            config={
                "response_mime_type": "application/json",
                "response_schema": TaskFieldInference,
                "http_options": {"timeout": LLM_TIMEOUT_MS},
            },
        )
        if not response.text:
            raise ValueError("LLM 回傳空內容")
        return _validated_inference(json.loads(response.text))

    except Exception:
        logger.warning(
            "LLM task field inference failed for title=%r, falling back to defaults",
            title,
            exc_info=True,
        )
        return _default_inference()


async def infer_missing_subtask_fields(parent_title: str, parent_description: str, subtasks: list[dict]) -> list[dict]:
    """
    一次推斷多個子任務的 priority 和 duration，參考主任務的標題和描述；回傳的順序和 subtasks 相同。
    任何失敗（含筆數不符、其中一筆的值不合法）都讓全部子任務套用預設值，不讓建立失敗。
    """
    if not subtasks:
        return []
    try:
        lines = "\n".join(
            SUBTASK_LINE.format(
                number=number,
                title=subtask["title"],
                description=subtask.get("description") or "（無描述）",
                hint=subtask.get("inference_hint") or "（無）",
            )
            for number, subtask in enumerate(subtasks, start=1)
        )
        prompt = SUBTASK_FIELD_INFERENCE_PROMPT.format(
            parent_title=parent_title,
            parent_description=parent_description or "（無描述）",
            subtasks=lines,
        )
        response = await run_in_threadpool(
            client.models.generate_content,
            model="gemini-2.0-flash",
            contents=prompt,
            config={
                "response_mime_type": "application/json",
                "response_schema": list[TaskFieldInference],
                "http_options": {"timeout": LLM_TIMEOUT_MS},
            },
        )
        if not response.text:
            raise ValueError("LLM 回傳空內容")
        parsed = json.loads(response.text)
        if not isinstance(parsed, list) or len(parsed) != len(subtasks):
            raise ValueError(f"LLM 回傳的筆數和子任務數量不符: {parsed!r}")
        return [_validated_inference(item) for item in parsed]

    except Exception:
        logger.warning(
            "LLM subtask field inference failed for parent_title=%r, falling back to defaults",
            parent_title,
            exc_info=True,
        )
        return [_default_inference() for _ in subtasks]


def _validated_inference(parsed) -> dict:
    if not isinstance(parsed, dict):
        raise ValueError(f"LLM 回傳的不是物件: {parsed!r}")
    priority = parsed.get("priority")
    duration = parsed.get("duration_minutes")
    reason = parsed.get("reason")

    if priority not in VALID_PRIORITIES:
        raise ValueError(f"LLM 回傳不合法的 priority: {priority!r}")
    if not isinstance(duration, (int, float)) or isinstance(duration, bool):
        raise ValueError(f"LLM 回傳不合法的 duration_minutes: {duration!r}")
    if not (MIN_DURATION_MINUTES <= duration <= MAX_DURATION_MINUTES):
        raise ValueError(f"LLM 回傳的 duration_minutes 超出合理範圍: {duration!r}")
    # reason 只是說明文字，不合法時不必丟掉整組結果
    if not isinstance(reason, str):
        reason = ""

    return {"priority": priority, "duration": int(duration), "reason": reason}


def _default_inference() -> dict:
    return {
        "priority": DEFAULT_PRIORITY,
        "duration": DEFAULT_DURATION_MINUTES,
        "reason": DEFAULT_REASON,
    }
