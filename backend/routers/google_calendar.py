import logging
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from crud.google_tokens import save_google_calendar_token, is_google_calendar_connected
from core.errors import ExternalServiceError, InvalidRequestError
from services.google_calendar import list_calendars_for_user
from services.google_errors import RATE_LIMITED_DETAIL, UPSTREAM_DETAIL, is_rate_limited, request_error_code
from services.google_oauth import google_oauth_error
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


# 我方的 OAuth client 或請求設定錯誤，使用者重試也不會成功
_OUR_CONFIG_ERRORS = {"invalid_client", "invalid_request", "unauthorized_client", "redirect_uri_mismatch"}


def _token_exchange_error(response: httpx.Response) -> InvalidRequestError:
    oauth_error = google_oauth_error(response)
    if oauth_error == "invalid_grant":
        return InvalidRequestError("授權碼無效或已過期，請重新連接 Google Calendar", error_code="INVALID_AUTHORIZATION_CODE")
    if oauth_error in _OUR_CONFIG_ERRORS:
        logger.error("Google 拒絕 OAuth 設定: %s", oauth_error)
        return InvalidRequestError("伺服器設定錯誤，請聯絡管理員", error_code="INTERNAL_ERROR")
    if is_rate_limited(response):
        return InvalidRequestError(RATE_LIMITED_DETAIL, error_code="UPSTREAM_RATE_LIMITED")
    return InvalidRequestError(UPSTREAM_DETAIL, error_code="UPSTREAM_ERROR")


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
    # 狀態碼維持目前的值：Google 回錯誤與拿不到 access token 是 400，連不上與逾時是 502
    try:
        async with httpx.AsyncClient(timeout=GOOGLE_HTTP_TIMEOUT) as client:
            res = await client.post(token_url, data=token_payload)
            res.raise_for_status()
    except httpx.RequestError as e:
        logger.error("連線 Google Token Endpoint 失敗: %s", e)
        error_code, detail = request_error_code(e)
        raise ExternalServiceError(detail, error_code=error_code)
    except httpx.HTTPStatusError as e:
        logger.warning("Google OAuth 換 token 失敗: %s %s", e.response.status_code, e.response.text)
        raise _token_exchange_error(e.response)

    token_data = res.json()
    access_token = token_data.get("access_token")
    refresh_token = token_data.get("refresh_token")

    if not access_token:
        raise InvalidRequestError("Google 沒有回傳授權，請稍後再試", error_code="UPSTREAM_ERROR")

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
