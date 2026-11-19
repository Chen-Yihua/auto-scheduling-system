"""AC1：驗證字串輸入可能缺值，而 datetime 輸入一定回傳 datetime。"""
from datetime import datetime
from typing import Optional, assert_type

from core.datetimes import to_utc_datetime


def string_value() -> str:
    return ""


maybe_datetime: str = string_value()
datetime_value: datetime = datetime.now()

assert_type(to_utc_datetime(maybe_datetime), Optional[datetime])
assert_type(to_utc_datetime(datetime_value), datetime)
