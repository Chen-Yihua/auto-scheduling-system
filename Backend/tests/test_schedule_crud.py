from datetime import datetime, timedelta, timezone

from crud.schedule import build_schedule_suggestion


def _task(id, title, priority, status="To Do", due_date=None, duration=None):
    return {
        "id": id, "title": title, "priority": priority, "status": status,
        "due_date": due_date, "duration": duration,
    }


def _slot(start_iso, end_iso):
    return {"start": start_iso, "end": end_iso}


def test_high_priority_scheduled_before_low_when_only_one_slot_fits_one_task():
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


def test_same_priority_sorted_by_due_date_earliest_first():
    tasks = [
        _task("t1", "晚一點的deadline", "High", due_date=datetime(2026, 9, 20)),
        _task("t2", "早一點的deadline", "High", due_date=datetime(2026, 9, 12)),
    ]
    free_slots = [_slot("2026-09-10T09:00:00Z", "2026-09-10T10:00:00Z")]

    result = build_schedule_suggestion(tasks, free_slots)

    assert len(result["scheduled"]) == 1
    assert result["scheduled"][0]["task_id"] == "t2"


def test_task_without_due_date_sorted_after_ones_with_due_date_in_same_priority():
    tasks = [
        _task("t1", "沒有deadline", "High", due_date=None),
        _task("t2", "有deadline", "High", due_date=datetime(2026, 9, 12)),
    ]
    free_slots = [_slot("2026-09-10T09:00:00Z", "2026-09-10T10:00:00Z")]

    result = build_schedule_suggestion(tasks, free_slots)

    assert result["scheduled"][0]["task_id"] == "t2"
    assert result["unscheduled"][0]["task_id"] == "t1"


def test_done_tasks_are_excluded():
    tasks = [
        _task("t1", "已完成", "High", status="Done"),
        _task("t2", "還沒做", "Low"),
    ]
    free_slots = [_slot("2026-09-10T09:00:00Z", "2026-09-10T10:00:00Z")]

    result = build_schedule_suggestion(tasks, free_slots)

    assert len(result["scheduled"]) == 1
    assert result["scheduled"][0]["task_id"] == "t2"


def test_multiple_tasks_fill_sequentially_within_one_long_slot():
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
    tasks = [_task("t1", "太大的任務", "High")]
    # 空檔只有 30 分鐘，塞不下預設 60 分鐘的任務
    free_slots = [_slot("2026-09-10T09:00:00Z", "2026-09-10T09:30:00Z")]

    result = build_schedule_suggestion(tasks, free_slots)

    assert result["scheduled"] == []
    assert len(result["unscheduled"]) == 1
    assert result["unscheduled"][0]["task_id"] == "t1"
    assert "空檔" in result["unscheduled"][0]["reason"]


def test_free_slots_out_of_order_are_still_used_earliest_first():
    tasks = [_task("t1", "任務", "High")]
    free_slots = [
        _slot("2026-09-11T09:00:00Z", "2026-09-11T10:00:00Z"),
        _slot("2026-09-10T09:00:00Z", "2026-09-10T10:00:00Z"),  # 比上面早，但排在後面
    ]

    result = build_schedule_suggestion(tasks, free_slots)

    assert result["scheduled"][0]["start"] == datetime(2026, 9, 10, 9, 0, tzinfo=timezone.utc)


def test_custom_task_duration_minutes():
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
    """
    這條專門驗證「不能因為前面任務太大塞不下，就整個放棄那個空檔」的邏輯：
    - 第一個空檔只有 20 分鐘：大任務（90分）塞不下，但小任務（15分）塞得下
    - 第二個空檔有 90 分鐘：大任務可以塞進去
    正確結果：大任務排進第二個空檔，小任務排進第一個空檔——不能因為
    處理大任務時「跳過」了第一個空檔，就害小任務沒地方去。
    """
    tasks = [
        # 兩個都是 High，用 due_date 確保「大任務」先被處理（早 deadline 先排）
        _task("big", "大任務", "High", duration=90, due_date=datetime(2026, 9, 10)),
        _task("small", "小任務", "High", duration=15, due_date=datetime(2026, 9, 20)),
    ]
    free_slots = [
        _slot("2026-09-10T09:00:00Z", "2026-09-10T09:20:00Z"),  # 20 分鐘
        _slot("2026-09-10T10:00:00Z", "2026-09-10T11:30:00Z"),  # 90 分鐘
    ]

    result = build_schedule_suggestion(tasks, free_slots)

    assert result["unscheduled"] == []
    by_id = {s["task_id"]: s for s in result["scheduled"]}
    assert by_id["big"]["start"] == datetime(2026, 9, 10, 10, 0, tzinfo=timezone.utc)
    assert by_id["small"]["start"] == datetime(2026, 9, 10, 9, 0, tzinfo=timezone.utc)


def test_task_without_duration_falls_back_to_default():
    tasks = [_task("t1", "沒填時長的任務", "High", duration=None)]
    free_slots = [_slot("2026-09-10T09:00:00Z", "2026-09-10T10:00:00Z")]

    result = build_schedule_suggestion(tasks, free_slots)

    assert result["scheduled"][0]["end"] - result["scheduled"][0]["start"] == timedelta(minutes=60)
