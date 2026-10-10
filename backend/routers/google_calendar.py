import logging
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from crud.google_tokens import save_google_calendar_token, is_google_calendar_connected
from services.google_calendar import list_calendars_for_user
from services.google_calendar_client import GOOGLE_HTTP_TIMEOUT
from core.security import get_current_clerk_user
import httpx
import os

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

    # 不用 except Exception，以免蓋掉後面更具體的錯誤（例如 DB 的 503）
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


# 只查 DB 不呼叫 Google，讓前端先確認是否已授權
@router.get("/status")
async def get_google_calendar_status(clerk_user: dict = Depends(get_current_clerk_user)):
    connected = await is_google_calendar_connected(clerk_user["sub"])
    return {"connected": connected}

@router.get("/calendars")
async def get_google_calendars(clerk_user: dict = Depends(get_current_clerk_user)):
    calendars = await list_calendars_for_user(clerk_user["sub"])
    return {"items": calendars}
