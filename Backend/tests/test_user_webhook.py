import json
import pytest
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException
from svix.webhooks import WebhookVerificationError

import routers.user as user_router


class FakeRequest:
    """clerk_webhook 只用到 request.body()，用一個假 Request 就夠了。"""
    def __init__(self, payload: dict):
        self._raw = json.dumps(payload).encode()

    async def body(self):
        return self._raw


def _headers(svix_id="msg_test", svix_timestamp="1700000000", svix_signature="v1,fake"):
    return dict(svix_id=svix_id, svix_timestamp=svix_timestamp, svix_signature=svix_signature)


async def _call_webhook(monkeypatch, payload, secret="whsec_test", verify_ok=True, **header_overrides):
    monkeypatch.setattr(user_router, "CLERK_WEBHOOK_SIGNING_SECRET", secret)
    request = FakeRequest(payload)

    def fake_verify(self, data, headers):
        if not verify_ok:
            raise WebhookVerificationError("bad signature")
        return None

    with patch.object(user_router.Webhook, "verify", fake_verify):
        return await user_router.clerk_webhook(request, **_headers(**header_overrides))


# ========== 簽章驗證：不是誰都能打這支端點 ==========

@pytest.mark.asyncio
async def test_webhook_rejects_when_secret_not_configured():
    # 沒設定密鑰時要全部拒絕，不能因為忘記設定就變成沒有保護
    user_router.CLERK_WEBHOOK_SIGNING_SECRET = None
    request = FakeRequest({"type": "user.deleted", "data": {"id": "u1"}})

    with pytest.raises(HTTPException) as exc_info:
        await user_router.clerk_webhook(request, **_headers())

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_webhook_rejects_invalid_signature(monkeypatch):
    with pytest.raises(HTTPException) as exc_info:
        await _call_webhook(
            monkeypatch,
            {"type": "user.deleted", "data": {"id": "u1"}},
            verify_ok=False,
        )

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_webhook_rejects_signature_header_that_is_not_valid_base64(monkeypatch):
    # svix-signature 是外部可控的輸入，格式不對時底層函式庫丟的不是
    # WebhookVerificationError（例如 binascii.Error），也要被當成 401，不能漏成 500
    monkeypatch.setattr(user_router, "CLERK_WEBHOOK_SIGNING_SECRET", "whsec_dGVzdHNlY3JldA==")
    request = FakeRequest({"type": "user.deleted", "data": {"id": "u1"}})

    with pytest.raises(HTTPException) as exc_info:
        await user_router.clerk_webhook(
            request, **_headers(svix_signature="v1,not-valid-base64!!!")
        )

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_webhook_rejects_malformed_json(monkeypatch):
    monkeypatch.setattr(user_router, "CLERK_WEBHOOK_SIGNING_SECRET", "whsec_test")
    request = FakeRequest({})
    request._raw = b"not valid json"  # 模擬 body 不是合法 JSON

    with patch.object(user_router.Webhook, "verify", lambda self, data, headers: None):
        with pytest.raises(HTTPException) as exc_info:
            await user_router.clerk_webhook(request, **_headers())

    assert exc_info.value.status_code == 400


# ========== user.deleted 事件的實際行為 ==========

@pytest.mark.asyncio
@patch("routers.user.user_crud.delete_user_by_clerk_id", new_callable=AsyncMock)
async def test_webhook_user_deleted_removes_local_user(mock_delete, monkeypatch):
    mock_delete.return_value = True

    result = await _call_webhook(monkeypatch, {"type": "user.deleted", "data": {"id": "clerk_user_id"}})

    mock_delete.assert_awaited_once_with("clerk_user_id")
    assert result == {"status": "ok"}


@pytest.mark.asyncio
@patch("routers.user.user_crud.delete_user_by_clerk_id", new_callable=AsyncMock)
async def test_webhook_user_deleted_not_found_locally_still_returns_ok(mock_delete, monkeypatch):
    # 本地本來就沒有這個使用者，對這次事件來說已經是「想要的狀態」，
    # 不該回錯誤讓 Clerk 一直重試
    mock_delete.return_value = False

    result = await _call_webhook(monkeypatch, {"type": "user.deleted", "data": {"id": "ghost_user"}})

    assert result == {"status": "ok"}


@pytest.mark.asyncio
async def test_webhook_user_deleted_missing_clerk_id_returns_400(monkeypatch):
    with pytest.raises(HTTPException) as exc_info:
        await _call_webhook(monkeypatch, {"type": "user.deleted", "data": {}})

    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_webhook_ignores_unhandled_event_types(monkeypatch):
    result = await _call_webhook(monkeypatch, {"type": "user.created", "data": {"id": "u1"}})

    assert result == {"status": "ok"}
