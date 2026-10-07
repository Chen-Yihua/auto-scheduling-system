import logging
import os

import pytest

from core import logging_config
import crud.linked_account as linked_mod
import platforms.moodle as moodle_platform
from schemas.linked_account import LinkedAccountCreate

# 這些模組原本用 print() 做除錯輸出，這裡確認全部換成 logging 之後沒有殘留
MODULES_CONVERTED_TO_LOGGING = [
    "crud/linked_account.py",
    "crud/google_tokens.py",
    "services/google_calendar.py",
    "crud/manual_task.py",
    "platforms/moodle.py",
    "routers/google_calendar.py",
    "routers/manual_task.py",
]
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


# ========== logging_config ==========

def test_setup_logging_defaults_to_info(monkeypatch):
    """沒設定 LOG_LEVEL → 預設 INFO。"""
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    logging_config.setup_logging()

    assert logging.getLogger().level == logging.INFO


def test_setup_logging_respects_log_level_env_var(monkeypatch):
    """LOG_LEVEL 設為 DEBUG → 日誌層級要跟著變成 DEBUG。"""
    # 測完把層級還原成 INFO，避免影響其他測試
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    logging_config.setup_logging()

    assert logging.getLogger().level == logging.DEBUG

    # 還原成預設值，避免影響其他測試
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    logging_config.setup_logging()


# ========== 沒有殘留 print() ==========

def test_no_print_left_in_converted_modules():
    """已經改用 logging 的模組不能再殘留 print()。"""
    for relative_path in MODULES_CONVERTED_TO_LOGGING:
        full_path = os.path.join(BACKEND_DIR, relative_path)
        with open(full_path, encoding="utf-8") as f:
            source = f.read()

        assert "print(" not in source, f"{relative_path} 還留有 print()，應該全部換成 logging"


# ========== 實際行為：debug/error 真的有透過 logging 發出 ==========

@pytest.mark.asyncio
async def test_create_linked_account_logs_debug(monkeypatch, caplog):
    """建立綁定帳號時要留下 debug log（記錄是哪個平台）。"""
    async def mock_update_one(*args, **kwargs):
        return type("Mock", (), {"matched_count": 1, "modified_count": 1, "upserted_id": None})()

    monkeypatch.setattr(linked_mod.db.linkedAccounts, "update_one", mock_update_one)
    monkeypatch.setattr(moodle_platform, "verify_moodle_login", lambda username, password: True)

    account = LinkedAccountCreate(
        platform="moodle", status="", username="stu123", password="pw123456"
    )

    with caplog.at_level(logging.DEBUG, logger="crud.linked_account"):
        await linked_mod.create_linked_account("uid123", account)

    assert any(
        "create_linked_account platform=moodle" in record.message
        for record in caplog.records
    )
