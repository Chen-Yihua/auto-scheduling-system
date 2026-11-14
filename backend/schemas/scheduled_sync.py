from pydantic import BaseModel


class ScheduledSyncResult(BaseModel):
    """只帶筆數，不帶使用者 id、憑證或錯誤訊息：GitHub Actions 的 log 是公開的。"""
    succeeded: int
    failed: int
    skipped: int
