import json
import pytest
from unittest.mock import MagicMock

import routers.webhook as webhook_router


class FakeRequest:
    """gitlab_webhook 只用到 request.json()，用一個假 Request 就夠了。"""
    def __init__(self, payload):
        self._payload = payload

    async def json(self):
        return self._payload


def _mr_payload(action, target_branch="main"):
    return {
        "object_kind": "merge_request",
        "object_attributes": {
            "action": action,
            "title": "Fix bug",
            "description": "desc",
            "iid": 42,
            "target_branch": target_branch,
            "url": "https://gitlab.com/x/y/-/merge_requests/42",
            "updated_at": "2024-01-01T00:00:00Z",
            "commits_count": 3,
        },
        "project": {"id": 999},
        "user": {"name": "Alice"},
    }


def _mock_gemini_response(monkeypatch):
    fake_response = MagicMock()
    fake_response.text = json.dumps(
        {"summary": "摘要", "frontend": None, "backend": None, "refactor": None}
    )
    monkeypatch.setattr(webhook_router.client.models, "generate_content", lambda **kwargs: fake_response)


# ========== open MR：貼 MR 摘要用的 Discord webhook ==========

@pytest.mark.asyncio
async def test_open_mr_posts_to_configured_mr_webhook(monkeypatch):
    monkeypatch.setattr(webhook_router, "DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/test/mr")
    monkeypatch.setattr(webhook_router, "MAIN_WEBHOOK_URL", None)
    monkeypatch.setenv("GITLAB_TOKEN", "dummy")

    posted_urls = []
    monkeypatch.setattr(webhook_router.requests, "get", lambda *a, **k: MagicMock(json=lambda: {"changes": []}))
    monkeypatch.setattr(webhook_router.requests, "post", lambda url, **k: posted_urls.append(url))
    _mock_gemini_response(monkeypatch)

    await webhook_router.gitlab_webhook(FakeRequest(_mr_payload("open")))

    assert "https://discord.com/api/webhooks/test/mr" in posted_urls


@pytest.mark.asyncio
async def test_open_mr_skips_discord_when_webhook_not_configured(monkeypatch):
    monkeypatch.setattr(webhook_router, "DISCORD_WEBHOOK_URL", None)
    monkeypatch.setattr(webhook_router, "MAIN_WEBHOOK_URL", None)
    monkeypatch.setenv("GITLAB_TOKEN", "dummy")

    posted_urls = []
    monkeypatch.setattr(webhook_router.requests, "get", lambda *a, **k: MagicMock(json=lambda: {"changes": []}))
    monkeypatch.setattr(webhook_router.requests, "post", lambda url, **k: posted_urls.append(url))
    _mock_gemini_response(monkeypatch)

    await webhook_router.gitlab_webhook(FakeRequest(_mr_payload("open")))

    # 沒設定 webhook 網址就不該對任何 discord.com 網址發送
    assert not any("discord.com" in url for url in posted_urls)


# ========== merge 到 main：合併通知用的 Discord webhook ==========

@pytest.mark.asyncio
async def test_merge_to_main_posts_to_configured_main_webhook(monkeypatch):
    monkeypatch.setattr(webhook_router, "DISCORD_WEBHOOK_URL", None)
    monkeypatch.setattr(webhook_router, "MAIN_WEBHOOK_URL", "https://discord.com/api/webhooks/test/main")

    posted = []
    monkeypatch.setattr(webhook_router.requests, "post", lambda url, **k: posted.append((url, k)))

    await webhook_router.gitlab_webhook(FakeRequest(_mr_payload("merge", target_branch="main")))

    assert len(posted) == 1
    assert posted[0][0] == "https://discord.com/api/webhooks/test/main"


@pytest.mark.asyncio
async def test_merge_to_main_skips_discord_when_webhook_not_configured(monkeypatch):
    monkeypatch.setattr(webhook_router, "DISCORD_WEBHOOK_URL", None)
    monkeypatch.setattr(webhook_router, "MAIN_WEBHOOK_URL", None)

    posted = []
    monkeypatch.setattr(webhook_router.requests, "post", lambda url, **k: posted.append(url))

    await webhook_router.gitlab_webhook(FakeRequest(_mr_payload("merge", target_branch="main")))

    assert posted == []


@pytest.mark.asyncio
async def test_no_hardcoded_discord_url_left_in_source():
    import inspect
    source = inspect.getsource(webhook_router)
    assert "discord.com/api/webhooks/" not in source
