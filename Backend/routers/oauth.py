import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from crud.oauth import get_google_calendar_token, save_google_calendar_token, refresh_google_calendar_token, get_free_slots_for_user, is_google_calendar_connected
from services.google_calendar import GOOGLE_HTTP_TIMEOUT, fetch_events_in_next_7_days, fetch_google_calendar_list
from db.security import get_current_clerk_user
import httpx
import os
import json,copy
from zoneinfo import ZoneInfo
from datetime import datetime

logger = logging.getLogger(__name__)

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
    token_payload = {
        "code": code,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "grant_type": "authorization_code",
    }

    # 分開處理「連不上 Google」「Google 拒絕這個授權碼」兩種情況，
    # 不要用大範圍的 except Exception 把下面更具體的錯誤（例如
    # save_google_calendar_token 可能丟出的 503）也接住蓋掉
    try:
        async with httpx.AsyncClient(timeout=GOOGLE_HTTP_TIMEOUT) as client:
            res = await client.post(token_url, data=token_payload)
            res.raise_for_status()
    except httpx.RequestError as e:
        logger.error("連線 Google Token Endpoint 失敗: %s", e)
        raise HTTPException(status_code=502, detail="無法連線至 Google，請稍後再試")
    except httpx.HTTPStatusError as e:
        logger.warning("Google OAuth 換 token 失敗: %s", e.response.text)
        raise HTTPException(status_code=400, detail="授權碼無效或已過期，請重新登入 Google")

    token_data = res.json()
    access_token = token_data.get("access_token")
    refresh_token = token_data.get("refresh_token")

    if not access_token:
        raise HTTPException(status_code=400, detail="無法取得 Access Token")

    await save_google_calendar_token(clerk_user["sub"], access_token, refresh_token)

    return JSONResponse(content={"message": "Google Calendar 授權成功"})


# 輕量檢查：只查 DB 有沒有存過 token，不會真的打 Google API，
# 給前端在呼叫 /oauth/calendars 之前先確認是否已授權
@router.get("/status")
async def get_google_calendar_status(clerk_user: dict = Depends(get_current_clerk_user)):
    connected = await is_google_calendar_connected(clerk_user["sub"])
    return {"connected": connected}

# 取得使用者的 Google Calendar 清單
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
    except httpx.RequestError as e:
        logger.error("連線 Google Calendar API 失敗: %s", e)
        raise HTTPException(status_code=502, detail="無法連線至 Google，請稍後再試")
    return {"items": calendars}

# 取得指定行事曆 ID 下，接下來 7 天內的事件
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
    except httpx.RequestError as e:
        logger.error("連線 Google Calendar API 失敗: %s", e)
        raise HTTPException(status_code=502, detail="無法連線至 Google，請稍後再試")

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
    except httpx.RequestError as e:
        logger.error("連線 Google Calendar API 失敗: %s", e)
        raise HTTPException(status_code=502, detail="無法連線至 Google，請稍後再試")


    return {"items": events}

@router.get("/available")
async def get_available_times(clerk_user: dict = Depends(get_current_clerk_user)):
    """
    取得使用者 primary calendar 未來 7 天的 FreeBusy 回應，並回傳UTC空閒時段，並在log回應taipei時區以方便檢查
    """
    free_utc = await get_free_slots_for_user(clerk_user["sub"])
    tz = ZoneInfo("Asia/Taipei")
    free_local = []
    for i in free_utc:
        dt_s = datetime.fromisoformat(i["start"].replace("Z", "+00:00")).astimezone(tz)
        dt_e = datetime.fromisoformat(i["end"].replace("Z", "+00:00")).astimezone(tz)
        free_local.append({
            "start": dt_s.isoformat(),
            "end":   dt_e.isoformat()
        })

    # 把空閒時間log 出來（注意以轉成taipei時區，方便檢查）
    logger.debug("空閒時段 (Asia/Taipei): %s", json.dumps(free_local, ensure_ascii=False, indent=2))

    # 回傳的空閒時段給前端（UTC時間）
    return JSONResponse(content={"freeSlotsUtc":  free_utc})