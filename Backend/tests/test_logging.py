import logging
import os

import pytest

import logging_config
import crud.linkedAccount as linked_mod
import crud.oauth as oauth_crud_mod
import routers.oauth as oauth_router_mod
from schemas.linkedAccount import LinkedAccountCreate

# 這些模組原本用 print() 做除錯輸出，這裡確認全部換成 logging 之後沒有殘留
MODULES_CONVERTED_TO_LOGGING = [
    "crud/linkedAccount.py",
    "crud/oauth.py",
    "crud/manualTask.py",
    "crud/moodle.py",
    "routers/oauth.py",
    "routers/manualTask.py",
]
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


# ========== logging_config ==========

def test_setup_logging_defaults_to_info(monkeypatch):
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    logging_config.setup_logging()

    assert logging.getLogger().level == logging.INFO


def test_setup_logging_respects_log_level_env_var(monkeypatch):
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    logging_config.setup_logging()

    assert logging.getLogger().level == logging.DEBUG

    # 還原成預設值，避免影響其他測試
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    logging_config.setup_logging()


# ========== 沒有殘留 print() ==========

def test_no_print_left_in_converted_modules():
    for relative_path in MODULES_CONVERTED_TO_LOGGING:
        full_path = os.path.join(BACKEND_DIR, relative_path)
        with open(full_path, encoding="utf-8") as f:
            source = f.read()

        assert "print(" not in source, f"{relative_path} 還留有 print()，應該全部換成 logging"


# ========== 實際行為：debug/error 真的有透過 logging 發出 ==========

@pytest.mark.asyncio
async def test_create_linked_account_logs_debug(monkeypatch, caplog):
    async def mock_update_one(*args, **kwargs):
        return type("Mock", (), {"modified_count": 1, "upserted_id": None})()

    monkeypatch.setattr(linked_mod.db.linkedAccounts, "update_one", mock_update_one)
    monkeypatch.setattr(linked_mod, "verify_moodle_login", lambda username, password: True)

    account = LinkedAccountCreate(
        platform="moodle", status="", username="stu123", password="pw123456"
    )

    with caplog.at_level(logging.DEBUG, logger="crud.linkedAccount"):
        await linked_mod.create_linked_account("uid123", account)

    assert any(
        "create_linked_account platform=moodle" in record.message
        for record in caplog.records
    )


@pytest.mark.asyncio
async def test_oauth_callback_logs_exception_on_failure(monkeypatch, caplog):
    async def mock_get_current_clerk_user():
        return {"sub": "uid123"}

    class FailingClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            pass

        async def post(self, *a, **k):
            raise Exception("Google 掛了")

    monkeypatch.setattr(oauth_router_mod.httpx, "AsyncClient", lambda: FailingClient())

    from fastapi import HTTPException

    payload = oauth_router_mod.OAuthCallbackPayload(code="fake-code")

    with caplog.at_level(logging.ERROR, logger="routers.oauth"):
        with pytest.raises(HTTPException):
            await oauth_router_mod.oauth_callback(
                payload=payload, clerk_user={"sub": "uid123"}
            )

    assert any("Google OAuth callback failed" in record.message for record in caplog.records)
    # logger.exception 應該連 traceback 都一起記下來
    assert any(record.exc_info for record in caplog.records)


@pytest.mark.asyncio
async def test_refresh_google_token_logs_info_on_success(monkeypatch, caplog):
    async def mock_find_one(query):
        return {"_id": "uid123", "refresh_token": "old-refresh-token"}

    async def mock_update_one(*a, **k):
        return None

    class MockResponse:
        status_code = 200
        text = '{"access_token": "new-token"}'

        def raise_for_status(self):
            pass

        def json(self):
            return {"access_token": "new-token"}

    class MockClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            pass

        async def post(self, *a, **k):
            return MockResponse()

    monkeypatch.setattr(oauth_crud_mod.db.googleCalendarTokens, "find_one", mock_find_one)
    monkeypatch.setattr(oauth_crud_mod.db.googleCalendarTokens, "update_one", mock_update_one)
    monkeypatch.setattr(oauth_crud_mod.httpx, "AsyncClient", lambda: MockClient())

    with caplog.at_level(logging.INFO, logger="crud.oauth"):
        token = await oauth_crud_mod.refresh_google_calendar_token("uid123")

    assert token == "new-token"
    assert any(
        "Refreshed Google Calendar token for clerk_id=uid123" in record.message
        for record in caplog.records
    )
