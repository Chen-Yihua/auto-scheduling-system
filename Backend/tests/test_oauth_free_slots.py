import pytest
import httpx
from fastapi import HTTPException
from pymongo.errors import PyMongoError

import cache
import crud.oauth as oauth_crud


@pytest.fixture(autouse=True)
def clear_free_slots_cache():
    """get_free_slots_for_user 現在會寫快取，清乾淨避免測試之間互相汙染。"""
    cache._memory_store.clear()
    yield
    cache._memory_store.clear()


@pytest.mark.asyncio
async def test_get_free_slots_happy_path(monkeypatch):
    async def mock_find_one(query):
        return {"_id": "uid123", "access_token": "valid-token"}

    async def mock_fetch_calendar_list(token):
        assert token == "valid-token"
        return [{"id": "primary-cal-id", "primary": True}]

    async def mock_fetch_freebusy(token, calendar_id):
        assert calendar_id == "primary-cal-id"
        return {
            "timeMin": "2026-09-10T00:00:00Z",
            "timeMax": "2026-09-17T00:00:00Z",
            "calendars": {"primary-cal-id": {"busy": [{"start": "2026-09-10T09:00:00Z", "end": "2026-09-10T10:00:00Z"}]}},
        }

    monkeypatch.setattr(oauth_crud.db.googleCalendarTokens, "find_one", mock_find_one)
    monkeypatch.setattr(oauth_crud, "fetch_google_calendar_list", mock_fetch_calendar_list)
    monkeypatch.setattr(oauth_crud, "fetch_freebusy", mock_fetch_freebusy)

    result = await oauth_crud.get_free_slots_for_user("uid123")

    assert isinstance(result, list)
    assert result[0]["start"] == "2026-09-10T00:00:00Z"
    assert result[0]["end"] == "2026-09-10T09:00:00Z"


@pytest.mark.asyncio
async def test_get_free_slots_refreshes_token_on_401(monkeypatch):
    async def mock_find_one(query):
        return {"_id": "uid123", "access_token": "expired-token", "refresh_token": "rt"}

    calls = {"n": 0}

    async def mock_fetch_calendar_list(token):
        calls["n"] += 1
        if token == "expired-token":
            request = httpx.Request("GET", "https://example.com")
            response = httpx.Response(401, request=request)
            raise httpx.HTTPStatusError("Unauthorized", request=request, response=response)
        return [{"id": "primary-cal-id", "primary": True}]

    async def mock_refresh(clerk_id):
        return "new-token"

    async def mock_fetch_freebusy(token, calendar_id):
        assert token == "new-token"
        return {
            "timeMin": "2026-09-10T00:00:00Z",
            "timeMax": "2026-09-17T00:00:00Z",
            "calendars": {"primary-cal-id": {"busy": []}},
        }

    monkeypatch.setattr(oauth_crud.db.googleCalendarTokens, "find_one", mock_find_one)
    monkeypatch.setattr(oauth_crud, "fetch_google_calendar_list", mock_fetch_calendar_list)
    monkeypatch.setattr(oauth_crud, "refresh_google_calendar_token", mock_refresh)
    monkeypatch.setattr(oauth_crud, "fetch_freebusy", mock_fetch_freebusy)

    result = await oauth_crud.get_free_slots_for_user("uid123")

    assert calls["n"] == 2  # 第一次拿到 401，refresh 後重打一次
    assert result[0]["start"] == "2026-09-10T00:00:00Z"
    assert result[0]["end"] == "2026-09-17T00:00:00Z"


@pytest.mark.asyncio
async def test_get_free_slots_raises_404_when_no_primary_calendar(monkeypatch):
    async def mock_find_one(query):
        return {"_id": "uid123", "access_token": "valid-token"}

    async def mock_fetch_calendar_list(token):
        return [{"id": "some-other-cal", "primary": False}]

    monkeypatch.setattr(oauth_crud.db.googleCalendarTokens, "find_one", mock_find_one)
    monkeypatch.setattr(oauth_crud, "fetch_google_calendar_list", mock_fetch_calendar_list)

    with pytest.raises(HTTPException) as exc_info:
        await oauth_crud.get_free_slots_for_user("uid123")

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_get_free_slots_raises_400_when_not_connected(monkeypatch):
    # 尚未連接 Google Calendar 用 400（跟 github.py/jira.py「尚未連結帳號」對齊），
    # 跟「連過但憑證失效」的 401 分開
    async def mock_find_one(query):
        return None

    monkeypatch.setattr(oauth_crud.db.googleCalendarTokens, "find_one", mock_find_one)

    with pytest.raises(HTTPException) as exc_info:
        await oauth_crud.get_free_slots_for_user("uid123")

    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_get_google_calendar_token_raises_503_when_db_down(monkeypatch):
    async def mock_find_one(query):
        raise PyMongoError("connection lost")

    monkeypatch.setattr(oauth_crud.db.googleCalendarTokens, "find_one", mock_find_one)

    with pytest.raises(HTTPException) as exc_info:
        await oauth_crud.get_google_calendar_token("uid123")

    assert exc_info.value.status_code == 503


@pytest.mark.asyncio
async def test_is_google_calendar_connected_raises_503_when_db_down(monkeypatch):
    async def mock_find_one(query):
        raise PyMongoError("connection lost")

    monkeypatch.setattr(oauth_crud.db.googleCalendarTokens, "find_one", mock_find_one)

    with pytest.raises(HTTPException) as exc_info:
        await oauth_crud.is_google_calendar_connected("uid123")

    assert exc_info.value.status_code == 503


@pytest.mark.asyncio
async def test_get_free_slots_raises_502_when_google_unreachable(monkeypatch):
    # 網路連不上 Google（DNS/逾時/連線被拒...）是 httpx.RequestError，
    # 跟「Google 有回應但狀態碼是錯的」httpx.HTTPStatusError 是不同情況，
    # 502 = 連不上上游服務，不該跟其他情況共用同一個 400
    async def mock_find_one(query):
        return {"_id": "uid123", "access_token": "valid-token"}

    async def mock_fetch_calendar_list(token):
        raise httpx.ConnectError("Google 掛了")

    monkeypatch.setattr(oauth_crud.db.googleCalendarTokens, "find_one", mock_find_one)
    monkeypatch.setattr(oauth_crud, "fetch_google_calendar_list", mock_fetch_calendar_list)

    with pytest.raises(HTTPException) as exc_info:
        await oauth_crud.get_free_slots_for_user("uid123")

    assert exc_info.value.status_code == 502


@pytest.mark.asyncio
async def test_is_google_calendar_connected_true_when_token_stored(monkeypatch):
    async def mock_find_one(query):
        return {"_id": "uid123", "access_token": "valid-token"}

    monkeypatch.setattr(oauth_crud.db.googleCalendarTokens, "find_one", mock_find_one)

    assert await oauth_crud.is_google_calendar_connected("uid123") is True


@pytest.mark.asyncio
async def test_is_google_calendar_connected_false_when_no_doc(monkeypatch):
    async def mock_find_one(query):
        return None

    monkeypatch.setattr(oauth_crud.db.googleCalendarTokens, "find_one", mock_find_one)

    assert await oauth_crud.is_google_calendar_connected("uid123") is False


@pytest.mark.asyncio
async def test_is_google_calendar_connected_false_when_doc_has_no_access_token(monkeypatch):
    # 理論上不該發生，但 doc 存在卻沒有 access_token 時也該當作沒連接
    async def mock_find_one(query):
        return {"_id": "uid123", "access_token": None}

    monkeypatch.setattr(oauth_crud.db.googleCalendarTokens, "find_one", mock_find_one)

    assert await oauth_crud.is_google_calendar_connected("uid123") is False


@pytest.mark.asyncio
async def test_get_free_slots_second_call_within_ttl_uses_cache_not_live_api(monkeypatch):
    calendar_list_calls = {"n": 0}
    freebusy_calls = {"n": 0}

    async def mock_find_one(query):
        return {"_id": "uid123", "access_token": "valid-token"}

    async def mock_fetch_calendar_list(token):
        calendar_list_calls["n"] += 1
        return [{"id": "primary-cal-id", "primary": True}]

    async def mock_fetch_freebusy(token, calendar_id):
        freebusy_calls["n"] += 1
        return {
            "timeMin": "2026-09-10T00:00:00Z",
            "timeMax": "2026-09-17T00:00:00Z",
            "calendars": {"primary-cal-id": {"busy": []}},
        }

    monkeypatch.setattr(oauth_crud.db.googleCalendarTokens, "find_one", mock_find_one)
    monkeypatch.setattr(oauth_crud, "fetch_google_calendar_list", mock_fetch_calendar_list)
    monkeypatch.setattr(oauth_crud, "fetch_freebusy", mock_fetch_freebusy)

    first = await oauth_crud.get_free_slots_for_user("uid123")
    second = await oauth_crud.get_free_slots_for_user("uid123")

    assert first == second
    # 第二次應該直接用快取，完全不該再打 Google API
    assert calendar_list_calls["n"] == 1
    assert freebusy_calls["n"] == 1


@pytest.mark.asyncio
async def test_get_free_slots_different_users_have_independent_cache(monkeypatch):
    async def mock_find_one(query):
        return {"_id": query["_id"], "access_token": "valid-token"}

    async def mock_fetch_calendar_list(token):
        return [{"id": "primary-cal-id", "primary": True}]

    call_count = {"n": 0}

    async def mock_fetch_freebusy(token, calendar_id):
        call_count["n"] += 1
        return {
            "timeMin": "2026-09-10T00:00:00Z",
            "timeMax": "2026-09-17T00:00:00Z",
            "calendars": {"primary-cal-id": {"busy": []}},
        }

    monkeypatch.setattr(oauth_crud.db.googleCalendarTokens, "find_one", mock_find_one)
    monkeypatch.setattr(oauth_crud, "fetch_google_calendar_list", mock_fetch_calendar_list)
    monkeypatch.setattr(oauth_crud, "fetch_freebusy", mock_fetch_freebusy)

    await oauth_crud.get_free_slots_for_user("uid123")
    await oauth_crud.get_free_slots_for_user("uid456")

    # 不同使用者不該共用同一份快取
    assert call_count["n"] == 2


# ========== save_google_calendar_token ==========

@pytest.mark.asyncio
async def test_save_google_calendar_token_success(monkeypatch):
    saved = {}

    async def mock_update_one(filter, update, upsert=False):
        saved["filter"] = filter
        saved["doc"] = update["$set"]
        return None

    monkeypatch.setattr(oauth_crud.db.googleCalendarTokens, "update_one", mock_update_one)

    result = await oauth_crud.save_google_calendar_token("uid123", "access-tok", "refresh-tok")

    assert result == {"message": "Google Token 儲存成功"}
    assert saved["filter"] == {"_id": "uid123"}
    assert saved["doc"]["access_token"] == "access-tok"
    assert saved["doc"]["refresh_token"] == "refresh-tok"


@pytest.mark.asyncio
async def test_save_google_calendar_token_raises_503_when_db_down(monkeypatch):
    async def mock_update_one(filter, update, upsert=False):
        raise PyMongoError("connection lost")

    monkeypatch.setattr(oauth_crud.db.googleCalendarTokens, "update_one", mock_update_one)

    with pytest.raises(HTTPException) as exc_info:
        await oauth_crud.save_google_calendar_token("uid123", "access-tok", "refresh-tok")

    assert exc_info.value.status_code == 503


# ========== refresh_google_calendar_token：其餘分支 ==========

@pytest.mark.asyncio
async def test_refresh_google_calendar_token_raises_503_when_db_down_on_lookup(monkeypatch):
    async def mock_find_one(query):
        raise PyMongoError("connection lost")

    monkeypatch.setattr(oauth_crud.db.googleCalendarTokens, "find_one", mock_find_one)

    with pytest.raises(HTTPException) as exc_info:
        await oauth_crud.refresh_google_calendar_token("uid123")

    assert exc_info.value.status_code == 503


@pytest.mark.asyncio
async def test_refresh_google_calendar_token_raises_401_when_no_refresh_token_stored(monkeypatch):
    async def mock_find_one(query):
        return {"_id": "uid123"}  # 沒有 refresh_token 欄位

    monkeypatch.setattr(oauth_crud.db.googleCalendarTokens, "find_one", mock_find_one)

    with pytest.raises(HTTPException) as exc_info:
        await oauth_crud.refresh_google_calendar_token("uid123")

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_refresh_google_calendar_token_raises_502_when_google_unreachable(monkeypatch):
    async def mock_find_one(query):
        return {"_id": "uid123", "refresh_token": "old-rt"}

    class FailingClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            pass

        async def post(self, *a, **k):
            raise httpx.ConnectError("Google 掛了")

    monkeypatch.setattr(oauth_crud.db.googleCalendarTokens, "find_one", mock_find_one)
    monkeypatch.setattr(oauth_crud.httpx, "AsyncClient", lambda: FailingClient())

    with pytest.raises(HTTPException) as exc_info:
        await oauth_crud.refresh_google_calendar_token("uid123")

    assert exc_info.value.status_code == 502


@pytest.mark.asyncio
async def test_refresh_google_calendar_token_still_401s_when_cleanup_delete_fails(monkeypatch):
    # Google 拒絕 refresh_token 之後，清除 DB 舊紀錄這一步本身也可能失敗
    # （DB 剛好也斷線）——就算清不掉，還是要讓使用者看到「請重新連接」的 401，
    # 不能讓一個次要的清理動作失敗，蓋掉主要的錯誤訊息
    async def mock_find_one(query):
        return {"_id": "uid123", "refresh_token": "revoked-rt"}

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

    monkeypatch.setattr(oauth_crud.db.googleCalendarTokens, "find_one", mock_find_one)
    monkeypatch.setattr(oauth_crud.db.googleCalendarTokens, "delete_one", mock_delete_one)
    monkeypatch.setattr(oauth_crud.httpx, "AsyncClient", lambda: MockClient())

    with pytest.raises(HTTPException) as exc_info:
        await oauth_crud.refresh_google_calendar_token("uid123")

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_refresh_google_calendar_token_raises_400_when_google_response_missing_access_token(monkeypatch):
    async def mock_find_one(query):
        return {"_id": "uid123", "refresh_token": "old-rt"}

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

    monkeypatch.setattr(oauth_crud.db.googleCalendarTokens, "find_one", mock_find_one)
    monkeypatch.setattr(oauth_crud.httpx, "AsyncClient", lambda: MockClient())

    with pytest.raises(HTTPException) as exc_info:
        await oauth_crud.refresh_google_calendar_token("uid123")

    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_refresh_google_calendar_token_raises_503_when_saving_new_token_fails(monkeypatch):
    async def mock_find_one(query):
        return {"_id": "uid123", "refresh_token": "old-rt"}

    async def mock_update_one(*a, **k):
        raise PyMongoError("connection lost")

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

        async def post(self, *a, **k):
            return MockResponse()

    monkeypatch.setattr(oauth_crud.db.googleCalendarTokens, "find_one", mock_find_one)
    monkeypatch.setattr(oauth_crud.db.googleCalendarTokens, "update_one", mock_update_one)
    monkeypatch.setattr(oauth_crud.httpx, "AsyncClient", lambda: MockClient())

    with pytest.raises(HTTPException) as exc_info:
        await oauth_crud.refresh_google_calendar_token("uid123")

    assert exc_info.value.status_code == 503


# ========== get_free_slots_for_user：其餘分支 ==========

@pytest.mark.asyncio
async def test_get_free_slots_raises_400_on_non_401_status_error(monkeypatch):
    async def mock_find_one(query):
        return {"_id": "uid123", "access_token": "valid-token"}

    async def mock_fetch_calendar_list(token):
        request = httpx.Request("GET", "https://example.com")
        response = httpx.Response(500, request=request)
        raise httpx.HTTPStatusError("error", request=request, response=response)

    monkeypatch.setattr(oauth_crud.db.googleCalendarTokens, "find_one", mock_find_one)
    monkeypatch.setattr(oauth_crud, "fetch_google_calendar_list", mock_fetch_calendar_list)

    with pytest.raises(HTTPException) as exc_info:
        await oauth_crud.get_free_slots_for_user("uid123")

    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_get_free_slots_raises_502_when_freebusy_unreachable(monkeypatch):
    async def mock_find_one(query):
        return {"_id": "uid123", "access_token": "valid-token"}

    async def mock_fetch_calendar_list(token):
        return [{"id": "primary-cal-id", "primary": True}]

    async def mock_fetch_freebusy(token, calendar_id):
        raise httpx.ConnectError("Google 掛了")

    monkeypatch.setattr(oauth_crud.db.googleCalendarTokens, "find_one", mock_find_one)
    monkeypatch.setattr(oauth_crud, "fetch_google_calendar_list", mock_fetch_calendar_list)
    monkeypatch.setattr(oauth_crud, "fetch_freebusy", mock_fetch_freebusy)

    with pytest.raises(HTTPException) as exc_info:
        await oauth_crud.get_free_slots_for_user("uid123")

    assert exc_info.value.status_code == 502
