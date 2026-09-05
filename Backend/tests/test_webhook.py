import hashlib
import hmac
import json
import pytest
from fastapi import HTTPException
from unittest.mock import MagicMock

import routers.webhook as webhook_router


class FakeRequest:
    """github_webhook 只用到 request.body()，用一個假 Request 就夠了。"""
    def __init__(self, payload: dict):
        self._raw = json.dumps(payload).encode()

    async def body(self):
        return self._raw


def _sign(secret: str, raw_body: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()


def _pr_payload(action, merged=False, base_ref="main"):
    return {
        "action": action,
        "pull_request": {
            "number": 42,
            "title": "Fix bug",
            "body": "desc",
            "html_url": "https://github.com/owner/repo/pull/42",
            "merged": merged,
            "merged_at": "2024-01-01T00:00:00Z",
            "commits": 3,
            "user": {"login": "alice"},
            "base": {"ref": base_ref},
        },
        "repository": {"full_name": "owner/repo"},
    }


def _mock_gemini_response(monkeypatch):
    fake_response = MagicMock()
    fake_response.text = json.dumps(
        {"summary": "摘要", "frontend": None, "backend": None, "refactor": None}
    )
    monkeypatch.setattr(webhook_router.client.models, "generate_content", lambda **kwargs: fake_response)


async def _call_webhook(monkeypatch, payload, secret="test-secret", event="pull_request"):
    monkeypatch.setattr(webhook_router, "GITHUB_WEBHOOK_SECRET", secret)
    request = FakeRequest(payload)
    raw_body = await request.body()
    signature = _sign(secret, raw_body) if secret else None
    return await webhook_router.github_webhook(
        request, x_hub_signature_256=signature, x_github_event=event
    )


# ========== open PR：貼 PR 摘要用的 Discord webhook ==========

@pytest.mark.asyncio
async def test_open_pr_posts_to_configured_mr_webhook(monkeypatch):
    monkeypatch.setattr(webhook_router, "DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/test/mr")
    monkeypatch.setattr(webhook_router, "MAIN_WEBHOOK_URL", None)
    monkeypatch.setenv("GITHUB_BOT_TOKEN", "dummy")

    posted_urls = []
    monkeypatch.setattr(webhook_router.requests, "get", lambda *a, **k: MagicMock(json=lambda: [{"filename": "app.py"}]))
    monkeypatch.setattr(webhook_router.requests, "post", lambda url, **k: posted_urls.append(url))
    _mock_gemini_response(monkeypatch)

    await _call_webhook(monkeypatch, _pr_payload("opened"))

    assert "https://discord.com/api/webhooks/test/mr" in posted_urls


@pytest.mark.asyncio
async def test_open_pr_skips_discord_when_webhook_not_configured(monkeypatch):
    monkeypatch.setattr(webhook_router, "DISCORD_WEBHOOK_URL", None)
    monkeypatch.setattr(webhook_router, "MAIN_WEBHOOK_URL", None)
    monkeypatch.setenv("GITHUB_BOT_TOKEN", "dummy")

    posted_urls = []
    monkeypatch.setattr(webhook_router.requests, "get", lambda *a, **k: MagicMock(json=lambda: [{"filename": "app.py"}]))
    monkeypatch.setattr(webhook_router.requests, "post", lambda url, **k: posted_urls.append(url))
    _mock_gemini_response(monkeypatch)

    await _call_webhook(monkeypatch, _pr_payload("opened"))

    # 沒設定 webhook 網址就不該對任何 discord.com 網址發送
    assert not any("discord.com" in url for url in posted_urls)


# ========== merge 到 main：合併通知用的 Discord webhook ==========

@pytest.mark.asyncio
async def test_merge_to_main_posts_to_configured_main_webhook(monkeypatch):
    monkeypatch.setattr(webhook_router, "DISCORD_WEBHOOK_URL", None)
    monkeypatch.setattr(webhook_router, "MAIN_WEBHOOK_URL", "https://discord.com/api/webhooks/test/main")

    posted = []
    monkeypatch.setattr(webhook_router.requests, "post", lambda url, **k: posted.append((url, k)))

    await _call_webhook(monkeypatch, _pr_payload("closed", merged=True, base_ref="main"))

    assert len(posted) == 1
    assert posted[0][0] == "https://discord.com/api/webhooks/test/main"


@pytest.mark.asyncio
async def test_merge_to_main_skips_discord_when_webhook_not_configured(monkeypatch):
    monkeypatch.setattr(webhook_router, "DISCORD_WEBHOOK_URL", None)
    monkeypatch.setattr(webhook_router, "MAIN_WEBHOOK_URL", None)

    posted = []
    monkeypatch.setattr(webhook_router.requests, "post", lambda url, **k: posted.append(url))

    await _call_webhook(monkeypatch, _pr_payload("closed", merged=True, base_ref="main"))

    assert posted == []


@pytest.mark.asyncio
async def test_closed_but_not_merged_does_not_post_merge_notification(monkeypatch):
    monkeypatch.setattr(webhook_router, "DISCORD_WEBHOOK_URL", None)
    monkeypatch.setattr(webhook_router, "MAIN_WEBHOOK_URL", "https://discord.com/api/webhooks/test/main")

    posted = []
    monkeypatch.setattr(webhook_router.requests, "post", lambda url, **k: posted.append(url))

    # PR 被關掉但沒有 merge
    await _call_webhook(monkeypatch, _pr_payload("closed", merged=False, base_ref="main"))

    assert posted == []


@pytest.mark.asyncio
async def test_no_hardcoded_discord_url_left_in_source():
    import inspect
    source = inspect.getsource(webhook_router)
    assert "discord.com/api/webhooks/" not in source


# ========== Gemini 失敗時，例外細節不該外洩到公開的 PR 留言 ==========

@pytest.mark.asyncio
async def test_gemini_failure_does_not_leak_exception_detail_to_public_comment(monkeypatch, caplog):
    monkeypatch.setattr(webhook_router, "DISCORD_WEBHOOK_URL", None)
    monkeypatch.setattr(webhook_router, "MAIN_WEBHOOK_URL", None)
    monkeypatch.setenv("GITHUB_BOT_TOKEN", "dummy")

    monkeypatch.setattr(webhook_router.requests, "get", lambda *a, **k: MagicMock(json=lambda: [{"filename": "app.py"}]))

    posted_comments = []

    def fake_post(url, **kwargs):
        if "/comments" in url:
            posted_comments.append(kwargs.get("json", {}).get("body", ""))
        return MagicMock()

    monkeypatch.setattr(webhook_router.requests, "post", fake_post)

    secret_detail = "internal database connection string leaked: mongodb://user:pass@10.0.0.5"

    def fake_generate_content(**kwargs):
        raise Exception(secret_detail)

    monkeypatch.setattr(webhook_router.client.models, "generate_content", fake_generate_content)

    import logging
    with caplog.at_level(logging.ERROR, logger="routers.webhook"):
        await _call_webhook(monkeypatch, _pr_payload("opened"))

    assert len(posted_comments) == 1
    # 公開留言絕對不能出現例外訊息的內容
    assert secret_detail not in posted_comments[0]
    assert "無法" in posted_comments[0] or "失敗" in posted_comments[0]

    # 但完整的例外細節要留在後端 log，方便事後排查
    assert any(secret_detail in record.getMessage() or record.exc_info for record in caplog.records)


# ========== /webhook 必須驗證 X-Hub-Signature-256，不是誰都能打 ==========

@pytest.mark.asyncio
async def test_webhook_rejects_missing_signature(monkeypatch):
    monkeypatch.setattr(webhook_router, "GITHUB_WEBHOOK_SECRET", "correct-secret")
    request = FakeRequest(_pr_payload("opened"))

    with pytest.raises(HTTPException) as exc_info:
        await webhook_router.github_webhook(request, x_hub_signature_256=None, x_github_event="pull_request")

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_webhook_rejects_wrong_signature(monkeypatch):
    monkeypatch.setattr(webhook_router, "GITHUB_WEBHOOK_SECRET", "correct-secret")
    request = FakeRequest(_pr_payload("opened"))
    wrong_signature = _sign("wrong-secret", await request.body())

    with pytest.raises(HTTPException) as exc_info:
        await webhook_router.github_webhook(
            request, x_hub_signature_256=wrong_signature, x_github_event="pull_request"
        )

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_webhook_rejects_everything_when_secret_not_configured(monkeypatch):
    # 沒設定密鑰時要全部拒絕，不能因為忘記設定就變成沒有保護
    monkeypatch.setattr(webhook_router, "GITHUB_WEBHOOK_SECRET", None)
    request = FakeRequest(_pr_payload("opened"))

    with pytest.raises(HTTPException) as exc_info:
        await webhook_router.github_webhook(request, x_hub_signature_256=None, x_github_event="pull_request")

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_webhook_accepts_correct_signature(monkeypatch):
    monkeypatch.setattr(webhook_router, "DISCORD_WEBHOOK_URL", None)
    monkeypatch.setattr(webhook_router, "MAIN_WEBHOOK_URL", None)

    result = await _call_webhook(monkeypatch, {"zen": "Keep it logically awesome."}, event="ping")

    assert result == {"status": "ok"}
