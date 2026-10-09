import logging

import pytest
import httpx
from fastapi import HTTPException
from pymongo.errors import PyMongoError

import crud.google_tokens as google_tokens
from core.crypto import encrypt_secret, decrypt_secret


@pytest.mark.asyncio
async def test_is_google_calendar_connected_true_when_token_stored(monkeypatch):
    """資料庫有存 access token → 已連接（True）。"""
    async def mock_find_one(query):
        return {"_id": "uid123", "access_token": "valid-token"}

    monkeypatch.setattr(google_tokens.db.googleCalendarTokens, "find_one", mock_find_one)

    assert await google_tokens.is_google_calendar_connected("uid123") is True


@pytest.mark.asyncio
async def test_is_google_calendar_connected_false_when_no_doc(monkeypatch):
    """資料庫沒有這筆資料 → 未連接（False）。"""
    async def mock_find_one(query):
        return None

    monkeypatch.setattr(google_tokens.db.googleCalendarTokens, "find_one", mock_find_one)

    assert await google_tokens.is_google_calendar_connected("uid123") is False


@pytest.mark.asyncio
async def test_is_google_calendar_connected_false_when_doc_has_no_access_token(monkeypatch):
    """有這筆資料但 access_token 是空的（理論上不該發生）→ 也當作未連接。"""
    async def mock_find_one(query):
        return {"_id": "uid123", "access_token": None}

    monkeypatch.setattr(google_tokens.db.googleCalendarTokens, "find_one", mock_find_one)

    assert await google_tokens.is_google_calendar_connected("uid123") is False


# ========== save_google_calendar_token ==========

@pytest.mark.asyncio
async def test_save_google_calendar_token_stores_encrypted_tokens(monkeypatch):
    """儲存 Google token：access token 和 refresh token 都加密後才寫進資料庫。"""
    saved = {}

    async def mock_update_one(filter, update, upsert=False):
        saved["filter"] = filter
        saved["doc"] = update["$set"]
        return None

    monkeypatch.setattr(google_tokens.db.googleCalendarTokens, "update_one", mock_update_one)

    await google_tokens.save_google_calendar_token("uid123", "access-tok", "refresh-tok")

    assert saved["filter"] == {"_id": "uid123"}
    assert saved["doc"]["access_token"] != "access-tok"
    assert saved["doc"]["refresh_token"] != "refresh-tok"
    assert decrypt_secret(saved["doc"]["access_token"]) == "access-tok"
    assert decrypt_secret(saved["doc"]["refresh_token"]) == "refresh-tok"


@pytest.mark.asyncio
async def test_save_google_calendar_token_without_refresh_token(monkeypatch):
    """Google 沒給 refresh token（使用者之前已授權過）→ 存 None，不會拿 None 去加密而炸掉。"""
    saved = {}

    async def mock_update_one(filter, update, upsert=False):
        saved["doc"] = update["$set"]

    monkeypatch.setattr(google_tokens.db.googleCalendarTokens, "update_one", mock_update_one)

    await google_tokens.save_google_calendar_token("uid123", "access-tok", None)

    assert saved["doc"]["refresh_token"] is None


# ========== get_google_calendar_token ==========

@pytest.mark.asyncio
async def test_get_google_calendar_token_returns_decrypted_token(monkeypatch):
    """資料庫存的是密文 → 回傳解密後的 access token。"""
    async def mock_find_one(query):
        return {"_id": "uid123", "access_token": encrypt_secret("access-tok")}

    monkeypatch.setattr(google_tokens.db.googleCalendarTokens, "find_one", mock_find_one)

    assert await google_tokens.get_google_calendar_token("uid123") == "access-tok"


# ========== refresh_google_calendar_token ==========

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
    monkeypatch.setattr(google_tokens.db.googleCalendarTokens, "find_one", mock_find_one)
    monkeypatch.setattr(google_tokens.db.googleCalendarTokens, "update_one", mock_update_one)
    monkeypatch.setattr(google_tokens.httpx, "AsyncClient", lambda *a, **kw: MockClient())

    with caplog.at_level(logging.INFO, logger="crud.google_tokens"):
        token = await google_tokens.refresh_google_calendar_token("uid123")

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
    """Google 拒絕 refresh token 本身（使用者撤銷授權，或 OAuth 同意畫面還在 Testing 狀態時 7 天後自動失效）→ 清掉資料庫裡失效的 token 並回 401，請使用者重新連接。這跟「網路連不上 Google」是不同情況。"""
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

    monkeypatch.setattr(google_tokens.db.googleCalendarTokens, "find_one", mock_find_one)
    monkeypatch.setattr(google_tokens.db.googleCalendarTokens, "delete_one", mock_delete_one)
    monkeypatch.setattr(google_tokens.httpx, "AsyncClient", lambda *a, **kw: MockClient())

    with pytest.raises(HTTPException) as exc_info:
        await google_tokens.refresh_google_calendar_token("uid123")

    assert exc_info.value.status_code == 401
    assert delete_calls["n"] == 1


@pytest.mark.asyncio
async def test_refresh_google_calendar_token_raises_401_when_no_refresh_token_stored(monkeypatch):
    """資料庫裡沒有 refresh_token → 401，請使用者重新授權。"""
    async def mock_find_one(query):
        return {"_id": "uid123"}  # 沒有 refresh_token 欄位

    monkeypatch.setattr(google_tokens.db.googleCalendarTokens, "find_one", mock_find_one)

    with pytest.raises(HTTPException) as exc_info:
        await google_tokens.refresh_google_calendar_token("uid123")

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

    monkeypatch.setattr(google_tokens.db.googleCalendarTokens, "find_one", mock_find_one)
    monkeypatch.setattr(google_tokens.httpx, "AsyncClient", lambda *a, **kw: FailingClient())

    with pytest.raises(HTTPException) as exc_info:
        await google_tokens.refresh_google_calendar_token("uid123")

    assert exc_info.value.status_code == 502


@pytest.mark.asyncio
async def test_refresh_google_calendar_token_still_401s_when_cleanup_delete_fails(monkeypatch):
    """Google 拒絕 refresh token 後，清掉資料庫舊紀錄這一步也失敗（資料庫剛好也斷線）→ 仍要回 401 請使用者重新連接；次要的清理失敗不能蓋掉主要的錯誤訊息。"""
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

    monkeypatch.setattr(google_tokens.db.googleCalendarTokens, "find_one", mock_find_one)
    monkeypatch.setattr(google_tokens.db.googleCalendarTokens, "delete_one", mock_delete_one)
    monkeypatch.setattr(google_tokens.httpx, "AsyncClient", lambda *a, **kw: MockClient())

    with pytest.raises(HTTPException) as exc_info:
        await google_tokens.refresh_google_calendar_token("uid123")

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

    monkeypatch.setattr(google_tokens.db.googleCalendarTokens, "find_one", mock_find_one)
    monkeypatch.setattr(google_tokens.httpx, "AsyncClient", lambda *a, **kw: MockClient())

    with pytest.raises(HTTPException) as exc_info:
        await google_tokens.refresh_google_calendar_token("uid123")

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
    monkeypatch.setattr(google_tokens.db.googleCalendarTokens, "find_one", mock_find_one)
    monkeypatch.setattr(google_tokens.db.googleCalendarTokens, "delete_one", mock_delete_one)
    monkeypatch.setattr(google_tokens.db.googleCalendarTokens, "update_one", mock_update_one)
    monkeypatch.setattr(
        google_tokens.httpx, "AsyncClient",
        lambda *a, **k: real_client(transport=httpx.MockTransport(handler)),
    )
    return deleted


@pytest.mark.asyncio
async def test_refresh_google_calendar_token_keeps_token_when_google_has_server_error(monkeypatch):
    """Google 自己暫時故障（5xx）→ 回 502 請使用者稍後再試，不能把還有效的 token 刪掉。"""
    deleted = _mock_token_endpoint(monkeypatch, 503, "Service Unavailable")

    with pytest.raises(HTTPException) as exc_info:
        await google_tokens.refresh_google_calendar_token("uid123")

    assert exc_info.value.status_code == 502
    assert deleted == []


@pytest.mark.asyncio
async def test_refresh_google_calendar_token_keeps_token_when_client_config_is_wrong(monkeypatch):
    """伺服器的 GOOGLE_CLIENT_ID/SECRET 設錯（invalid_client）→ 回 500，不是使用者的錯，不能刪 token。"""
    deleted = _mock_token_endpoint(monkeypatch, 401, '{"error": "invalid_client"}')

    with pytest.raises(HTTPException) as exc_info:
        await google_tokens.refresh_google_calendar_token("uid123")

    assert exc_info.value.status_code == 500
    assert deleted == []
