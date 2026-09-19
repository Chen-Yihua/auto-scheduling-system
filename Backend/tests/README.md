# 後端測試：哪種測試寫在哪個檔案

每個模組（github、jira、moodle…）的測試依「測到哪一層」分成最多四種檔案：

| 檔名 | 怎麼測 | 負責測什麼 | 不測什麼 |
|---|---|---|---|
| `test_<x>_crud.py` | 直接呼叫 `crud/<x>.py` 的函式 | 商業邏輯、資料轉換、對外 API 呼叫（翻頁、重試規則、錯誤分類） | HTTP、狀態碼 |
| `test_<x>_router.py` | 直接呼叫 router 函式，例如 `await jira_router.get_jira_issues(...)` | router 自己的判斷分支：查不到帳號 / DB 掛掉 / 解密失敗 / 同步失敗各回什麼狀態碼、有沒有設回應 header | 路由註冊、登入驗證、JSON 格式 |
| `test_<x>_api.py` | 走 HTTP：`AsyncClient(ASGITransport(app=main.app))` + `logged_in_user` fixture | 「接線」：路由有註冊、登入驗證有掛上、`response_model` 的 JSON 格式、狀態碼與 `detail` 真的送得出去、請求內容驗證（422） | 每個錯誤分支（交給 router 測試） |
| `test_<x>_scenario.py` | 走 HTTP，串多個步驟 | 端對端情境（例如建立 -> 查詢 -> 刪除） | 單一分支 |

`_api.py` 的標準結構是三種測試：**成功**、**典型錯誤**（例如未綁定帳號）、**沒登入被擋**。
github、jira、moodle、oauth、schedule 已照這個結構；linked account、manual task、user 的 `_api.py` 是較早寫的，
還沒補「沒登入被擋」，manual task 與 user 也還用自己的 `TestClient` + fixture，沒改用 `logged_in_user`。

## 各模組現況

| 模組 | crud | router | api | 其他 |
|---|---|---|---|---|
| github | ✅ | ✅ | ✅ | |
| jira | ✅ | ✅ | ✅ | |
| moodle | ✅ | ✅ | ✅ | |
| oauth | ✅（`_free_slots`） | ✅ | ✅ | `test_google_calendar_service.py`（`services/`） |
| schedule | ✅ | ✅ | ✅ | |
| linked account | ✅ | ✅ | ✅ | `_scenario`、`_secrets` |
| manual task | ✅ | — | ✅ | `_scenario` |
| user | ✅ | — | ✅ | `test_user_webhook.py` |

`—` 代表目前沒有獨立的 router 測試（該 router 沒有額外分支，或分支已由 `_api.py` 涵蓋）。

## 跨模組的測試

`test_security.py`（登入驗證）、`test_cors.py`、`test_rate_limit.py`、`test_cache.py`、
`test_crypto.py`、`test_db_indexes.py`、`test_external_sync.py`、`test_logging.py` 等，
測的是共用元件，不屬於單一模組。

## 共用工具

`conftest.py` 的 `logged_in_user` fixture：假裝已登入的使用者（`{"sub": "test_user_123"}`），
測試結束後一定會還原，`_api.py` 需要「已登入」時就把它加進測試函式的參數。
不想登入（測「沒登入被擋」）就不要用它。
