# 走 HTTP 確認 router 與 crud 裡需要專屬 error_code 的錯誤，狀態碼照 ADR 0011 的對照表
import hashlib
import hmac
import json

import httpx
import pytest
from httpx import AsyncClient
from httpx._transports.asgi import ASGITransport

from main import app
from core import cache
from core.database import db
import routers.pr_review_webhook as webhook_router
import routers.schedule as schedule_router
import routers.user as user_router


async def _request(method, path, **kwargs):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        return await ac.request(method, path, **kwargs)


# ---------- 使用者 ----------

@pytest.mark.asyncio
async def test_register_existing_user_is_already_exists(logged_in_user):
    """使用者已註冊 → 409 ALREADY_EXISTS（前端 useUserSync 當成已註冊）。"""
    await db.users.delete_many({"_id": "test_user_123"})
    await db.users.insert_one({"_id": "test_user_123", "name": "me", "email": "me@example.com"})

    try:
        res = await _request("POST", "/users/", json={"clerk_id": "test_user_123", "name": "me", "email": "me@example.com"})
    finally:
        await db.users.delete_many({"_id": "test_user_123"})

    assert res.status_code == 409
    assert res.json()["error_code"] == "ALREADY_EXISTS"


@pytest.mark.asyncio
async def test_update_user_without_fields_is_invalid_request(logged_in_user):
    """AC1：更新使用者時沒有可更新的欄位 → 400 INVALID_REQUEST（不再是 404）。"""
    res = await _request("PUT", "/users/me", json={})

    assert res.status_code == 400
    assert res.json()["error_code"] == "INVALID_REQUEST"


@pytest.mark.asyncio
async def test_clerk_webhook_bad_signature_is_invalid_webhook_signature(monkeypatch):
    """AC6：Clerk webhook 簽章錯誤 → 401 INVALID_WEBHOOK_SIGNATURE。"""
    monkeypatch.setattr(user_router, "CLERK_WEBHOOK_SIGNING_SECRET", "whsec_dGVzdHNlY3JldA==")

    res = await _request("POST", "/users/webhook/clerk", content=b"{}",
                         headers={"svix-id": "x", "svix-timestamp": "1", "svix-signature": "v1,bad"})

    assert res.status_code == 401
    assert res.json()["error_code"] == "INVALID_WEBHOOK_SIGNATURE"


@pytest.mark.asyncio
async def test_clerk_webhook_without_configured_secret_is_401(monkeypatch):
    """AC6：沒設定 Clerk webhook 密鑰 → 401 INVALID_WEBHOOK_SIGNATURE（不回 500，不讓外部知道漏了設定）。"""
    monkeypatch.setattr(user_router, "CLERK_WEBHOOK_SIGNING_SECRET", None)

    res = await _request("POST", "/users/webhook/clerk", content=b"{}",
                         headers={"svix-id": "x", "svix-timestamp": "1", "svix-signature": "v1,bad"})

    assert res.status_code == 401
    assert res.json() == {"detail": "Invalid webhook signature", "error_code": "INVALID_WEBHOOK_SIGNATURE"}


# ---------- 排程 ----------

@pytest.mark.asyncio
async def test_confirm_expired_suggestion_is_suggestion_expired(logged_in_user):
    """排程建議過期 → 409 SUGGESTION_EXPIRED。"""
    cache._memory_store.clear()

    res = await _request("POST", "/schedule/confirm")

    assert res.status_code == 409
    assert res.json()["error_code"] == "SUGGESTION_EXPIRED"


@pytest.mark.asyncio
async def test_malformed_external_task_id_is_invalid_request(logged_in_user):
    """AC1、AC8：排程的外部來源 id 格式錯誤（GitHub 的 id 不是數字）→ 400 INVALID_REQUEST。"""
    res = await _request("PATCH", "/schedule/tasks/done", json={"task_id": "github:not-a-number", "done": True})
    reorder = await _request("PUT", "/schedule/reorder",
                             json={"items": [{"task_id": "github:not-a-number", "priority": "High"}]})

    assert res.status_code == 400
    assert res.json()["error_code"] == "INVALID_REQUEST"
    assert reorder.status_code == 400
    assert reorder.json()["error_code"] == "INVALID_REQUEST"


# ---------- GitHub PR webhook ----------

SECRET = "pr-webhook-secret"


def _signed(body: bytes) -> dict:
    signature = "sha256=" + hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()
    return {"X-Hub-Signature-256": signature, "X-GitHub-Event": "pull_request"}


@pytest.mark.asyncio
async def test_pr_webhook_bad_signature_is_invalid_webhook_signature(monkeypatch):
    """AC6：GitHub webhook 簽章錯誤 → 401 INVALID_WEBHOOK_SIGNATURE。"""
    monkeypatch.setattr(webhook_router, "GITHUB_WEBHOOK_SECRET", SECRET)

    res = await _request("POST", "/webhook", content=b"{}", headers={"X-Hub-Signature-256": "sha256=bad"})

    assert res.status_code == 401
    assert res.json()["error_code"] == "INVALID_WEBHOOK_SIGNATURE"


@pytest.mark.asyncio
async def test_pr_webhook_without_configured_secret_is_401(monkeypatch):
    """AC6：沒設定 GitHub webhook 密鑰 → 401 INVALID_WEBHOOK_SIGNATURE。"""
    monkeypatch.setattr(webhook_router, "GITHUB_WEBHOOK_SECRET", None)

    res = await _request("POST", "/webhook", content=b"{}", headers=_signed(b"{}"))

    assert res.status_code == 401
    assert res.json()["error_code"] == "INVALID_WEBHOOK_SIGNATURE"


@pytest.mark.asyncio
@pytest.mark.parametrize("body", [b"not json", json.dumps({"action": "opened"}).encode(), b"[1, 2]"],
                         ids=["not-json", "missing-pull-request", "not-object"])
async def test_pr_webhook_bad_payload_is_invalid_request(monkeypatch, body):
    """AC1：GitHub webhook 的 payload 不是 JSON 或缺欄位 → 400 INVALID_REQUEST。"""
    monkeypatch.setattr(webhook_router, "GITHUB_WEBHOOK_SECRET", SECRET)

    res = await _request("POST", "/webhook", content=body, headers=_signed(body))

    assert res.status_code == 400
    assert res.json()["error_code"] == "INVALID_REQUEST"


@pytest.mark.asyncio
@pytest.mark.parametrize("error, status_code, error_code", [
    (httpx.ConnectError("down"), 502, "UPSTREAM_ERROR"),
    (httpx.ReadTimeout("slow"), 504, "UPSTREAM_TIMEOUT"),
])
async def test_pr_webhook_comment_post_failure_is_upstream_error(monkeypatch, error, status_code, error_code):
    """AC1：貼 PR 留言時連不上 GitHub → 502 UPSTREAM_ERROR；逾時 504 UPSTREAM_TIMEOUT。"""
    monkeypatch.setattr(webhook_router, "GITHUB_WEBHOOK_SECRET", SECRET)
    monkeypatch.setattr(webhook_router, "DISCORD_WEBHOOK_URL", None)

    async def failing_generate(**kwargs):
        raise RuntimeError("no LLM in tests")

    monkeypatch.setattr(webhook_router.client.aio.models, "generate_content", failing_generate)

    class FailingClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def get(self, *args, **kwargs):
            raise error

        async def post(self, *args, **kwargs):
            raise error

    monkeypatch.setattr(webhook_router.httpx, "AsyncClient", FailingClient)
    payload = {"action": "opened", "pull_request": {"number": 1, "title": "t", "body": ""},
               "repository": {"full_name": "o/r"}}
    body = json.dumps(payload).encode()

    res = await _request("POST", "/webhook", content=body, headers=_signed(body))

    assert res.status_code == status_code
    assert res.json()["error_code"] == error_code
