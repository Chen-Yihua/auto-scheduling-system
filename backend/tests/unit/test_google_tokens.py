import pytest

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


@pytest.mark.asyncio
async def test_get_google_calendar_token_returns_none_when_not_connected(monkeypatch):
    """還沒連接 → 回傳 None，由呼叫端決定怎麼處理。"""
    async def mock_find_one(query):
        return None

    monkeypatch.setattr(google_tokens.db.googleCalendarTokens, "find_one", mock_find_one)

    assert await google_tokens.get_google_calendar_token("uid123") is None
