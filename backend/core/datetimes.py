"""後端唯一的「時間轉成帶時區的 UTC」：外部平台的字串時間、資料庫讀出或請求帶來的 datetime 都經過這裡。"""
import re
from datetime import datetime, timezone
from typing import Any, Literal, Optional, overload

# Jira 的時區是 +0800（沒有冒號）；先補成 +08:00，不依賴各 Python 版本 fromisoformat 支援的格式
_OFFSET_WITHOUT_COLON = re.compile(r"([+-]\d{2})(\d{2})$")


@overload
def to_utc_datetime(value: None | Literal[""]) -> None: ...
@overload
def to_utc_datetime(value: str | datetime) -> datetime: ...
@overload
def to_utc_datetime(value: Any) -> Optional[datetime]: ...
def to_utc_datetime(value: Any) -> Optional[datetime]:
    """ISO 字串或 datetime 轉成帶時區的 UTC datetime；缺值（None、空字串）回 None。"""
    if value is None or value == "":
        return None
    if isinstance(value, str):
        text = value.strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        value = datetime.fromisoformat(_OFFSET_WITHOUT_COLON.sub(r"\1:\2", text))
    # 不帶時區的視為 UTC：後端只存 UTC，MongoDB 的日期也只存 UTC
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
