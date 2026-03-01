from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from crud.oauth import get_google_calendar_token, save_google_calendar_token,refresh_google_calendar_token
from services.google_calendar import fetch_events_in_next_7_days, fetch_google_calendar_list,fetch_freebusy,compute_free_times
from db.security import get_current_clerk_user
import httpx
import os
import json,copy  
from zoneinfo import ZoneInfo
from datetime import datetime

router = APIRouter(prefix="/oauth", tags=["oauth"])

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI")

class OAuthCallbackPayload(BaseModel):
    code: str

@router.post("/callback")
async def oauth_callback(
    payload: OAuthCallbackPayload,
    clerk_user: dict = Depends(get_current_clerk_user)
):
    code = payload.code
    token_url = "https://oauth2.googleapis.com/token"
    payload = {
        "code": code,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "grant_type": "authorization_code",
    }

    try:
        async with httpx.AsyncClient() as client:
            res = await client.post(token_url, data=payload)
            res.raise_for_status()
            token_data =res.json()

        access_token = token_data.get("access_token")
        refresh_token = token_data.get("refresh_token")

        if not access_token:
            raise HTTPException(status_code=400, detail="無法取得 Access Token")

        await save_google_calendar_token(clerk_user["sub"], access_token, refresh_token)

        return JSONResponse(content={"message": "Google Calendar 授權成功"})

    except Exception as e:
        print("❌ OAuth Error:", e)
        raise HTTPException(status_code=400, detail="Google OAuth callback 發生錯誤")


# 📅 取得使用者的 Google Calendar 清單
@router.get("/calendars")
async def get_google_calendars(clerk_user: dict = Depends(get_current_clerk_user)):
    access_token = await get_google_calendar_token(clerk_user["sub"])
   
    # 抓 calendar list（enqueue refresh if 401）
    try:
        calendars = await fetch_google_calendar_list(access_token)
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            # Token 過期，自動 refresh，再 retry
            access_token = await refresh_google_calendar_token(clerk_user["sub"])
            calendars   = await fetch_google_calendar_list(access_token)
        else:
            raise HTTPException(status_code=400, detail="取得行事曆列表失敗")
    return {"items": calendars}

# 📆 取得指定行事曆 ID 下，接下來 7 天內的事件
@router.get("/events")
async def get_primary_calendar_events(clerk_user: dict = Depends(get_current_clerk_user)):
    access_token = await get_google_calendar_token(clerk_user["sub"])
    
    # 抓 calendar list（enqueue refresh if 401）
    try:
        calendars = await fetch_google_calendar_list(access_token)
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            access_token = await refresh_google_calendar_token(clerk_user["sub"])
            calendars   = await fetch_google_calendar_list(access_token)
        else:
            raise HTTPException(status_code=400, detail="取得行事曆列表失敗")

    # 找出 primary 行事曆
    primary = next((c for c in calendars if c.get("primary")), None)
    if not primary:
        raise HTTPException(status_code=404, detail="找不到 primary calendar")
    
    # 抓未來 7 天事件（enqueue refresh if 401）
    try:
        events = await fetch_events_in_next_7_days(access_token, primary["id"])
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            access_token = await refresh_google_calendar_token(clerk_user["sub"])
            events       = await fetch_events_in_next_7_days(access_token, primary["id"])
        else:
            raise HTTPException(status_code=400, detail="取得 7 天事件失敗")


    return {"items": events}

@router.get("/available")
async def get_available_times(clerk_user: dict = Depends(get_current_clerk_user)):
    """
    取得使用者 primary calendar 未來 7 天的 FreeBusy 回應，並回傳UTC空閒時段，並在log回應taipei時區以方便檢查
    """
    # 取出當前使用者的 Access Token
    access_token = await get_google_calendar_token(clerk_user["sub"])

    # 抓 calendar list，若 401 -> refresh -> retry
    try:
        calendars = await fetch_google_calendar_list(access_token)
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            access_token = await refresh_google_calendar_token(clerk_user["sub"])
            calendars   = await fetch_google_calendar_list(access_token)
        else:
            raise HTTPException(status_code=400, detail="取得行事曆列表失敗")
    
    # 先取得行事曆列表，找出 primary calendar id
    primary = next((c for c in calendars if c.get("primary")), None)
    if not primary:
        raise HTTPException(status_code=404, detail="找不到 primary calendar")

    # 呼叫 FreeBusy API
    fb_response = await fetch_freebusy(access_token, primary["id"])

    # 計算空閒時間
    window_start = fb_response["timeMin"]
    window_end   = fb_response["timeMax"]
    busy_list    = fb_response["calendars"][primary["id"]]["busy"]
    free_utc     = compute_free_times(busy_list, window_start, window_end)
    tz = ZoneInfo("Asia/Taipei")
    free_local = []
    for i in free_utc:
        dt_s = datetime.fromisoformat(i["start"].replace("Z", "+00:00")).astimezone(tz)
        dt_e = datetime.fromisoformat(i["end"].replace("Z", "+00:00")).astimezone(tz)
        free_local.append({
            "start": dt_s.isoformat(),
            "end":   dt_e.isoformat()
        })

    # 把空閒時間log 出來（注意以轉成taipei時區，方便檢查）)
    print("================ 空閒時段 ================")
    print(json.dumps(free_local, ensure_ascii=False, indent=2))

    # 回傳的空閒時段給前端（UTC時間）
    return JSONResponse(content={"freeSlotsUtc":  free_utc})