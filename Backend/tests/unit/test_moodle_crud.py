"""
crud/moodle.py 的 Selenium 爬蟲邏輯——「例外路徑也要收尾（driver.quit()）」正好
是這裡的活教材，但這個檔案先前完全沒有專屬測試。

策略：完全 mock 掉 selenium 的 webdriver.Chrome 跟 WebDriverWait，不真的開瀏覽器，
只驗證 control flow——該不該收尾、該不該丟例外——不驗證 DOM 互動細節本身。
"""
import pytest
from unittest.mock import MagicMock

import crud.moodle as moodle_crud
from crud.errors import NonRetryableError


@pytest.fixture(autouse=True)
def mock_selenium_wait(monkeypatch):
    # 讓 WebDriverWait(...).until(...) 直接跳過，不真的等待/檢查任何 DOM 條件
    monkeypatch.setattr(
        moodle_crud, "WebDriverWait",
        lambda driver, timeout: MagicMock(until=lambda condition: MagicMock())
    )
    # 不要真的 sleep，測試才會快
    monkeypatch.setattr(moodle_crud.time, "sleep", lambda seconds: None)


def _mock_chrome(monkeypatch, final_url):
    driver = MagicMock()
    driver.current_url = final_url
    monkeypatch.setattr(moodle_crud.webdriver, "Chrome", lambda **kwargs: driver)
    return driver


def test_login_to_moodle_returns_driver_on_success(monkeypatch):
    """帳密正確 → 登入成功，回傳的瀏覽器要保持開著，給後續爬蟲使用。"""
    driver = _mock_chrome(monkeypatch, "https://moodle.nccu.edu.tw/my/")

    result = moodle_crud._login_to_moodle("stu123", "pw123")

    assert result is driver
    driver.quit.assert_not_called()


def test_login_to_moodle_quits_driver_and_raises_when_login_fails(monkeypatch):
    """帳密錯誤 → 丟 NonRetryableError（重試也沒用），而且要先關掉瀏覽器，不能留著 Chrome 行程。"""
    driver = _mock_chrome(monkeypatch, "https://i.nccu.edu.tw/Login.aspx?error=1")

    with pytest.raises(NonRetryableError):
        moodle_crud._login_to_moodle("stu123", "wrong-password")

    driver.quit.assert_called_once()


def test_login_to_moodle_quits_driver_on_unexpected_exception(monkeypatch):
    """登入過程出現非帳密問題的錯誤（例如等待逾時）→ 錯誤照樣往外丟，瀏覽器一樣要關掉。"""
    driver = _mock_chrome(monkeypatch, "https://moodle.nccu.edu.tw/my/")
    # 模擬 WebDriverWait 本身出包（例如逾時），不是帳密問題——驗證不管哪種
    # 例外，driver 都要被收掉，不能留著 Chrome 行程
    monkeypatch.setattr(
        moodle_crud, "WebDriverWait",
        lambda driver, timeout: MagicMock(until=MagicMock(side_effect=TimeoutError("等待逾時")))
    )

    with pytest.raises(TimeoutError):
        moodle_crud._login_to_moodle("stu123", "pw123")

    driver.quit.assert_called_once()


def test_verify_moodle_login_returns_true_and_quits_driver(monkeypatch):
    """驗證 Moodle 帳密：登入成功 → 回傳 True，用完就關掉瀏覽器。"""
    driver = MagicMock()
    monkeypatch.setattr(moodle_crud, "_login_to_moodle", lambda u, p: driver)

    result = moodle_crud.verify_moodle_login("stu123", "pw123")

    assert result is True
    driver.quit.assert_called_once()


def test_verify_moodle_login_propagates_nonretryable_error(monkeypatch):
    """帳密錯誤的 NonRetryableError 要原封不動往外丟，不能被吞掉或轉成 False。"""
    def fake_login(u, p):
        raise NonRetryableError("帳密錯誤")

    monkeypatch.setattr(moodle_crud, "_login_to_moodle", fake_login)

    with pytest.raises(NonRetryableError):
        moodle_crud.verify_moodle_login("stu123", "wrong")


def test_fetch_assignments_quits_driver_even_when_scraping_raises(monkeypatch):
    """爬蟲中途出錯 → 錯誤照樣往外丟，但瀏覽器一定要關掉。"""
    driver = MagicMock()
    driver.find_element.side_effect = RuntimeError("找不到課程列表")
    monkeypatch.setattr(moodle_crud, "_login_to_moodle", lambda u, p: driver)

    with pytest.raises(RuntimeError):
        moodle_crud.fetch_assignments("stu123", "pw123")

    driver.quit.assert_called_once()


def test_fetch_assignments_happy_path_returns_parsed_assignments(monkeypatch):
    """正常流程：找到課程 → 進入課程頁 → 找出作業 → 回傳課程名稱、作業標題（不含尾巴多出的「作業」二字）和截止日期，最後關掉瀏覽器。"""
    driver = MagicMock()
    monkeypatch.setattr(moodle_crud, "_login_to_moodle", lambda u, p: driver)

    # 課程列表：一個課程連結
    course_link = MagicMock()
    course_link.text = "資料庫課程"
    course_link.get_attribute.return_value = "https://moodle.nccu.edu.tw/course/view.php?id=1"
    semester_div = MagicMock()
    semester_div.find_elements.return_value = [course_link]

    # 該課程頁面裡的作業區塊
    assignment_block = MagicMock()
    a_tag = MagicMock()
    a_tag.text = "第一次作業\n作業"
    a_tag.get_attribute.return_value = "https://moodle.nccu.edu.tw/mod/assign/view.php?id=10"
    assignment_block.find_element.return_value = a_tag

    due_div = MagicMock()
    due_div.text = "2026年9月30日 23:59"

    def find_element_router(by, selector):
        if selector == "SemesterItem_1":
            return semester_div
        if "activity-dates" in selector:
            return due_div
        raise AssertionError(f"unexpected find_element selector: {selector}")

    driver.find_element.side_effect = find_element_router

    def find_elements_router(by, selector):
        if "modtype_assign" in selector:
            return [assignment_block]
        raise AssertionError(f"unexpected find_elements selector: {selector}")

    driver.find_elements.side_effect = find_elements_router

    result = moodle_crud.fetch_assignments("stu123", "pw123")

    assert len(result) == 1
    assert result[0]["course_name"] == "資料庫課程"
    assert result[0]["title"] == "第一次作業"  # 尾巴的「\n作業」被去掉
    assert result[0]["due_date"] == "2026年9月30日 23:59"
    driver.quit.assert_called_once()


def test_fetch_assignments_skips_bad_course_link_but_keeps_going(monkeypatch):
    """單一課程連結壞掉不能讓整支爬蟲當掉：跳過它，繼續處理其他課程。"""
    driver = MagicMock()
    monkeypatch.setattr(moodle_crud, "_login_to_moodle", lambda u, p: driver)

    bad_link = MagicMock()
    bad_link.text = "壞掉的課程"
    bad_link.get_attribute.side_effect = RuntimeError("讀不到連結")

    good_link = MagicMock()
    good_link.text = "正常的課程"
    good_link.get_attribute.return_value = "https://moodle.nccu.edu.tw/course/view.php?id=3"

    semester_div = MagicMock()
    semester_div.find_elements.return_value = [bad_link, good_link]

    driver.find_element.return_value = semester_div
    driver.find_elements.return_value = []  # 正常課程沒有作業，測到這裡就夠了

    result = moodle_crud.fetch_assignments("stu123", "pw123")

    assert result == []  # 沒有整支炸掉，安全跳過壞的那個連結
    driver.quit.assert_called_once()


def test_fetch_assignments_skips_course_that_fails_to_open(monkeypatch):
    """課程頁面打不開 → 跳過這個課程，繼續處理其他課程。"""
    driver = MagicMock()
    monkeypatch.setattr(moodle_crud, "_login_to_moodle", lambda u, p: driver)

    course_link = MagicMock()
    course_link.text = "打不開的課程"
    course_link.get_attribute.return_value = "https://moodle.nccu.edu.tw/course/view.php?id=4"
    semester_div = MagicMock()
    semester_div.find_elements.return_value = [course_link]

    driver.find_element.return_value = semester_div
    driver.get.side_effect = RuntimeError("連線逾時")

    result = moodle_crud.fetch_assignments("stu123", "pw123")

    assert result == []
    driver.quit.assert_called_once()


def test_fetch_assignments_skips_assignment_that_fails_to_parse(monkeypatch):
    """某個作業區塊解析失敗（例如缺 a.stretched-link）→ 跳過它，不影響其他作業。"""
    driver = MagicMock()
    monkeypatch.setattr(moodle_crud, "_login_to_moodle", lambda u, p: driver)

    course_link = MagicMock()
    course_link.text = "課程"
    course_link.get_attribute.return_value = "https://moodle.nccu.edu.tw/course/view.php?id=5"
    semester_div = MagicMock()
    semester_div.find_elements.return_value = [course_link]

    bad_assignment = MagicMock()
    bad_assignment.find_element.side_effect = RuntimeError("找不到 a.stretched-link")

    driver.find_element.return_value = semester_div
    driver.find_elements.return_value = [bad_assignment]

    result = moodle_crud.fetch_assignments("stu123", "pw123")

    assert result == []
    driver.quit.assert_called_once()


def test_fetch_assignments_defaults_due_date_when_missing(monkeypatch):
    """作業沒設截止日期是正常狀態 → due_date 顯示「無截止日期」，不能讓爬蟲當掉。"""
    driver = MagicMock()
    monkeypatch.setattr(moodle_crud, "_login_to_moodle", lambda u, p: driver)

    course_link = MagicMock()
    course_link.text = "課程"
    course_link.get_attribute.return_value = "https://moodle.nccu.edu.tw/course/view.php?id=6"
    semester_div = MagicMock()
    semester_div.find_elements.return_value = [course_link]

    a_tag = MagicMock()
    a_tag.text = "沒有期限的作業"
    a_tag.get_attribute.return_value = "https://moodle.nccu.edu.tw/mod/assign/view.php?id=20"
    assignment_block = MagicMock()
    assignment_block.find_element.return_value = a_tag

    def find_element_router(by, selector):
        if selector == "SemesterItem_1":
            return semester_div
        if "activity-dates" in selector:
            raise RuntimeError("這個作業沒有設截止日期")
        raise AssertionError(f"unexpected find_element selector: {selector}")

    driver.find_element.side_effect = find_element_router
    driver.find_elements.return_value = [assignment_block]

    result = moodle_crud.fetch_assignments("stu123", "pw123")

    assert len(result) == 1
    assert result[0]["due_date"] == "無截止日期"
    driver.quit.assert_called_once()


def test_fetch_assignments_skips_assignment_page_that_fails_to_open(monkeypatch):
    """課程頁面打得開、但個別作業的頁面打不開 → 跳過這筆作業，不影響其他作業。"""
    driver = MagicMock()
    monkeypatch.setattr(moodle_crud, "_login_to_moodle", lambda u, p: driver)

    course_link = MagicMock()
    course_link.text = "課程"
    course_link.get_attribute.return_value = "https://moodle.nccu.edu.tw/course/view.php?id=7"
    semester_div = MagicMock()
    semester_div.find_elements.return_value = [course_link]

    a_tag = MagicMock()
    a_tag.text = "打不開的作業"
    a_tag.get_attribute.return_value = "https://moodle.nccu.edu.tw/mod/assign/view.php?id=30"
    assignment_block = MagicMock()
    assignment_block.find_element.return_value = a_tag

    driver.find_element.return_value = semester_div
    driver.find_elements.return_value = [assignment_block]
    # 第一次 driver.get 是打開課程頁（成功），第二次是打開作業頁（失敗）
    driver.get.side_effect = [None, RuntimeError("作業頁面連線逾時")]

    result = moodle_crud.fetch_assignments("stu123", "pw123")

    assert result == []
    driver.quit.assert_called_once()


def test_fetch_assignments_skips_course_with_no_assignments(monkeypatch):
    """課程裡沒有任何作業區塊 → 回傳空清單，不是錯誤。"""
    driver = MagicMock()
    monkeypatch.setattr(moodle_crud, "_login_to_moodle", lambda u, p: driver)

    course_link = MagicMock()
    course_link.text = "沒有作業的課程"
    course_link.get_attribute.return_value = "https://moodle.nccu.edu.tw/course/view.php?id=2"
    semester_div = MagicMock()
    semester_div.find_elements.return_value = [course_link]

    driver.find_element.return_value = semester_div
    driver.find_elements.return_value = []  # 這個課程沒有 modtype_assign 區塊

    result = moodle_crud.fetch_assignments("stu123", "pw123")

    assert result == []
    driver.quit.assert_called_once()


@pytest.mark.asyncio
async def test_sync_moodle_assignments_delegates_to_sync_platform_items(monkeypatch):
    """同步 Moodle 作業 → 交給通用的同步流程處理，並原樣回傳它的結果。"""
    # 檢查交給通用流程的參數（儲存位置、使用者 id、識別欄位、抓資料的函式）都正確；通用流程本身的邏輯不在這裡重測
    # 它只是包一層 sync_platform_items，所以只檢查傳進去的參數，不重測 sync_platform_items 本身的邏輯
    captured = {}

    async def fake_sync_platform_items(**kwargs):
        captured.update(kwargs)
        return ("issues", False, None, False)

    monkeypatch.setattr(moodle_crud, "sync_platform_items", fake_sync_platform_items)

    async def fetch_fn():
        return []

    result = await moodle_crud.sync_moodle_assignments("uid123", fetch_fn)

    assert result == ("issues", False, None, False)
    assert captured["collection"] is moodle_crud.db.moodle_assignments
    assert captured["user_id"] == "uid123"
    assert captured["id_field"] == "id"
    assert captured["fetch_fn"] is fetch_fn
