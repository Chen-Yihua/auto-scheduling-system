"""
外部平台（GitHub、Jira、Moodle…）的共同介面。

每個平台一個 PlatformAdapter 子類別，把這個平台需要的所有東西集中在同一個地方：
怎麼抓資料、怎麼轉成統一格式、怎麼驗證使用者連結的帳號、存在哪個 collection、
怎樣算完成。共用的流程（查帳號 → 解密 → 抓資料 → 重試／退回舊資料 → 回應 header）
在 platforms/router.py，排程整合在 crud/schedulable_items.py，帳號連結在
crud/linked_account.py——它們都只透過這個介面跟平台打交道。

新增一個平台：在 platforms/ 底下寫一個子類別，再到 platforms/__init__.py 的
PLATFORMS 註冊一行，其餘地方都不用改。
"""
from typing import Awaitable, Callable, Optional, TypedDict

from core.database import db
from platforms.sync import sync_platform_items


class PlatformUserInfo(TypedDict):
    username: str
    avatar_url: str


class PlatformAdapter:
    # ---------- 識別 ----------
    name: str            # "github"——也是 linkedAccounts.platform 的值、組合 id 的來源前綴
    display_name: str    # "GitHub"——錯誤訊息用

    # ---------- 對外 API（GET 這個路徑回傳使用者在這個平台的項目）----------
    route_path: str                          # 例如 "/github/issues"，前端已經在用，不能隨便改
    response_model: type
    rate_limit: Optional[str] = None         # 例如 "5/minute"；None 表示不另外限流
    cache_ttl_seconds: Optional[int] = None  # 抓取成本高的平台才需要（例如要開瀏覽器的爬蟲）

    # ---------- 錯誤訊息（前端會直接顯示）----------
    not_linked_detail: str
    auth_failed_detail: str
    fetch_failed_detail: str

    # ---------- 資料儲存 ----------
    collection_name: str
    # 組合 id（"github:42"）拆出來一律是字串，查資料庫前要轉回這個平台實際存的型別，
    # 不然用字串查 int 欄位會悄悄查不到任何資料
    id_type: type = str

    # ---------- 連結帳號 ----------
    required_create_fields: tuple[str, ...]  # 建立連結時必填的欄位
    secret_field: str                        # 要加密的那個欄位（apiKey 或 password）

    @property
    def collection(self):
        # 用屬性存取（db.github_issues），不用 db["github_issues"]——兩者在 PyMongo 裡
        # 是不同的物件，測試是把假的 collection 設成 db 的屬性來替換
        return getattr(db, self.collection_name)

    def credentials_from_account(self, account: dict, decrypt: Callable[[str], str]) -> Optional[dict]:
        """
        從 linkedAccounts 的那筆資料取出抓資料要用的憑證（密文用 decrypt 解開）。
        回傳 None 代表帳號資料不完整，當成「還沒連結」處理。
        """
        raise NotImplementedError

    async def fetch_items(self, credentials: dict) -> list[dict]:
        """用憑證即時抓資料，並轉成 response_model 的格式。每筆都要有唯一的 "id"。"""
        raise NotImplementedError

    async def sync(self, user_id: str, fetch_fn: Callable[[], Awaitable[list[dict]]]):
        """即時抓資料、寫進 collection，失敗時退回上次成功的資料（見 platforms/sync.py）。"""
        return await sync_platform_items(
            collection=self.collection,
            user_id=user_id,
            id_field="id",
            fetch_fn=fetch_fn,
        )

    def is_done(self, item: dict) -> bool:
        """平台自己回報這筆是否已完成。拿不到完成狀態的平台就一律 False，只靠使用者手動標記。"""
        return False

    # ---------- 連結帳號時的驗證 ----------

    async def verify_new(self, account: dict) -> dict:
        """
        建立連結前，用使用者填的明文憑證真的打一次平台驗證。
        回傳要一併存進帳號資料的欄位（username、avatar_url、status…）。
        驗證失敗直接丟 HTTPException，帶使用者看得懂的訊息。
        """
        raise NotImplementedError

    def needs_reverify(self, changes: dict) -> bool:
        """更新帳號時，這次改到的欄位是否需要重新驗證。"""
        return self.secret_field in changes

    async def apply_update(self, changes: dict, composite_id: str) -> dict:
        """
        更新帳號、而且 needs_reverify 為 True 時呼叫：重新驗證，並回傳加密好、
        可以直接寫進資料庫的欄位。
        """
        raise NotImplementedError

    def __repr__(self) -> str:
        return f"<{type(self).__name__} {self.name}>"
