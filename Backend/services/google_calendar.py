from datetime import datetime, timedelta
import httpx

# 取得所有行事曆列表
async def fetch_google_calendar_list(access_token: str) -> list:
    url = "https://www.googleapis.com/calendar/v3/users/me/calendarList"
    headers = {"Authorization": f"Bearer {access_token}"}
    async with httpx.AsyncClient() as client:
        res = await client.get(url, headers=headers)
        res.raise_for_status()
        return res.json().get("items", [])

# 抓 7 天內的事件
async def fetch_events_in_next_7_days(access_token: str, calendar_id: str) -> list:
    now = datetime.utcnow().isoformat() + "Z"
    next_week = (datetime.utcnow() + timedelta(days=7)).isoformat() + "Z"
    url = f"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events"
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {
        "timeMin": now,
        "timeMax": next_week,
        "singleEvents": True,
        "orderBy": "startTime"
    }

    async with httpx.AsyncClient() as client:
        res = await client.get(url, headers=headers, params=params)
        res.raise_for_status()
        return res.json().get("items", [])


async def fetch_freebusy(access_token: str, calendar_id: str) -> dict:
    """
    使用 Google Calendar FreeBusy API 取得未來 7 天該行事曆的忙碌時間區段
    """
    now = datetime.utcnow().isoformat() + "Z"
    next_week = (datetime.utcnow() + timedelta(days=7)).isoformat() + "Z"
    url = "https://www.googleapis.com/calendar/v3/freeBusy"
    headers = {"Authorization": f"Bearer {access_token}"}
    body = {
        "timeMin": now,
        "timeMax": next_week,
        "timeZone": "UTC",
        "items": [{"id": calendar_id}]
    }
    async with httpx.AsyncClient() as client:
        res = await client.post(url, headers=headers, json=body)
        res.raise_for_status()
        return res.json()


def compute_free_times(busy: list[dict], window_start: str, window_end: str) -> list[dict]:
    """
    busy: [{ "start": "...Z", "end": "...Z" }, ...]
    window_start/end: "...Z"
    回傳 free intervals：[{ "start": ISO, "end": ISO }, ...]
    """

    fmt = lambda s: datetime.fromisoformat(s.replace("Z", "+00:00"))
    start = fmt(window_start)
    end   = fmt(window_end)

    # 解析並排序 busy
    intervals = sorted([
        (fmt(i["start"]), fmt(i["end"]))
        for i in busy
    ], key=lambda x: x[0])

    free = []
    cursor = start

    # 計算 complement
    for b_start, b_end in intervals:
        if cursor < b_start:
            free.append((cursor, b_start))
        cursor = max(cursor, b_end)
    if cursor < end:
        free.append((cursor, end))

    # 回傳成 ISO 字串
    return [
        { "start": s.isoformat().replace("+00:00", "Z"),
          "end":   e.isoformat().replace("+00:00", "Z") }
        for s, e in free
    ]
