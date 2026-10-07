"""
所有支援的外部平台。新增平台：在 platforms/ 底下寫一個 PlatformAdapter 子類別
（見 platforms/base.py），再加進下面的 PLATFORMS，其餘地方都會自動支援——
對外 API 路由（platforms/router.py）、排程整合（crud/schedulable_items.py）、
帳號連結驗證（crud/linked_account.py）、資料庫索引（core/database.py）都是讀這份清單。
"""
from platforms.base import PlatformAdapter
from platforms.github import GITHUB
from platforms.jira import JIRA
from platforms.moodle import MOODLE

PLATFORMS: dict[str, PlatformAdapter] = {
    platform.name: platform
    for platform in (GITHUB, JIRA, MOODLE)
}
