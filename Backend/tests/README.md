# 後端測試：哪種測試寫在哪個檔案

## 資料夾：先看有沒有走 HTTP

```
tests/
├── conftest.py      共用設定（假資料庫、假登入 logged_in_user），所有子資料夾都會自動使用
├── unit/            單元測試：不碰 HTTP，直接呼叫函式（crud、router 函式、services、cache、crypto…）
└── integration/     整合 / API 測試：用 AsyncClient 打 endpoint（*_api、*_scenario，以及
                     資料庫錯誤處理、兜底 500、CORS、限流）
```

只跑其中一類：

```bash
pytest tests/unit          # 幾秒內跑完，開發時常跑
pytest tests/integration   # 走 HTTP 的測試
pytest                     # 全部（CI 用這個）
```

新增測試時：先決定「有沒有走 HTTP」放進對應資料夾，再照下面的檔名規則命名。
每個模組的測試依「測到哪一層」分成最多四種檔案：

| 檔名 | 怎麼測 | 負責測什麼 | 不測什麼 |
|---|---|---|---|
| `unit/test_<x>_crud.py` | 直接呼叫 `crud/<x>.py` 的函式 | 商業邏輯、資料轉換、對外 API 呼叫（翻頁、重試規則、錯誤分類） | HTTP、狀態碼 |
| `unit/test_<x>_router.py` | 直接呼叫 router 函式，例如 `await jira_router.get_jira_issues(...)` | router 自己的判斷分支：查不到帳號 / 解密失敗 / 同步失敗各回什麼狀態碼、有沒有設回應 header（資料庫連不上由全域 handler 統一處理，見 `integration/test_db_error_handling.py`） | 路由註冊、登入驗證、JSON 格式 |
| `integration/test_<x>_api.py` | 走 HTTP：`AsyncClient(ASGITransport(app=main.app))` + `logged_in_user` fixture | 「接線」：路由有註冊、登入驗證有掛上、`response_model` 的 JSON 格式、狀態碼與 `detail` 真的送得出去、請求內容驗證（422） | 每個錯誤分支（交給 router 測試） |
| `integration/test_<x>_scenario.py` | 走 HTTP，串多個步驟 | 端對端情境（例如建立 -> 查詢 -> 刪除） | 單一分支 |

`_api.py` 的標準結構是三種測試：**成功**、**典型錯誤**（例如未綁定帳號回 400、找不到回 404），以及**沒登入被擋**。
所有 `_api.py` 都用 `AsyncClient` + `logged_in_user` fixture，crud 或外部呼叫用 `monkeypatch` / `@patch` 換掉。

## 各模組現況

| 模組 | crud | router | api | 其他 |
|---|---|---|---|---|
| github | ✅ | ✅ | ✅ | |
| jira | ✅ | ✅ | ✅ | |
| moodle | ✅ | ✅ | ✅ | |
| oauth | ✅（`_free_slots`） | ✅ | ✅ | `test_google_calendar_service.py`（`services/`） |
| schedule | ✅ | ✅ | ✅ | |
| linked account | ✅ | ✅ | ✅ | `_scenario`、`_secrets` |
| manual task | ✅ | ✅ | ✅ | `_scenario` |
| user | ✅ | — | ✅ | `test_user_webhook.py` |

`—` 代表目前沒有獨立的 router 測試（該 router 沒有額外分支，或分支已由 `_api.py` 涵蓋）。目前只有 user。

## 跨模組的測試

測的是共用元件，不屬於單一模組：

- `integration/`（走 HTTP）：`test_db_error_handling.py`（資料庫例外集中處理：連線類錯誤 503、其他 500）、
  `test_unhandled_error_handling.py`（兜底：沒預期的例外回帶 CORS 的 JSON 500）、
  `test_cors.py`、`test_rate_limit.py`。
- `unit/`（不走 HTTP）：`test_security.py`（登入驗證）、`test_cache.py`、`test_crypto.py`、
  `test_db_indexes.py`、`test_external_sync.py`、`test_logging.py`、`test_ci_env_requirements.py` 等。

## 共用工具

`conftest.py` 的 `logged_in_user` fixture：假裝已登入的使用者（`{"sub": "test_user_123"}`），
測試結束後一定會還原，`_api.py` 需要「已登入」時就把它加進測試函式的參數。
不想登入（測「沒登入被擋」）就不要用它。

## 每個測試的說明寫法

每個測試函式開頭用 docstring（一到兩行）寫「**什麼情境 → 預期什麼行為（為什麼）**」，
例如：`token 失效（NonRetryableError）要回 401，跟一般暫時性失敗（500）分開——重試也沒用。`

- docstring 寫的是「測什麼」：情境、預期結果、背後的規則或要防的問題。
- 「怎麼測」（怎麼 mock、為什麼用某個假物件、為什麼走 HTTP）不放進 docstring，
  需要說明時寫成測試裡面、靠近該段程式碼的 `#` 註解。
- 名稱已經說完的不用重複。

所有測試檔案都已補齊（新增測試時請照這個格式寫）。
