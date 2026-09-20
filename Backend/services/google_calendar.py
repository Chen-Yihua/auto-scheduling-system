from datetime import datetime, timedelta, timezone
import httpx

# 呼叫 Google 的逾時時間。httpx 預設只有 5 秒（連線階段包含 DNS 查詢），
# 在 DNS 偶爾卡住 5 秒的網路環境（例如本機 WSL 開發環境）第一次呼叫就會剛好逾時、
# 回 502，下一次 DNS 有快取又成功，使用者看到的就是「先失敗、過幾秒又成功」。
# 放寬成 15 秒，讓這種偶發的慢一點也能成功；真的連不上 Google 時，
# 各處仍會照樣回 502，只是最多多等 15 秒。
GOOGLE_HTTP_TIMEOUT = httpx.Timeout(15.0)

# 取得所有行事曆列表
async def fetch_google_calendar_list(access_token: str) -> list:
    url = "https://www.googleapis.com/calendar/v3/users/me/calendarList"
    headers = {"Authorization": f"Bearer {access_token}"}
    async with httpx.AsyncClient(timeout=GOOGLE_HTTP_TIMEOUT) as client:
        res = await client.get(url, headers=headers)
        res.raise_for_status()
        return res.json().get("items", [])

# 抓 7 天內的事件
async def fetch_events_in_next_7_days(access_token: str, calendar_id: str) -> list:
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    next_week = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat().replace("+00:00", "Z")
    url = f"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events"
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {
        "timeMin": now,
        "timeMax": next_week,
        "singleEvents": True,
        "orderBy": "startTime"
    }

    async with httpx.AsyncClient(timeout=GOOGLE_HTTP_TIMEOUT) as client:
        res = await client.get(url, headers=headers, params=params)
        res.raise_for_status()
        return res.json().get("items", [])


async def fetch_freebusy(access_token: str, calendar_id: str) -> dict:
    """
    使用 Google Calendar FreeBusy API 取得未來 7 天該行事曆的忙碌時間區段
    """
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
