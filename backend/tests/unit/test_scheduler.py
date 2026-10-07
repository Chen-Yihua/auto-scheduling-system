from datetime import date, datetime, timedelta, timezone

import pytest

from services.scheduler import build_schedule_suggestion, apply_blocked_periods, check_suggestion_still_valid, _parse_iso, _sortable_due_date


def _task(id, title, priority, status="To Do", due_date=None, duration=None, sort_order=None, calendar_event_id=None):
    return {
        "id": id, "title": title, "priority": priority, "status": status,
        "due_date": due_date, "duration": duration, "sort_order": sort_order,
        "calendar_event_id": calendar_event_id,
    }


def _slot(start_iso, end_iso):
    return {"start": start_iso, "end": end_iso}


# 測試裡的空檔、截止日都是寫死的日期，判斷「24 小時內到期」的基準時間也要寫死，
# 不然結果會隨著實際跑測試的日期改變。這個時間點比測試裡所有截止日都早很多，
# 不會把它們誤判成緊急任務——只測一般排序規則的測試都用這個
NOW = datetime(2026, 8, 1, tzinfo=timezone.utc)


def test_high_priority_scheduled_before_low_when_only_one_slot_fits_one_task():
    """優先度高的先排：只有一個空檔、只夠排一個任務時，High 排進去，Low 進 unscheduled 並附上原因。"""
    tasks = [
        _task("t1", "低優先", "Low"),
        _task("t2", "高優先", "High"),
    ]
    # 一個 60 分鐘的空檔，只夠排一個任務
    free_slots = [_slot("2026-09-10T09:00:00Z", "2026-09-10T10:00:00Z")]

    result = build_schedule_suggestion(tasks, free_slots)

    assert len(result["scheduled"]) == 1
    assert result["scheduled"][0]["task_id"] == "t2"
    assert len(result["unscheduled"]) == 1
    assert result["unscheduled"][0]["task_id"] == "t1"
    assert result["unscheduled"][0]["reason"]


def test_priority_still_wins_over_sort_order_across_different_priorities():
    """priority 仍然是主要依據：Low 任務就算 sort_order 排在最前面，也不會排在 High 任務前面
    ——拖拉排序精靈現在是三欄式（低/中/高），sort_order 只在同一欄內才有意義。"""
    tasks = [
        _task("t1", "High，沒特別排過序", "High"),
        _task("t2", "Low，但 sort_order=0", "Low", sort_order=0),
    ]
    free_slots = [_slot("2026-09-10T09:00:00Z", "2026-09-10T10:00:00Z")]

    result = build_schedule_suggestion(tasks, free_slots)

    assert result["scheduled"][0]["task_id"] == "t1"  # priority 較高，即使沒有 sort_order 也先排
    assert result["unscheduled"][0]["task_id"] == "t2"


def test_sort_order_breaks_ties_within_the_same_priority():
    """同一個 priority 內，sort_order 小的先排——這是使用者在拖拉排序精靈同一欄
    內排的上下順序（見 PUT /schedule/reorder）。"""
    tasks = [
        _task("t1", "同為 High，排序在後面", "High", sort_order=1),
        _task("t2", "同為 High，排序在前面", "High", sort_order=0),
    ]
    free_slots = [_slot("2026-09-10T09:00:00Z", "2026-09-10T10:00:00Z")]

    result = build_schedule_suggestion(tasks, free_slots)

    assert result["scheduled"][0]["task_id"] == "t2"
    assert result["unscheduled"][0]["task_id"] == "t1"


def test_tasks_without_sort_order_fall_back_to_due_date_and_are_sorted_after_ones_with_sort_order():
    """同一個 priority 內，沒有 sort_order 的任務（例如排完序後才新建的）退回 due_date 排序，
    但一律排在同 priority 內有 sort_order 的任務後面——手動排過序的結果優先。"""
    tasks = [
        _task("t1", "同為 Low，沒排過序", "Low", sort_order=None, due_date=datetime(2026, 9, 15)),
        _task("t2", "同為 Low，排過序 sort_order=0", "Low", sort_order=0, due_date=datetime(2026, 12, 1)),
    ]
    free_slots = [_slot("2026-09-10T09:00:00Z", "2026-09-10T10:00:00Z")]

    result = build_schedule_suggestion(tasks, free_slots, now=NOW)

    assert result["scheduled"][0]["task_id"] == "t2"
    assert result["unscheduled"][0]["task_id"] == "t1"


def test_tasks_already_confirmed_and_locked_are_excluded_from_scheduling():
    """已經「確認排程」寫進 Google Calendar 的任務（有 calendar_event_id）→ 排除在外，
    不會再出現在 scheduled 或 unscheduled 裡，那個時段已經是既成事實。"""
    tasks = [
        _task("t1", "已鎖定的任務", "High", calendar_event_id="event-123"),
        _task("t2", "還沒排程的任務", "High"),
    ]
    free_slots = [_slot("2026-09-10T09:00:00Z", "2026-09-10T10:00:00Z")]

    result = build_schedule_suggestion(tasks, free_slots)

    all_task_ids = [t["task_id"] for t in result["scheduled"]] + [t["task_id"] for t in result["unscheduled"]]
    assert "t1" not in all_task_ids
    assert result["scheduled"][0]["task_id"] == "t2"


def test_same_priority_sorted_by_due_date_earliest_first():
    """同優先度時，截止日早的先排。"""
    tasks = [
        _task("t1", "晚一點的deadline", "High", due_date=datetime(2026, 9, 20)),
        _task("t2", "早一點的deadline", "High", due_date=datetime(2026, 9, 12)),
    ]
    free_slots = [_slot("2026-09-10T09:00:00Z", "2026-09-10T10:00:00Z")]

    result = build_schedule_suggestion(tasks, free_slots, now=NOW)

    assert len(result["scheduled"]) == 1
    assert result["scheduled"][0]["task_id"] == "t2"


def test_task_without_due_date_sorted_after_ones_with_due_date_in_same_priority():
    """同優先度下，沒有截止日的排在有截止日的後面。"""
    tasks = [
        _task("t1", "沒有deadline", "High", due_date=None),
        _task("t2", "有deadline", "High", due_date=datetime(2026, 9, 12)),
    ]
    free_slots = [_slot("2026-09-10T09:00:00Z", "2026-09-10T10:00:00Z")]

    result = build_schedule_suggestion(tasks, free_slots, now=NOW)

    assert result["scheduled"][0]["task_id"] == "t2"
    assert result["unscheduled"][0]["task_id"] == "t1"


def test_done_tasks_are_excluded():
    """已完成（Done）的任務不排進行程。"""
    tasks = [
        _task("t1", "已完成", "High", status="Done"),
        _task("t2", "還沒做", "Low"),
    ]
    free_slots = [_slot("2026-09-10T09:00:00Z", "2026-09-10T10:00:00Z")]

    result = build_schedule_suggestion(tasks, free_slots)

    assert len(result["scheduled"]) == 1
    assert result["scheduled"][0]["task_id"] == "t2"


def test_multiple_tasks_fill_sequentially_within_one_long_slot():
    """一個長空檔可以依序塞多個任務，第二個接在第一個結束時間之後開始，不能重疊。"""
    tasks = [
        _task("t1", "任務一", "High"),
        _task("t2", "任務二", "High"),
    ]
    # 一個 2 小時的空檔，足夠塞兩個 60 分鐘任務
    free_slots = [_slot("2026-09-10T09:00:00Z", "2026-09-10T11:00:00Z")]

    result = build_schedule_suggestion(tasks, free_slots)

    assert len(result["scheduled"]) == 2
    assert result["unscheduled"] == []

    first, second = result["scheduled"]
    assert first["start"] == datetime(2026, 9, 10, 9, 0, tzinfo=timezone.utc)
    assert first["end"] == datetime(2026, 9, 10, 10, 0, tzinfo=timezone.utc)
    # 第二個任務接續在第一個任務結束的時間點開始，不能重疊
    assert second["start"] == first["end"]
    assert second["end"] == datetime(2026, 9, 10, 11, 0, tzinfo=timezone.utc)


def test_task_that_does_not_fit_any_slot_is_unscheduled_with_reason():
    """塞不進任何空檔的任務 → 放進 unscheduled，並附上包含「空檔」的原因。"""
    tasks = [_task("t1", "太大的任務", "High")]
    # 空檔只有 30 分鐘，塞不下預設 60 分鐘的任務
    free_slots = [_slot("2026-09-10T09:00:00Z", "2026-09-10T09:30:00Z")]

    result = build_schedule_suggestion(tasks, free_slots)

    assert result["scheduled"] == []
    assert len(result["unscheduled"]) == 1
    assert result["unscheduled"][0]["task_id"] == "t1"
    assert "空檔" in result["unscheduled"][0]["reason"]


def test_free_slots_out_of_order_are_still_used_earliest_first():
    """空檔沒照時間排序也要能用：永遠先用最早的空檔。"""
    tasks = [_task("t1", "任務", "High")]
    free_slots = [
        _slot("2026-09-11T09:00:00Z", "2026-09-11T10:00:00Z"),
        _slot("2026-09-10T09:00:00Z", "2026-09-10T10:00:00Z"),  # 比上面早，但排在後面
    ]

    result = build_schedule_suggestion(tasks, free_slots)

    assert result["scheduled"][0]["start"] == datetime(2026, 9, 10, 9, 0, tzinfo=timezone.utc)


def test_custom_task_duration_minutes():
    """指定每個任務的預設時長為 20 分鐘 → 一個 60 分鐘的空檔可以塞下 3 個任務。"""
    tasks = [
        _task("t1", "任務一", "High"),
        _task("t2", "任務二", "High"),
        _task("t3", "任務三", "High"),
    ]
    free_slots = [_slot("2026-09-10T09:00:00Z", "2026-09-10T10:00:00Z")]

    # 每個任務只佔 20 分鐘，一個 60 分鐘的空檔應該可以塞下 3 個
    result = build_schedule_suggestion(tasks, free_slots, task_duration_minutes=20)

    assert len(result["scheduled"]) == 3
    assert result["unscheduled"] == []


def test_each_task_uses_its_own_duration_field():
    """每個任務用自己的 duration 欄位（90 分鐘、30 分鐘）排，不是全部用同一個預設時長。"""
    tasks = [
        _task("t1", "任務一", "High", duration=90),
        _task("t2", "任務二", "Medium", duration=30),
    ]
    free_slots = [_slot("2026-09-10T09:00:00Z", "2026-09-10T11:00:00Z")]  # 2 小時

    result = build_schedule_suggestion(tasks, free_slots)

    assert len(result["scheduled"]) == 2
    first, second = result["scheduled"]
    assert first["end"] - first["start"] == timedelta(minutes=90)
    assert second["end"] - second["start"] == timedelta(minutes=30)


def test_small_task_can_still_use_a_slot_too_small_for_an_earlier_big_task():
    """前面的大任務塞不下的空檔，仍要留給後面較小的任務用。
例：20 分鐘和 90 分鐘兩個空檔，90 分鐘的大任務排進後者，15 分鐘的小任務排進前者——
不能因為處理大任務時「跳過」了 20 分鐘的空檔，就害小任務沒地方去。"""
    tasks = [
        # 兩個都是 High，用 due_date 確保「大任務」先被處理（早 deadline 先排）
        _task("big", "大任務", "High", duration=90, due_date=datetime(2026, 9, 15)),
        _task("small", "小任務", "High", duration=15, due_date=datetime(2026, 9, 20)),
    ]
    free_slots = [
        _slot("2026-09-10T09:00:00Z", "2026-09-10T09:20:00Z"),  # 20 分鐘
        _slot("2026-09-10T10:00:00Z", "2026-09-10T11:30:00Z"),  # 90 分鐘
    ]

    result = build_schedule_suggestion(tasks, free_slots, now=NOW)

    assert result["unscheduled"] == []
    by_id = {s["task_id"]: s for s in result["scheduled"]}
    assert by_id["big"]["start"] == datetime(2026, 9, 10, 10, 0, tzinfo=timezone.utc)
    assert by_id["small"]["start"] == datetime(2026, 9, 10, 9, 0, tzinfo=timezone.utc)


def test_task_without_duration_falls_back_to_default():
    """任務沒填時長 → 退回預設的 60 分鐘。"""
    tasks = [_task("t1", "沒填時長的任務", "High", duration=None)]
    free_slots = [_slot("2026-09-10T09:00:00Z", "2026-09-10T10:00:00Z")]

    result = build_schedule_suggestion(tasks, free_slots)

    assert result["scheduled"][0]["end"] - result["scheduled"][0]["start"] == timedelta(minutes=60)


def test_task_missing_required_field_is_skipped_not_crashed():
    """任務缺必要欄位（例如 priority 是 None 的壞資料）→ 跳過這筆，不能讓整個請求 KeyError 當掉。正常情況 id/title/priority 一定有值。"""
    tasks = [
        {"id": "t1", "title": "缺 priority", "priority": None, "status": "To Do"},
        _task("t2", "正常任務", "High"),
    ]
    free_slots = [_slot("2026-09-10T09:00:00Z", "2026-09-10T10:00:00Z")]

    result = build_schedule_suggestion(tasks, free_slots)

    assert len(result["scheduled"]) == 1
    assert result["scheduled"][0]["task_id"] == "t2"
    assert result["unscheduled"] == []


def test_parse_iso_passes_through_existing_datetime_unchanged():
    """_parse_iso 收到已經是 datetime 的值 → 原樣回傳，不重新解析。"""
    # 空檔目前都是 ISO 字串，但函式也支援直接傳 datetime，這個情況要單獨測
    dt = datetime(2026, 9, 10, 9, 0, tzinfo=timezone.utc)

    result = _parse_iso(dt)

    assert result is dt


def test_sortable_due_date_strips_timezone_from_aware_datetime():
    """有時區的 due_date 排序前要去掉時區資訊，才能跟沒有時區的日期比較。"""
    aware = datetime(2026, 9, 10, 9, 0, tzinfo=timezone.utc)

    result = _sortable_due_date(aware)

    assert result == datetime(2026, 9, 10, 9, 0)
    assert result.tzinfo is None


def test_slot_missing_start_or_end_is_skipped_not_crashed():
    """空檔缺 start 或 end（壞資料）→ 跳過那個空檔，用下一個正常的空檔排。"""
    tasks = [_task("t1", "任務", "High")]
    free_slots = [
        {"start": "2026-09-10T09:00:00Z", "end": None},  # 壞資料，跳過
        _slot("2026-09-10T10:00:00Z", "2026-09-10T11:00:00Z"),
    ]

    result = build_schedule_suggestion(tasks, free_slots)

    assert len(result["scheduled"]) == 1
    assert result["scheduled"][0]["start"] == datetime(2026, 9, 10, 10, 0, tzinfo=timezone.utc)


# ---------- buffer_minutes ----------

def test_buffer_minutes_zero_keeps_tasks_back_to_back():
    """buffer_minutes 預設 0：兩個任務加起來剛好塞滿空檔，完全貼著排。"""
    tasks = [
        _task("t1", "T1", "High", sort_order=0, duration=60),
        _task("t2", "T2", "High", sort_order=1, duration=30),
    ]
    free_slots = [_slot("2026-09-10T09:00:00Z", "2026-09-10T10:30:00Z")]

    result = build_schedule_suggestion(tasks, free_slots)

    assert [t["task_id"] for t in result["scheduled"]] == ["t1", "t2"]
    assert result["unscheduled"] == []


def test_buffer_minutes_leaves_gap_that_can_push_next_task_to_unscheduled():
    """buffer_minutes>0：任務之間留緩衝時間，同一個空檔可能因此塞不下原本剛好塞得下的任務。"""
    tasks = [
        _task("t1", "T1", "High", sort_order=0, duration=60),
        _task("t2", "T2", "High", sort_order=1, duration=30),
    ]
    free_slots = [_slot("2026-09-10T09:00:00Z", "2026-09-10T10:30:00Z")]

    result = build_schedule_suggestion(tasks, free_slots, buffer_minutes=15)

    assert [t["task_id"] for t in result["scheduled"]] == ["t1"]
    assert [t["task_id"] for t in result["unscheduled"]] == ["t2"]


# ---------- daily_max_minutes ----------

def test_daily_max_minutes_spills_task_over_to_a_later_day_slot():
    """同一天已經排到上限 → 該天剩下的空檔先跳過，改用別天的空檔，不會整段消耗掉。"""
    tasks = [
        _task("t1", "T1", "High", sort_order=0, duration=60),
        _task("t2", "T2", "High", sort_order=1, duration=60),
    ]
    free_slots = [
        _slot("2026-09-10T09:00:00Z", "2026-09-10T12:00:00Z"),
        _slot("2026-09-11T09:00:00Z", "2026-09-11T12:00:00Z"),
    ]

    result = build_schedule_suggestion(tasks, free_slots, daily_max_minutes=60)

    assert result["unscheduled"] == []
    scheduled_by_id = {t["task_id"]: t for t in result["scheduled"]}
    assert scheduled_by_id["t1"]["start"] == datetime(2026, 9, 10, 9, 0, tzinfo=timezone.utc)
    assert scheduled_by_id["t2"]["start"] == datetime(2026, 9, 11, 9, 0, tzinfo=timezone.utc)


def test_daily_max_minutes_none_means_no_cap():
    """daily_max_minutes 沒帶（None）→ 不做任何每日上限限制，維持原本行為。"""
    tasks = [
        _task("t1", "T1", "High", sort_order=0, duration=60),
        _task("t2", "T2", "High", sort_order=1, duration=60),
    ]
    free_slots = [_slot("2026-09-10T09:00:00Z", "2026-09-10T12:00:00Z")]

    result = build_schedule_suggestion(tasks, free_slots)

    assert [t["task_id"] for t in result["scheduled"]] == ["t1", "t2"]


# ---------- apply_blocked_periods ----------


# ---------- 緊急任務（24 小時內到期）與截止日檢查 ----------

def test_urgent_low_priority_task_is_scheduled_before_non_urgent_high_priority_task():
    """今晚就要交的 Low 任務，要排在下週才到期的 High 任務前面——
    不能只看 priority，讓緊急的任務被擠到截止日之後。"""
    now = datetime(2026, 9, 10, 18, 0, tzinfo=timezone.utc)
    tasks = [
        _task("report", "下週要交的報告", "High", duration=120, due_date=datetime(2026, 9, 17, tzinfo=timezone.utc)),
        _task("homework", "今晚要交的作業", "Low", duration=60, due_date=datetime(2026, 9, 10, 23, 59, tzinfo=timezone.utc)),
    ]
    free_slots = [
        _slot("2026-09-10T19:00:00Z", "2026-09-10T21:00:00Z"),  # 今晚只剩這段
        _slot("2026-09-11T09:00:00Z", "2026-09-11T12:00:00Z"),
    ]

    result = build_schedule_suggestion(tasks, free_slots, now=now)

    by_id = {s["task_id"]: s for s in result["scheduled"]}
    assert by_id["homework"]["start"] == datetime(2026, 9, 10, 19, 0, tzinfo=timezone.utc)
    assert by_id["report"]["start"] == datetime(2026, 9, 11, 9, 0, tzinfo=timezone.utc)
    assert result["unscheduled"] == []


def test_multiple_urgent_tasks_are_ordered_by_due_date_regardless_of_priority():
    """緊急任務之間依截止日早到晚（EDF），priority 不影響——都快到期了，先到期的先做。"""
    now = datetime(2026, 9, 10, 8, 0, tzinfo=timezone.utc)
    tasks = [
        _task("high_later", "High，晚上到期", "High", due_date=datetime(2026, 9, 10, 22, 0, tzinfo=timezone.utc)),
        _task("low_sooner", "Low，中午到期", "Low", due_date=datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc)),
    ]
    free_slots = [_slot("2026-09-10T09:00:00Z", "2026-09-10T11:00:00Z")]

    result = build_schedule_suggestion(tasks, free_slots, now=now)

    assert [s["task_id"] for s in result["scheduled"]] == ["low_sooner", "high_later"]


def test_task_is_not_placed_after_its_deadline():
    """唯一放得下的空檔在截止日之後 → 不能排進去還顯示成「已排入」，
    要列進 unscheduled，並說明是截止日前排不進去。"""
    now = datetime(2026, 9, 1, tzinfo=timezone.utc)
    tasks = [_task("t1", "9/10 中午前要交", "High", duration=60, due_date=datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc))]
    free_slots = [_slot("2026-09-10T13:00:00Z", "2026-09-10T15:00:00Z")]

    result = build_schedule_suggestion(tasks, free_slots, now=now)

    assert result["scheduled"] == []
    assert result["unscheduled"][0]["reason"] == "截止日前沒有足夠的空檔"


def test_task_skips_too_small_early_slot_but_still_fits_before_deadline():
    """最早的空檔太小，下一個空檔還在截止日前 → 照樣排進去；截止日只擋「排在截止日之後」，
    不會因為第一個空檔放不下就誤判成趕不上。"""
    now = datetime(2026, 9, 1, tzinfo=timezone.utc)
    tasks = [_task("t1", "任務", "High", duration=60, due_date=datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc))]
    free_slots = [
        _slot("2026-09-10T08:00:00Z", "2026-09-10T08:30:00Z"),  # 30 分鐘，太小
        _slot("2026-09-10T10:00:00Z", "2026-09-10T11:30:00Z"),
    ]

    result = build_schedule_suggestion(tasks, free_slots, now=now)

    assert result["scheduled"][0]["start"] == datetime(2026, 9, 10, 10, 0, tzinfo=timezone.utc)


def test_overdue_task_is_still_scheduled_as_soon_as_possible():
    """已經過期的任務沒有「趕得上」的可能，不套用截止日檢查（不然永遠排不進去），
    而是當成緊急任務，排在一般 High 任務前面、盡早補做。"""
    now = datetime(2026, 9, 10, 8, 0, tzinfo=timezone.utc)
    tasks = [
        _task("high", "一般 High", "High"),
        _task("overdue", "昨天就該交了", "Low", due_date=datetime(2026, 9, 9, tzinfo=timezone.utc)),
    ]
    free_slots = [_slot("2026-09-10T09:00:00Z", "2026-09-10T10:00:00Z")]

    result = build_schedule_suggestion(tasks, free_slots, now=now)

    assert result["scheduled"][0]["task_id"] == "overdue"
    assert result["unscheduled"][0]["task_id"] == "high"


def test_deadline_with_non_utc_timezone_is_compared_at_the_same_instant():
    """截止日帶台灣時區（+08:00）時，要換算成同一個時刻跟 UTC 的空檔比較：
    台灣時間 18:00 = UTC 10:00，09:00–10:00Z 的空檔剛好趕得上。"""
    now = datetime(2026, 9, 1, tzinfo=timezone.utc)
    taipei = timezone(timedelta(hours=8))
    tasks = [_task("t1", "台灣時間 18:00 截止", "High", duration=60, due_date=datetime(2026, 9, 10, 18, 0, tzinfo=taipei))]
    free_slots = [_slot("2026-09-10T09:00:00Z", "2026-09-10T10:00:00Z")]

    result = build_schedule_suggestion(tasks, free_slots, now=now)

    assert result["scheduled"][0]["task_id"] == "t1"

def test_apply_blocked_periods_returns_input_unchanged_when_no_rules():
    free_slots = [_slot("2026-09-10T09:00:00Z", "2026-09-10T17:00:00Z")]

    result = apply_blocked_periods(free_slots)

    assert result is free_slots


def test_apply_blocked_periods_recurring_all_day_removes_whole_day_slot():
    """「週六、週日全天」這種規則：全天都不工作，那一天的空檔整個被挖掉。"""
    day = date(2026, 9, 12)
    free_slots = [_slot(f"{day}T09:00:00Z", f"{day}T17:00:00Z")]
    rule = {"days_of_week": [day.weekday()], "all_day": True}

    result = apply_blocked_periods(free_slots, blocked_recurring=[rule])

    assert result == []


def test_apply_blocked_periods_output_keeps_utc_marker_so_frontend_does_not_misread_it_as_local_time():
    """曾經是真的會炸的 bug：內部比較時把時間去掉時區（當成牆上時鐘時間）算完後，
    輸出忘記補回 UTC 標記（Z），少了它前端 new Date(...) 會把這個字串當成瀏覽器
    所在時區的本地時間解讀——結果使用者看到排程建議排在已經過去的時間
    （例如現在已經是晚上，卻顯示排在「今天早上」）。"""
    day = date(2026, 9, 10)
    free_slots = [_slot(f"{day}T09:00:00Z", f"{day}T17:00:00Z")]
    rule = {"days_of_week": [day.weekday()], "all_day": False, "start_time": "12:00", "end_time": "13:00"}

    result = apply_blocked_periods(free_slots, blocked_recurring=[rule])

    for slot in result:
        assert slot["start"].endswith("Z")
        assert slot["end"].endswith("Z")


def test_apply_blocked_periods_recurring_time_range_splits_slot_into_two():
    """「每天中午 12:00-13:00」這種規則：把一個空檔從中間挖掉一段，變成前後兩段。"""
    day = date(2026, 9, 10)
    free_slots = [_slot(f"{day}T09:00:00Z", f"{day}T17:00:00Z")]
    rule = {"days_of_week": [day.weekday()], "all_day": False, "start_time": "12:00", "end_time": "13:00"}

    result = apply_blocked_periods(free_slots, blocked_recurring=[rule])

    assert result == [
        {"start": "2026-09-10T09:00:00Z", "end": "2026-09-10T12:00:00Z"},
        {"start": "2026-09-10T13:00:00Z", "end": "2026-09-10T17:00:00Z"},
    ]


def test_apply_blocked_periods_recurring_overnight_wrap_blocks_across_midnight():
    """跨過午夜的規律（例如「每天 22:00-08:00」）：拆成當天晚上跟隔天一早兩段一起挖掉。"""
    day = date(2026, 9, 10)
    next_day = day + timedelta(days=1)
    free_slots = [_slot(f"{day}T20:00:00Z", f"{next_day}T10:00:00Z")]
    rule = {
        "days_of_week": [day.weekday(), next_day.weekday()],
        "all_day": False, "start_time": "22:00", "end_time": "08:00",
    }

    result = apply_blocked_periods(free_slots, blocked_recurring=[rule])

    assert result == [
        {"start": "2026-09-10T20:00:00Z", "end": "2026-09-10T22:00:00Z"},
        {"start": "2026-09-11T08:00:00Z", "end": "2026-09-11T10:00:00Z"},
    ]


def test_apply_blocked_periods_exception_cuts_specific_range_out_of_slot():
    """這次排程期間內額外加的一次性例外時段，只挖掉那一段，不影響其他規律。"""
    free_slots = [_slot("2026-09-10T09:00:00Z", "2026-09-10T17:00:00Z")]
    exceptions = [{"start": "2026-09-10T14:00:00Z", "end": "2026-09-10T15:00:00Z"}]

    result = apply_blocked_periods(free_slots, blocked_exceptions=exceptions)

    assert result == [
        {"start": "2026-09-10T09:00:00Z", "end": "2026-09-10T14:00:00Z"},
        {"start": "2026-09-10T15:00:00Z", "end": "2026-09-10T17:00:00Z"},
    ]


def test_apply_blocked_periods_skips_malformed_slots_and_exceptions():
    """壞資料（缺 start/end）不該讓整個計算炸掉：壞的空檔跳過，壞的例外當沒這條規則。"""
    free_slots = [
        {"start": "2026-09-10T09:00:00Z", "end": None},
        _slot("2026-09-10T09:00:00Z", "2026-09-10T10:00:00Z"),
    ]
    exceptions = [{"start": "2026-09-10T09:30:00Z"}]  # 沒有 end，忽略這條

    result = apply_blocked_periods(free_slots, blocked_exceptions=exceptions)

    assert result == [{"start": "2026-09-10T09:00:00Z", "end": "2026-09-10T10:00:00Z"}]


def test_apply_blocked_periods_skips_recurring_rule_missing_start_or_end_time():
    """使用者在精靈畫面勾了星期、但還沒填起訖時間（規律填到一半）就送出——
    不是 all_day 卻缺 start_time/end_time 的規則當還沒設定完整，跳過，
    不該讓整個排程建議計算噴例外（曾經是真的會炸：AttributeError on None.split）。"""
    day = date(2026, 9, 10)
    free_slots = [_slot(f"{day}T09:00:00Z", f"{day}T17:00:00Z")]
    rule = {"days_of_week": [day.weekday()], "all_day": False, "start_time": None, "end_time": None}

    result = apply_blocked_periods(free_slots, blocked_recurring=[rule])

    assert result == [{"start": "2026-09-10T09:00:00Z", "end": "2026-09-10T17:00:00Z"}]


# ---------- 使用者時區：不工作時段、每日上限都要用當地時間算 ----------

EVERY_DAY = [0, 1, 2, 3, 4, 5, 6]


def test_apply_blocked_periods_uses_user_local_time_not_utc():
    """台灣使用者（UTC+8）設定「每天 22:00-08:00 不工作」，擋掉的要是台灣時間的半夜，
    也就是 UTC 14:00 到隔天 00:00——之前直接拿 UTC 比，擋成了台灣時間 06:00-16:00。"""
    # 台灣時間 9/10 08:00 ~ 9/11 07:59
    free_slots = [_slot("2026-09-10T00:00:00Z", "2026-09-10T23:59:00Z")]
    rule = {"days_of_week": EVERY_DAY, "all_day": False, "start_time": "22:00", "end_time": "08:00"}

    result = apply_blocked_periods(free_slots, blocked_recurring=[rule], tz_name="Asia/Taipei")

    # 剩下台灣時間 08:00-22:00，換回 UTC 就是 00:00-14:00
    assert result == [_slot("2026-09-10T00:00:00Z", "2026-09-10T14:00:00Z")]


def test_apply_blocked_periods_exception_is_an_exact_instant_regardless_of_timezone():
    """單次例外時段前端送的是 UTC 時刻（toISOString），不管使用者在哪個時區，
    擋掉的都要是那個確切的時刻。"""
    free_slots = [_slot("2026-09-10T00:00:00Z", "2026-09-10T06:00:00Z")]
    exception = {"start": "2026-09-10T02:00:00Z", "end": "2026-09-10T03:00:00Z"}

    result = apply_blocked_periods(free_slots, blocked_exceptions=[exception], tz_name="Asia/Taipei")

    assert result == [
        _slot("2026-09-10T00:00:00Z", "2026-09-10T02:00:00Z"),
        _slot("2026-09-10T03:00:00Z", "2026-09-10T06:00:00Z"),
    ]


def test_daily_max_minutes_counts_days_in_user_local_time():
    """每日上限的「一天」是使用者當地的日曆日：UTC 9/10 15:00 和 17:00 是同一個 UTC 日，
    但在台灣分別是 9/10 23:00 和 9/11 01:00，屬於不同的兩天，各自都還有額度。"""
    tasks = [
        _task("t1", "任務一", "High", duration=60),
        _task("t2", "任務二", "High", duration=60),
    ]
    free_slots = [
        _slot("2026-09-10T15:00:00Z", "2026-09-10T16:00:00Z"),  # 台灣 9/10 23:00
        _slot("2026-09-10T17:00:00Z", "2026-09-10T18:00:00Z"),  # 台灣 9/11 01:00
    ]

    result = build_schedule_suggestion(tasks, free_slots, daily_max_minutes=60, now=NOW, tz_name="Asia/Taipei")

    assert len(result["scheduled"]) == 2
    assert result["unscheduled"] == []



# ---------- check_suggestion_still_valid：確認排程前檢查快照還能不能照寫 ----------

CHECK_NOW = datetime(2026, 9, 10, 8, 0, tzinfo=timezone.utc)


def _scheduled_item(task_id, start_hour, end_hour):
    return {
        "task_id": task_id, "title": task_id, "priority": "High",
        "start": datetime(2026, 9, 10, start_hour, 0, tzinfo=timezone.utc),
        "end": datetime(2026, 9, 10, end_hour, 0, tzinfo=timezone.utc),
    }


def _current_task(task_id, status="To Do", calendar_event_id=None):
    return {"id": task_id, "title": task_id, "status": status, "calendar_event_id": calendar_event_id}


def test_check_suggestion_keeps_items_whose_task_and_slot_are_still_valid():
    """任務還在、還沒完成或鎖定、時段也還空著 → 照原本的時間寫入。"""
    item = _scheduled_item("t1", 9, 10)
    free_slots = [_slot("2026-09-10T08:00:00Z", "2026-09-10T12:00:00Z")]

    to_write, failed = check_suggestion_still_valid([item], [_current_task("t1")], free_slots, now=CHECK_NOW)

    assert to_write == [item]
    assert failed == []


@pytest.mark.parametrize("current_tasks, start_hour, free_slot, reason", [
    ([], 9, ("08:00", "12:00"), "任務已不存在"),
    ([_current_task("t1", status="Done")], 9, ("08:00", "12:00"), "任務已經完成"),
    ([_current_task("t1", calendar_event_id="event-1")], 9, ("08:00", "12:00"), "任務已經排入行事曆"),
    ([_current_task("t1")], 7, ("06:00", "12:00"), "這個時段已經過了，請重新產生排程"),
    ([_current_task("t1")], 9, ("09:30", "12:00"), "這個時段已被其他行程占用，請重新產生排程"),
])
def test_check_suggestion_rejects_items_that_changed_since_the_user_saw_them(current_tasks, start_hour, free_slot, reason):
    """看到建議到按下確認之間，任務或行事曆變了 → 這筆不寫入，附上使用者看得懂的原因。"""
    item = _scheduled_item("t1", start_hour, start_hour + 1)
    free_slots = [_slot(f"2026-09-10T{free_slot[0]}:00Z", f"2026-09-10T{free_slot[1]}:00Z")]

    to_write, failed = check_suggestion_still_valid([item], current_tasks, free_slots, now=CHECK_NOW)

    assert to_write == []
    assert failed == [{"task_id": "t1", "title": "t1", "reason": reason}]
