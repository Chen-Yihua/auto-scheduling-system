"""外部平台時間的格式統一。"""
import re
from datetime import datetime, timezone
from typing import Optional

# Jira 的時區是 +0800（沒有冒號）；先補成 +08:00，不依賴各 Python 版本 fromisoformat 支援的格式
_OFFSET_WITHOUT_COLON = re.compile(r"([+-]\d{2})(\d{2})$")


def to_utc_datetime(value) -> Optional[datetime]:
    """平台的時間（ISO 字串或 datetime）轉成帶時區的 UTC datetime；缺值（None、空字串）回 None。"""
    if value is None or value == "":
        return None
    if isinstance(value, str):
        text = value.strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        value = datetime.fromisoformat(_OFFSET_WITHOUT_COLON.sub(r"\1:\2", text))
    # Mongo 讀出的 datetime 不帶時區，但存的是 UTC
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
