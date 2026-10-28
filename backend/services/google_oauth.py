"""向 Google 換新 access_token。"""
import logging
import os

import httpx
from core.errors import ConfigurationError, ExternalServiceError, InvalidRequestError, ReauthRequiredError
from pymongo.errors import PyMongoError

from crud.google_tokens import delete_google_calendar_token, get_google_refresh_token, update_google_calendar_token
from services.google_calendar_client import GOOGLE_HTTP_TIMEOUT

logger = logging.getLogger(__name__)

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"


def _google_error_code(res: httpx.Response) -> str | None:
    """取出 Google OAuth 錯誤回應裡的 error 欄位，例如 invalid_grant。"""
    try:
        body = res.json()
    except ValueError:
        return None
    return body.get("error") if isinstance(body, dict) else None


async def refresh_google_calendar_token(clerk_id: str) -> str:
    """用 refresh_token 向 Google 換新的 access_token，寫回 DB 後回傳。"""
    refresh_token = await get_google_refresh_token(clerk_id)
    if not refresh_token:
        raise ReauthRequiredError("沒有可用的 Refresh Token，請重新授權")

    payload = {
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }
    try:
        async with httpx.AsyncClient(timeout=GOOGLE_HTTP_TIMEOUT) as client:
            res = await client.post(GOOGLE_TOKEN_URL, data=payload)
            logger.debug("Google token refresh response status=%s", res.status_code)
            if res.status_code != 200:
                logger.warning("Google token refresh failed: %s", res.text)
            res.raise_for_status()
            token_data = res.json()
    except httpx.RequestError as e:
        logger.error("連線 Google Token Endpoint 失敗: %s", e)
        raise ExternalServiceError("無法連線至 Google，請稍後再試")
    except httpx.HTTPStatusError as e:
        error_code = _google_error_code(e.response)
        if error_code == "invalid_grant":
            # refresh_token 已失效，清掉讓使用者重新連接
            logger.warning("Google refresh token 已失效: %s", e.response.text)
            try:
                await delete_google_calendar_token(clerk_id)
            except PyMongoError:
                logger.exception("清除失效的 Google Calendar token 失敗")
            raise ReauthRequiredError("Google 授權已失效，請重新連接 Google Calendar")
        if error_code == "invalid_client":
            # 伺服器的 client 設定錯誤，使用者的 token 沒壞，不能刪
            logger.error("Google 拒絕 OAuth client 設定: %s", e.response.text)
            raise ConfigurationError("伺服器設定錯誤，請聯絡管理員")
        # 429、5xx 等暫時性錯誤，token 可能還有效，不能刪
        raise ExternalServiceError("Google 暫時無法處理請求，請稍後再試")

    # Google 不一定會回新的 refresh_token
    access_token = token_data.get("access_token")
    new_refresh_token = token_data.get("refresh_token", refresh_token)
    if not access_token:
        raise InvalidRequestError("Google 刷新 Token 失敗")

    await update_google_calendar_token(clerk_id, access_token, new_refresh_token)
    logger.info("Refreshed Google Calendar token for clerk_id=%s", clerk_id)
    return access_token
