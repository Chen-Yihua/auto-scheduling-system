"""
外部平台（GitHub、Jira、Moodle）的共同介面。

新增平台：在 platforms/ 寫一個 PlatformAdapter 子類別，再到 platforms/__init__.py
的 PLATFORMS 註冊。
"""
from datetime import datetime
from typing import Callable, Optional, TypedDict

from core.database import db


class PlatformUserInfo(TypedDict):
    username: str
    avatar_url: str


class PlatformAdapter:
    # ---------- 識別 ----------
    name: str            # 例如 "github"，也是 linkedAccounts.platform 的值和組合 id（"github:42"）的前綴
    display_name: str    # 例如 "GitHub"，錯誤訊息用

    # ---------- 對外 API ----------
    route_path: str                   # GET 讀資料庫裡的項目，例如 "/github/issues"，前端已經在用，不能隨便改
    sync_route_path: str              # POST 立即同步，例如 "/github/sync"
    response_model: type
    rate_limit: Optional[str] = None  # 立即同步的限流，例如 "5/minute"；None 表示不限流

    # ---------- 錯誤訊息（前端會直接顯示）----------
    not_linked_detail: str
    auth_failed_detail: str
    fetch_failed_detail: str

    # ---------- 資料儲存 ----------
    collection_name: str
    # 組合 id 拆出來是字串，查 DB 前要轉回實際型別，否則查 int 欄位會查不到
    id_type: type = str

    # ---------- 連結帳號 ----------
    required_create_fields: tuple[str, ...]  # 建立連結時必填的欄位
    secret_field: str                        # 要加密的欄位（apiKey 或 password）

    @property
    def collection(self):
        # 不能改成 db[name]：測試替換的是 db 的屬性，db[name] 會拿到真的 collection
        return getattr(db, self.collection_name)

    def credentials_from_account(self, account: dict, decrypt: Callable[[str], str]) -> Optional[dict]:
        """從帳號資料取出抓資料用的憑證。回傳 None 代表資料不完整，當成還沒連結。"""
        raise NotImplementedError

    async def fetch_items(self, credentials: dict) -> list[dict]:
        """
        用憑證即時抓資料，並轉成 response_model 的格式。每筆都要有唯一的 "id"。
        不重試的失敗丟 NonRetryableError（401），平台暫時性失敗丟 UpstreamError（502），
        回應無法解析丟 InvalidResponseError（500）；三者都帶 error_code（見 platforms/sync.py）。
        其他例外會被當成程式錯誤（500）。
        """
        raise NotImplementedError

    def is_done(self, item: dict) -> bool:
        """平台回報的完成狀態。拿不到狀態的平台回 False，只靠使用者手動標記。"""
        return False

    def completed_at(self, item: dict) -> Optional[datetime]:
        """平台記錄的完成時間。拿不到的平台回 None，改用使用者手動標記的時間。"""
        return None

    # ---------- 連結帳號時的驗證 ----------

    async def verify_new_account(self, account: dict) -> dict:
        """
        用明文憑證實際呼叫平台驗證，回傳要一併存入的欄位（username、avatar_url 等）。
        驗證失敗丟 core/errors.py 的例外。
        """
        raise NotImplementedError

    def needs_reverify(self, changes: dict) -> bool:
        """預設只有改到 secret_field 才重新驗證；還有其他憑證欄位的平台（例如 Jira 的 domain）要覆寫。"""
        return self.secret_field in changes

    async def verify_account_update(self, changes: dict, existing: dict) -> dict:
        """
        needs_reverify 為 True 時呼叫：重新驗證，回傳加密好、可直接寫入 DB 的欄位。
        existing 是現有的帳號資料（憑證是密文），用來補齊這次沒改到的欄位。
        """
        raise NotImplementedError

    def __repr__(self) -> str:
        return f"<{type(self).__name__} {self.name}>"
