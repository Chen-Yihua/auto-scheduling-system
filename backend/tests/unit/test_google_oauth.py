"""services/google_oauth.py：用 refresh_token 向 Google 換新 access_token。"""
import logging

import pytest
import httpx
from fastapi import HTTPException
from pymongo.errors import PyMongoError

import services.google_oauth as google_oauth
from core.crypto import encrypt_secret, decrypt_secret
from core.database import db

@pytest.mark.asyncio
async def test_refresh_google_token_logs_info_on_success(monkeypatch, caplog):
    """換新 token 成功 → 回傳新 token，並用 logging 記下 info 訊息。"""
    async def mock_find_one(query):
        return {"_id": "uid123", "refresh_token": encrypt_secret("old-refresh-token")}

    written = {}

    async def mock_update_one(filter, update):
        written.update(update["$set"])

    class MockResponse:
        status_code = 200
        text = '{"access_token": "new-token"}'

        def raise_for_status(self):
            pass

        def json(self):
            return {"access_token": "new-token"}

    class MockClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            pass

        async def post(self, url, data):
            sent["refresh_token"] = data["refresh_token"]
            return MockResponse()

    sent = {}
    monkeypatch.setattr(db.googleCalendarTokens, "find_one", mock_find_one)
    monkeypatch.setattr(db.googleCalendarTokens, "update_one", mock_update_one)
    monkeypatch.setattr(google_oauth.httpx, "AsyncClient", lambda *a, **kw: MockClient())

    with caplog.at_level(logging.INFO, logger="crud.google_tokens"):
        token = await google_oauth.refresh_google_calendar_token("uid123")

    assert token == "new-token"
    assert sent["refresh_token"] == "old-refresh-token"  # 送給 Google 的是解密後的明文
    assert decrypt_secret(written["access_token"]) == "new-token"
    assert decrypt_secret(written["refresh_token"]) == "old-refresh-token"
    assert any(
        "Refreshed Google Calendar token for clerk_id=uid123" in record.message
        for record in caplog.records
    )


@pytest.mark.asyncio
async def test_refresh_google_token_raises_401_and_clears_doc_when_google_rejects_it(monkeypatch):
    """Google 回 invalid_grant → 刪除失效的 token 並回 401。"""
    async def mock_find_one(query):
        return {"_id": "uid123", "refresh_token": encrypt_secret("revoked-refresh-token")}

    delete_calls = {"n": 0}

    async def mock_delete_one(query):
        delete_calls["n"] += 1
        assert query == {"_id": "uid123"}

    class MockResponse:
        status_code = 400
        text = '{"error": "invalid_grant"}'

        def raise_for_status(self):
            request = httpx.Request("POST", "https://oauth2.googleapis.com/token")
            response = httpx.Response(400, request=request, text=self.text)
            raise httpx.HTTPStatusError("Bad Request", request=request, response=response)

    class MockClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            pass

        async def post(self, *a, **k):
            return MockResponse()

    monkeypatch.setattr(db.googleCalendarTokens, "find_one", mock_find_one)
    monkeypatch.setattr(db.googleCalendarTokens, "delete_one", mock_delete_one)
    monkeypatch.setattr(google_oauth.httpx, "AsyncClient", lambda *a, **kw: MockClient())

    with pytest.raises(HTTPException) as exc_info:
        await google_oauth.refresh_google_calendar_token("uid123")

    assert exc_info.value.status_code == 401
    assert delete_calls["n"] == 1


@pytest.mark.asyncio
async def test_refresh_google_calendar_token_raises_401_when_no_refresh_token_stored(monkeypatch):
    """資料庫裡沒有 refresh_token → 401，請使用者重新授權。"""
    async def mock_find_one(query):
        return {"_id": "uid123"}  # 沒有 refresh_token 欄位

    monkeypatch.setattr(db.googleCalendarTokens, "find_one", mock_find_one)

    with pytest.raises(HTTPException) as exc_info:
        await google_oauth.refresh_google_calendar_token("uid123")

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_refresh_google_calendar_token_raises_502_when_google_unreachable(monkeypatch):
    """refresh 時連不上 Google → 502。"""
    async def mock_find_one(query):
        return {"_id": "uid123", "refresh_token": encrypt_secret("old-rt")}

    class FailingClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            pass

        async def post(self, *a, **k):
            raise httpx.ConnectError("Google 掛了")

    monkeypatch.setattr(db.googleCalendarTokens, "find_one", mock_find_one)
    monkeypatch.setattr(google_oauth.httpx, "AsyncClient", lambda *a, **kw: FailingClient())

    with pytest.raises(HTTPException) as exc_info:
        await google_oauth.refresh_google_calendar_token("uid123")

    assert exc_info.value.status_code == 502


@pytest.mark.asyncio
async def test_refresh_google_calendar_token_still_401s_when_cleanup_delete_fails(monkeypatch):
    """刪除失效 token 時 DB 也失敗 → 仍回 401，不被清理失敗蓋掉。"""
    async def mock_find_one(query):
        return {"_id": "uid123", "refresh_token": encrypt_secret("revoked-rt")}

    async def mock_delete_one(query):
        raise PyMongoError("connection lost")

    class MockResponse:
        status_code = 400
        text = '{"error": "invalid_grant"}'

        def raise_for_status(self):
            request = httpx.Request("POST", "https://oauth2.googleapis.com/token")
            response = httpx.Response(400, request=request, text=self.text)
            raise httpx.HTTPStatusError("Bad Request", request=request, response=response)

    class MockClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            pass

        async def post(self, *a, **k):
            return MockResponse()

    monkeypatch.setattr(db.googleCalendarTokens, "find_one", mock_find_one)
    monkeypatch.setattr(db.googleCalendarTokens, "delete_one", mock_delete_one)
    monkeypatch.setattr(google_oauth.httpx, "AsyncClient", lambda *a, **kw: MockClient())

    with pytest.raises(HTTPException) as exc_info:
        await google_oauth.refresh_google_calendar_token("uid123")

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_refresh_google_calendar_token_raises_400_when_google_response_missing_access_token(monkeypatch):
    """Google 回 200 但回應裡沒有 access_token → 400。"""
    async def mock_find_one(query):
        return {"_id": "uid123", "refresh_token": encrypt_secret("old-rt")}

    class MockResponse:
        status_code = 200
        text = "{}"

        def raise_for_status(self):
            pass

        def json(self):
            return {}  # 200 但沒有 access_token

    class MockClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            pass

        async def post(self, *a, **k):
            return MockResponse()

    monkeypatch.setattr(db.googleCalendarTokens, "find_one", mock_find_one)
    monkeypatch.setattr(google_oauth.httpx, "AsyncClient", lambda *a, **kw: MockClient())

    with pytest.raises(HTTPException) as exc_info:
        await google_oauth.refresh_google_calendar_token("uid123")

    assert exc_info.value.status_code == 400


def _mock_token_endpoint(monkeypatch, status_code, text):
    """Google token endpoint 回指定的狀態碼與內容；回傳一個 list 記錄 delete_one 被呼叫幾次。"""
    async def mock_find_one(query):
        return {"_id": "uid123", "refresh_token": encrypt_secret("valid-rt")}

    deleted = []

    async def mock_delete_one(query):
        deleted.append(query)

    async def mock_update_one(*a, **k):
        pass

    def handler(request):
        return httpx.Response(status_code, text=text)

    real_client = httpx.AsyncClient
    monkeypatch.setattr(db.googleCalendarTokens, "find_one", mock_find_one)
    monkeypatch.setattr(db.googleCalendarTokens, "delete_one", mock_delete_one)
    monkeypatch.setattr(db.googleCalendarTokens, "update_one", mock_update_one)
    monkeypatch.setattr(
        google_oauth.httpx, "AsyncClient",
        lambda *a, **k: real_client(transport=httpx.MockTransport(handler)),
    )
    return deleted


@pytest.mark.asyncio
async def test_refresh_google_calendar_token_keeps_token_when_google_has_server_error(monkeypatch):
    """Google 自己暫時故障（5xx）→ 回 502 請使用者稍後再試，不能把還有效的 token 刪掉。"""
    deleted = _mock_token_endpoint(monkeypatch, 503, "Service Unavailable")

    with pytest.raises(HTTPException) as exc_info:
        await google_oauth.refresh_google_calendar_token("uid123")

    assert exc_info.value.status_code == 502
    assert deleted == []


@pytest.mark.asyncio
async def test_refresh_google_calendar_token_keeps_token_when_client_config_is_wrong(monkeypatch):
    """invalid_client（伺服器設定錯誤）→ 500，不刪 token。"""
    deleted = _mock_token_endpoint(monkeypatch, 401, '{"error": "invalid_client"}')

    with pytest.raises(HTTPException) as exc_info:
        await google_oauth.refresh_google_calendar_token("uid123")

    assert exc_info.value.status_code == 500
    assert deleted == []
