# API 錯誤回應第三階段：router 的 HTTPException 改成 AppError

- 狀態：已核准
- 等級：一般（只換丟出的例外類別，回應不變；`core/security.py` 的登入 dependency 只換例外類別，認證的行為與保證不變）
- issue：#90
- PR：

## 背景

來源 issue：https://github.com/Chen-Yihua/auto-scheduling-system/issues/90

[ADR 0011](../decisions/0011-api-error-status-codes.md) 定下錯誤回應的設計：狀態碼表示類別，`error_code` 表示原因，狀態碼由 `backend/core/error_codes.py` 的對照表決定。[docs/specs/issue-62-status-codes.md](issue-62-status-codes.md) 分三個階段修改，這是第三階段（P12）。第一階段是 [issue-77](issue-77-error-codes.md)，第二階段是 [issue-82](issue-82-status-codes-phase2.md)。

`fastapi.HTTPException` 只能帶 `status_code`、`detail`、`headers`，沒有 `error_code`。丟 `HTTPException` 的地方要自己決定狀態碼，`error_code` 則由 `backend/core/exception_handlers.py` 的 `http_exception_handler` 依狀態碼反推（`_ERROR_CODE_BY_HTTP_STATUS` 在 `:50-59`，handler 在 `:62-66`），表達不了比類別更精確的原因，也繞過了對照表。`core/errors.py` 的 `AppError` 則是丟的地方只選 `error_code`，狀態碼查對照表。

受影響的是後端開發者：同一個專案有兩種丟錯誤的方式，新程式照著舊的 `HTTPException` 寫，就會繞過對照表。使用者目前沒有影響。

### 目前還在丟 HTTPException 的地方

| 位置 | 情況 | 目前的回應 |
|---|---|---|
| `backend/routers/user.py:50` | `GET /users/me` 找不到使用者 | 404 `NOT_FOUND`，"User not found" |
| `backend/routers/user.py:84` | `DELETE /users/me` 找不到使用者 | 404 `NOT_FOUND`，"User not found" |
| `backend/routers/user.py:107`、`:110` | Clerk webhook 的 body 不是 JSON，或不是 object | 400 `INVALID_REQUEST`，"Invalid JSON payload" |
| `backend/routers/user.py:121` | Clerk webhook 的 `user.deleted` 沒有 `data.id` | 400 `INVALID_REQUEST`，"Clerk ID not found in payload" |
| `backend/routers/linked_account.py:49` | `PATCH /users/me/linked-accounts/{platform}` 帳號不存在 | 404 `NOT_FOUND`，"Linked account not found or no valid fields to update" |
| `backend/routers/schedule.py:116` | 計算排程建議時發生未預期的例外（`_compute_suggestion`） | 500 `INTERNAL_ERROR`，`detail` 是呼叫端傳入的 `error_detail` |
| `backend/core/security.py:144` | `get_current_clerk_user` 沒有 credentials 或沒有解出的 payload；只有直接呼叫函式（unit 測試）才走得到：請求經過 `clerk_auth`（`auto_error=True`，`:136`）時，缺 token、scheme 錯、token 無效都已先由 library 丟 403 | 401 `UNAUTHENTICATED`，"Invalid authentication credentials"，帶 `WWW-Authenticate: Bearer` |

- `linked_account.py:49` 的訊息後半句已經不會發生：沒有可更新的欄位時，`crud/linked_account.py:76-77` 先丟 `InvalidRequestError`（400）。router 收到 `False` 只剩帳號不存在一種情況（`crud/linked_account.py:82-83`、`:88-89`）。
- 前端把字串型的 `detail` 接在錯誤說明後面顯示（`frontend/utils/errorMessages.ts:62-66`），所以 `detail` 的文字使用者看得到。
- 文件寫著舊的分工：`backend/README.md:69`「只有 router 用 `HTTPException`」、`docs/architecture.md:21`「只有這層用 HTTPException」、`backend/core/errors.py` 的模組 docstring「crud、services 和各平台用的例外」。
- `http_exception_handler` 之後還會收到：未知路由的 404、不支援的方法 405（Starlette），以及 `fastapi-clerk-auth` 在沒帶 token、scheme 錯、token 無效時丟的 403 "Forbidden"（`fastapi_clerk_auth/__init__.py:148-163`），經對照轉成 401 `UNAUTHENTICATED`，不帶 `WWW-Authenticate`（`tests/integration/test_error_responses_api.py:41-48`）。這是使用者實際收到的登入失敗回應。

## 需求

1. 上表每一處都改成丟 `backend/core/errors.py` 的例外，不指定狀態碼：
   - `user.py:50`、`:84`、`linked_account.py:49` → `NotFoundError`
   - `user.py:107`、`:110`、`:121` → `InvalidRequestError`
   - `schedule.py:116` → `AppError`（預設 `INTERNAL_ERROR`）
   - `security.py:144` → `AppError(..., error_code="UNAUTHENTICATED", headers={"WWW-Authenticate": "Bearer"})`
2. 除了第 3 點，每一處的狀態碼、`error_code`、`detail`、header 都和改之前相同。
3. `PATCH /users/me/linked-accounts/{platform}` 帳號不存在時，`detail` 改成 "Linked account not found"（和 `DELETE` 一致，`crud/linked_account.py:95`），仍是 404 `NOT_FOUND`。
4. `http_exception_handler` 與 `_ERROR_CODE_BY_HTTP_STATUS` 保留，只把 `:49` 的註解改成目前還會用到它的來源（未知路由、不支援的方法、Clerk 驗證 library 的 403、FastAPI 或其他 library 丟的 `HTTPException`），拿掉「router 還沒改成 AppError」。
5. 文件改成所有層都丟 `core/errors.py` 的例外、不用 `HTTPException`：`backend/README.md`「錯誤處理」第一條、`docs/architecture.md` 後端分層圖的 `routers/` 那一行、`backend/core/errors.py` 的模組 docstring。
6. 移除改完後沒用到的 `HTTPException` import。

## 不做

- 不加自動檢查（測試或 lint）防止之後又寫 `raise HTTPException`，靠需求 5 的文件與審查。
- 不改其他 `detail` 的文字（例如英文改中文），除了需求 3。
- 不改 `_ERROR_CODE_BY_HTTP_STATUS` 的內容與 `http_exception_handler` 的行為。
- 不改 ADR 0011 與前端。

## 驗收條件

| # | 條件 | 類型 |
|---|---|---|
| AC1 | `GET /users/me`、`DELETE /users/me` 找不到使用者時，回 404 `{"detail": "User not found", "error_code": "NOT_FOUND"}` | 使用者行為 |
| AC2 | Clerk webhook 簽章正確、但 body 不是 JSON、不是 object，或 `user.deleted` 沒有 `data.id` 時，回 400，`error_code` 是 `INVALID_REQUEST`，`detail` 分別是 "Invalid JSON payload"、"Invalid JSON payload"、"Clerk ID not found in payload" | 不變條件 |
| AC3 | `PATCH /users/me/linked-accounts/{platform}` 帳號不存在時回 404 `{"detail": "Linked account not found", "error_code": "NOT_FOUND"}`；沒有可更新的欄位時仍回 400 `INVALID_REQUEST` | 使用者行為 |
| AC4 | 計算排程建議時發生未預期的例外，回 500 `INTERNAL_ERROR`，`detail` 是呼叫端給的固定文字（不含例外內容），並照舊記下例外的 log | 不變條件 |
| AC5 | `get_current_clerk_user` 沒有 credentials 或沒有解出的 payload 時，回 401 `UNAUTHENTICATED`，`detail` "Invalid authentication credentials"，帶 `WWW-Authenticate: Bearer` | 不變條件 |
| AC6 | 未知路由回 404 `NOT_FOUND`、不支援的方法回 405 `METHOD_NOT_ALLOWED`、沒帶 token 或 token 無效回 401 `{"detail": "Forbidden", "error_code": "UNAUTHENTICATED"}`，和改之前相同 | 不變條件 |
| AC7 | `backend/` 的正式程式（不含 `tests/`）沒有 `raise HTTPException`；`backend/README.md`、`docs/architecture.md`、`core/errors.py` 的說明寫明所有層都丟 `core/errors.py` 的例外 | 不變條件 |

## 不適用的情境

| 情境 | 原因 |
|---|---|
| 空資料、載入中 | 沒有改到資料的讀寫與畫面 |
| 未登入／無權限 | 登入驗證的判斷不變，只換例外類別；請求實際收到的回應由 AC6 確認相同，AC5 確認直接呼叫時的例外內容 |
| 資料處理 | 沒有改資料庫與資料格式 |
| 安全性 | `detail` 都是固定文字，不帶 payload、例外內容或其他使用者的資料，由 AC2、AC4 確認 |

## 實作計畫

1. `backend/routers/user.py`、`linked_account.py`、`schedule.py`、`backend/core/security.py`：照需求 1 換成 `core/errors.py` 的例外，移除沒用到的 `HTTPException` import（需求 6）。`security.py` 的 `status` import 若只剩這裡用，一併移除。
2. `backend/core/exception_handlers.py:49`：照需求 4 改註解。
3. 文件：照需求 5 改 `backend/README.md`、`docs/architecture.md`、`backend/core/errors.py` 的 docstring。
4. 測試：既有測試用 `HTTPException` 斷言或 mock 這幾處的，改成新的例外類別或改斷言回應（照 `backend/tests/README.md`）。已知的有：
   - `tests/unit/test_security.py:346-351`：改成斷言 `AppError` 的 `error_code` 與 `headers`。
   - `tests/unit/test_exception_handlers.py:181-187`：測的是 `HTTPException` 保留 header，行為仍要保留；只把 docstring 裡「`core/security.py` 401」的例子拿掉。
   - `tests/integration/test_linked_account_api.py:108`：改成新的 `detail`。
   - `tests/unit/test_linked_account_router.py:93`（docstring `:86` 的「或沒有合法欄位可更新」一併改）、`tests/unit/test_user_webhook.py:106`、`:140`、`:157`、`tests/unit/test_schedule_router.py:80`、`:102`：`pytest.raises(HTTPException)` 改成新的例外類別（`AppError` 不是 `HTTPException` 的子類別，不改會失敗）。
   - `tests/unit/test_linked_account_router.py:123`、`tests/integration/test_user_api.py:108` 等用 `HTTPException` 當 mock 的 side effect：若是模擬 crud 丟錯，改成 crud 實際會丟的例外。

為什麼這樣做：`AppError` 的子類別已經涵蓋這幾種原因（`NotFoundError`、`InvalidRequestError`），`AppError` 本身支援 `headers`，不用新增類別；`http_exception_handler` 仍要處理 Starlette 與 library 丟的例外，所以不移除。

## 測試對應

| AC | 測試 |
|---|---|
| AC1 | integration：`tests/integration/test_unhandled_error_handling.py:63-73`（GET，已斷言整個 body）、`tests/integration/test_user_api.py:134-142`（DELETE，補斷言整個 body） |
| AC2 | unit：`tests/unit/test_user_webhook.py:99-109`、`:138-143`、`:155-160` 三種 payload，改成斷言 `error_code` 與 `detail`（目前只斷言狀態碼） |
| AC3 | integration：`tests/integration/test_linked_account_api.py:108` 改新 `detail`；沒有欄位的 400 既有測試保留 |
| AC4 | unit：`tests/unit/test_schedule_router.py:64-83`、`:86-105`，斷言 `error_code` 是 `INTERNAL_ERROR` 與固定的 `detail`；其中一個測試用 `caplog` 斷言有 ERROR 等級的 log |
| AC5 | unit：`tests/unit/test_security.py:345-351` 斷言 `AppError` 的 `error_code`、`detail` 與 `headers` |
| AC6 | 既有的 `tests/integration/test_error_responses_api.py` 的 `test_unknown_route_returns_not_found_code`、`test_unsupported_method_returns_method_not_allowed_and_keeps_allow_header`、`test_missing_or_invalid_jwt_returns_unauthenticated` 不改、全部通過 |
| AC7 | `grep -rn "raise HTTPException" backend --include=*.py --exclude-dir=tests` 沒有結果；讀三份文件 |

## 修改紀錄

| 日期 | 修改 | 原因 | 確認者 |
|---|---|---|---|
