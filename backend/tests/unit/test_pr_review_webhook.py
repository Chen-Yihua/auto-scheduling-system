import hashlib
import hmac
import json
import httpx
import pytest
from fastapi import HTTPException
from unittest.mock import MagicMock

import routers.pr_review_webhook as webhook_router


class FakeRequest:
    """github_webhook 只用到 request.body()，用一個假 Request 就夠了。"""
    def __init__(self, payload: dict):
        self._raw = json.dumps(payload).encode()

    async def body(self):
        return self._raw


class FakeAsyncClient:
    """取代 httpx.AsyncClient：get/post 轉給測試設定的同步函式，並記下建立時帶的參數。"""
    created = []
    get_handler = staticmethod(lambda url, **k: MagicMock(json=lambda: [{"filename": "app.py"}]))
    post_handler = staticmethod(lambda url, **k: MagicMock())

    def __init__(self, *a, **kwargs):
        FakeAsyncClient.created.append(kwargs)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        pass

    async def get(self, url, **k):
        return self.get_handler(url, **k)

    async def post(self, url, **k):
        return self.post_handler(url, **k)


def _patch_http(monkeypatch, method, handler):
    monkeypatch.setattr(FakeAsyncClient, f"{method}_handler", staticmethod(handler))
    monkeypatch.setattr(webhook_router.httpx, "AsyncClient", FakeAsyncClient)


def _patch_gemini(monkeypatch, fake):
    """把 client.aio.models.generate_content 換成假的；fake 是同步函式，這裡包成 async。"""
    async def fake_async(**kwargs):
        return fake(**kwargs)
    monkeypatch.setattr(webhook_router.client.aio.models, "generate_content", fake_async)


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
    _patch_gemini(monkeypatch, lambda **kwargs: fake_response)


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
    """新開的 PR → 用 Gemini 產生摘要，貼到有設定的 PR 摘要 Discord webhook。"""
    monkeypatch.setattr(webhook_router, "DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/test/mr")
    monkeypatch.setattr(webhook_router, "MAIN_WEBHOOK_URL", None)
    monkeypatch.setenv("GITHUB_BOT_TOKEN", "dummy")

    posted_urls = []
    _patch_http(monkeypatch, "get", lambda *a, **k: MagicMock(json=lambda: [{"filename": "app.py"}]))
    _patch_http(monkeypatch, "post", lambda url, **k: posted_urls.append(url) or MagicMock())
    _mock_gemini_response(monkeypatch)

    await _call_webhook(monkeypatch, _pr_payload("opened"))

    assert "https://discord.com/api/webhooks/test/mr" in posted_urls


@pytest.mark.asyncio
async def test_open_pr_falls_back_when_fetching_changed_files_fails(monkeypatch):
    """抓 PR 變更檔案清單失敗（GitHub API 逾時或出錯）不該讓整支 webhook 中斷：改用「無法取得變更檔案」的預設文字頂替，繼續產生摘要。"""
    monkeypatch.setattr(webhook_router, "DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/test/mr")
    monkeypatch.setattr(webhook_router, "MAIN_WEBHOOK_URL", None)
    monkeypatch.setenv("GITHUB_BOT_TOKEN", "dummy")

    def raise_error(*a, **k):
        raise ConnectionError("GitHub API 連不上")

    _patch_http(monkeypatch, "get", raise_error)

    posted = []
    _patch_http(monkeypatch, "post", lambda url, **k: posted.append((url, k)) or MagicMock())

    captured_prompt = {}

    def fake_generate_content(**kwargs):
        captured_prompt["contents"] = kwargs.get("contents")
        fake_response = MagicMock()
        fake_response.text = json.dumps(
            {"summary": "摘要", "frontend": None, "backend": None, "refactor": None}
        )
        return fake_response

    _patch_gemini(monkeypatch, fake_generate_content)

    # 不會因為抓變更檔案出錯而讓整支處理當掉
    await _call_webhook(monkeypatch, _pr_payload("opened"))

    assert "https://discord.com/api/webhooks/test/mr" in [url for url, _ in posted]
    assert "無法取得變更檔案" in captured_prompt["contents"]


@pytest.mark.asyncio
async def test_open_pr_skips_discord_when_webhook_not_configured(monkeypatch):
    """沒設定 PR 摘要的 Discord webhook 網址 → 不對任何 discord.com 網址發送。"""
    monkeypatch.setattr(webhook_router, "DISCORD_WEBHOOK_URL", None)
    monkeypatch.setattr(webhook_router, "MAIN_WEBHOOK_URL", None)
    monkeypatch.setenv("GITHUB_BOT_TOKEN", "dummy")

    posted_urls = []
    _patch_http(monkeypatch, "get", lambda *a, **k: MagicMock(json=lambda: [{"filename": "app.py"}]))
    _patch_http(monkeypatch, "post", lambda url, **k: posted_urls.append(url) or MagicMock())
    _mock_gemini_response(monkeypatch)

    await _call_webhook(monkeypatch, _pr_payload("opened"))

    # 沒設定 webhook 網址就不該對任何 discord.com 網址發送
    assert not any("discord.com" in url for url in posted_urls)


# ========== merge 到 main：合併通知用的 Discord webhook ==========

@pytest.mark.asyncio
async def test_merge_to_main_posts_to_configured_main_webhook(monkeypatch):
    """PR 合併到 main → 發合併通知到有設定的 main Discord webhook（只發一次）。"""
    monkeypatch.setattr(webhook_router, "DISCORD_WEBHOOK_URL", None)
    monkeypatch.setattr(webhook_router, "MAIN_WEBHOOK_URL", "https://discord.com/api/webhooks/test/main")

    posted = []
    _patch_http(monkeypatch, "post", lambda url, **k: posted.append((url, k)) or MagicMock())

    await _call_webhook(monkeypatch, _pr_payload("closed", merged=True, base_ref="main"))

    assert len(posted) == 1
    assert posted[0][0] == "https://discord.com/api/webhooks/test/main"


@pytest.mark.asyncio
async def test_merge_to_main_skips_discord_when_webhook_not_configured(monkeypatch):
    """PR 合併到 main、但沒設定 main webhook 網址 → 不發送任何通知。"""
    monkeypatch.setattr(webhook_router, "DISCORD_WEBHOOK_URL", None)
    monkeypatch.setattr(webhook_router, "MAIN_WEBHOOK_URL", None)

    posted = []
    _patch_http(monkeypatch, "post", lambda url, **k: posted.append(url) or MagicMock())

    await _call_webhook(monkeypatch, _pr_payload("closed", merged=True, base_ref="main"))

    assert posted == []


@pytest.mark.asyncio
async def test_closed_but_not_merged_does_not_post_merge_notification(monkeypatch):
    """PR 被關掉但沒有 merge → 不發合併通知。"""
    monkeypatch.setattr(webhook_router, "DISCORD_WEBHOOK_URL", None)
    monkeypatch.setattr(webhook_router, "MAIN_WEBHOOK_URL", "https://discord.com/api/webhooks/test/main")

    posted = []
    _patch_http(monkeypatch, "post", lambda url, **k: posted.append(url) or MagicMock())

    # PR 被關掉但沒有 merge
    await _call_webhook(monkeypatch, _pr_payload("closed", merged=False, base_ref="main"))

    assert posted == []


@pytest.mark.asyncio
async def test_no_hardcoded_discord_url_left_in_source():
    """原始碼裡不能寫死任何 Discord webhook 網址（網址屬於機密，只能從環境變數讀）。"""
    import inspect
    source = inspect.getsource(webhook_router)
    assert "discord.com/api/webhooks/" not in source


# ========== Gemini 失敗時，例外細節不該外洩到公開的 PR 留言 ==========

@pytest.mark.asyncio
async def test_gemini_failure_does_not_leak_exception_detail_to_public_comment(monkeypatch, caplog):
    """Gemini 產生摘要失敗 → 公開的 PR 留言只能是「無法…」之類的通用訊息，不能外洩例外內容（例如連線字串）；完整例外要留在後端 log 供事後排查。"""
    monkeypatch.setattr(webhook_router, "DISCORD_WEBHOOK_URL", None)
    monkeypatch.setattr(webhook_router, "MAIN_WEBHOOK_URL", None)
    monkeypatch.setenv("GITHUB_BOT_TOKEN", "dummy")

    _patch_http(monkeypatch, "get", lambda *a, **k: MagicMock(json=lambda: [{"filename": "app.py"}]))

    posted_comments = []

    def fake_post(url, **kwargs):
        if "/comments" in url:
            posted_comments.append(kwargs.get("json", {}).get("body", ""))
        return MagicMock()

    _patch_http(monkeypatch, "post", fake_post)

    secret_detail = "internal database connection string leaked: mongodb://user:pass@10.0.0.5"

    def fake_generate_content(**kwargs):
        raise Exception(secret_detail)

    _patch_gemini(monkeypatch, fake_generate_content)

    import logging
    with caplog.at_level(logging.ERROR, logger="routers.pr_review_webhook"):
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
    """/webhook 沒帶 X-Hub-Signature-256 → 401。"""
    monkeypatch.setattr(webhook_router, "GITHUB_WEBHOOK_SECRET", "correct-secret")
    request = FakeRequest(_pr_payload("opened"))

    with pytest.raises(HTTPException) as exc_info:
        await webhook_router.github_webhook(request, x_hub_signature_256=None, x_github_event="pull_request")

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_webhook_rejects_wrong_signature(monkeypatch):
    """簽章是用錯誤的密鑰算出來的 → 401。"""
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
    """沒設定 GITHUB_WEBHOOK_SECRET → 一律拒絕（401），不能因為忘記設定就變成沒有保護。"""
    monkeypatch.setattr(webhook_router, "GITHUB_WEBHOOK_SECRET", None)
    request = FakeRequest(_pr_payload("opened"))

    with pytest.raises(HTTPException) as exc_info:
        await webhook_router.github_webhook(request, x_hub_signature_256=None, x_github_event="pull_request")

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_webhook_accepts_correct_signature(monkeypatch):
    """簽章正確 → 通過驗證，回 {"status": "ok"}。"""
    # 用不會觸發其他動作的 ping 事件，只看驗證有沒有過
    monkeypatch.setattr(webhook_router, "DISCORD_WEBHOOK_URL", None)
    monkeypatch.setattr(webhook_router, "MAIN_WEBHOOK_URL", None)

    result = await _call_webhook(monkeypatch, {"zen": "Keep it logically awesome."}, event="ping")

    assert result == {"status": "ok"}


# ========== Gemini 格式錯誤、Discord 失敗時的處理 ==========

def _setup_open_pr(monkeypatch, gemini_payload, discord_post):
    """open PR 情境的共用設定：回傳一個 list，收集貼到 GitHub PR 的留言內容。"""
    monkeypatch.setattr(webhook_router, "DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/test/mr")
    monkeypatch.setattr(webhook_router, "MAIN_WEBHOOK_URL", None)
    _patch_http(monkeypatch, "get", lambda *a, **k: MagicMock(json=lambda: [{"filename": "app.py"}]))
    _patch_gemini(monkeypatch, lambda **kwargs: MagicMock(text=json.dumps(gemini_payload)))

    github_comments = []

    def fake_post(url, **k):
        if "discord.com" in url:
            return discord_post(url, **k)
        github_comments.append(k["json"]["body"])
        return MagicMock()

    _patch_http(monkeypatch, "post", fake_post)
    return github_comments


@pytest.mark.asyncio
async def test_open_pr_keeps_summary_comment_when_discord_fails(monkeypatch):
    """Discord 連不上 → 只影響 Discord 通知，PR 留言照樣貼出摘要，不能被換成「摘要產生失敗」。"""
    def discord_down(url, **k):
        raise httpx.ConnectError("Discord 連不上")

    github_comments = _setup_open_pr(
        monkeypatch,
        {"summary": "修正登入 bug", "frontend": None, "backend": None, "refactor": None},
        discord_down,
    )

    await _call_webhook(monkeypatch, _pr_payload("opened"))

    assert len(github_comments) == 1
    assert "修正登入 bug" in github_comments[0]
    assert "自動摘要產生失敗" not in github_comments[0]


@pytest.mark.asyncio
async def test_open_pr_reports_failure_when_gemini_omits_summary(monkeypatch):
    """Gemini 回傳的 JSON 少了必填的 summary → PR 留言改成「摘要產生失敗」，也不發 Discord。"""
    discord_calls = []
    github_comments = _setup_open_pr(
        monkeypatch,
        {"frontend": "改了按鈕"},
        lambda url, **k: discord_calls.append(url) or MagicMock(),
    )

    await _call_webhook(monkeypatch, _pr_payload("opened"))

    assert "自動摘要產生失敗" in github_comments[0]
    assert discord_calls == []


@pytest.mark.asyncio
async def test_open_pr_truncates_long_summary_to_discord_limits(monkeypatch):
    """Gemini 回很長的內容 → 截斷到 Discord 上限，否則 Discord 會整筆拒收；PR 留言則保留完整內容。"""
    sent = []
    long_text = "很長的建議" * 500
    github_comments = _setup_open_pr(
        monkeypatch,
        {"summary": long_text, "frontend": long_text, "backend": None, "refactor": None},
        lambda url, **k: sent.append(k["json"]) or MagicMock(),
    )

    await _call_webhook(monkeypatch, _pr_payload("opened"))

    embed = sent[0]["embeds"][0]
    assert len(embed["description"]) <= webhook_router.DISCORD_DESCRIPTION_LIMIT
    assert all(len(f["value"]) <= webhook_router.DISCORD_FIELD_LIMIT for f in embed["fields"])
    assert long_text in github_comments[0]


@pytest.mark.asyncio
async def test_open_pr_outbound_http_calls_all_set_timeout(monkeypatch):
    """打 GitHub、Discord 都要設 timeout，對方不回應時才不會一直卡住。"""
    monkeypatch.setattr(FakeAsyncClient, "created", [])
    _setup_open_pr(
        monkeypatch,
        {"summary": "摘要", "frontend": None, "backend": None, "refactor": None},
        lambda url, **k: MagicMock(),
    )

    await _call_webhook(monkeypatch, _pr_payload("opened"))

    # 抓變更檔案、Discord、PR 留言
    assert len(FakeAsyncClient.created) == 3
    assert all(kwargs.get("timeout") for kwargs in FakeAsyncClient.created)
