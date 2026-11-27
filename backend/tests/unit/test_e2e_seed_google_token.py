"""scripts/e2e_seed_google_token.py：只能寫入 E2E 資料庫。"""
import importlib.util
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

from core import database
from crud import google_tokens

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "e2e_seed_google_token.py"


def _load():
    spec = importlib.util.spec_from_file_location("e2e_seed_google_token", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("db_name", ["auto_scheduling_db", "", None])
def test_AC4_MONGO_DB_不是_auto_scheduling_e2e_時結束且不寫入(monkeypatch, db_name):
    module = _load()
    monkeypatch.setenv("MONGO_URI", "mongodb://127.0.0.1:1")
    monkeypatch.setenv("SECRET_ENCRYPTION_KEY", Fernet.generate_key().decode())
    if db_name is None:
        monkeypatch.delenv("MONGO_DB", raising=False)
    else:
        monkeypatch.setenv("MONGO_DB", db_name)

    async def boom(*a, **k):
        raise AssertionError("不應該連線或寫入")

    monkeypatch.setattr(database, "open_database", boom)
    monkeypatch.setattr(google_tokens, "save_google_calendar_token", boom)

    assert module.main(["script", "user_1"]) == 1


def test_AC4_沒有明確傳入_MONGO_URI_時結束且不寫入(monkeypatch):
    module = _load()
    monkeypatch.setenv("MONGO_DB", "auto_scheduling_e2e")
    monkeypatch.delenv("MONGO_URI", raising=False)
    monkeypatch.setenv("SECRET_ENCRYPTION_KEY", Fernet.generate_key().decode())

    async def boom(*a, **k):
        raise AssertionError("不應該連線或寫入")

    monkeypatch.setattr(database, "open_database", boom)
    monkeypatch.setattr(google_tokens, "save_google_calendar_token", boom)

    assert module.main(["script", "user_1"]) == 1
