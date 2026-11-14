"""外部平台 integration 測試共用：假的 httpx client、在 mongomock 放帳號與舊資料、不真的等重試。"""
from types import SimpleNamespace

import httpx
import pytest_asyncio

import platforms.sync as platform_sync
from core.crypto import encrypt_secret
from core.database import db

USER_ID = "test_user_123"
# 第三方回應原文裡的字串，錯誤回應的 detail 不能出現
UPSTREAM_SECRET_TEXT = "upstream-raw-text-7f3a"


class FakeHttpClient:
    """每次 GET 都回 outcome（Response 或要丟的例外），記錄呼叫次數。"""

    def __init__(self, outcome):
        self.outcome = outcome
        self.calls = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def get(self, url, headers=None, params=None):
        self.calls += 1
        if isinstance(self.outcome, Exception):
            raise self.outcome
        response = self.outcome
        response.request = httpx.Request("GET", url)
        return response


def use_fake_http(monkeypatch, module, outcome) -> FakeHttpClient:
    client = FakeHttpClient(outcome)
    monkeypatch.setattr(module.httpx, "AsyncClient", lambda *a, **k: client)
    return client


def skip_retry_delay(monkeypatch):
    async def no_sleep(seconds):
        pass

    monkeypatch.setattr(platform_sync, "asyncio", SimpleNamespace(sleep=no_sleep))


async def link_account(platform: str, fields: dict):
    await db.linkedAccounts.delete_many({"clerk_id": USER_ID})
    secret_field = "password" if platform == "moodle" else "apiKey"
    doc = {"_id": f"{USER_ID}_{platform}", "clerk_id": USER_ID, "platform": platform, "status": "connected",
           "username": "someone", **fields}
    doc[secret_field] = encrypt_secret(doc[secret_field])
    await db.linkedAccounts.insert_one(doc)


async def reset_items(collection, old_item: dict | None):
    await collection.delete_many({"user_id": USER_ID})
    if old_item is not None:
        await collection.insert_one({**old_item, "user_id": USER_ID})


def response(status_code: int, headers: dict | None = None, json_body=None, content: bytes | None = None) -> httpx.Response:
    if content is not None:
        return httpx.Response(status_code, headers=headers, content=content)
    return httpx.Response(status_code, headers=headers, json=json_body if json_body is not None else {"message": UPSTREAM_SECRET_TEXT})


@pytest_asyncio.fixture
async def clean_platform_data():
    """測試結束後清掉這裡放進 mongomock 的帳號與項目，其他測試才不會讀到。"""
    yield
    await db.linkedAccounts.delete_many({"clerk_id": USER_ID})
    for collection in (db.github_issues, db.jira_issues, db.moodle_assignments):
        await collection.delete_many({"user_id": USER_ID})
