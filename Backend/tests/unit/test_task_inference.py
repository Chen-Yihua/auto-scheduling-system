import json
import pytest
from unittest.mock import MagicMock

import crud.task_inference as task_inference


def _mock_response(payload: dict):
    return MagicMock(text=json.dumps(payload))


@pytest.mark.asyncio
async def test_infer_missing_task_fields_success(monkeypatch):
    """LLM 回傳合法結果 → 採用它給的優先度、時長和理由。"""
    monkeypatch.setattr(
        task_inference.client.models,
        "generate_content",
        lambda **kwargs: _mock_response({
            "priority": "High",
            "duration_minutes": 90,
            "reason": "報告類任務通常需要較長時間準備",
        }),
    )

    result = await task_inference.infer_missing_task_fields("期末報告", "整理資料並簡報")

    assert result["priority"] == "High"
    assert result["duration"] == 90
    assert result["reason"] == "報告類任務通常需要較長時間準備"


@pytest.mark.asyncio
async def test_infer_missing_task_fields_includes_hint_in_prompt(monkeypatch):
    """使用者給的提醒（hint）要放進送給 LLM 的 prompt。"""
    captured = {}

    def fake_generate_content(**kwargs):
        captured["prompt"] = kwargs["contents"]
        return _mock_response({"priority": "High", "duration_minutes": 90, "reason": "..."})

    monkeypatch.setattr(task_inference.client.models, "generate_content", fake_generate_content)

    await task_inference.infer_missing_task_fields(
        "期末報告", "整理資料並簡報", hint="這比想像中難，可能要抓長一點"
    )

    assert "這比想像中難，可能要抓長一點" in captured["prompt"]


@pytest.mark.asyncio
async def test_infer_missing_task_fields_uses_placeholder_when_no_hint(monkeypatch):
    """沒有提醒時，prompt 要寫「使用者給的提醒：（無）」，不能留空或出現 None。"""
    captured = {}

    def fake_generate_content(**kwargs):
        captured["prompt"] = kwargs["contents"]
        return _mock_response({"priority": "High", "duration_minutes": 90, "reason": "..."})

    monkeypatch.setattr(task_inference.client.models, "generate_content", fake_generate_content)

    await task_inference.infer_missing_task_fields("期末報告", "整理資料並簡報", hint=None)

    assert "使用者給的提醒：（無）" in captured["prompt"]


@pytest.mark.asyncio
async def test_infer_missing_task_fields_falls_back_on_invalid_priority(monkeypatch):
    """LLM 回了不在 High/Medium/Low 內的優先度 → 整組退回預設值，不採用亂掉的結果。"""
    monkeypatch.setattr(
        task_inference.client.models,
        "generate_content",
        lambda **kwargs: _mock_response({"priority": "Urgent!!", "duration_minutes": 90, "reason": "..."}),
    )

    result = await task_inference.infer_missing_task_fields("任務", "描述")

    assert result["priority"] == task_inference.DEFAULT_PRIORITY
    assert result["duration"] == task_inference.DEFAULT_DURATION_MINUTES
    assert result["reason"] == task_inference.DEFAULT_REASON


@pytest.mark.asyncio
async def test_infer_missing_task_fields_falls_back_on_out_of_range_duration(monkeypatch):
    """LLM 回的時長超出合理範圍（9999 分鐘）→ 退回預設值。"""
    monkeypatch.setattr(
        task_inference.client.models,
        "generate_content",
        lambda **kwargs: _mock_response({"priority": "Low", "duration_minutes": 9999, "reason": "..."}),
    )

    result = await task_inference.infer_missing_task_fields("任務", "描述")

    assert result["priority"] == task_inference.DEFAULT_PRIORITY
    assert result["duration"] == task_inference.DEFAULT_DURATION_MINUTES


@pytest.mark.asyncio
async def test_infer_missing_task_fields_falls_back_on_non_numeric_duration(monkeypatch):
    """LLM 回的時長不是數字（「大概兩小時吧」）→ 退回預設值。"""
    monkeypatch.setattr(
        task_inference.client.models,
        "generate_content",
        lambda **kwargs: _mock_response({"priority": "Low", "duration_minutes": "大概兩小時吧", "reason": "..."}),
    )

    result = await task_inference.infer_missing_task_fields("任務", "描述")

    assert result["priority"] == task_inference.DEFAULT_PRIORITY
    assert result["duration"] == task_inference.DEFAULT_DURATION_MINUTES


@pytest.mark.asyncio
async def test_infer_missing_task_fields_falls_back_on_malformed_json(monkeypatch):
    """LLM 回的不是合法 JSON → 退回預設值，不能讓建立任務失敗。"""
    monkeypatch.setattr(
        task_inference.client.models,
        "generate_content",
        lambda **kwargs: MagicMock(text="這不是 JSON"),
    )

    result = await task_inference.infer_missing_task_fields("任務", "描述")

    assert result["priority"] == task_inference.DEFAULT_PRIORITY
    assert result["duration"] == task_inference.DEFAULT_DURATION_MINUTES


@pytest.mark.asyncio
async def test_infer_missing_task_fields_falls_back_on_api_exception(monkeypatch):
    """LLM 服務出錯（例如服務掛了）→ 退回預設值；推斷是輔助功能，不能因為它壞掉就擋住使用者建立任務。"""
    def raise_error(**kwargs):
        raise Exception("Gemini API down")

    monkeypatch.setattr(task_inference.client.models, "generate_content", raise_error)

    result = await task_inference.infer_missing_task_fields("任務", "描述")

    assert result["priority"] == task_inference.DEFAULT_PRIORITY
    assert result["duration"] == task_inference.DEFAULT_DURATION_MINUTES
    assert result["reason"] == task_inference.DEFAULT_REASON
