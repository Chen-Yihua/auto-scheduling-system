"""
把手動任務、GitHub issue、Jira issue、Moodle 作業統一成同一種「可排程項目」格式，
讓 crud/schedule.py 的 build_schedule_suggestion（一支不碰資料庫的純函式）能一視
同仁地排序、塞空檔，不用自己認識四種不同的資料庫 schema。

每個項目的 id 統一加上來源前綴（"manual:<id>"／"github:<id>"／"jira:<id>"／
"moodle:<id>"），因為 GitHub 的 issue id 跟 Jira 的 issue id 完全有可能
撞號；這個前綴同時也讓 reorder／confirm 這些跨來源的操作知道要寫回哪個 collection。
"""
from datetime import datetime, timezone
from db.mongodb import db
from crud.manualTask import get_manual_tasks_by_user_id, reorder_manual_tasks, set_calendar_event_id

SOURCE_MANUAL = "manual"
SOURCE_GITHUB = "github"
SOURCE_JIRA = "jira"
SOURCE_MOODLE = "moodle"

# 每個外部平台：collection、同步時用的 id 欄位名稱跟型別。手動任務不在這裡——
# 它有自己一整套 crud（crud/manualTask.py），這裡只處理三個外部平台共通的部分。
# id_type 很重要：GitHub 的 issue id 在資料庫裡存的是 int（raw["id"]），
# 但組合 id 組回字串之後就沒有型別資訊了，parse_composite_id 拆出來一律是字串，
# 用字串去查 int 欄位在 Mongo 裡完全比對不到、悄悄查不到任何資料，要查詢前轉型別轉回來
_EXTERNAL_SOURCES = {
    SOURCE_GITHUB: {"collection": lambda: db.github_issues, "id_field": "id", "id_type": int},
    SOURCE_JIRA:   {"collection": lambda: db.jira_issues,   "id_field": "id", "id_type": str},
    SOURCE_MOODLE: {"collection": lambda: db.moodle_assignments, "id_field": "id", "id_type": str},
}


def make_composite_id(source: str, item_id) -> str:
    return f"{source}:{item_id}"


def parse_composite_id(composite_id: str) -> tuple[str, str]:
    source, _, item_id = composite_id.partition(":")
    return source, item_id


def _query_id(source: str, raw_id: str):
    """把 parse_composite_id 拆出來的字串 id，轉回該來源資料庫裡實際存的型別。"""
    return _EXTERNAL_SOURCES[source]["id_type"](raw_id)


def _is_externally_done(source: str, doc: dict) -> bool:
    """平台自己回報的完成狀態。跟使用者在 App 內手動標記的 done 欄位分開判斷，
    兩者只要有一個成立就視為已完成（見 _normalize_external）。"""
    if source == SOURCE_GITHUB:
        return doc.get("status") == "closed"
    if source == SOURCE_JIRA:
        return doc.get("status_category") == "done"
    # Moodle 爬蟲拿不到提交狀態，完全沒有自動判斷依據，只能靠使用者手動標記
    return False


def _normalize_external(source: str, doc: dict, id_field: str) -> dict:
    done = bool(doc.get("done")) or _is_externally_done(source, doc)
    return {
        "id": make_composite_id(source, doc[id_field]),
        "source": source,
        "title": doc.get("title") or "",
        "status": "Done" if done else "To Do",
        "priority": doc.get("priority"),
        "duration": doc.get("duration"),
        "due_date": doc.get("scheduling_due_date"),
        "sort_order": doc.get("sort_order"),
        "calendar_event_id": doc.get("calendar_event_id"),
        "url": doc.get("url"),
    }


async def get_all_schedulable_items(user_id: str) -> list[dict]:
    """
    手動任務 + 三個外部平台的項目，統一成 build_schedule_suggestion 看得懂的格式
    （id/title/status/priority/duration/due_date/sort_order/calendar_event_id）。
    id 一律是加了來源前綴的組合 id。
    """
    manual_tasks = await get_manual_tasks_by_user_id(user_id)
    items = [
        {**t, "source": SOURCE_MANUAL, "id": make_composite_id(SOURCE_MANUAL, t["id"]), "url": None}
        for t in manual_tasks
    ]

    for source, config in _EXTERNAL_SOURCES.items():
        docs = await config["collection"]().find({"user_id": user_id}).to_list(length=None)
        items.extend(_normalize_external(source, doc, config["id_field"]) for doc in docs)

    return items


async def reorder_schedulable_items(user_id: str, items: list[dict]):
    """
    items: [{"task_id": "<composite id>", "priority": "High"}, ...]，依使用者在
    拖拉排序精靈裡提交的完整順序列出（可能混著手動任務跟外部平台項目）。

    sort_order 直接用這份清單裡的索引（0 開始）——刻意不分來源各自重新從 0
    編號，因為 sort_order 只在同一個 priority 內比較（見 crud/schedule.py 的
    sort_key），如果分開編號，兩個來源在同一欄裡本來交錯的順序就會被打散。
    """
    manual_items = []
    for index, item in enumerate(items):
        source, raw_id = parse_composite_id(item["task_id"])
        if source == SOURCE_MANUAL:
            manual_items.append({"task_id": raw_id, "priority": item["priority"], "sort_order": index})
        elif source in _EXTERNAL_SOURCES:
            config = _EXTERNAL_SOURCES[source]
            await config["collection"]().update_one(
                {config["id_field"]: _query_id(source, raw_id), "user_id": user_id},
                {"$set": {"sort_order": index, "priority": item["priority"]}},
            )

    if manual_items:
        await reorder_manual_tasks(user_id, manual_items)


async def update_scheduling_fields(user_id: str, composite_id: str, data: dict):
    """
    設定單一項目的排程欄位（目前只有 due_date／duration，見排程精靈 step 2）。
    手動任務走它自己既有的更新邏輯（crud/manualTask.py），外部平台項目
    直接 $set 到對應 collection，不動平台自己同步回來的原始資料。
    """
    source, raw_id = parse_composite_id(composite_id)
    if source == SOURCE_MANUAL:
        # 沿用手動任務既有的更新方式：get_manual_task_by_id/update_manual_task_by_id
        # 有自己一套「保留沒帶欄位」的邏輯，這裡直接呼叫，不重寫一次
        from crud.manualTask import get_manual_task_by_id, update_manual_task_by_id
        task = await get_manual_task_by_id(raw_id, user_id)
        task.update({"updated": datetime.now(timezone.utc)})
        task.update(data)
        await update_manual_task_by_id(raw_id, task)
        return

    if source in _EXTERNAL_SOURCES:
        config = _EXTERNAL_SOURCES[source]
        await config["collection"]().update_one(
            {config["id_field"]: _query_id(source, raw_id), "user_id": user_id},
            {"$set": data},
        )


async def set_done(user_id: str, composite_id: str, done: bool):
    """
    使用者在 App 內手動標記完成／取消完成。手動任務用既有的 status 欄位
    （"Done" / "To Do"），外部平台項目用新加的 done 欄位——跟平台自己的狀態
    分開存，不會因為這裡標記了就誤以為 GitHub issue 真的關閉了，也不會被
    下一次同步覆蓋掉（sync_platform_items 用 $set，只會動它自己抓回來的欄位）。
    """
    source, raw_id = parse_composite_id(composite_id)
    if source == SOURCE_MANUAL:
        from crud.manualTask import get_manual_task_by_id, update_manual_task_by_id
        task = await get_manual_task_by_id(raw_id, user_id)
        task.update({"status": "Done" if done else "To Do", "updated": datetime.now(timezone.utc)})
        await update_manual_task_by_id(raw_id, task)
        return

    if source in _EXTERNAL_SOURCES:
        config = _EXTERNAL_SOURCES[source]
        await config["collection"]().update_one(
            {config["id_field"]: _query_id(source, raw_id), "user_id": user_id},
            {"$set": {"done": done}},
        )


async def set_calendar_event_id_for_composite(user_id: str, composite_id: str, calendar_event_id: str):
    """確認排程成功後，把 Google Calendar 事件 id 寫回對應來源的那筆項目，標記為已鎖定。"""
    source, raw_id = parse_composite_id(composite_id)
    if source == SOURCE_MANUAL:
        await set_calendar_event_id(raw_id, user_id, calendar_event_id)
        return

    if source in _EXTERNAL_SOURCES:
        config = _EXTERNAL_SOURCES[source]
        await config["collection"]().update_one(
            {config["id_field"]: _query_id(source, raw_id), "user_id": user_id},
            {"$set": {"calendar_event_id": calendar_event_id}},
        )
