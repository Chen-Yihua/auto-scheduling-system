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
    """成功流程：取 token → 找 primary 行事曆 → 查忙碌時段 → 回傳空檔（忙碌時段之前的 00:00–09:00 是第一段空檔）。"""
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
    """取得行事曆清單時 token 過期（401）→ 自動 refresh 換新 token 後重打一次（共 2 次），後續查忙碌時段用的是新 token。"""
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
    """行事曆清單裡沒有 primary → 404。"""
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
    """尚未連接 Google Calendar → 400（跟 github/jira 的「尚未連結帳號」一致），跟「連過但憑證失效」的 401 分開。"""
    async def mock_find_one(query):
        return None

    monkeypatch.setattr(oauth_crud.db.googleCalendarTokens, "find_one", mock_find_one)

    with pytest.raises(HTTPException) as exc_info:
        await oauth_crud.get_free_slots_for_user("uid123")

    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_get_free_slots_raises_502_when_google_unreachable(monkeypatch):
    """連不上 Google（網路、DNS、逾時等）→ 502，跟「Google 有回應、但回了錯誤」的 400 分開。"""
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
    """資料庫有存 access token → 已連接（True）。"""
    async def mock_find_one(query):
        return {"_id": "uid123", "access_token": "valid-token"}

    monkeypatch.setattr(oauth_crud.db.googleCalendarTokens, "find_one", mock_find_one)

    assert await oauth_crud.is_google_calendar_connected("uid123") is True


@pytest.mark.asyncio
async def test_is_google_calendar_connected_false_when_no_doc(monkeypatch):
    """資料庫沒有這筆資料 → 未連接（False）。"""
    async def mock_find_one(query):
        return None

    monkeypatch.setattr(oauth_crud.db.googleCalendarTokens, "find_one", mock_find_one)

    assert await oauth_crud.is_google_calendar_connected("uid123") is False


@pytest.mark.asyncio
async def test_is_google_calendar_connected_false_when_doc_has_no_access_token(monkeypatch):
    """有這筆資料但 access_token 是空的（理論上不該發生）→ 也當作未連接。"""
    async def mock_find_one(query):
        return {"_id": "uid123", "access_token": None}

    monkeypatch.setattr(oauth_crud.db.googleCalendarTokens, "find_one", mock_find_one)

    assert await oauth_crud.is_google_calendar_connected("uid123") is False


@pytest.mark.asyncio
async def test_get_free_slots_second_call_within_ttl_uses_cache_not_live_api(monkeypatch):
    """短時間內重複查詢空檔：第二次要直接用快取，不再打 Google API。"""
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
    """不同使用者的快取要各自獨立，不能共用同一份。"""
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
    """儲存 Google token：把使用者的 access token 和 refresh token 存下來，並回傳成功訊息。"""
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


# ========== refresh_google_calendar_token：其餘分支 ==========

@pytest.mark.asyncio
async def test_refresh_google_calendar_token_raises_401_when_no_refresh_token_stored(monkeypatch):
    """資料庫裡沒有 refresh_token → 401，請使用者重新授權。"""
    async def mock_find_one(query):
        return {"_id": "uid123"}  # 沒有 refresh_token 欄位

    monkeypatch.setattr(oauth_crud.db.googleCalendarTokens, "find_one", mock_find_one)

    with pytest.raises(HTTPException) as exc_info:
        await oauth_crud.refresh_google_calendar_token("uid123")

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_refresh_google_calendar_token_raises_502_when_google_unreachable(monkeypatch):
    """refresh 時連不上 Google → 502。"""
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
    monkeypatch.setattr(oauth_crud.httpx, "AsyncClient", lambda *a, **kw: FailingClient())

    with pytest.raises(HTTPException) as exc_info:
        await oauth_crud.refresh_google_calendar_token("uid123")

    assert exc_info.value.status_code == 502


@pytest.mark.asyncio
async def test_refresh_google_calendar_token_still_401s_when_cleanup_delete_fails(monkeypatch):
    """Google 拒絕 refresh token 後，清掉資料庫舊紀錄這一步也失敗（資料庫剛好也斷線）→ 仍要回 401 請使用者重新連接；次要的清理失敗不能蓋掉主要的錯誤訊息。"""
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
    monkeypatch.setattr(oauth_crud.httpx, "AsyncClient", lambda *a, **kw: MockClient())

    with pytest.raises(HTTPException) as exc_info:
        await oauth_crud.refresh_google_calendar_token("uid123")

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_refresh_google_calendar_token_raises_400_when_google_response_missing_access_token(monkeypatch):
    """Google 回 200 但回應裡沒有 access_token → 400。"""
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
    monkeypatch.setattr(oauth_crud.httpx, "AsyncClient", lambda *a, **kw: MockClient())

    with pytest.raises(HTTPException) as exc_info:
        await oauth_crud.refresh_google_calendar_token("uid123")

    assert exc_info.value.status_code == 400


# ========== get_free_slots_for_user：其餘分支 ==========

@pytest.mark.asyncio
async def test_get_free_slots_raises_400_on_non_401_status_error(monkeypatch):
    """取得行事曆清單時 Google 回 401 以外的錯誤（例如 500）→ 400。"""
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
    """查忙碌時段時連不上 Google → 502。"""
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
