"""platforms/account_sync.py：一個帳號一次同步的結果種類，以及同一帳號同時有兩次同步時以誰為準。"""
import asyncio

import pytest
import pytest_asyncio

import platforms.account_sync as account_sync
from core.database import db
from platforms.account_sync import SyncOutcome, sync_account
from platforms.github import GITHUB
from platforms.sync import NonRetryableError
from tests.unit.sync_fakes import (
    ACCOUNT_ID,
    PAST,
    USER,
    ControlledFetch,
    PausingCollection,
    account,
    cleanup,
    expire_lock,
    hold_lock_by_someone_else,
    item,
    items_by_id,
    link_github,
    start_after,
)


@pytest_asyncio.fixture(autouse=True)
async def clean():
    await cleanup()
    yield
    await cleanup()


@pytest.fixture(autouse=True)
def fast_lock_polling(monkeypatch):
    monkeypatch.setattr(account_sync, "LOCK_POLL_SECONDS", 0.01)


@pytest.fixture
def fetch(monkeypatch) -> ControlledFetch:
    controlled = ControlledFetch()
    monkeypatch.setattr(GITHUB, "fetch_items", controlled)
    return controlled


@pytest.fixture
def pausing_items(monkeypatch) -> PausingCollection:
    collection = PausingCollection(db.github_issues)
    monkeypatch.setattr(db, "github_issues", collection)
    return collection


async def _run_alone(fetch: ControlledFetch, result):
    _, gate = fetch.plan(result)
    gate.set()
    return await sync_account(GITHUB, USER)


# ---------- 單次同步 ----------

@pytest.mark.asyncio
async def test_success_writes_items_and_sync_result(fetch):
    """抓取成功 → 寫入項目、記下成功時間、清掉之前的錯誤，並釋放鎖。"""
    await link_github(last_sync_error_code="REAUTH_REQUIRED")
    await db.github_issues.insert_one({"id": 9, "title": "平台上已刪除", "user_id": USER})

    result = await _run_alone(fetch, [item(1, "a")])

    assert result.outcome is SyncOutcome.SUCCEEDED
    assert [i["title"] for i in result.items] == ["a"]
    assert await items_by_id() == {1: "a"}
    doc = await account()
    assert doc is not None
    assert doc["last_synced_at"] == result.synced_at
    assert doc["last_sync_error_code"] is None
    assert "sync_lock_owner" not in doc and "sync_lock_until" not in doc


@pytest.mark.asyncio
async def test_fetch_failure_records_error_code_and_keeps_items(fetch):
    """AC9：重試後仍失敗 → 項目維持原樣，只記下 error_code，last_synced_at 不變。"""
    await link_github(last_synced_at=PAST)
    await db.github_issues.insert_one({"id": 9, "title": "舊資料", "user_id": USER})

    result = await _run_alone(fetch, NonRetryableError("401", error_code="REAUTH_REQUIRED"))

    assert result.outcome is SyncOutcome.FAILED
    assert result.error_code == "REAUTH_REQUIRED"
    assert await items_by_id() == {9: "舊資料"}
    doc = await account()
    assert doc is not None
    assert doc["last_sync_error_code"] == "REAUTH_REQUIRED"
    assert doc["last_synced_at"] == PAST


@pytest.mark.asyncio
async def test_undecryptable_credentials_write_nothing(fetch):
    """需求 27a：憑證解不開 → 不抓資料、不搶鎖、不寫任何同步欄位。"""
    await link_github(apiKey="not-actually-encrypted", last_sync_error_code="UPSTREAM_ERROR")
    before = await account()

    result = await sync_account(GITHUB, USER)

    assert result.outcome is SyncOutcome.UNDECRYPTABLE
    assert await account() == before


@pytest.mark.asyncio
async def test_incomplete_credentials_write_nothing():
    """憑證資料不完整（沒有 apiKey）→ 回傳「憑證資料不完整」，不寫任何同步欄位。"""
    await link_github(apiKey="")
    before = await account()

    result = await sync_account(GITHUB, USER)

    assert result.outcome is SyncOutcome.INCOMPLETE_CREDENTIALS
    assert await account() == before


@pytest.mark.asyncio
async def test_lock_held_by_another_sync_times_out_without_writing(fetch, monkeypatch):
    """需求 24b：鎖一直被別人拿著，等到上限就放棄 → SERVICE_UNAVAILABLE，不寫任何欄位。"""
    monkeypatch.setattr(account_sync, "LOCK_WAIT_SECONDS", 0.05)
    await link_github()
    await hold_lock_by_someone_else()
    before = await account()

    result = await _run_alone(fetch, [item(1, "a")])

    assert result.outcome is SyncOutcome.LOCK_TIMEOUT
    assert result.error_code == "SERVICE_UNAVAILABLE"
    assert await account() == before
    assert await items_by_id() == {}


# ---------- 兩次同步：比較晚開始的為準 ----------

@pytest.mark.asyncio
async def test_earlier_sync_finishing_later_is_superseded(fetch):
    """AC46、AC47、AC48：先開始的同步比較晚寫入時被取代：項目、同步結果、開始時間都是後開始那次的，後開始那次新增的項目還在。"""
    await link_github()
    a_entered, a_gate = fetch.plan([item(1, "A only"), item(2, "shared from A")])
    a = asyncio.create_task(sync_account(GITHUB, USER))
    b_entered, b_gate = fetch.plan([item(2, "shared from B"), item(3, "B only")])
    b = await start_after(a_entered, sync_account(GITHUB, USER))
    await b_entered.wait()

    b_gate.set()
    b_result = await b
    after_b = await account()
    a_gate.set()
    a_result = await a

    assert b_result.outcome is SyncOutcome.SUCCEEDED
    assert a_result.outcome is SyncOutcome.SUPERSEDED
    assert await items_by_id() == {2: "shared from B", 3: "B only"}
    doc = await account()
    assert doc is not None and after_b is not None
    assert doc["last_synced_at"] == b_result.synced_at
    assert doc["sync_started_at"] == after_b["sync_started_at"]


@pytest.mark.asyncio
async def test_later_sync_waits_for_lock_while_earlier_sync_writes(fetch, pausing_items):
    """AC51：先開始的同步正在寫入時，後開始的同步要等它寫完才寫；最後的結果是後開始那次的。"""
    await link_github()
    a_reached, a_release = pausing_items.pause_on("A1")
    a_entered, a_gate = fetch.plan([item(1, "A1")])
    a = asyncio.create_task(sync_account(GITHUB, USER))
    b_entered, b_gate = fetch.plan([item(1, "B1"), item(2, "B2")])
    b = await start_after(a_entered, sync_account(GITHUB, USER))
    await b_entered.wait()

    a_gate.set()
    await a_reached.wait()
    b_gate.set()
    await asyncio.sleep(0.1)  # 讓後開始的同步搶鎖幾輪

    assert not b.done()
    assert await items_by_id() == {}

    a_release.set()
    a_result, b_result = await asyncio.gather(a, b)

    assert a_result.outcome is SyncOutcome.SUCCEEDED
    assert b_result.outcome is SyncOutcome.SUCCEEDED
    assert await items_by_id() == {1: "B1", 2: "B2"}
    doc = await account()
    assert doc is not None
    assert doc["last_synced_at"] == b_result.synced_at


@pytest.mark.asyncio
async def test_earlier_sync_whose_lock_expired_cannot_delete_or_record(fetch, pausing_items):
    """AC52：先開始的同步寫入期間鎖過期、被後開始的同步拿走 → 先開始的不能刪項目，也不能寫同步結果。"""
    await link_github()
    a_reached, a_release = pausing_items.pause_on("A1")
    a_entered, a_gate = fetch.plan([item(1, "A1")])
    a = asyncio.create_task(sync_account(GITHUB, USER))
    b_entered, b_gate = fetch.plan([item(1, "B1"), item(2, "B only")])
    b = await start_after(a_entered, sync_account(GITHUB, USER))
    await b_entered.wait()

    a_gate.set()
    await a_reached.wait()
    await expire_lock()
    b_gate.set()
    b_result = await b
    a_release.set()
    a_result = await a

    assert b_result.outcome is SyncOutcome.SUCCEEDED
    assert a_result.outcome is SyncOutcome.LOCK_LOST
    assert 2 in await items_by_id()
    doc = await account()
    assert doc is not None
    assert doc["last_synced_at"] == b_result.synced_at
    assert doc["last_sync_error_code"] is None


@pytest.mark.asyncio
async def test_sync_releases_only_its_own_lock(fetch, pausing_items):
    """AC53：鎖過期被別人拿走後，原本的同步結束時不能釋放別人的鎖。"""
    await link_github()
    a_reached, a_release = pausing_items.pause_on("A1")
    b_reached, b_release = pausing_items.pause_on("B1")
    a_entered, a_gate = fetch.plan([item(1, "A1")])
    a = asyncio.create_task(sync_account(GITHUB, USER))
    b_entered, b_gate = fetch.plan([item(1, "B1")])
    b = await start_after(a_entered, sync_account(GITHUB, USER))
    await b_entered.wait()

    a_gate.set()
    await a_reached.wait()
    await expire_lock()
    b_gate.set()
    await b_reached.wait()
    b_doc = await account()
    assert b_doc is not None
    b_owner = b_doc["sync_lock_owner"]

    a_release.set()
    a_result = await a
    after_a = await account()

    assert a_result.outcome is SyncOutcome.LOCK_LOST
    assert after_a is not None
    assert after_a["sync_lock_owner"] == b_owner

    b_release.set()
    assert (await b).outcome is SyncOutcome.SUCCEEDED


@pytest.mark.asyncio
async def test_earlier_sync_taking_expired_lock_of_later_sync_is_superseded(fetch, pausing_items):
    """AC68：後開始的同步拿著鎖寫入、鎖過期後被先開始的同步拿到 → 先開始的同步回傳被取代，不寫項目也不寫同步結果。"""
    await link_github(last_synced_at=PAST)
    await db.github_issues.insert_one({"id": 9, "title": "既有", "user_id": USER})
    b_reached, b_release = pausing_items.pause_on("B1")
    a_entered, a_gate = fetch.plan([item(1, "A1")])
    a = asyncio.create_task(sync_account(GITHUB, USER))
    b_entered, b_gate = fetch.plan([item(1, "B1")])
    b = await start_after(a_entered, sync_account(GITHUB, USER))
    await b_entered.wait()

    b_gate.set()
    await b_reached.wait()
    await expire_lock()
    a_gate.set()
    a_result = await a

    assert a_result.outcome is SyncOutcome.SUPERSEDED
    assert await items_by_id() == {9: "既有"}
    doc = await account()
    assert doc is not None
    assert doc["last_synced_at"] == PAST
    assert "last_sync_error_code" not in doc

    b_release.set()
    await b


# ---------- 帳號連結在同步途中變更 ----------

@pytest.mark.asyncio
async def test_account_deleted_during_fetch_writes_nothing(fetch):
    """AC54：抓資料期間帳號連結被刪除 → 不寫項目、不寫同步結果，也不會重新建出帳號文件。"""
    await link_github()
    entered, gate = fetch.plan([item(1, "a")])
    task = asyncio.create_task(sync_account(GITHUB, USER))
    await entered.wait()
    await db.linkedAccounts.delete_one({"_id": ACCOUNT_ID})
    gate.set()
    result = await task

    assert result.outcome is SyncOutcome.ACCOUNT_CHANGED
    assert await items_by_id() == {}
    assert await account() is None


@pytest.mark.asyncio
@pytest.mark.parametrize("original_link_id", ["link-1", None], ids=["with-link-id", "legacy-without-link-id"])
async def test_relinked_during_fetch_writes_nothing(fetch, original_link_id):
    """AC55：抓資料期間重新連結或更新憑證（link_id 換掉）→ 項目與同步結果都不變；上線前建立、沒有 link_id 的帳號也一樣。"""
    await link_github(link_id=original_link_id, last_synced_at=PAST)
    await db.github_issues.insert_one({"id": 9, "title": "舊", "user_id": USER})
    entered, gate = fetch.plan([item(1, "新")])
    task = asyncio.create_task(sync_account(GITHUB, USER))
    await entered.wait()
    await db.linkedAccounts.update_one({"_id": ACCOUNT_ID}, {"$set": {"link_id": "link-2"}})
    gate.set()
    result = await task

    assert result.outcome is SyncOutcome.ACCOUNT_CHANGED
    assert await items_by_id() == {9: "舊"}
    doc = await account()
    assert doc is not None
    assert doc["last_synced_at"] == PAST
    assert "last_sync_error_code" not in doc


@pytest.mark.asyncio
async def test_relinked_while_writing_items_cannot_delete_or_record(fetch, pausing_items):
    """AC69：寫入項目期間更新憑證 → 這次同步不刪項目，也不寫同步結果。"""
    await link_github(last_synced_at=PAST)
    await db.github_issues.insert_one({"id": 9, "title": "這次抓不到", "user_id": USER})
    reached, release = pausing_items.pause_on("A1")
    entered, gate = fetch.plan([item(1, "A1")])
    gate.set()
    task = asyncio.create_task(sync_account(GITHUB, USER))
    await reached.wait()
    await db.linkedAccounts.update_one({"_id": ACCOUNT_ID}, {"$set": {"link_id": "link-2"}})
    release.set()
    result = await task

    assert result.outcome is SyncOutcome.ACCOUNT_CHANGED
    assert 9 in await items_by_id()
    doc = await account()
    assert doc is not None
    assert doc["last_synced_at"] == PAST
    assert "last_sync_error_code" not in doc


@pytest.mark.asyncio
async def test_lock_taken_while_writing_items_is_lock_lost(fetch, pausing_items):
    """寫入項目期間鎖被換成別人的 → 回傳鎖被拿走，不刪項目、不寫同步結果。"""
    await link_github(last_synced_at=PAST)
    await db.github_issues.insert_one({"id": 9, "title": "這次抓不到", "user_id": USER})
    reached, release = pausing_items.pause_on("A1")
    _, gate = fetch.plan([item(1, "A1")])
    gate.set()
    task = asyncio.create_task(sync_account(GITHUB, USER))
    await reached.wait()
    await db.linkedAccounts.update_one({"_id": ACCOUNT_ID}, {"$set": {"sync_lock_owner": "someone-else"}})
    release.set()
    result = await task

    assert result.outcome is SyncOutcome.LOCK_LOST
    assert 9 in await items_by_id()
    doc = await account()
    assert doc is not None
    assert doc["last_synced_at"] == PAST
    assert doc["sync_lock_owner"] == "someone-else"
