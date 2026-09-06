import json
import pytest
from unittest.mock import MagicMock

import crud.task_inference as task_inference


def _mock_response(payload: dict):
    return MagicMock(text=json.dumps(payload))


@pytest.mark.asyncio
async def test_infer_missing_task_fields_success(monkeypatch):
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
    captured = {}

    def fake_generate_content(**kwargs):
        captured["prompt"] = kwargs["contents"]
        return _mock_response({"priority": "High", "duration_minutes": 90, "reason": "..."})

    monkeypatch.setattr(task_inference.client.models, "generate_content", fake_generate_content)

    await task_inference.infer_missing_task_fields("期末報告", "整理資料並簡報", hint=None)

    assert "使用者給的提醒：（無）" in captured["prompt"]


@pytest.mark.asyncio
async def test_infer_missing_task_fields_falls_back_on_invalid_priority(monkeypatch):
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
    def raise_error(**kwargs):
        raise Exception("Gemini API down")

    monkeypatch.setattr(task_inference.client.models, "generate_content", raise_error)

    result = await task_inference.infer_missing_task_fields("任務", "描述")

    assert result["priority"] == task_inference.DEFAULT_PRIORITY
    assert result["duration"] == task_inference.DEFAULT_DURATION_MINUTES
    assert result["reason"] == task_inference.DEFAULT_REASON
