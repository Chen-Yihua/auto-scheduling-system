from datetime import datetime, timedelta, timezone
import httpx

# httpx 預設 5 秒（含 DNS 查詢），DNS 偶爾較慢時第一次呼叫會逾時，所以放寬
GOOGLE_HTTP_TIMEOUT = httpx.Timeout(15.0)

async def fetch_google_calendar_list(access_token: str) -> list:
    url = "https://www.googleapis.com/calendar/v3/users/me/calendarList"
    headers = {"Authorization": f"Bearer {access_token}"}
    async with httpx.AsyncClient(timeout=GOOGLE_HTTP_TIMEOUT) as client:
        res = await client.get(url, headers=headers)
        res.raise_for_status()
        return res.json().get("items", [])

async def fetch_freebusy(access_token: str, calendar_id: str) -> dict:
    """取得該行事曆未來 7 天的忙碌時段。"""
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    next_week = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat().replace("+00:00", "Z")
    url = "https://www.googleapis.com/calendar/v3/freeBusy"
    headers = {"Authorization": f"Bearer {access_token}"}
    body = {
        "timeMin": now,
        "timeMax": next_week,
        "timeZone": "UTC",
        "items": [{"id": calendar_id}]
    }
    async with httpx.AsyncClient(timeout=GOOGLE_HTTP_TIMEOUT) as client:
        res = await client.post(url, headers=headers, json=body)
        res.raise_for_status()
        return res.json()


async def create_calendar_event(access_token: str, calendar_id: str, summary: str, start: str, end: str) -> dict:
    """在指定行事曆建立事件。start/end 是 ISO 8601 UTC 字串，例如 "2026-09-10T09:00:00Z"。"""
    url = f"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events"
    headers = {"Authorization": f"Bearer {access_token}"}
    body = {
        "summary": summary,
        "start": {"dateTime": start},
        "end": {"dateTime": end},
    }
    async with httpx.AsyncClient(timeout=GOOGLE_HTTP_TIMEOUT) as client:
        res = await client.post(url, headers=headers, json=body)
        res.raise_for_status()
        return res.json()


def compute_free_times(busy: list[dict], window_start: str, window_end: str) -> list[dict]:
    """從時間窗扣掉 busy 時段，回傳空檔 [{"start", "end"}]。時間都是 ISO UTC 字串。"""

    fmt = lambda s: datetime.fromisoformat(s.replace("Z", "+00:00"))
    start = fmt(window_start)
    end   = fmt(window_end)

    intervals = sorted([
        (fmt(i["start"]), fmt(i["end"]))
        for i in busy
    ], key=lambda x: x[0])

    free = []
    cursor = start

    for b_start, b_end in intervals:
        if cursor < b_start:
            free.append((cursor, b_start))
        cursor = max(cursor, b_end)
    if cursor < end:
        free.append((cursor, end))

    return [
        { "start": s.isoformat().replace("+00:00", "Z"),
          "end":   e.isoformat().replace("+00:00", "Z") }
        for s, e in free
    ]
