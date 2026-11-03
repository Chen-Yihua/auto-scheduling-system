"""services/productivity.py：工作效率統計的各項規則。"""
from datetime import date, datetime, timezone

from services.productivity import TREND_WEEKS, build_productivity_summary

# 2026-11-04 是週三
NOW = datetime(2026, 11, 4, 12, 0, tzinfo=timezone.utc)


def _item(source="manual", status="To Do", priority="Medium", duration=60, due_date=None, completed_at=None):
    return {
        "source": source, "status": status, "priority": priority, "duration": duration,
        "due_date": due_date, "completed_at": completed_at,
    }


def _weekly(summary) -> dict:
    return {row["week_start"]: row for row in summary["weekly"]}


def test_empty_list_has_no_rates_and_zero_counts():
    """沒有任何項目 → 完成率和準時率是 None（不是 0），週趨勢仍有 8 週、每週 0。"""
    summary = build_productivity_summary([], NOW, "UTC")

    assert summary["total"] == 0
    assert summary["completion_rate"] is None
    assert summary["on_time"] == {"completed_with_due": 0, "on_time": 0, "rate": None}
    assert len(summary["weekly"]) == TREND_WEEKS
    assert all(row["completed"] == 0 for row in summary["weekly"])
    assert summary["by_source"] == []
    assert summary["by_priority"] == []


def test_completion_rate_and_estimated_minutes():
    """In Progress 算未完成；沒有 duration 的項目不計入工時，未完成的另外算進未估時數。"""
    items = [
        _item(status="Done", duration=30, completed_at=NOW),
        _item(status="In Progress", duration=90),
        _item(status="To Do", duration=None),
        _item(status="To Do", duration=60),
    ]

    summary = build_productivity_summary(items, NOW, "UTC")

    assert (summary["total"], summary["done"]) == (4, 1)
    assert summary["completion_rate"] == 0.25
    assert summary["done_minutes"] == 30
    assert summary["remaining_minutes"] == 150
    assert summary["unestimated_remaining"] == 1


def test_overdue_counts_only_unfinished_items_past_due():
    items = [
        _item(status="To Do", due_date=datetime(2026, 11, 1, tzinfo=timezone.utc)),   # 逾期
        _item(status="Done", due_date=datetime(2026, 11, 1, tzinfo=timezone.utc), completed_at=NOW),  # 已完成不算
        _item(status="To Do", due_date=datetime(2026, 12, 1, tzinfo=timezone.utc)),   # 還沒到期
        _item(status="To Do", due_date=None),                                          # 沒有截止日
    ]

    assert build_productivity_summary(items, NOW, "UTC")["overdue"] == 1


def test_naive_datetimes_from_mongo_are_treated_as_utc():
    """Mongo 讀出來的 datetime 不帶時區（存的是 UTC），要能和帶時區的 now 比較。"""
    items = [_item(status="To Do", due_date=datetime(2026, 11, 4, 11, 0))]

    assert build_productivity_summary(items, NOW, "UTC")["overdue"] == 1


def test_by_source_and_by_priority_only_list_groups_that_have_items():
    items = [
        _item(source="manual", priority="High", status="Done", completed_at=NOW),
        _item(source="manual", priority="Low"),
        _item(source="github", priority=None, status="Done", completed_at=NOW),
    ]

    summary = build_productivity_summary(items, NOW, "UTC")

    assert summary["by_source"] == [
        {"source": "manual", "total": 2, "done": 1},
        {"source": "github", "total": 1, "done": 1},
    ]
    assert summary["by_priority"] == [
        {"priority": "High", "total": 1, "done": 1},
        {"priority": "Low", "total": 1, "done": 0},
        {"priority": None, "total": 1, "done": 1},
    ]


def test_weekly_trend_covers_eight_weeks_ending_with_current_week_starting_monday():
    summary = build_productivity_summary([], NOW, "UTC")

    starts = [row["week_start"] for row in summary["weekly"]]
    assert starts[-1] == date(2026, 11, 2)  # 本週一
    assert starts[0] == date(2026, 9, 14)   # 往前 7 週


def test_weekly_trend_buckets_by_local_time_of_given_timezone():
    """
    台北週日 23:30（UTC 週日 15:30）算上一週；台北週一 00:30（UTC 週日 16:30）算本週。
    用 UTC 切的話兩筆都會落在上一週。
    """
    items = [
        _item(status="Done", duration=20, completed_at=datetime(2026, 11, 1, 15, 30, tzinfo=timezone.utc)),
        _item(status="Done", duration=40, completed_at=datetime(2026, 11, 1, 16, 30, tzinfo=timezone.utc)),
    ]

    weekly = _weekly(build_productivity_summary(items, NOW, "Asia/Taipei"))

    assert weekly[date(2026, 10, 26)] == {"week_start": date(2026, 10, 26), "completed": 1, "completed_minutes": 20}
    assert weekly[date(2026, 11, 2)] == {"week_start": date(2026, 11, 2), "completed": 1, "completed_minutes": 40}


def test_weekly_trend_excludes_completions_before_the_window():
    items = [
        _item(status="Done", completed_at=datetime(2026, 9, 13, 23, 0, tzinfo=timezone.utc)),  # 窗口前一天
        _item(status="Done", completed_at=datetime(2026, 9, 14, 0, 0, tzinfo=timezone.utc)),   # 窗口第一刻
    ]

    summary = build_productivity_summary(items, NOW, "UTC")

    assert sum(row["completed"] for row in summary["weekly"]) == 1
    assert _weekly(summary)[date(2026, 9, 14)]["completed"] == 1
    assert summary["done"] == 2  # 現況統計仍算進去


def test_on_time_rate_counts_completions_in_window_that_have_due_date():
    """AC9（假設 8）：只算近 8 週內完成且有截止日的項目；窗口前完成的即使有截止日也不列入。"""
    items = [
        _item(status="Done", due_date=datetime(2026, 11, 3, tzinfo=timezone.utc),
              completed_at=datetime(2026, 11, 2, tzinfo=timezone.utc)),   # 準時
        _item(status="Done", due_date=datetime(2026, 11, 3, tzinfo=timezone.utc),
              completed_at=datetime(2026, 11, 3, tzinfo=timezone.utc)),   # 剛好截止時完成，算準時
        _item(status="Done", due_date=datetime(2026, 11, 1, tzinfo=timezone.utc),
              completed_at=datetime(2026, 11, 3, tzinfo=timezone.utc)),   # 遲交
        _item(status="Done", due_date=None, completed_at=NOW),            # 沒截止日，不列入
        _item(status="Done", due_date=datetime(2026, 9, 14, tzinfo=timezone.utc),
              completed_at=datetime(2026, 9, 13, tzinfo=timezone.utc)),   # 窗口前完成，不列入
    ]

    on_time = build_productivity_summary(items, NOW, "UTC")["on_time"]

    assert on_time == {"completed_with_due": 3, "on_time": 2, "rate": 2 / 3}


def test_done_items_without_completed_at_are_untracked():
    """開始記錄完成時間前就完成的項目：算進完成數，但不算進週趨勢和準時率。"""
    items = [_item(status="Done", due_date=datetime(2026, 11, 3, tzinfo=timezone.utc), completed_at=None)]

    summary = build_productivity_summary(items, NOW, "UTC")

    assert summary["done"] == 1
    assert summary["untracked_done"] == 1
    assert sum(row["completed"] for row in summary["weekly"]) == 0
    assert summary["on_time"]["completed_with_due"] == 0
