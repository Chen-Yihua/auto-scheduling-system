"""E2E 用：在測試使用者底下寫入假的 Google 日曆連線資料。只能寫入 auto_scheduling_e2e。

用法：python scripts/e2e_seed_google_token.py <clerk_id>
MONGO_URI、MONGO_DB、SECRET_ENCRYPTION_KEY 由呼叫的 setup project 明確傳入。
"""
import asyncio
import os
import sys

E2E_DB_NAME = "auto_scheduling_e2e"
FAKE_ACCESS_TOKEN = "e2e-fake-access-token"
FAKE_REFRESH_TOKEN = "e2e-fake-refresh-token"


async def seed(clerk_id: str) -> None:
    # 在這裡才 import：core.database 在 import 時就讀 MONGO_DB，要先確認過資料庫名稱
    from core import database
    from crud.google_tokens import save_google_calendar_token

    await database.open_database()
    try:
        await save_google_calendar_token(clerk_id, FAKE_ACCESS_TOKEN, FAKE_REFRESH_TOKEN)
    finally:
        await database.close_database()


def main(argv: list[str]) -> int:
    if len(argv) != 2 or not argv[1]:
        print("用法：e2e_seed_google_token.py <clerk_id>", file=sys.stderr)
        return 2
    db_name = os.environ.get("MONGO_DB")
    if db_name != E2E_DB_NAME:
        print(f"不寫入：MONGO_DB 是 {db_name!r}，只能寫入 {E2E_DB_NAME}", file=sys.stderr)
        return 1
    if not os.environ.get("MONGO_URI") or not os.environ.get("SECRET_ENCRYPTION_KEY"):
        print("不寫入：MONGO_URI 與 SECRET_ENCRYPTION_KEY 都要明確傳入", file=sys.stderr)
        return 1
    asyncio.run(seed(argv[1]))
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    sys.exit(main(sys.argv))
