"""所有支援的外部平台。路由、排程、帳號連結和 DB 索引都依這份清單自動支援。"""
from platforms.base import PlatformAdapter
from platforms.github import GITHUB
from platforms.jira import JIRA
from platforms.moodle import MOODLE

PLATFORMS: dict[str, PlatformAdapter] = {
    platform.name: platform
    for platform in (GITHUB, JIRA, MOODLE)
}
