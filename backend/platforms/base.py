"""
外部平台（GitHub、Jira、Moodle）的共同介面。

新增平台：在 platforms/ 寫一個 PlatformAdapter 子類別，再到 platforms/__init__.py
的 PLATFORMS 註冊。
"""
from typing import Awaitable, Callable, Optional, TypedDict

from core.database import db
from platforms.sync import sync_platform_items


class PlatformUserInfo(TypedDict):
    username: str
    avatar_url: str


class PlatformAdapter:
    # ---------- 識別 ----------
    name: str            # 例如 "github"，也是 linkedAccounts.platform 的值和組合 id 的前綴
    display_name: str    # 例如 "GitHub"，錯誤訊息用

    # ---------- 對外 API（GET 這個路徑回傳使用者在這個平台的項目）----------
    route_path: str                          # 例如 "/github/issues"，前端已經在用，不能隨便改
    response_model: type
    rate_limit: Optional[str] = None         # 例如 "5/minute"；None 表示不限流
    cache_ttl_seconds: Optional[int] = None  # 抓取成本高的平台才設，例如爬蟲

    # ---------- 錯誤訊息（前端會直接顯示）----------
    not_linked_detail: str
    auth_failed_detail: str
    fetch_failed_detail: str

    # ---------- 資料儲存 ----------
    collection_name: str
    # 組合 id（"github:42"）拆出來是字串，查 DB 前要轉回實際型別，否則查 int 欄位會查不到
    id_type: type = str

    # ---------- 連結帳號 ----------
    required_create_fields: tuple[str, ...]  # 建立連結時必填的欄位
    secret_field: str                        # 要加密的那個欄位（apiKey 或 password）

    @property
    def collection(self):
        # 不用 db[name]：測試是替換 db 的屬性，用 [] 取不到替換後的物件
        return getattr(db, self.collection_name)

    def credentials_from_account(self, account: dict, decrypt: Callable[[str], str]) -> Optional[dict]:
        """從帳號資料取出抓資料用的憑證。回傳 None 代表資料不完整，當成還沒連結。"""
        raise NotImplementedError

    async def fetch_items(self, credentials: dict) -> list[dict]:
        """用憑證即時抓資料，並轉成 response_model 的格式。每筆都要有唯一的 "id"。"""
        raise NotImplementedError

    async def sync(self, user_id: str, fetch_fn: Callable[[], Awaitable[list[dict]]]):
        """即時抓資料並寫進 collection，失敗時退回上次成功的資料。"""
        return await sync_platform_items(
            collection=self.collection,
            user_id=user_id,
            id_field="id",
            fetch_fn=fetch_fn,
        )

    def is_done(self, item: dict) -> bool:
        """平台回報的完成狀態。拿不到狀態的平台回 False，只靠使用者手動標記。"""
        return False

    # ---------- 連結帳號時的驗證 ----------

    async def verify_new(self, account: dict) -> dict:
        """
        用明文憑證實際呼叫平台驗證，回傳要一併存入的欄位（username、avatar_url 等）。
        驗證失敗丟 HTTPException。
        """
        raise NotImplementedError

    def needs_reverify(self, changes: dict) -> bool:
        """更新帳號時，這次改到的欄位是否需要重新驗證。"""
        return self.secret_field in changes

    async def apply_update(self, changes: dict, composite_id: str) -> dict:
        """needs_reverify 為 True 時呼叫：重新驗證，回傳加密好、可直接寫入 DB 的欄位。"""
        raise NotImplementedError

    def __repr__(self) -> str:
        return f"<{type(self).__name__} {self.name}>"
