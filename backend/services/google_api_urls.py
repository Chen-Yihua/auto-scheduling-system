"""Google Calendar API 與 OAuth token endpoint 的網址。"""
import os

GOOGLE_CALENDAR_API = "https://www.googleapis.com"
GOOGLE_OAUTH_API = "https://oauth2.googleapis.com"


def _base_url(default: str) -> str:
    # 每次呼叫才讀環境變數：只給 E2E 指向假的 Google 伺服器；正式環境不設定，沒設定就連真的 Google
    override = os.getenv("GOOGLE_API_BASE_URL")
    return override.rstrip("/") if override else default


def calendar_list_url() -> str:
    return f"{_base_url(GOOGLE_CALENDAR_API)}/calendar/v3/users/me/calendarList"


def freebusy_url() -> str:
    return f"{_base_url(GOOGLE_CALENDAR_API)}/calendar/v3/freeBusy"


def events_url(calendar_id: str) -> str:
    return f"{_base_url(GOOGLE_CALENDAR_API)}/calendar/v3/calendars/{calendar_id}/events"


def event_url(calendar_id: str, event_id: str) -> str:
    return f"{events_url(calendar_id)}/{event_id}"


def token_url() -> str:
    return f"{_base_url(GOOGLE_OAUTH_API)}/token"
