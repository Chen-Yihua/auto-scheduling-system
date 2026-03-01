from db.mongodb import db
from fastapi import HTTPException
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import os

async def get_user_account(clerk_id: str):
    """
    Get the user from the database
    """
    user = await db.linkedAccounts.find_one({"platform":"moodle","clerk_id":clerk_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user



def fetch_assignments(username, password):
    opts = Options()
    opts.binary_location = "/usr/bin/chromium"   # Debian 的 chromium 可執行檔
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")

    service = Service("/usr/bin/chromedriver")   # ★ arm64 driver 的真實路徑
    driver = webdriver.Chrome(service=service, options=opts)
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
    if current_url == 'https://moodle.nccu.edu.tw/my/':
        print("成功登錄")
    else:
        print("登錄失敗或需要進一步驗證")

    # 找到包住所有課程的主容器
    semester_div = driver.find_element(By.ID, "SemesterItem_1")

    # 抓出所有課程連結（<a>）
    course_links = semester_div.find_elements(By.TAG_NAME, "a")
    
    all_data = []
    assignments_links = []
    # 建立存放課程資訊的清單
    courses = []
    print(len(course_links))
    for link in course_links:
        try:
            name = link.text.strip()
            url = link.get_attribute("href")
            courses.append((name, url))
        except Exception as e:
            print(f"忽略某個課程連結：{e}")

    for name, url in courses:
        print(f"課程名稱：{name}")
        print(f"課程連結：{url}")

        driver.get(url)
        time.sleep(2)

        assignments = driver.find_elements(By.CSS_SELECTOR, "div.modtype_assign")
        if len(assignments)==0:
            print("無作業")
            print("-" * 40)
            continue
        for assign in assignments:
            try:
                a_tag = assign.find_element(By.CSS_SELECTOR, "a.stretched-link")
                title = a_tag.text.strip()
                assignments_url = a_tag.get_attribute("href")
                assignments_links.append((name,title,assignments_url))
                print(f"  作業標題：{title}")
                print(f"  作業連結：{assignments_url}")
            except Exception as e:
                print(f"  無法抓取作業：{e}")
        print("-" * 40)
    print("注意：以上log都是用來debug的，請忽略。")
    print("-" * 40)
    print("注意：以下會顯示回傳給前端的所有作業資訊")
    print(f"總作業數量 :{len(assignments_links)}")
    print("-" * 40)
    for name, title, url in assignments_links:
        if title.endswith("\n作業"):
            title = title[:-3]
        print(f"作業名稱：{title}")
        driver.get(url)
        time.sleep(2)
        try:
            due_div = driver.find_element(By.CSS_SELECTOR, 'div.activity-dates div.description-inner > div')
            due_date = due_div.text
            print(f"  截止日期：{due_date}")
        except Exception as e:
            print("截止日期：無截止日期")
            due_date = "無截止日期"
            
        all_data.append({
            "course_name": name,
            "assignment_title": title,
            "assignment_url": url,
            "due_date": due_date
        })
    driver.quit()
    return all_data
