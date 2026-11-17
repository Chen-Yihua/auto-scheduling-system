# Google OAuth token 回應非 JSON 時正確回報上游錯誤

- 狀態：已核准
- 等級：高風險（涉及外部 OAuth token 流程的可靠性與錯誤分類）
- issue：#85
- PR：尚未建立

## 簡短說明

修正 Google token endpoint 回 HTTP 200 但內容不是 JSON 時的錯誤處理，避免 OAuth callback 與換新 token 流程把解析例外回成未預期的 500。

## 背景

使用者在帳號設定連接 Google Calendar，授權後系統呼叫 `POST /oauth/callback`。目前 `backend/routers/google_calendar.py` 在 `res.raise_for_status()` 的 try/except 之外執行 `res.json()`；Google token endpoint 若回 HTTP 200 但內容是 HTML 等非 JSON，`res.json()` 會丟出未處理例外，系統回 `INTERNAL_ERROR`（500），使用者只看到連接失敗。

系統在 `backend/services/google_oauth.py` 的 `refresh_google_calendar_token` 也在處理連線錯誤與 HTTP 狀態錯誤的 try/except 內直接執行 `res.json()`，同樣可能將 HTTP 200 的非 JSON 回應變成未預期的 500。

HTTP 200 只表示 HTTP 層成功回應；OAuth token 交換還必須有可解析的 JSON 與必要的 `access_token`。ADR 0011 將外部服務回應無法解析或缺少必要內容分類為 `UPSTREAM_ERROR`，`backend/services/google_errors.py` 已提供固定 detail `UPSTREAM_DETAIL`，`backend/core/error_codes.py` 將其對應為 502。

## 需求

1. `/oauth/callback` 收到 HTTP 200 但無法解析為 JSON 的 Google token 回應時，丟出 `UPSTREAM_ERROR`，並使用既有固定 detail。
2. `refresh_google_calendar_token` 收到 HTTP 200 但無法解析為 JSON 的 Google token 回應時，丟出 `UPSTREAM_ERROR`，並使用既有固定 detail。
3. HTTP 200 且回應為 JSON object 並含非空 `access_token` 時，`refresh_google_calendar_token` 要回傳新的 access token、更新 access token；若沒有新的 `refresh_token`，要保留原本的 refresh token。
4. HTTP 200 但回應無法解析為 JSON、JSON payload 不是 object，或 object 缺少 `access_token` 時，OAuth callback 不得儲存 token，refresh token 流程不得更新或刪除既有 token。
5. 非 JSON 回應的原文不得出現在回給使用者的 detail。

## 不做

- 不修改 HTTP 200 且有效 token 回應的成功判定。
- 不修改 Google OAuth endpoint、請求參數、token 儲存格式或前端顯示流程。
- 不重新分類既有的 `invalid_grant`、設定錯誤、限流、逾時或連線錯誤。
- 不修改 HTTP 200 且 JSON object 含非空 `access_token` 的 OAuth callback 成功流程與 refresh token 成功流程。

## 驗收條件

| # | 條件 |
|---|---|
| AC1 | `/oauth/callback` 收到 Google HTTP 200 但非 JSON 的 token 回應時，系統要回 `UPSTREAM_ERROR`（HTTP 502）。 |
| AC2 | `refresh_google_calendar_token` 收到 Google HTTP 200 但非 JSON 的 token 回應時，系統要丟出 `ExternalServiceError`，其 `error_code` 為 `UPSTREAM_ERROR`，且狀態碼對應為 502。 |
| AC3 | `/oauth/callback` 與 `refresh_google_calendar_token` 收到 HTTP 200 但 JSON payload 不是 object 時，系統要以固定 `UPSTREAM_DETAIL` 回 `UPSTREAM_ERROR`（502）。 |
| AC4 | `/oauth/callback` 與 `refresh_google_calendar_token` 收到 HTTP 200 的 JSON object 但缺少 `access_token` 時，系統要以固定 `UPSTREAM_DETAIL` 回 `UPSTREAM_ERROR`（502）。 |
| AC5 | AC1 至 AC4 的錯誤 detail 要是固定的 `UPSTREAM_DETAIL`，不得包含 Google 回應原文。 |
| AC6 | AC1 至 AC4 的錯誤發生時，`/oauth/callback` 不得儲存 token，`refresh_google_calendar_token` 不得更新或刪除既有 token。 |
| AC7 | Google HTTP 200 回傳 JSON object 且含非空 `access_token` 時，`/oauth/callback` 要照既有流程儲存 token 並回授權成功。 |
| AC8 | Google HTTP 200 回傳 JSON object 且含非空 `access_token` 時，`refresh_google_calendar_token` 要回傳新的 access token、更新 access token；沒有新的 `refresh_token` 時要保留原本的 refresh token。 |
| AC9 | 既有非 200、連線錯誤、逾時、未登入或無權限行為不因本次修正改變。 |

## 不適用的情境

| 情境 | 原因 |
|---|---|
| 載入中、未登入或無權限的畫面行為 | 本次只處理已通過依賴驗證、已進入後端 Google token 呼叫的錯誤分類，不修改前端或認證流程。 |
| 資料一致性與併發 | 本次不改 token 資料模型、儲存時機或並行操作。 |

## 實作計畫

1. 在 `backend/routers/google_calendar.py` 將 Google token payload 限定為 JSON object，並將解析失敗、非 object、缺少非空 `access_token` 的回應轉成 `ExternalServiceError(UPSTREAM_DETAIL)`；確認錯誤路徑在儲存前結束，`save_google_calendar_token` 不會被呼叫。
2. 在 `backend/services/google_oauth.py` 對 refresh token response 套用相同的 payload 驗證與固定錯誤分類；確認解析或 payload 驗證失敗時在更新／刪除 token 前結束，`update_google_calendar_token` 與 `delete_google_calendar_token` 都不會被呼叫。
3. 保留兩個流程對有效 JSON object 與非空 `access_token` 的成功行為，並驗證 refresh 流程沒有新的 `refresh_token` 時保留原本的 refresh token。
4. 在 `backend/tests/unit/test_google_calendar_router.py` 新增 callback 的 HTTP 200 非 JSON 與非 object JSON 回應測試，確認 error code、502、固定 detail、不洩漏原文及未呼叫 token 儲存。
5. 在 `backend/tests/unit/test_google_oauth.py` 補上 refresh token 的 HTTP 200 非 JSON 與非 object JSON 回應測試，攔截並確認 `update_google_calendar_token`、`delete_google_calendar_token` 都未被呼叫；確認既有成功測試涵蓋 token 更新與保留 refresh token。
6. 執行後端 `pyright` 與 `pytest`。

未採用只在 router 層修正的方案，因為 refresh token 流程共用同一個 Google token endpoint 且已有相同根因；只修 callback 會留下同類未處理 500。

## 測試對應

| AC | 測試 | 改程式前是否失敗 |
|---|---|---|
| AC1 | `backend/tests/unit/test_google_calendar_router.py`：callback 收到 HTTP 200 非 JSON | 是 |
| AC2 | refresh token 對應 unit test：HTTP 200 非 JSON | 是 |
| AC3 | callback 與 refresh token 對應 unit test：HTTP 200 的 JSON array、string、`null` | 是 |
| AC4 | callback 與 refresh token 對應 unit test：HTTP 200 的 JSON object 缺少 `access_token` | 否 |
| AC5 | 上述錯誤測試檢查固定 detail 且不含回應原文 | 是 |
| AC6 | callback 錯誤測試攔截並斷言 `save_google_calendar_token` 未被呼叫；refresh 錯誤測試攔截並斷言 `update_google_calendar_token` 與 `delete_google_calendar_token` 都未被呼叫 | 是 |
| AC7 | `test_oauth_callback_happy_path_saves_token` | 否 |
| AC8 | `backend/tests/unit/test_google_oauth.py` 的 refresh token 成功測試 | 否 |
| AC9 | callback 與 refresh token 既有非 200、連線錯誤、逾時、認證與授權測試 | 否 |

## 修改紀錄

| 日期 | 修改 | 原因 | 確認者 |
|---|---|---|---|
| 2026-11-17 | 將 callback 與 refresh token 流程的 HTTP 200 非 JSON 回應納入修正範圍；明確保留 HTTP 200 且有效 token 的成功流程 | 開發者確認 Q1 納入、Q2 沿用，並釐清 HTTP 200 不等於 token payload 有效 | 開發者 |
| 2026-11-17 | 納入 refresh 成功流程、錯誤時 token 不更新，以及非 object JSON payload 的錯誤分類 | 開發者確認 Q1、Q2、Q3 採用；規格審查指出這些是 OAuth token 流程的一致性必要條件 | 開發者 |

## 請你決定

無
