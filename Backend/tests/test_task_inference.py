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
