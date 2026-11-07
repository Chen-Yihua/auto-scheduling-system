"""後端時間統一轉成帶時區的 UTC：to_utc_datetime 的各種輸入，以及 Mongo client 讀出的時間帶時區。"""
from datetime import datetime, timedelta, timezone

import pytest

from core import database
from core.datetimes import to_utc_datetime

UTC_NOON = datetime(2026, 10, 2, 12, 0, tzinfo=timezone.utc)


@pytest.mark.parametrize("value", [None, ""])
def test_missing_values_become_none(value):
    """AC9：缺值（None、Jira 舊資料的空字串）回 None，不是丟例外。"""
    assert to_utc_datetime(value) is None


@pytest.mark.parametrize("value", [
    "2026-10-02T12:00:00Z",
    "2026-10-02T12:00:00.000Z",
    "2026-10-02T12:00:00+00:00",
    "2026-10-02T20:00:00.000+0800",
    "2026-10-02T20:00:00+08:00",
])
def test_iso_strings_with_offset_become_utc(value):
    """AC9：Z、+00:00、Jira 沒有冒號的 +0800 字串，都轉成同一個 UTC 時間點，而且時區是 UTC。"""
    result = to_utc_datetime(value)

    assert result == UTC_NOON
    assert result is not None and result.utcoffset() == timedelta(0)


def test_naive_values_are_treated_as_utc():
    """AC9：不帶時區的 datetime 或字串視為 UTC，補上時區，時間值不變。"""
    assert to_utc_datetime(datetime(2026, 10, 2, 12, 0)) == UTC_NOON
    assert to_utc_datetime("2026-10-02T12:00:00") == UTC_NOON


def test_aware_datetime_in_other_timezone_is_converted_to_utc():
    """AC9：其他時區的 datetime 轉成 UTC，時間點不變。"""
    taipei = datetime(2026, 10, 2, 20, 0, tzinfo=timezone(timedelta(hours=8)))

    result = to_utc_datetime(taipei)

    assert result == UTC_NOON
    assert result is not None and result.tzinfo == timezone.utc


def test_production_mongo_client_reads_datetimes_with_timezone():
    """AC1、AC4：正式環境的 Mongo client 設 tz_aware，讀出的時間才帶 UTC 時區、回應序列化時才有 Z。"""
    assert database.client.codec_options.tz_aware is True
