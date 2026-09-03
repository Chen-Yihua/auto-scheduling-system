from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

import db.mongodb as mongodb_mod
import main as main_mod


@pytest.mark.asyncio
async def test_ensure_indexes_creates_expected_indexes(monkeypatch):
    linked_accounts_mock = AsyncMock()
    manual_tasks_mock = AsyncMock()
    github_issues_mock = AsyncMock()
    jira_issues_mock = AsyncMock()
    moodle_assignments_mock = AsyncMock()

    monkeypatch.setattr(mongodb_mod.db.linkedAccounts, "create_index", linked_accounts_mock)
    monkeypatch.setattr(mongodb_mod.db.manual_tasks, "create_index", manual_tasks_mock)
    monkeypatch.setattr(mongodb_mod.db.github_issues, "create_index", github_issues_mock)
    monkeypatch.setattr(mongodb_mod.db.jira_issues, "create_index", jira_issues_mock)
    monkeypatch.setattr(mongodb_mod.db.moodle_assignments, "create_index", moodle_assignments_mock)

    await mongodb_mod.ensure_indexes()

    # linkedAccounts：常用 clerk_id 單獨查，也常用 (clerk_id, platform) 一起查
    linked_accounts_mock.assert_any_call([("clerk_id", 1), ("platform", 1)])

    # manual_tasks：id 是應用層自產的查詢鍵，必須唯一；user_id 是列表查詢常用欄位
    manual_tasks_mock.assert_any_call("id", unique=True)
    manual_tasks_mock.assert_any_call("user_id")

    # github_issues / jira_issues / moodle_assignments：sync_platform_items() upsert 用的
    # 複合鍵，三個平台一致，都不強制 unique，避免舊資料造成建立索引失敗
    for platform_mock in (github_issues_mock, jira_issues_mock, moodle_assignments_mock):
        platform_mock.assert_any_call([("user_id", 1), ("id", 1)])
        for call in platform_mock.call_args_list:
            assert call.kwargs.get("unique") is not True


def test_app_startup_calls_ensure_indexes(monkeypatch):
    called = {"count": 0}

    async def fake_ensure_indexes():
        called["count"] += 1

    monkeypatch.setattr(main_mod, "ensure_indexes", fake_ensure_indexes)

    with TestClient(main_mod.app):
        pass

    assert called["count"] == 1
