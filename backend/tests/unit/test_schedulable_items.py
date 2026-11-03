import pytest
from datetime import datetime, timezone

import crud.schedulable_items as schedulable_items
from core.database import db


async def _cleanup():
    await db.manual_tasks.delete_many({"user_id": "sched-user"})
    await db.github_issues.delete_many({"user_id": "sched-user"})
    await db.jira_issues.delete_many({"user_id": "sched-user"})
    await db.moodle_assignments.delete_many({"user_id": "sched-user"})


# ---------- make_composite_id / parse_composite_id ----------

def test_composite_id_round_trip():
    composite = schedulable_items.make_composite_id("github", 42)
    assert composite == "github:42"
    assert schedulable_items.parse_composite_id(composite) == ("github", "42")


def test_parse_composite_id_handles_ids_that_themselves_contain_colons():
    """Moodle 的 id 是完整 URL，可能自己就帶冒號（https://...）——只切第一個冒號。"""
    composite = "moodle:https://moodle.nccu.edu.tw/mod/assign/view.php?id=1"
    source, raw_id = schedulable_items.parse_composite_id(composite)
    assert source == "moodle"
    assert raw_id == "https://moodle.nccu.edu.tw/mod/assign/view.php?id=1"


# ---------- get_all_schedulable_items ----------

@pytest.mark.asyncio
async def test_get_all_schedulable_items_combines_all_four_sources():
    try:
        await db.manual_tasks.insert_one({
            "_id": "t1", "user_id": "sched-user", "title": "手動任務", "status": "To Do",
            "priority": "High", "duration": 30, "due_date": None, "sort_order": None, "calendar_event_id": None,
        })
        await db.github_issues.insert_one({
            "id": 1, "user_id": "sched-user", "title": "GitHub Issue", "status": "open",
        })
        await db.jira_issues.insert_one({
            "id": "100", "user_id": "sched-user", "title": "Jira Issue", "status": "To Do", "status_category": "new",
        })
        await db.moodle_assignments.insert_one({
            "id": "https://moodle/1", "user_id": "sched-user", "title": "Moodle 作業", "url": "https://moodle/1",
        })

        items = await schedulable_items.get_all_schedulable_items("sched-user")

        ids = {item["id"] for item in items}
        assert ids == {"manual:t1", "github:1", "jira:100", "moodle:https://moodle/1"}
        sources = {item["id"]: item["source"] for item in items}
        assert sources == {
            "manual:t1": "manual", "github:1": "github", "jira:100": "jira", "moodle:https://moodle/1": "moodle",
        }
    finally:
        await _cleanup()


@pytest.mark.asyncio
async def test_get_all_schedulable_items_github_closed_issue_is_done():
    try:
        await db.github_issues.insert_one({
            "id": 1, "user_id": "sched-user", "title": "已關閉的 issue", "status": "closed",
        })

        items = await schedulable_items.get_all_schedulable_items("sched-user")

        assert items[0]["status"] == "Done"
    finally:
        await _cleanup()


@pytest.mark.asyncio
async def test_get_all_schedulable_items_jira_done_category_is_done():
    try:
        await db.jira_issues.insert_one({
            "id": "100", "user_id": "sched-user", "title": "已完成", "status": "已完成", "status_category": "done",
        })

        items = await schedulable_items.get_all_schedulable_items("sched-user")

        assert items[0]["status"] == "Done"
    finally:
        await _cleanup()


@pytest.mark.asyncio
async def test_get_all_schedulable_items_jira_indeterminate_category_is_not_done():
    """status.name 可能長得很像完成（"處理中"之類），但只有 statusCategory 是 done 才算數。"""
    try:
        await db.jira_issues.insert_one({
            "id": "100", "user_id": "sched-user", "title": "進行中", "status": "In Progress", "status_category": "indeterminate",
        })

        items = await schedulable_items.get_all_schedulable_items("sched-user")

        assert items[0]["status"] == "To Do"
    finally:
        await _cleanup()


@pytest.mark.asyncio
async def test_get_all_schedulable_items_moodle_never_auto_done():
    """Moodle 爬蟲沒有任何完成訊號可用，不管其他欄位長怎樣都不會自動判斷完成。"""
    try:
        await db.moodle_assignments.insert_one({
            "id": "https://moodle/1", "user_id": "sched-user", "title": "作業", "url": "https://moodle/1",
        })

        items = await schedulable_items.get_all_schedulable_items("sched-user")

        assert items[0]["status"] == "To Do"
    finally:
        await _cleanup()


@pytest.mark.asyncio
async def test_get_all_schedulable_items_manual_done_flag_overrides_platform_status():
    """使用者在 App 內手動標記完成的外部項目，即使平台狀態還是 open/未完成，也視為已完成。"""
    try:
        await db.github_issues.insert_one({
            "id": 1, "user_id": "sched-user", "title": "還開著但使用者手動標完成", "status": "open", "done": True,
        })

        items = await schedulable_items.get_all_schedulable_items("sched-user")

        assert items[0]["status"] == "Done"
    finally:
        await _cleanup()


@pytest.mark.asyncio
async def test_get_all_schedulable_items_exposes_scheduling_fields_and_url():
    try:
        await db.jira_issues.insert_one({
            "id": "100", "user_id": "sched-user", "title": "任務", "status": "To Do", "status_category": "new",
            "priority": "High", "duration": 45, "scheduling_due_date": "2026-10-01T00:00:00Z",
            "sort_order": 2, "calendar_event_id": "event-1",
        })

        items = await schedulable_items.get_all_schedulable_items("sched-user")

        item = items[0]
        assert item["priority"] == "High"
        assert item["duration"] == 45
        assert item["due_date"] == "2026-10-01T00:00:00Z"
        assert item["sort_order"] == 2
        assert item["calendar_event_id"] == "event-1"
    finally:
        await _cleanup()


@pytest.mark.asyncio
async def test_get_all_schedulable_items_only_returns_the_given_users_items():
    try:
        await db.github_issues.insert_many([
            {"id": 1, "user_id": "sched-user", "title": "我的", "status": "open"},
            {"id": 2, "user_id": "someone-else", "title": "別人的", "status": "open"},
        ])

        items = await schedulable_items.get_all_schedulable_items("sched-user")

        assert [item["id"] for item in items] == ["github:1"]
    finally:
        await _cleanup()
        await db.github_issues.delete_many({"id": 2})


# ---------- reorder_schedulable_items ----------

@pytest.mark.asyncio
async def test_reorder_schedulable_items_preserves_global_index_across_sources():
    """混合來源時，sort_order 是整份清單的索引，不分來源各自編號。"""
    try:
        await db.manual_tasks.insert_one({"_id": "t1", "user_id": "sched-user", "title": "手動任務", "priority": "Low"})
        await db.github_issues.insert_one({"id": 1, "user_id": "sched-user", "title": "GitHub", "status": "open"})

        await schedulable_items.reorder_schedulable_items("sched-user", [
            {"task_id": "manual:t1", "priority": "High"},
            {"task_id": "github:1", "priority": "High"},
        ])

        manual_task = await db.manual_tasks.find_one({"_id": "t1"})
        github_issue = await db.github_issues.find_one({"id": 1})
        assert manual_task["sort_order"] == 0
        assert manual_task["priority"] == "High"
        assert github_issue["sort_order"] == 1
        assert github_issue["priority"] == "High"
    finally:
        await _cleanup()


@pytest.mark.asyncio
async def test_reorder_schedulable_items_dispatches_each_source_to_its_own_collection():
    try:
        await db.github_issues.insert_one({"id": 1, "user_id": "sched-user", "title": "G", "status": "open"})
        await db.jira_issues.insert_one({"id": "100", "user_id": "sched-user", "title": "J", "status": "To Do"})
        await db.moodle_assignments.insert_one({"id": "https://m/1", "user_id": "sched-user", "title": "M", "url": "https://m/1"})

        await schedulable_items.reorder_schedulable_items("sched-user", [
            {"task_id": "github:1", "priority": "Low"},
            {"task_id": "jira:100", "priority": "Medium"},
            {"task_id": "moodle:https://m/1", "priority": "High"},
        ])

        github_issue = await db.github_issues.find_one({"id": 1})
        jira_issue = await db.jira_issues.find_one({"id": "100"})
        moodle_assignment = await db.moodle_assignments.find_one({"id": "https://m/1"})
        assert (github_issue["priority"], github_issue["sort_order"]) == ("Low", 0)
        assert (jira_issue["priority"], jira_issue["sort_order"]) == ("Medium", 1)
        assert (moodle_assignment["priority"], moodle_assignment["sort_order"]) == ("High", 2)
    finally:
        await _cleanup()


# ---------- update_scheduling_fields ----------

@pytest.mark.asyncio
async def test_update_scheduling_fields_manual_task_goes_through_manual_task_update():
    try:
        await db.manual_tasks.insert_one({
            "_id": "t1", "user_id": "sched-user", "title": "任務", "description": "d",
            "status": "To Do", "priority": "Low", "duration": 60,
        })

        await schedulable_items.update_scheduling_fields("sched-user", "manual:t1", {"duration": 90})

        updated = await db.manual_tasks.find_one({"_id": "t1"})
        assert updated["duration"] == 90
        assert updated["title"] == "任務"  # 其他欄位不受影響
    finally:
        await _cleanup()


@pytest.mark.asyncio
async def test_update_scheduling_fields_external_item_sets_fields_directly():
    try:
        await db.jira_issues.insert_one({"id": "100", "user_id": "sched-user", "title": "任務", "status": "To Do"})

        await schedulable_items.update_scheduling_fields(
            "sched-user", "jira:100", {"duration": 45, "scheduling_due_date": "2026-10-01T00:00:00Z"}
        )

        updated = await db.jira_issues.find_one({"id": "100"})
        assert updated["duration"] == 45
        assert updated["scheduling_due_date"] == "2026-10-01T00:00:00Z"
    finally:
        await _cleanup()


# ---------- set_done ----------

@pytest.mark.asyncio
async def test_set_done_manual_task_sets_status():
    try:
        await db.manual_tasks.insert_one({
            "_id": "t1", "user_id": "sched-user", "title": "任務", "description": "d",
            "status": "To Do", "priority": "Low", "duration": 60,
        })

        await schedulable_items.set_done("sched-user", "manual:t1", True)

        updated = await db.manual_tasks.find_one({"_id": "t1"})
        assert updated["status"] == "Done"
    finally:
        await _cleanup()


@pytest.mark.asyncio
async def test_set_done_external_item_sets_done_flag():
    try:
        await db.github_issues.insert_one({"id": 1, "user_id": "sched-user", "title": "任務", "status": "open"})

        await schedulable_items.set_done("sched-user", "github:1", True)
        updated = await db.github_issues.find_one({"id": 1})
        assert updated["done"] is True

        await schedulable_items.set_done("sched-user", "github:1", False)
        updated = await db.github_issues.find_one({"id": 1})
        assert updated["done"] is False
    finally:
        await _cleanup()


# ---------- set_calendar_event_id_for_composite ----------

@pytest.mark.asyncio
async def test_set_calendar_event_id_for_composite_manual_task():
    try:
        await db.manual_tasks.insert_one({"_id": "t1", "user_id": "sched-user", "title": "任務"})

        await schedulable_items.set_calendar_event_id_for_composite("sched-user", "manual:t1", "event-1")

        updated = await db.manual_tasks.find_one({"_id": "t1"})
        assert updated["calendar_event_id"] == "event-1"
    finally:
        await _cleanup()


@pytest.mark.asyncio
async def test_set_calendar_event_id_for_composite_external_item():
    try:
        await db.moodle_assignments.insert_one({"id": "https://m/1", "user_id": "sched-user", "title": "作業", "url": "https://m/1"})

        await schedulable_items.set_calendar_event_id_for_composite("sched-user", "moodle:https://m/1", "event-2")

        updated = await db.moodle_assignments.find_one({"id": "https://m/1"})
        assert updated["calendar_event_id"] == "event-2"
    finally:
        await _cleanup()


# ---------- 完成時間 completed_at ----------

@pytest.mark.asyncio
async def test_set_done_manual_task_records_and_clears_completed_at():
    """標記完成寫入當下時間；已完成的再標一次保留原本的時間；取消完成清空。"""
    done_at = datetime(2026, 10, 1)
    try:
        await db.manual_tasks.insert_one({
            "_id": "t1", "user_id": "sched-user", "title": "任務", "description": "d",
            "status": "To Do", "priority": "Low", "duration": 60,
        })
        await db.manual_tasks.insert_one({
            "_id": "t2", "user_id": "sched-user", "title": "已完成", "description": "d",
            "status": "Done", "priority": "Low", "duration": 60, "completed_at": done_at,
        })

        before = datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)
        await schedulable_items.set_done("sched-user", "manual:t1", True)
        completed_at = (await db.manual_tasks.find_one({"_id": "t1"}))["completed_at"]
        assert before <= completed_at.replace(tzinfo=None) <= datetime.now(timezone.utc).replace(tzinfo=None)

        await schedulable_items.set_done("sched-user", "manual:t2", True)
        assert (await db.manual_tasks.find_one({"_id": "t2"}))["completed_at"] == done_at

        await schedulable_items.set_done("sched-user", "manual:t2", False)
        assert (await db.manual_tasks.find_one({"_id": "t2"}))["completed_at"] is None
    finally:
        await _cleanup()


@pytest.mark.asyncio
async def test_set_done_external_item_records_and_clears_completed_at():
    try:
        await db.moodle_assignments.insert_one({"id": "https://m/1", "user_id": "sched-user", "title": "作業"})

        before = datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)
        await schedulable_items.set_done("sched-user", "moodle:https://m/1", True)
        first = (await db.moodle_assignments.find_one({"id": "https://m/1"}))["completed_at"]
        assert before <= first.replace(tzinfo=None) <= datetime.now(timezone.utc).replace(tzinfo=None)

        await schedulable_items.set_done("sched-user", "moodle:https://m/1", True)
        assert (await db.moodle_assignments.find_one({"id": "https://m/1"}))["completed_at"] == first

        await schedulable_items.set_done("sched-user", "moodle:https://m/1", False)
        assert (await db.moodle_assignments.find_one({"id": "https://m/1"}))["completed_at"] is None
    finally:
        await _cleanup()


@pytest.mark.asyncio
async def test_completed_at_of_external_item_survives_next_platform_sync():
    """同步只 $set 平台回傳的欄位，使用者標記的完成時間不能被洗掉。"""
    from platforms.sync import sync_platform_items

    try:
        await db.moodle_assignments.insert_one({"id": "https://m/1", "user_id": "sched-user", "title": "作業"})
        await schedulable_items.set_done("sched-user", "moodle:https://m/1", True)

        async def fetch():
            return [{"id": "https://m/1", "title": "作業（改名）"}]

        await sync_platform_items(db.moodle_assignments, "sched-user", "id", fetch)

        items = await schedulable_items.get_all_schedulable_items("sched-user")
        assert items[0]["title"] == "作業（改名）"
        assert items[0]["completed_at"] is not None
    finally:
        await _cleanup()


@pytest.mark.asyncio
async def test_completed_at_of_platform_closed_item_uses_platform_time():
    """平台判定完成（GitHub closed、Jira done）→ 用平台的關閉時間，不用使用者標記的時間。"""
    try:
        await db.github_issues.insert_one({
            "id": 1, "user_id": "sched-user", "title": "已關閉", "status": "closed",
            "closed_at": "2026-10-01T08:00:00Z",
            "done": True, "completed_at": datetime(2026, 10, 5, tzinfo=timezone.utc),
        })
        await db.jira_issues.insert_one({
            "id": "100", "user_id": "sched-user", "title": "已解決", "status": "完成",
            "status_category": "done", "resolved_at": "2026-10-02T10:00:00.000+0800",
        })

        items = {item["id"]: item for item in await schedulable_items.get_all_schedulable_items("sched-user")}

        assert items["github:1"]["completed_at"] == datetime(2026, 10, 1, 8, 0, tzinfo=timezone.utc)
        assert items["jira:100"]["completed_at"] == datetime(2026, 10, 2, 2, 0, tzinfo=timezone.utc)
    finally:
        await _cleanup()


@pytest.mark.asyncio
async def test_completed_at_of_reopened_item_marked_done_by_user_uses_user_time():
    """GitHub 還開著、使用者手動標記完成 → 用標記的時間；之前的 closed_at 不算數。"""
    marked_at = datetime(2026, 10, 5, tzinfo=timezone.utc)
    try:
        await db.github_issues.insert_one({
            "id": 1, "user_id": "sched-user", "title": "重開的 issue", "status": "open",
            "closed_at": None, "done": True, "completed_at": marked_at,
        })
        await db.github_issues.insert_one({
            "id": 2, "user_id": "sched-user", "title": "未完成", "status": "open",
            "closed_at": None, "completed_at": None,
        })

        items = {item["id"]: item for item in await schedulable_items.get_all_schedulable_items("sched-user")}

        assert items["github:1"]["completed_at"].replace(tzinfo=timezone.utc) == marked_at
        assert items["github:2"]["completed_at"] is None
    finally:
        await _cleanup()


@pytest.mark.asyncio
async def test_completed_at_of_platform_closed_item_stored_as_datetime():
    """AC19：同步後平台時間存成 datetime，算出的完成時間要是帶時區的 UTC，才能和截止日比較。"""
    try:
        await db.github_issues.insert_one({
            "id": 1, "user_id": "sched-user", "title": "已關閉", "status": "closed",
            "closed_at": datetime(2026, 10, 1, 8, 0, tzinfo=timezone.utc),
        })
        await db.jira_issues.insert_one({
            "id": "100", "user_id": "sched-user", "title": "已解決", "status": "完成",
            "status_category": "done", "resolved_at": datetime(2026, 10, 2, 2, 0, tzinfo=timezone.utc),
        })

        items = {item["id"]: item for item in await schedulable_items.get_all_schedulable_items("sched-user")}

        assert items["github:1"]["completed_at"] == datetime(2026, 10, 1, 8, 0, tzinfo=timezone.utc)
        assert items["jira:100"]["completed_at"] == datetime(2026, 10, 2, 2, 0, tzinfo=timezone.utc)
    finally:
        await _cleanup()
