"""
情境測試：外部平台先同步成功、再抓取失敗退回資料庫的舊資料，確認回應裡的時間和 X-Synced-At 都帶 UTC 時區。
clerk_id 用這個檔案獨有的值，避免和其他測試共用的資料庫互相影響。
"""
from datetime import datetime, timezone

import pytest
from fastapi import status
from httpx import AsyncClient
from httpx._transports.asgi import ASGITransport

from main import app
from core.cache import cache_delete
from core.crypto import encrypt_secret
from core.database import db
from core.datetimes import to_utc_datetime
from core.security import get_current_clerk_user
from platforms.github import GITHUB
from platforms.jira import JIRA
from platforms.moodle import MOODLE
from platforms.router import _cache_key
from platforms.sync import UpstreamError

SCENARIO_USER = {"sub": "scenario_user_platform_datetimes"}

# UTC 20:00 在 +8 時區已經是隔天，前端把它當成當地時間時日期會錯
CREATED_AT = datetime(2024, 1, 1, 20, 0, tzinfo=timezone.utc)
UPDATED_AT = datetime(2024, 1, 2, 18, 30, tzinfo=timezone.utc)
CLOSED_AT = datetime(2024, 1, 3, 23, 15, tzinfo=timezone.utc)
SCHEDULING_DUE = datetime(2030, 1, 9, 16, 0, tzinfo=timezone.utc)

PLATFORM_CASES = {
    "github": {
        "platform": GITHUB,
        "account": {"apiKey": encrypt_secret("token")},
        "item": {
            "id": 1, "number": 1, "title": "Fix bug", "status": "closed",
            "created_at": CREATED_AT, "updated_at": UPDATED_AT, "closed_at": CLOSED_AT,
            "url": "https://github.com/u/r/issues/1", "isPR": False,
            "author": {"username": "u", "avatar": ""}, "labels": [], "comments": 0,
        },
        "times": {"created_at": CREATED_AT, "updated_at": UPDATED_AT, "closed_at": CLOSED_AT},
    },
    "jira": {
        "platform": JIRA,
        "account": {"apiKey": encrypt_secret("key"), "domain": "example.atlassian.net"},
        "item": {
            "id": "10001", "key": "J-1", "title": "Jira issue", "status": "完成", "status_category": "done",
            "updated_at": UPDATED_AT, "resolved_at": CLOSED_AT,
            "assignee": "u", "avatar": "", "type": "Task", "iconUrl": "",
        },
        "times": {"updated_at": UPDATED_AT, "resolved_at": CLOSED_AT},
    },
    "moodle": {
        "platform": MOODLE,
        "account": {"username": "student", "password": encrypt_secret("pw")},
        "item": {
            "id": "https://moodle.example/assign?id=1", "course_name": "課程", "title": "作業",
            "url": "https://moodle.example/assign?id=1", "due_date": "2030年1月10日",
        },
        "times": {},
    },
}


@pytest.fixture(autouse=True)
def _override_auth():
    async def mock_get_user():
        return SCENARIO_USER
    app.dependency_overrides[get_current_clerk_user] = mock_get_user
    yield
    app.dependency_overrides.pop(get_current_clerk_user, None)


@pytest.fixture(autouse=True)
def _no_retry_wait(monkeypatch):
    async def fake_sleep(seconds):
        return None
    monkeypatch.setattr("platforms.sync.asyncio.sleep", fake_sleep)


def assert_utc_string(value, expected: datetime):
    """回應的時間字串要明確標示 UTC（Z 或 +00:00），而且和資料庫存的是同一個時間點。"""
    assert isinstance(value, str)
    assert value.endswith("Z") or value.endswith("+00:00"), value
    assert to_utc_datetime(value) == expected


async def _sync_then_fail(ac: AsyncClient, case: dict, monkeypatch):
    """同步成功一次 → 使用者設定排程截止日 → 平台抓取失敗。回傳 (成功的回應, 退回舊資料的回應)。"""
    platform = case["platform"]
    user_id = SCENARIO_USER["sub"]
    await db.linkedAccounts.insert_one({
        "_id": f"{user_id}_{platform.name}", "clerk_id": user_id, "platform": platform.name, **case["account"],
    })

    async def fetch_ok(credentials):
        return [dict(case["item"])]

    monkeypatch.setattr(platform, "fetch_items", fetch_ok)
    fresh = await ac.get(platform.route_path)
    assert fresh.status_code == status.HTTP_200_OK, fresh.text

    await platform.collection.update_one(
        {"user_id": user_id, "id": case["item"]["id"]},
        {"$set": {"scheduling_due_date": SCHEDULING_DUE}},
    )
    # Moodle 成功的結果會進快取，要清掉才會真的再抓一次
    await cache_delete(_cache_key(platform, user_id))

    async def fetch_fail(credentials):
        raise UpstreamError("暫時連不上")

    monkeypatch.setattr(platform, "fetch_items", fetch_fail)
    stale = await ac.get(platform.route_path)
    assert stale.status_code == status.HTTP_200_OK, stale.text
    assert stale.headers["X-Data-Stale"] == "true"
    return fresh, stale


async def _cleanup(platform):
    user_id = SCENARIO_USER["sub"]
    await db.linkedAccounts.delete_many({"clerk_id": user_id})
    await platform.collection.delete_many({"user_id": user_id})
    await cache_delete(_cache_key(platform, user_id))


@pytest.mark.asyncio
async def test_github_stale_fallback_returns_issue_times_in_utc(monkeypatch):
    """AC1：GitHub 連不上、退回資料庫的舊資料 → created_at、updated_at、closed_at 帶 UTC 時區，時間值和存的相同。"""
    case = PLATFORM_CASES["github"]
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            _, stale = await _sync_then_fail(ac, case, monkeypatch)

        [issue] = stale.json()
        assert_utc_string(issue["created_at"], CREATED_AT)
        assert_utc_string(issue["updated_at"], UPDATED_AT)
        assert_utc_string(issue["closed_at"], CLOSED_AT)
    finally:
        await _cleanup(case["platform"])


@pytest.mark.asyncio
@pytest.mark.parametrize("name", ["github", "jira", "moodle"])
async def test_platform_times_are_utc_on_fresh_sync_and_stale_fallback(name, monkeypatch):
    """AC2：同步成功時平台的時間欄位帶 UTC 時區（scheduling_due_date 是 null）；退回舊資料時包括 scheduling_due_date 全部帶 UTC 時區。"""
    case = PLATFORM_CASES[name]
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            fresh, stale = await _sync_then_fail(ac, case, monkeypatch)

        [fresh_item] = fresh.json()
        for field, expected in case["times"].items():
            assert_utc_string(fresh_item[field], expected)
        assert fresh_item["scheduling_due_date"] is None

        [stale_item] = stale.json()
        for field, expected in case["times"].items():
            assert_utc_string(stale_item[field], expected)
        assert_utc_string(stale_item["scheduling_due_date"], SCHEDULING_DUE)
    finally:
        await _cleanup(case["platform"])


@pytest.mark.asyncio
@pytest.mark.parametrize("name", ["github", "jira", "moodle"])
async def test_stale_fallback_synced_at_header_is_utc(name, monkeypatch):
    """AC3：退回舊資料時 X-Synced-At 帶 UTC 時區，而且是上次同步成功的時間；不帶時區時前端在 +8 時區會多算 8 小時。"""
    case = PLATFORM_CASES[name]
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            fresh, stale = await _sync_then_fail(ac, case, monkeypatch)

        synced_at = stale.headers["X-Synced-At"]
        assert synced_at.endswith("Z") or synced_at.endswith("+00:00"), synced_at
        # Mongo 的日期只存到毫秒，比對時去掉更細的部分
        expected = to_utc_datetime(fresh.headers["X-Synced-At"])
        assert expected is not None
        assert to_utc_datetime(synced_at) == expected.replace(microsecond=expected.microsecond // 1000 * 1000)
    finally:
        await _cleanup(case["platform"])
