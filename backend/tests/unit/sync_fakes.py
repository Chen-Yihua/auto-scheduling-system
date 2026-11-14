"""同步流程測試共用：可控制何時完成的 fetch、可在寫入某個項目時暫停的 collection、在 mongomock 放帳號。"""
import asyncio
from datetime import datetime, timedelta, timezone

from core.crypto import encrypt_secret
from core.database import db

USER = "sync-user"
ACCOUNT_ID = f"{USER}_github"
PAST = datetime(2020, 1, 1, tzinfo=timezone.utc)


def item(item_id: int, title: str) -> dict:
    return {"id": item_id, "title": title}


class ControlledFetch:
    """每次呼叫依序取用一個 plan：等 gate 放行後回傳 items（或丟出例外）。entered 在進入 fetch 時設定。"""

    def __init__(self):
        self._plans: list[tuple[asyncio.Event, asyncio.Event, object]] = []

    def plan(self, result) -> tuple[asyncio.Event, asyncio.Event]:
        entered, gate = asyncio.Event(), asyncio.Event()
        self._plans.append((entered, gate, result))
        return entered, gate

    async def __call__(self, credentials):
        entered, gate, result = self._plans.pop(0)
        entered.set()
        await gate.wait()
        if isinstance(result, Exception):
            raise result
        return [dict(i) for i in result]  # type: ignore[union-attr]


class PausingCollection:
    """寫入 title 為指定值的項目時暫停：設定 reached，等 release 放行才真的寫入。其他操作直接交給真的 collection。"""

    def __init__(self, inner):
        self._inner = inner
        self._pauses: dict[str, tuple[asyncio.Event, asyncio.Event]] = {}

    def pause_on(self, title: str) -> tuple[asyncio.Event, asyncio.Event]:
        reached, release = asyncio.Event(), asyncio.Event()
        self._pauses[title] = (reached, release)
        return reached, release

    def __getattr__(self, name):
        return getattr(self._inner, name)

    async def update_one(self, filter, update, *args, **kwargs):
        title = update.get("$set", {}).get("title")
        if title in self._pauses:
            reached, release = self._pauses.pop(title)
            reached.set()
            await release.wait()
        return await self._inner.update_one(filter, update, *args, **kwargs)


async def link_github(link_id: str | None = "link-1", **extra) -> None:
    await db.linkedAccounts.delete_many({"_id": ACCOUNT_ID})
    doc = {
        "_id": ACCOUNT_ID, "clerk_id": USER, "platform": "github", "status": "connected",
        "username": "someone", "apiKey": encrypt_secret("gh-token"), **extra,
    }
    if link_id is not None:
        doc["link_id"] = link_id
    await db.linkedAccounts.insert_one(doc)


async def account() -> dict | None:
    return await db.linkedAccounts.find_one({"_id": ACCOUNT_ID})


async def items_by_id() -> dict:
    return {d["id"]: d["title"] async for d in db.github_issues.find({"user_id": USER})}


async def expire_lock() -> None:
    await db.linkedAccounts.update_one({"_id": ACCOUNT_ID}, {"$set": {"sync_lock_until": PAST}})


async def hold_lock_by_someone_else() -> None:
    until = datetime.now(timezone.utc) + timedelta(minutes=5)
    await db.linkedAccounts.update_one(
        {"_id": ACCOUNT_ID}, {"$set": {"sync_lock_owner": "someone-else", "sync_lock_until": until}},
    )


async def start_after(previous_entered: asyncio.Event | None, coro) -> asyncio.Task:
    """等前一次同步進入 fetch 後才開始，讓這次的開始時間一定比較晚。"""
    if previous_entered is not None:
        await previous_entered.wait()
        await asyncio.sleep(0.005)
    return asyncio.create_task(coro)


async def cleanup() -> None:
    await db.linkedAccounts.delete_many({"clerk_id": USER})
    await db.github_issues.delete_many({"user_id": USER})
