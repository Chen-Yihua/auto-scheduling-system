# `get_current_clerk_user` 補足空 payload 測試

- 狀態：已核准
- 等級：一般（只補既有登入驗證函式的單元測試，不改程式行為、API、資料或安全規則）
- issue：#92（https://github.com/Chen-Yihua/auto-scheduling-system/issues/92）
- PR：#132

## 簡短說明

補上 `get_current_clerk_user` 對「有 credentials 但沒有解出 JWT payload」情況的單元測試，避免驗證條件被改錯時測試仍通過。

## 背景

後端開發者修改登入驗證 dependency 時，`backend/core/security.py` 的 `get_current_clerk_user` 會在 `credentials` 不存在或 `credentials.decoded` 為空時，丟出 `UNAUTHENTICATED` 的 `AppError`。現有 `backend/tests/unit/test_security.py` 只測 `credentials=None`，沒有測試有 credentials 但 `decoded=None` 的分支；因此條件若被改成只檢查 `credentials`，現有測試不會失敗。

實際使用者請求會先由 `clerk_auth`（`auto_error=True`）處理，正常請求不會走到有 credentials 但 `decoded=None` 的分支。本次缺口影響後端開發者維護登入驗證時的回歸保護，不影響使用者現有請求。

## 需求

1. 在 `backend/tests/unit/test_security.py` 為 `get_current_clerk_user` 增加 `HTTPAuthorizationCredentials(scheme="Bearer", credentials="x", decoded=None)` 測試案例。
2. 該測試案例要驗證與 credentials 缺失相同的 `AppError` 行為：`error_code` 為 `UNAUTHENTICATED`、detail 為 `Invalid authentication credentials`，且 headers 為 `{"WWW-Authenticate": "Bearer"}`。
3. 保留成功回傳 decoded payload 的既有測試與 credentials 缺失的既有行為測試。

## 不做

- 不修改 `backend/core/security.py` 的認證判斷或 `AppError` 行為。
- 不新增 endpoint、不修改 API response、不修改 Clerk 驗證流程或其他登入測試。

## 驗收條件

| # | 條件 |
|---|---|
| AC1 | `get_current_clerk_user` 收到 `decoded=None` 的 credentials 時，測試要確認函式丟出 `AppError`，其 `error_code` 為 `UNAUTHENTICATED`、detail 為 `Invalid authentication credentials`，且 headers 為 `{"WWW-Authenticate": "Bearer"}`。 |
| AC2 | `get_current_clerk_user` 收到有效 decoded payload 時，既有測試仍確認函式原樣回傳 payload。 |
| AC3 | `get_current_clerk_user` 收到 `credentials=None` 時，既有測試仍確認函式丟出與 AC1 相同的認證錯誤。 |

## 不適用的情境

| 情境 | 原因 |
|---|---|
| 失敗資料、空資料、載入中、未登入／無權限、資料處理、外部系統狀態 | 本次只新增直接呼叫既有函式的單元測試，不改 HTTP、資料處理、外部服務或權限流程；未登入情況由既有 `credentials=None` 測試涵蓋。 |

## 實作計畫

1. 修改 `backend/tests/unit/test_security.py` 的 `get_current_clerk_user` 錯誤測試，使用 pytest parametrization 或等價的共用測試結構，同時覆蓋 `credentials=None` 與 `decoded=None`。
2. 使用 `HTTPAuthorizationCredentials(scheme="Bearer", credentials="x", decoded=None)` 建立空 payload 案例，並保留對 `error_code`、detail 與 `WWW-Authenticate` header 的完整斷言。
3. 執行後端 `pyright` 與 `pytest`，確認新增案例在修改前可重現缺口、修改後通過，且既有測試不受影響。

## 測試對應

| AC | 測試 | 改程式前是否失敗 |
|---|---|---|
| AC1 | `backend/tests/unit/test_security.py` 的 `get_current_clerk_user` 錯誤案例，加入 `decoded=None` 參數案例 | 錯誤實作時是；目前沒有該案例，若把條件改成只檢查 credentials，新增測試應攔截錯誤 |
| AC2 | `test_get_current_clerk_user_returns_decoded_payload_on_success` | 否 |
| AC3 | `test_get_current_clerk_user_raises_401_when_credentials_missing` | 否 |
| AC4 | 規格審查修正 AC3 用詞後，規格修改紀錄要記載該修正的內容、原因與確認者。 | 不適用；文件檢查 |
| AC5 | `get_current_clerk_user` 錯誤測試的 docstring 要描述 credentials 缺失與 decoded payload 缺失兩種情境，且不引用過時的驗收條件。 | 不適用；文件檢查 |

## 修改紀錄

| 日期 | 修改 | 原因 | 確認者 |
|---|---|---|---|
| 2026-11-17 | 建立規格草稿 | 依 #92 確認補足 `decoded=None` 的測試缺口 | 開發者 |
| 2026-11-17 | 修正 AC3 用詞並補記規格修改紀錄 | 規格審查確認例外是「丟出」而非「回傳」；檢查 AC1、AC2、AC3 與實作計畫、測試對應後僅需補記此項 | 開發者 |
| 2026-11-17 | 更新錯誤測試 docstring | 開發者決定在本 PR 處理實作審查建議；檢查 AC1、AC2、AC3 不需修改，新增 AC5 | 開發者 |

## 請你決定

無。
