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
from platforms.sync import NonRetryableError
from platforms.base import PlatformAdapter
from schemas.moodle import MoodleAssignment

logger = logging.getLogger(__name__)


def _login_to_moodle(username, password):
    """
    開一個 headless Chrome、跑完 SSO 登入流程，回傳已登入狀態的 driver。
    帳密錯誤（登入後沒被導向 my/ 首頁）視為 NonRetryableError——重試也沒用。
    呼叫端用完記得自己 driver.quit()。
    """
    opts = Options()
    opts.binary_location = "/usr/bin/chromium"   # Debian 的 chromium 可執行檔
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")

    service = Service("/usr/bin/chromedriver")   # arm64 driver 的真實路徑
    driver = webdriver.Chrome(service=service, options=opts)
    try:
        driver.get("https://i.nccu.edu.tw/Login.aspx?ReturnUrl=%2fsso_app%2fMoodleSSO2.aspx")

        wait = WebDriverWait(driver, 10)
        # 模擬登入流程
        username_input = wait.until(EC.element_to_be_clickable((By.ID, "captcha_Login1_UserName")))
        username_input.send_keys(username)

        password_input = wait.until(EC.element_to_be_clickable((By.ID, "captcha_Login1_Password")))
        password_input.send_keys(password)

        login_button = wait.until(EC.element_to_be_clickable((By.ID, "captcha_Login1_LoginButton")))
        login_button.click()

        time.sleep(4)  # 等待頁面加載

        # 確認登錄是否成功
        current_url = driver.current_url
        if current_url != 'https://moodle.nccu.edu.tw/my/':
            raise NonRetryableError(f"Moodle 登入失敗，使用者：{username}")

        return driver
    except Exception:
        # 不管是帳密錯誤、逾時還是 WebDriver 本身出包，都不能讓 Chrome 進程留著
        driver.quit()
        raise


def verify_moodle_login(username, password) -> bool:
    """
    只驗證帳密能不能登入，不爬課程/作業——給連結帳號當下的驗證用，
    比 fetch_assignments() 輕量很多（不用開課程頁一個個爬）。
    帳密錯誤會拋 NonRetryableError，呼叫端接住轉成使用者看得懂的錯誤訊息。
    """
    driver = _login_to_moodle(username, password)
    driver.quit()
    return True


def fetch_assignments(username, password):
    driver = _login_to_moodle(username, password)
    try:
        # 找到包住所有課程的主容器
        semester_div = driver.find_element(By.ID, "SemesterItem_1")

        # 抓出所有課程連結（<a>）
        course_links = semester_div.find_elements(By.TAG_NAME, "a")

        all_data = []
        assignments_links = []
        # 建立存放課程資訊的清單
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
                "id": url,  # url 對每筆作業唯一，直接拿來當同步用的 id
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
    # 每次抓資料都是真的開一個 headless Chrome、跑好幾秒，成本比一般 API 呼叫高很多：
    # 限流限得比較嚴，結果也快取久一點——作業內容通常一天頂多變一次
    rate_limit = "5/minute"
    cache_ttl_seconds = 15 * 60

    not_linked_detail = "No Moodle linked account"
    auth_failed_detail = "無法取得 Moodle 資料，請確認帳號密碼是否正確"
    fetch_failed_detail = "無法取得 Moodle 資料，請稍後再試"

    collection_name = "moodle_assignments"
    id_type = str  # 作業網址

    required_create_fields = ("username", "password")
    secret_field = "password"

    def credentials_from_account(self, account, decrypt):
        if not account.get("username") or not account.get("password"):
            return None
        # 密碼只在這裡（伺服器內部、準備拿去登入 Moodle 的當下）解密，
        # 絕不印出來、絕不回傳給呼叫端以外的地方
        return {"username": account["username"], "password": decrypt(account["password"])}

    async def fetch_items(self, credentials):
        # Selenium 是同步、會阻塞的，丟到 thread pool 跑，不卡住其他請求
        return await run_in_threadpool(fetch_assignments, credentials["username"], credentials["password"])

    # Moodle 爬蟲拿不到提交狀態，沒有自動判斷依據，只能靠使用者手動標記完成（沿用預設的 is_done）

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
        # 帳號、密碼只要改其中一個都要重新驗證
        return "username" in changes or "password" in changes

    async def apply_update(self, changes, composite_id):
        # 帳號、密碼改其中一個，另一個沒帶的話就用現有值湊成完整一組再驗證，
        # 確保不管改哪一個欄位，存進資料庫前都真的登入驗證過一次
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
