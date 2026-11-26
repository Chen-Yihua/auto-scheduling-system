"""app 啟動時建立 MongoDB、Gemini 的連線，關閉時釋放（main.py 的 lifespan）。"""
import pytest

import main
from core import database
from routers import pr_review_webhook
from services import task_inference


class FakeMongoClient:
    def __init__(self, *args, **kwargs):
        self.closed = False

    def __getitem__(self, name):
        return object()

    async def close(self):
        self.closed = True


class FakeAio:
    def __init__(self, fail: bool):
        self.closed = False
        self.fail = fail

    async def aclose(self):
        self.closed = True
        if self.fail:
            raise RuntimeError("aclose failed")


class FakeGenaiClient:
    instances: list["FakeGenaiClient"] = []
    fail_aio_close = False

    def __init__(self, api_key=None):
        self.closed = False
        self.aio = FakeAio(FakeGenaiClient.fail_aio_close)
        FakeGenaiClient.instances.append(self)

    def close(self):
        self.closed = True


@pytest.fixture
def production_like(monkeypatch):
    """模擬正式環境：還沒有任何連線，建立時拿到的是假的 client。"""
    # conftest 已經換好記憶體資料庫和 Gemini client；這裡先清掉，lifespan 才會自己建立
    monkeypatch.setattr(database, "db", None)
    monkeypatch.setattr(database, "client", None)
    monkeypatch.setattr(database, "AsyncMongoClient", FakeMongoClient)
    monkeypatch.setattr(task_inference, "client", None)
    monkeypatch.setattr(pr_review_webhook, "client", None)
    monkeypatch.setattr(task_inference.genai, "Client", FakeGenaiClient)
    FakeGenaiClient.instances = []
    FakeGenaiClient.fail_aio_close = False

    async def no_indexes():
        pass

    monkeypatch.setattr(main, "ensure_indexes", no_indexes)


@pytest.mark.asyncio
async def test_startup_opens_connections_and_shutdown_closes_them(production_like):
    """啟動後資料庫和兩個 Gemini client 都能用；關閉後全部釋放，不留著沒關的連線。"""
    async with main.lifespan(main.app):
        mongo_client = database.client
        assert database.get_db() is not None
        assert task_inference.get_client() is not None
        assert pr_review_webhook.get_client() is not None

    assert isinstance(mongo_client, FakeMongoClient) and mongo_client.closed
    assert [c.closed for c in FakeGenaiClient.instances] == [True, True]
    assert database.db is None
    assert task_inference.client is None and pr_review_webhook.client is None


@pytest.mark.asyncio
async def test_failing_close_does_not_skip_closing_the_rest(production_like):
    """關閉 PR 審查用的 Gemini client 失敗時，其他連線（包括資料庫）仍然要關閉，錯誤照樣丟出。"""
    FakeGenaiClient.fail_aio_close = True

    with pytest.raises(RuntimeError, match="aclose failed"):
        async with main.lifespan(main.app):
            mongo_client = database.client

    assert isinstance(mongo_client, FakeMongoClient) and mongo_client.closed
    assert all(c.closed for c in FakeGenaiClient.instances)


@pytest.mark.asyncio
async def test_shutdown_keeps_connections_it_did_not_open(monkeypatch):
    """測試先換進來的記憶體資料庫和 Gemini client，lifespan 結束時不能被關掉或清掉。"""
    async def no_indexes():
        pass

    monkeypatch.setattr(main, "ensure_indexes", no_indexes)
    injected_db = database.db
    injected_clients = (task_inference.client, pr_review_webhook.client)

    async with main.lifespan(main.app):
        assert database.get_db() is injected_db

    assert database.db is injected_db
    assert (task_inference.client, pr_review_webhook.client) == injected_clients
