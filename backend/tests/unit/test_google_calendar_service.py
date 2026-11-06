"""token 換新和錯誤處理由各功能共用，這裡透過 get_free_slots_for_user 測試。"""
import pytest
from core.errors import ExternalServiceError, InvalidRequestError, NotFoundError, ReauthRequiredError
import httpx
from datetime import datetime, timezone
from cryptography.fernet import Fernet

from core import cache
from core.crypto import encrypt_secret
import crud.google_tokens as google_tokens
import services.google_calendar as calendar_service


# ========== get_free_slots_for_user ==========

@pytest.fixture(autouse=True)
def clear_free_slots_cache():
    """get_free_slots_for_user 現在會寫快取，清乾淨避免測試之間互相汙染。"""
    cache._memory_store.clear()
    yield
    cache._memory_store.clear()


@pytest.mark.asyncio
async def test_get_free_slots_happy_path(monkeypatch):
    """成功流程：找到 primary 行事曆並回傳忙碌時段以外的空檔。"""
    async def mock_find_one(query):
        return {"_id": "uid123", "access_token": encrypt_secret("valid-token")}

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

    monkeypatch.setattr(google_tokens.db.googleCalendarTokens, "find_one", mock_find_one)
    monkeypatch.setattr(calendar_service, "fetch_google_calendar_list", mock_fetch_calendar_list)
    monkeypatch.setattr(calendar_service, "fetch_freebusy", mock_fetch_freebusy)

    result = await calendar_service.get_free_slots_for_user("uid123")

    assert isinstance(result, list)
    assert result[0]["start"] == "2026-09-10T00:00:00Z"
    assert result[0]["end"] == "2026-09-10T09:00:00Z"


@pytest.mark.asyncio
async def test_get_free_slots_refreshes_token_on_401(monkeypatch):
    """token 過期（401）→ 換新後重試，之後的請求用新 token。"""
    async def mock_find_one(query):
        return {"_id": "uid123", "access_token": encrypt_secret("expired-token"), "refresh_token": encrypt_secret("rt")}

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

    monkeypatch.setattr(google_tokens.db.googleCalendarTokens, "find_one", mock_find_one)
    monkeypatch.setattr(calendar_service, "fetch_google_calendar_list", mock_fetch_calendar_list)
    monkeypatch.setattr(calendar_service, "refresh_google_calendar_token", mock_refresh)
    monkeypatch.setattr(calendar_service, "fetch_freebusy", mock_fetch_freebusy)

    result = await calendar_service.get_free_slots_for_user("uid123")

    assert calls["n"] == 2  # 第一次拿到 401，refresh 後重打一次
    assert result[0]["start"] == "2026-09-10T00:00:00Z"
    assert result[0]["end"] == "2026-09-17T00:00:00Z"


@pytest.mark.asyncio
async def test_get_free_slots_raises_404_when_no_primary_calendar(monkeypatch):
    """行事曆清單裡沒有 primary → 404。"""
    async def mock_find_one(query):
        return {"_id": "uid123", "access_token": encrypt_secret("valid-token")}

    async def mock_fetch_calendar_list(token):
        return [{"id": "some-other-cal", "primary": False}]

    monkeypatch.setattr(google_tokens.db.googleCalendarTokens, "find_one", mock_find_one)
    monkeypatch.setattr(calendar_service, "fetch_google_calendar_list", mock_fetch_calendar_list)

    with pytest.raises(NotFoundError):
        await calendar_service.get_free_slots_for_user("uid123")



@pytest.mark.asyncio
async def test_get_free_slots_raises_400_when_not_connected(monkeypatch):
    """尚未連接 Google Calendar → 400，和憑證失效的 401 區分。"""
    async def mock_find_one(query):
        return None

    monkeypatch.setattr(google_tokens.db.googleCalendarTokens, "find_one", mock_find_one)

    with pytest.raises(InvalidRequestError):
        await calendar_service.get_free_slots_for_user("uid123")



@pytest.mark.asyncio
async def test_get_free_slots_raises_502_when_google_unreachable(monkeypatch):
    """連不上 Google（網路、DNS、逾時等）→ 502，跟「Google 有回應、但回了錯誤」的 400 分開。"""
    async def mock_find_one(query):
        return {"_id": "uid123", "access_token": encrypt_secret("valid-token")}

    async def mock_fetch_calendar_list(token):
        raise httpx.ConnectError("Google 掛了")

    monkeypatch.setattr(google_tokens.db.googleCalendarTokens, "find_one", mock_find_one)
    monkeypatch.setattr(calendar_service, "fetch_google_calendar_list", mock_fetch_calendar_list)

    with pytest.raises(ExternalServiceError):
        await calendar_service.get_free_slots_for_user("uid123")



@pytest.mark.asyncio
async def test_get_free_slots_second_call_within_ttl_uses_cache_not_live_api(monkeypatch):
    """短時間內重複查詢空檔：第二次要直接用快取，不再打 Google API。"""
    calendar_list_calls = {"n": 0}
    freebusy_calls = {"n": 0}

    async def mock_find_one(query):
        return {"_id": "uid123", "access_token": encrypt_secret("valid-token")}

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

    monkeypatch.setattr(google_tokens.db.googleCalendarTokens, "find_one", mock_find_one)
    monkeypatch.setattr(calendar_service, "fetch_google_calendar_list", mock_fetch_calendar_list)
    monkeypatch.setattr(calendar_service, "fetch_freebusy", mock_fetch_freebusy)

    first = await calendar_service.get_free_slots_for_user("uid123")
    second = await calendar_service.get_free_slots_for_user("uid123")

    assert first == second
    # 第二次應該直接用快取，完全不該再打 Google API
    assert calendar_list_calls["n"] == 1
    assert freebusy_calls["n"] == 1


@pytest.mark.asyncio
async def test_get_free_slots_different_users_have_independent_cache(monkeypatch):
    """不同使用者的快取要各自獨立，不能共用同一份。"""
    async def mock_find_one(query):
        return {"_id": query["_id"], "access_token": encrypt_secret("valid-token")}

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

    monkeypatch.setattr(google_tokens.db.googleCalendarTokens, "find_one", mock_find_one)
    monkeypatch.setattr(calendar_service, "fetch_google_calendar_list", mock_fetch_calendar_list)
    monkeypatch.setattr(calendar_service, "fetch_freebusy", mock_fetch_freebusy)

    await calendar_service.get_free_slots_for_user("uid123")
    await calendar_service.get_free_slots_for_user("uid456")

    # 不同使用者不該共用同一份快取
    assert call_count["n"] == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("google_status, expected", [
    (500, ExternalServiceError), (429, ExternalServiceError), (403, InvalidRequestError),
])
async def test_get_free_slots_maps_google_calendar_list_errors(monkeypatch, google_status, expected):
    """取得行事曆清單時 Google 回 5xx 或 429 → 502（對方的問題）；其他 4xx → 400。"""
    async def mock_find_one(query):
        return {"_id": "uid123", "access_token": encrypt_secret("valid-token")}

    async def mock_fetch_calendar_list(token):
        request = httpx.Request("GET", "https://example.com")
        response = httpx.Response(google_status, request=request)
        raise httpx.HTTPStatusError("error", request=request, response=response)

    monkeypatch.setattr(google_tokens.db.googleCalendarTokens, "find_one", mock_find_one)
    monkeypatch.setattr(calendar_service, "fetch_google_calendar_list", mock_fetch_calendar_list)

    with pytest.raises(expected):
        await calendar_service.get_free_slots_for_user("uid123")


@pytest.mark.asyncio
async def test_get_free_slots_raises_502_when_freebusy_returns_server_error(monkeypatch):
    """查忙碌時段時 Google 回 5xx → 502，不是沒被處理的 500。"""
    async def mock_find_one(query):
        return {"_id": "uid123", "access_token": encrypt_secret("valid-token")}

    async def mock_fetch_calendar_list(token):
        return [{"id": "primary-cal-id", "primary": True}]

    async def mock_fetch_freebusy(token, calendar_id):
        request = httpx.Request("POST", "https://example.com")
        raise httpx.HTTPStatusError("error", request=request, response=httpx.Response(503, request=request))

    monkeypatch.setattr(google_tokens.db.googleCalendarTokens, "find_one", mock_find_one)
    monkeypatch.setattr(calendar_service, "fetch_google_calendar_list", mock_fetch_calendar_list)
    monkeypatch.setattr(calendar_service, "fetch_freebusy", mock_fetch_freebusy)

    with pytest.raises(ExternalServiceError):
        await calendar_service.get_free_slots_for_user("uid123")



@pytest.mark.asyncio
async def test_get_free_slots_raises_502_when_freebusy_unreachable(monkeypatch):
    """查忙碌時段時連不上 Google → 502。"""
    async def mock_find_one(query):
        return {"_id": "uid123", "access_token": encrypt_secret("valid-token")}

    async def mock_fetch_calendar_list(token):
        return [{"id": "primary-cal-id", "primary": True}]

    async def mock_fetch_freebusy(token, calendar_id):
        raise httpx.ConnectError("Google 掛了")

    monkeypatch.setattr(google_tokens.db.googleCalendarTokens, "find_one", mock_find_one)
    monkeypatch.setattr(calendar_service, "fetch_google_calendar_list", mock_fetch_calendar_list)
    monkeypatch.setattr(calendar_service, "fetch_freebusy", mock_fetch_freebusy)

    with pytest.raises(ExternalServiceError):
        await calendar_service.get_free_slots_for_user("uid123")



def _encrypt_with_other_key(plain: str) -> str:
    """用另一把 SECRET_ENCRYPTION_KEY 加密，模擬另一個環境寫進共用 DB 的 token。"""
    return Fernet(Fernet.generate_key()).encrypt(plain.encode()).decode()


def _unauthorized_error() -> httpx.HTTPStatusError:
    request = httpx.Request("GET", "https://example.com")
    return httpx.HTTPStatusError("Unauthorized", request=request, response=httpx.Response(401, request=request))


@pytest.mark.asyncio
async def test_get_free_slots_requires_reauth_when_access_token_cannot_be_decrypted(monkeypatch):
    """AC2(b)：存的 access token 解不開 → 401 請使用者重新連接，不是沒被處理的 500；不刪 token。"""
    async def mock_find_one(query):
        return {"_id": "uid123", "access_token": _encrypt_with_other_key("at"), "refresh_token": encrypt_secret("rt")}

    deleted = []

    async def mock_delete_one(query):
        deleted.append(query)

    monkeypatch.setattr(google_tokens.db.googleCalendarTokens, "find_one", mock_find_one)
    monkeypatch.setattr(google_tokens.db.googleCalendarTokens, "delete_one", mock_delete_one)

    with pytest.raises(ReauthRequiredError, match="重新連接 Google Calendar"):
        await calendar_service.get_free_slots_for_user("uid123")

    assert deleted == []


@pytest.mark.asyncio
async def test_get_free_slots_requires_reauth_when_refresh_token_cannot_be_decrypted(monkeypatch):
    """AC2(b)：access token 過期、要換新時 refresh token 解不開 → 401 請使用者重新連接；不刪 token。"""
    async def mock_find_one(query):
        return {"_id": "uid123", "access_token": encrypt_secret("expired-token"), "refresh_token": _encrypt_with_other_key("rt")}

    async def mock_fetch_calendar_list(token):
        raise _unauthorized_error()

    deleted = []

    async def mock_delete_one(query):
        deleted.append(query)

    monkeypatch.setattr(google_tokens.db.googleCalendarTokens, "find_one", mock_find_one)
    monkeypatch.setattr(google_tokens.db.googleCalendarTokens, "delete_one", mock_delete_one)
    monkeypatch.setattr(calendar_service, "fetch_google_calendar_list", mock_fetch_calendar_list)

    with pytest.raises(ReauthRequiredError, match="重新連接 Google Calendar"):
        await calendar_service.get_free_slots_for_user("uid123")

    assert deleted == []


@pytest.mark.asyncio
async def test_get_free_slots_requires_reauth_when_calendar_list_still_401_after_refresh(monkeypatch):
    """AC2(c)：換新 token 後重試行事曆列表，Google 還是回 401 → 401 請使用者重新連接，不是沒被處理的 500。"""
    async def mock_find_one(query):
        return {"_id": "uid123", "access_token": encrypt_secret("expired-token"), "refresh_token": encrypt_secret("rt")}

    calls = []

    async def mock_fetch_calendar_list(token):
        calls.append(token)
        raise _unauthorized_error()

    async def mock_refresh(clerk_id):
        return "new-token"

    monkeypatch.setattr(google_tokens.db.googleCalendarTokens, "find_one", mock_find_one)
    monkeypatch.setattr(calendar_service, "fetch_google_calendar_list", mock_fetch_calendar_list)
    monkeypatch.setattr(calendar_service, "refresh_google_calendar_token", mock_refresh)

    with pytest.raises(ReauthRequiredError, match="重新連接 Google Calendar"):
        await calendar_service.get_free_slots_for_user("uid123")

    assert calls == ["expired-token", "new-token"]


# ========== list_calendars_for_user ==========

@pytest.mark.asyncio
async def test_list_calendars_returns_all_calendars_not_only_primary(monkeypatch):
    """/oauth/calendars 用：回傳完整的行事曆列表，不是只有 primary。"""
    calendars = [{"id": "primary-cal-id", "primary": True}, {"id": "work-cal-id"}]

    async def mock_find_one(query):
        return {"_id": "uid123", "access_token": encrypt_secret("valid-token")}

    async def mock_fetch_calendar_list(token):
        assert token == "valid-token"
        return calendars

    monkeypatch.setattr(google_tokens.db.googleCalendarTokens, "find_one", mock_find_one)
    monkeypatch.setattr(calendar_service, "fetch_google_calendar_list", mock_fetch_calendar_list)

    assert await calendar_service.list_calendars_for_user("uid123") == calendars


# ========== create_calendar_events_for_scheduled_tasks ==========

def _scheduled_task(task_id, title="任務", start=None, end=None):
    return {
        "task_id": task_id,
        "title": title,
        "priority": "High",
        "start": start or datetime(2026, 9, 10, 9, 0, tzinfo=timezone.utc),
        "end": end or datetime(2026, 9, 10, 10, 0, tzinfo=timezone.utc),
    }


def _mock_token_and_primary_calendar(monkeypatch, calendar_id="primary-cal-id"):
    async def mock_find_one(query):
        return {"_id": "uid123", "access_token": encrypt_secret("valid-token")}

    async def mock_fetch_calendar_list(token):
        return [{"id": calendar_id, "primary": True}]

    monkeypatch.setattr(google_tokens.db.googleCalendarTokens, "find_one", mock_find_one)
    monkeypatch.setattr(calendar_service, "fetch_google_calendar_list", mock_fetch_calendar_list)


@pytest.mark.asyncio
async def test_create_calendar_events_returns_empty_result_without_calling_google_when_no_scheduled_tasks(monkeypatch):
    """沒有任何「已排入時段」的任務 → 直接回空結果，完全不打 Google API。"""
    async def fail_if_called(*args, **kwargs):
        raise AssertionError("不該呼叫 Google API")

    monkeypatch.setattr(calendar_service, "fetch_google_calendar_list", fail_if_called)

    result = await calendar_service.create_calendar_events_for_scheduled_tasks("uid123", [])

    assert result == {"confirmed": [], "failed": []}


@pytest.mark.asyncio
async def test_create_calendar_events_success_writes_calendar_event_id(monkeypatch):
    """成功建立事件 → 回傳 confirmed 清單，並把 calendar_event_id 存回對應任務。"""
    _mock_token_and_primary_calendar(monkeypatch)

    captured_calls = []

    async def mock_create_event(access_token, calendar_id, summary, start, end):
        captured_calls.append((access_token, calendar_id, summary, start, end))
        return {"id": f"event-{summary}"}

    saved = {}

    async def mock_set_calendar_event_id_for_composite(user_id, task_id, calendar_event_id):
        saved[task_id] = (user_id, calendar_event_id)

    monkeypatch.setattr(calendar_service, "create_calendar_event", mock_create_event)
    monkeypatch.setattr(calendar_service, "set_calendar_event_id_for_composite", mock_set_calendar_event_id_for_composite)

    scheduled = [_scheduled_task("t1", title="寫報告")]
    result = await calendar_service.create_calendar_events_for_scheduled_tasks("uid123", scheduled)

    assert result == {
        "confirmed": [{"task_id": "t1", "title": "寫報告", "calendar_event_id": "event-寫報告"}],
        "failed": [],
    }
    assert saved["t1"] == ("uid123", "event-寫報告")
    # start/end 要轉成 Google API 要的 ISO 字串（帶 Z），不是原本的 datetime 物件
    assert captured_calls[0][3] == "2026-09-10T09:00:00Z"
    assert captured_calls[0][4] == "2026-09-10T10:00:00Z"


@pytest.mark.asyncio
async def test_create_calendar_events_partial_failure_keeps_successful_ones(monkeypatch):
    """一批裡有成功有失敗 → 各自進對應的清單，不會因為一筆失敗就整批放棄。"""
    _mock_token_and_primary_calendar(monkeypatch)

    async def mock_create_event(access_token, calendar_id, summary, start, end):
        if summary == "會失敗的任務":
            request = httpx.Request("POST", "https://example.com")
            response = httpx.Response(500, request=request)
            raise httpx.HTTPStatusError("error", request=request, response=response)
        return {"id": "event-ok"}

    async def mock_set_calendar_event_id_for_composite(user_id, task_id, calendar_event_id):
        pass

    monkeypatch.setattr(calendar_service, "create_calendar_event", mock_create_event)
    monkeypatch.setattr(calendar_service, "set_calendar_event_id_for_composite", mock_set_calendar_event_id_for_composite)

    scheduled = [
        _scheduled_task("t1", title="會成功的任務"),
        _scheduled_task("t2", title="會失敗的任務"),
    ]
    result = await calendar_service.create_calendar_events_for_scheduled_tasks("uid123", scheduled)

    assert len(result["confirmed"]) == 1
    assert result["confirmed"][0]["task_id"] == "t1"
    assert len(result["failed"]) == 1
    assert result["failed"][0]["task_id"] == "t2"
    assert result["failed"][0]["reason"]


@pytest.mark.asyncio
async def test_create_calendar_events_network_error_marks_task_as_failed(monkeypatch):
    """連不上 Google（網路問題）→ 該筆進 failed，不會讓整個請求噴例外。"""
    _mock_token_and_primary_calendar(monkeypatch)

    async def mock_create_event(access_token, calendar_id, summary, start, end):
        raise httpx.ConnectError("Google 掛了")

    monkeypatch.setattr(calendar_service, "create_calendar_event", mock_create_event)

    result = await calendar_service.create_calendar_events_for_scheduled_tasks("uid123", [_scheduled_task("t1")])

    assert result["confirmed"] == []
    assert result["failed"][0]["task_id"] == "t1"


# ========== 階段任務：刪除還沒開始的事件 ==========

DELETE_NOW = datetime(2030, 1, 1, 12, 0, tzinfo=timezone.utc)


def _http_error(status):
    request = httpx.Request("GET", "https://example.com")
    return httpx.HTTPStatusError("error", request=request, response=httpx.Response(status, request=request))


def _event(start_iso):
    return {"id": "ev", "status": "confirmed", "start": {"dateTime": start_iso}, "end": {"dateTime": start_iso}}


@pytest.fixture
def google_events(monkeypatch):
    """假的 Google 事件：events 是 event_id → 事件或要丟的例外；記錄實際刪掉哪些。"""
    state = {"events": {}, "delete_errors": {}, "deleted": []}
    _mock_token_and_primary_calendar(monkeypatch)

    async def mock_get_event(access_token, calendar_id, event_id):
        value = state["events"][event_id]
        if isinstance(value, Exception):
            raise value
        return value

    async def mock_delete_event(access_token, calendar_id, event_id):
        error = state["delete_errors"].get(event_id)
        if error:
            raise error
        state["deleted"].append(event_id)

    monkeypatch.setattr(calendar_service, "get_calendar_event", mock_get_event)
    monkeypatch.setattr(calendar_service, "delete_calendar_event", mock_delete_event)
    return state


@pytest.mark.asyncio
async def test_ac28_only_events_that_have_not_started_are_deleted(google_events):
    """AC28：還沒開始的事件刪掉；已經開始或已經過去的事件保留。回傳真的刪掉的事件，呼叫端靠它判斷要不要清 calendar_event_id。"""
    google_events["events"] = {
        "future": _event("2030-01-02T09:00:00Z"),
        "started": _event("2030-01-01T11:30:00Z"),
        "past": _event("2029-12-30T09:00:00Z"),
    }

    deleted = await calendar_service.delete_upcoming_calendar_events("uid123", ["future", "started", "past"], now=DELETE_NOW)

    assert google_events["deleted"] == deleted == ["future"]


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [404, 410])
async def test_ac31_event_already_gone_counts_as_deleted(google_events, status):
    """AC31：查詢或刪除時 Google 回 404 / 410（事件已經不存在）→ 當作刪除成功，不丟錯誤。"""
    google_events["events"] = {"gone": _http_error(status), "racing": _event("2030-01-02T09:00:00Z")}
    google_events["delete_errors"] = {"racing": _http_error(status)}

    await calendar_service.delete_upcoming_calendar_events("uid123", ["gone", "racing"], now=DELETE_NOW)


@pytest.mark.asyncio
async def test_ac32_not_connected_requires_reconnect(monkeypatch):
    """AC32：需要刪事件但沒有連接 Google → 回 401 要求重新連接（前端沿用重新連接提示）。"""
    async def mock_find_one(query):
        return None

    monkeypatch.setattr(google_tokens.db.googleCalendarTokens, "find_one", mock_find_one)

    with pytest.raises(ReauthRequiredError):
        await calendar_service.delete_upcoming_calendar_events("uid123", ["ev-1"], now=DELETE_NOW)


@pytest.mark.asyncio
async def test_ac32_revoked_authorization_requires_reconnect(google_events):
    """AC32：Google 授權失效（刪事件時回 401）→ ReauthRequiredError。"""
    google_events["events"] = {"ev-1": _http_error(401)}

    with pytest.raises(ReauthRequiredError):
        await calendar_service.delete_upcoming_calendar_events("uid123", ["ev-1"], now=DELETE_NOW)


@pytest.mark.asyncio
@pytest.mark.parametrize("error", [_http_error(500), _http_error(429), httpx.ConnectError("連不上")])
async def test_ac33_failure_midway_asks_to_retry_and_keeps_already_deleted_events_deleted(google_events, error):
    """AC33：刪到一半 Google 5xx / 429 / 網路錯誤 → 丟 502 提示重試；已經刪掉的事件不復原。"""
    google_events["events"] = {"a": _event("2030-01-02T09:00:00Z"), "b": _event("2030-01-02T10:00:00Z")}
    google_events["delete_errors"] = {"b": error}

    with pytest.raises(ExternalServiceError) as exc_info:
        await calendar_service.delete_upcoming_calendar_events("uid123", ["a", "b"], now=DELETE_NOW)

    assert "重試" in exc_info.value.detail
    assert google_events["deleted"] == ["a"]


@pytest.mark.asyncio
async def test_no_events_to_delete_does_not_call_google(monkeypatch):
    """假設 11：要刪的子任務都沒有行事曆事件 → 完全不呼叫 Google，沒連接也能刪。"""
    async def fail_if_called(*args, **kwargs):
        raise AssertionError("不該呼叫 Google")

    monkeypatch.setattr(google_tokens.db.googleCalendarTokens, "find_one", fail_if_called)
    monkeypatch.setattr(calendar_service, "fetch_google_calendar_list", fail_if_called)

    await calendar_service.delete_upcoming_calendar_events("uid123", [], now=DELETE_NOW)


# ========== 階段任務：前一個階段事件的最新時間 ==========

@pytest.mark.asyncio
async def test_ac24_event_ends_come_from_google_and_missing_events_map_to_none(google_events):
    """AC24：事件的結束時間以 Google 上最新的為準；已不存在（404 / 410 / 已取消）的事件回 None。"""
    google_events["events"] = {
        "moved": {"status": "confirmed", "start": {"dateTime": "2030-01-02T13:00:00Z"}, "end": {"dateTime": "2030-01-02T14:30:00+08:00"}},
        "gone": _http_error(404),
        "cancelled": {"status": "cancelled"},
    }

    ends = await calendar_service.get_calendar_event_ends("uid123", ["moved", "gone", "cancelled"])

    assert ends == {
        "moved": datetime(2030, 1, 2, 6, 30, tzinfo=timezone.utc),
        "gone": None,
        "cancelled": None,
    }
