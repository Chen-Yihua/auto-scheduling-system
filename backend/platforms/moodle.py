"""Moodle（政大）：使用者課程裡的作業。Moodle 沒有可用的 API，用 Selenium 登入 SSO 後爬取。"""
import logging
import time

from fastapi import HTTPException
from fastapi.concurrency import run_in_threadpool
from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from core.database import db
from core.crypto import encrypt_secret, decrypt_secret
from platforms.sync import NonRetryableError, UpstreamError
from platforms.base import PlatformAdapter
from schemas.moodle import MoodleAssignment

logger = logging.getLogger(__name__)


def _login_to_moodle(username, password):
    """
    用 headless Chrome 完成 SSO 登入，回傳已登入的 driver，呼叫端要自己 quit()。
    帳密錯誤（登入後沒導向 my/）丟 NonRetryableError。
    """
    opts = Options()
    opts.binary_location = "/usr/bin/chromium"
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")

    service = Service("/usr/bin/chromedriver")
    driver = webdriver.Chrome(service=service, options=opts)
    try:
        driver.get("https://i.nccu.edu.tw/Login.aspx?ReturnUrl=%2fsso_app%2fMoodleSSO2.aspx")

        wait = WebDriverWait(driver, 10)
        username_input = wait.until(EC.element_to_be_clickable((By.ID, "captcha_Login1_UserName")))
        username_input.send_keys(username)

        password_input = wait.until(EC.element_to_be_clickable((By.ID, "captcha_Login1_Password")))
        password_input.send_keys(password)

        login_button = wait.until(EC.element_to_be_clickable((By.ID, "captcha_Login1_LoginButton")))
        login_button.click()

        time.sleep(4)  # 等待登入後的導向

        current_url = driver.current_url
        if current_url != 'https://moodle.nccu.edu.tw/my/':
            raise NonRetryableError(f"Moodle 登入失敗，使用者：{username}")

        return driver
    except Exception:
        # 任何失敗都要關掉 Chrome，否則進程會留著
        driver.quit()
        raise


def verify_moodle_login(username, password) -> bool:
    """只驗證能不能登入、不爬作業，連結帳號時用。帳密錯誤丟 NonRetryableError。"""
    driver = _login_to_moodle(username, password)
    driver.quit()
    return True


def fetch_assignments(username, password):
    driver = _login_to_moodle(username, password)
    try:
        semester_div = driver.find_element(By.ID, "SemesterItem_1")

        course_links = semester_div.find_elements(By.TAG_NAME, "a")

        all_data = []
        assignments_links = []
        courses = []
        logger.debug("Found %d course links", len(course_links))
        for link in course_links:
            try:
                name = link.text.strip()
                url = link.get_attribute("href")
                courses.append((name, url))
            except Exception as e:
                logger.warning("忽略某個課程連結：%s", e)

        for name, url in courses:
            logger.debug("課程名稱：%s，課程連結：%s", name, url)
            try:
                driver.get(url)
                time.sleep(2)
            except Exception as e:
                logger.warning("無法打開課程連結：%s, 錯誤：%s", url, e)
                continue
            assignments = driver.find_elements(By.CSS_SELECTOR, "div.modtype_assign")
            if len(assignments)==0:
                logger.debug("無作業")
                continue
            for assign in assignments:
                try:
                    a_tag = assign.find_element(By.CSS_SELECTOR, "a.stretched-link")
                    title = a_tag.text.strip()
                    assignments_url = a_tag.get_attribute("href")
                    assignments_links.append((name,title,assignments_url))
                    logger.debug("作業標題：%s，作業連結：%s", title, assignments_url)
                except Exception as e:
                    logger.warning("無法抓取作業：%s", e)
        logger.debug("總作業數量：%d", len(assignments_links))
        for name, title, url in assignments_links:
            if title.endswith("\n作業"):
                title = title[:-3]
            logger.debug("作業名稱：%s", title)
            try:
                driver.get(url)
                time.sleep(2)
            except Exception as e:
                logger.warning("無法打開作業連結：%s, 錯誤：%s", url, e)
                continue
            try:
                due_div = driver.find_element(By.CSS_SELECTOR, 'div.activity-dates div.description-inner > div')
                due_date = due_div.text
                logger.debug("截止日期：%s", due_date)
            except Exception:
                logger.debug("截止日期：無截止日期")
                due_date = "無截止日期"

            all_data.append({
                "id": url,  # 每筆作業的網址唯一
                "course_name": name,
                "title": title,
                "url": url,
                "due_date": due_date
            })
        return all_data
    finally:
        driver.quit()


class MoodlePlatform(PlatformAdapter):
    name = "moodle"
    display_name = "Moodle"

    route_path = "/moodle/assignments"
    response_model = MoodleAssignment
    # 每次抓取都要開 Chrome 跑好幾秒，所以限流較嚴、快取較久
    rate_limit = "5/minute"
    cache_ttl_seconds = 15 * 60

    not_linked_detail = "No Moodle linked account"
    auth_failed_detail = "無法取得 Moodle 資料，請確認帳號密碼是否正確"
    fetch_failed_detail = "無法取得 Moodle 資料，請稍後再試"

    collection_name = "moodle_assignments"
    id_type = str

    required_create_fields = ("username", "password")
    secret_field = "password"

    def credentials_from_account(self, account, decrypt):
        if not account.get("username") or not account.get("password"):
            return None
        return {"username": account["username"], "password": decrypt(account["password"])}

    async def fetch_items(self, credentials):
        # Selenium 是同步阻塞的，放到 thread pool 才不會卡住 event loop
        try:
            return await run_in_threadpool(fetch_assignments, credentials["username"], credentials["password"])
        except WebDriverException as e:
            raise UpstreamError(f"Moodle 爬取失敗: {e}") from e

    # 爬不到提交狀態，沿用預設的 is_done，只靠使用者手動標記完成

    async def _verify(self, username: str, password: str) -> None:
        try:
            await run_in_threadpool(verify_moodle_login, username, password)
        except NonRetryableError:
            raise HTTPException(status_code=401, detail="Moodle 帳號或密碼錯誤")
        except WebDriverException as e:
            logger.error("Moodle 驗證發生非預期錯誤: %s", e)
            raise HTTPException(status_code=503, detail="Moodle 服務暫時無法使用，請稍後再試")

    async def verify_new(self, account):
        await self._verify(account["username"], account["password"])
        return {"avatar_url": "", "status": "connected"}

    def needs_reverify(self, changes):
        return "username" in changes or "password" in changes

    async def apply_update(self, changes, composite_id):
        # 只改其中一個時，另一個用現有值補齊再驗證
        username = changes.get("username")
        password = changes.get("password")

        existing = None
        if not username or not password:
            existing = await db.linkedAccounts.find_one({"_id": composite_id})

        if not username:
            username = existing.get("username") if existing else None
        if not password and existing and existing.get("password"):
            password = decrypt_secret(existing["password"])

        if username and password:
            await self._verify(username, password)

        if "password" in changes:
            changes["password"] = encrypt_secret(changes["password"])
        changes["status"] = "connected"
        return changes


MOODLE = MoodlePlatform()
