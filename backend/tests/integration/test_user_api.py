# 透過 HTTP 確認路由、登入驗證、回應格式和錯誤狀態碼；細部邏輯由 unit 測試負責
import pytest
import pytest_asyncio
from httpx import AsyncClient
from httpx._transports.asgi import ASGITransport
from unittest.mock import AsyncMock, patch

from main import app  # 假設 FastAPI app 是定義在 main.py 裡
from schemas.user import UserOut, UserCreate


@pytest.fixture
def fake_user_out():
    return UserOut(
        id="test_user_123",
        name="John Doe",
        email="john@example.com"
    )

@pytest.fixture
def fake_user_create():
    return UserCreate(
        clerk_id="test_user_123",
        name="John Doe",
        email="john@example.com"
    )


"""
測試get me
"""
@pytest.mark.asyncio
@patch("crud.user.get_user_by_clerk_id", new_callable=AsyncMock)
async def test_get_current_user_success(mock_get_user_by_clerk_id, fake_user_out, logged_in_user):
    """GET /users/me：回傳目前登入使用者的資料。"""
    mock_get_user_by_clerk_id.return_value = fake_user_out

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/users/me")

    assert response.status_code == 200
    assert response.json()["name"] == "John Doe"
    assert response.json()["email"] == "john@example.com"

@pytest.mark.asyncio
@patch("crud.user.get_user_by_clerk_id", new_callable=AsyncMock)
async def test_get_current_user_not_found(mock_get_user_by_clerk_id, logged_in_user):
    """已登入、但資料庫裡沒有這個使用者 → 404 "User not found"。"""
    mock_get_user_by_clerk_id.return_value = None

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/users/me")

    assert response.status_code == 404
    assert response.json()["detail"] == "User not found"

"""
測試註冊新使用者
"""
@pytest.mark.asyncio
@patch("crud.user.get_user_by_clerk_id", new_callable=AsyncMock)
@patch("crud.user.create_user", new_callable=AsyncMock)
async def test_register_user_success(mock_create_user, mock_get_user_by_clerk_id, fake_user_create, fake_user_out, logged_in_user):
    """POST /users/：還沒註冊過的使用者註冊成功，回傳新使用者。"""
    mock_get_user_by_clerk_id.return_value = None
    mock_create_user.return_value = fake_user_out

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/users/", json=fake_user_create.model_dump())

    assert response.status_code == 201
    assert response.json()["name"] == "John Doe"

@pytest.mark.asyncio
@patch("crud.user.get_user_by_clerk_id", new_callable=AsyncMock)
@patch("crud.user.create_user", new_callable=AsyncMock)
async def test_register_user_already_registered(mock_create_user, mock_get_user_by_clerk_id, fake_user_create, fake_user_out, logged_in_user):
    """已經註冊過又重複註冊 → 409 "User already registered"。"""
    mock_get_user_by_clerk_id.return_value = fake_user_out
    mock_create_user.return_value = fake_user_out

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/users/", json=fake_user_create.model_dump())

    assert response.status_code == 409
    assert response.json()["detail"] == "User already registered"


"""
測試更新使用者
"""
@pytest.mark.asyncio
@patch("crud.user.update_user_by_clerk_id", new_callable=AsyncMock)
async def test_update_user_success(mock_update_user, logged_in_user):
    """PUT /users/me：更新自己的資料成功，回 {"success": True}。"""
    mock_update_user.return_value = True  # 模擬成功更新

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.put("/users/me", json={"name": "Updated Name"})

    assert response.status_code == 200
    assert response.json() == {"success": True}

@pytest.mark.asyncio
@patch("crud.user.update_user_by_clerk_id", new_callable=AsyncMock)
async def test_update_user_not_found(mock_update_user, logged_in_user):
    """找不到使用者或沒有任何變更 → 404。"""
    from core.errors import NotFoundError
    mock_update_user.side_effect = NotFoundError("User not found or no changes made")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.put("/users/me", json={"name": "No Change"})

    assert response.status_code == 404
    assert response.json()["detail"] == "User not found or no changes made"


"""
測試刪除使用者
"""
@pytest.mark.asyncio
@patch("crud.user.delete_user_by_clerk_id", new_callable=AsyncMock)
async def test_delete_user_success(mock_delete_user, logged_in_user):
    """DELETE /users/me：刪除自己成功，回 {"deleted": True}。"""
    mock_delete_user.return_value = True  # 模擬刪除成功

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.delete("/users/me")

    assert response.status_code == 200
    assert response.json() == {"deleted": True}

@pytest.mark.asyncio
@patch("crud.user.delete_user_by_clerk_id", new_callable=AsyncMock)
async def test_delete_user_not_found(mock_delete_user, logged_in_user):
    """AC1：要刪除的使用者不存在 → 404 NOT_FOUND。"""
    mock_delete_user.return_value = False  # 模擬找不到使用者

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.delete("/users/me")

    assert response.status_code == 404
    assert response.json() == {"detail": "User not found", "error_code": "NOT_FOUND"}


"""
測試沒登入
"""
@pytest.mark.asyncio
async def test_get_current_user_requires_login():
    """沒帶登入 token → 被擋在門外（401/403），不能進到函式裡。"""
    # 這個測試刻意不用 logged_in_user，所以請求是沒登入的
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/users/me")

    assert response.status_code in (401, 403)


"""
測試排程偏好（issue-182）
"""
from core import database  # noqa: E402

PREFS_URL = "/users/me/schedule-preferences"

_EMPTY_PREFS = {"blocked_recurring": [], "blocked_exceptions": [], "buffer_minutes": 0, "daily_max_minutes": None}

_FULL_PREFS = {
    "blocked_recurring": [{"days_of_week": [0, 2], "all_day": False, "start_time": "12:00", "end_time": "13:00"}],
    "blocked_exceptions": [{"start": "2030-01-01T09:00:00Z", "end": "2030-01-01T10:00:00Z"}],
    "buffer_minutes": 15,
    "daily_max_minutes": 240,
}


def _rule(**overrides):
    rule = {"days_of_week": [1], "all_day": False, "start_time": "09:00", "end_time": "10:00"}
    rule.update(overrides)
    return rule


@pytest_asyncio.fixture
async def prefs_users():
    """準備 test_user_123 與 other_user 兩份 users 文件，結束後清掉。"""
    users = database.db.users
    await users.delete_many({})
    await users.insert_one({"_id": "test_user_123", "name": "A", "email": "a@example.com"})
    await users.insert_one({"_id": "other_user", "name": "B", "email": "b@example.com"})
    yield users
    await users.delete_many({})


async def _put(body):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        return await ac.put(PREFS_URL, json=body)


async def _get():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        return await ac.get(PREFS_URL)


@pytest.mark.asyncio
async def test_issue182_ac1_ac2_saved_preferences_round_trip(logged_in_user, prefs_users):
    """AC1、AC2：PUT 一份 4 種都有的偏好，再 GET 得到同一份（偏好存在後端，同帳號任何裝置讀到的都一樣）。"""
    put = await _put(_FULL_PREFS)
    assert put.status_code == 200

    got = await _get()

    assert got.status_code == 200
    body = got.json()
    assert body["blocked_recurring"] == _FULL_PREFS["blocked_recurring"]
    assert body["buffer_minutes"] == 15
    assert body["daily_max_minutes"] == 240
    assert len(body["blocked_exceptions"]) == 1
    assert body["blocked_exceptions"][0]["start"].startswith("2030-01-01T09:00:00")
    assert body["blocked_exceptions"][0]["end"].startswith("2030-01-01T10:00:00")


@pytest.mark.asyncio
async def test_issue182_ac3_no_saved_preferences_returns_defaults(logged_in_user, prefs_users):
    """AC3：從來沒存過偏好 → GET 回空白預設值。"""
    got = await _get()

    assert got.status_code == 200
    assert got.json() == _EMPTY_PREFS


@pytest.mark.asyncio
async def test_issue182_ac17_requires_login(prefs_users):
    """AC17：沒登入打 GET、PUT 都回 401，資料庫不變。"""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        got = await ac.get(PREFS_URL)
        put = await ac.put(PREFS_URL, json=_FULL_PREFS)

    assert got.status_code == 401
    assert put.status_code == 401
    doc = await prefs_users.find_one({"_id": "test_user_123"})
    assert "schedule_preferences" not in doc


@pytest.mark.asyncio
async def test_issue182_ac18_users_only_see_their_own_preferences(logged_in_user, prefs_users):
    """AC18：A 存偏好後，B 讀到自己的（沒存過就是預設值），A 的不變。"""
    from core.security import get_current_clerk_user

    await _put(_FULL_PREFS)

    async def as_b():
        return {"sub": "other_user"}

    app.dependency_overrides[get_current_clerk_user] = as_b
    b_got = await _get()

    async def as_a():
        return {"sub": "test_user_123"}

    app.dependency_overrides[get_current_clerk_user] = as_a
    a_got = await _get()

    assert b_got.json() == _EMPTY_PREFS
    assert a_got.json()["buffer_minutes"] == 15


async def _assert_rejected_keeps_original(body):
    await _put(_FULL_PREFS)
    res = await _put(body)
    assert res.status_code == 422
    got = await _get()
    assert got.json()["buffer_minutes"] == 15
    assert got.json()["blocked_recurring"] == _FULL_PREFS["blocked_recurring"]


@pytest.mark.asyncio
async def test_issue182_ac19_wrong_type_is_422(logged_in_user, prefs_users):
    """AC19：型別不對（buffer_minutes 是 "abc"）→ 422，原本的偏好不變。"""
    await _assert_rejected_keeps_original({"buffer_minutes": "abc"})


@pytest.mark.asyncio
async def test_issue182_ac20_too_many_recurring_rules_is_422(logged_in_user, prefs_users):
    """AC20：每週規律 51 條 → 422，原本的偏好不變。"""
    await _assert_rejected_keeps_original({"blocked_recurring": [_rule() for _ in range(51)]})


@pytest.mark.asyncio
async def test_issue182_ac21_too_many_exceptions_is_422(logged_in_user, prefs_users):
    """AC21：一次性例外 51 條 → 422，原本的偏好不變。"""
    exc = {"start": "2030-01-01T09:00:00Z", "end": "2030-01-01T10:00:00Z"}
    await _assert_rejected_keeps_original({"blocked_exceptions": [exc for _ in range(51)]})


@pytest.mark.asyncio
@pytest.mark.parametrize("days", [[0, 1, 2, 3, 4, 5, 6, 0], [7], [-1]])
async def test_issue182_ac22_invalid_days_of_week_is_422(logged_in_user, prefs_users, days):
    """AC22：days_of_week 超過 7 個、或含 0–6 以外的數字 → 422，原本的偏好不變。"""
    await _assert_rejected_keeps_original({"blocked_recurring": [_rule(days_of_week=days)]})


@pytest.mark.asyncio
@pytest.mark.parametrize("field,value", [
    ("start_time", "24:00"), ("start_time", "9:00"), ("start_time", "abc"), ("start_time", ""), ("end_time", "24:00"),
])
async def test_issue182_ac23_invalid_time_is_422(logged_in_user, prefs_users, field, value):
    """AC23：起訖時間不是 null 或 HH:MM（00:00–23:59）→ 422，原本的偏好不變。"""
    await _assert_rejected_keeps_original({"blocked_recurring": [_rule(**{field: value})]})


@pytest.mark.asyncio
async def test_issue182_ac24_boundary_values_are_accepted(logged_in_user, prefs_users):
    """AC24：各 50 條、days_of_week 是 0–6 全選、時間 00:00–23:59 → 存成功，讀回來一樣。"""
    rules = [_rule(days_of_week=[0, 1, 2, 3, 4, 5, 6], start_time="00:00", end_time="23:59") for _ in range(50)]
    excs = [{"start": "2030-01-01T09:00:00Z", "end": "2030-01-01T10:00:00Z"} for _ in range(50)]

    put = await _put({"blocked_recurring": rules, "blocked_exceptions": excs, "buffer_minutes": 0, "daily_max_minutes": None})

    assert put.status_code == 200
    got = (await _get()).json()
    assert got["blocked_recurring"] == rules
    assert len(got["blocked_exceptions"]) == 50


@pytest.mark.asyncio
async def test_issue182_null_times_are_accepted(logged_in_user, prefs_users):
    """start_time、end_time 可以是 null（整天的規律）。"""
    rule = _rule(all_day=True, start_time=None, end_time=None)

    put = await _put({"blocked_recurring": [rule]})

    assert put.status_code == 200


@pytest.mark.asyncio
async def test_issue182_ac27_users_me_still_only_returns_id_email_name(logged_in_user, prefs_users):
    """AC27：存了偏好之後，GET /users/me 仍然只有 id、email、name。"""
    await _put(_FULL_PREFS)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/users/me")

    assert set(res.json().keys()) == {"id", "email", "name"}
