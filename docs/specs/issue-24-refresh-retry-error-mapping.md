# 換新 Google token 後重試行事曆列表的錯誤分類

- 狀態：已核准
- 等級：輕量（只在 Google Calendar 這個功能範圍內的 bug：改一個 service 函式的錯誤分類與它的測試，只改變失敗時回的狀態碼。不碰資料一致性：除了換新 token 時寫回的新 token（修正前後相同），例外在其他寫資料庫、刪任務之前就丟出；不碰認證與授權：401 → 重新連接的判斷不變）
- issue：[#24](https://github.com/Chen-Yihua/auto-scheduling-system/issues/24)
- PR：[#60](https://github.com/Chen-Yihua/auto-scheduling-system/pull/60)

## 背景

**現象**：使用者打開行事曆、產生或確認排程、刪除有排進行事曆的任務時，後端發現 Google access token 過期，換新 token 後重試抓行事曆列表。重試時如果 Google 剛好回 5xx、429，或連不上，後端回 500，而不是第一次請求遇到同樣情況時的 502。使用者看到的都是「稍後再試」，沒有差別；但開發者（維運者）看 log 和監控時，外部服務的暫時失敗會被分類成程式錯誤（全域 handler 記成未預期的例外），造成誤判。

**重現步驟**：
1. 使用者存的 access token 已過期，第一次抓行事曆列表時 Google 回 401。
2. 後端用 refresh token 換新 token 成功。
3. 用新 token 重試抓行事曆列表時，Google 回 503（或 429，或連線失敗）。

**預期**：API 回 502，和第一次請求遇到同樣錯誤時一樣。
**實際**：API 回 500。

**原因**：
- `backend/services/google_calendar.py:43-51` 的 `_fetch_calendar_list_after_refresh` 只處理 401（轉成 `ReauthRequiredError`），其他 `HTTPStatusError` 原樣 `raise`，`RequestError` 完全沒接。
- 它是在 `_get_access_token_and_calendars`（`:68-78`）的 `except httpx.HTTPStatusError` 區塊裡被呼叫的；在 except 區塊裡丟出的例外，同一個 try 的其他 except（`:76` 的 `RequestError`）接不到，所以原始的 httpx 例外一路往上，由 `core/exception_handlers.py` 的兜底回 500。
- 第一次請求的同類錯誤由 `:75` 的 `_google_error`（5xx／429 → `ExternalServiceError` 502，其他 4xx → `InvalidRequestError` 400）和 `:76-78`（連不上 → 502）處理。

**影響的 endpoint**（都經過 `_get_access_token_and_calendars`）：`GET /oauth/calendars`、`/schedule/suggest`（含 `get_calendar_event_ends`）、`/schedule/confirm`、`DELETE /manual-tasks/{task_id}`（任務有行事曆事件時）。`main` 上原本就是這樣。

## 需求

換新 token 後重試行事曆列表時，Google 回 5xx／429 或連不上，和第一次請求一樣回 502；仍回 401 時照舊請使用者重新連接。

## 不做

- 不改第一次請求、FreeBusy、寫入事件、刪除事件各自的錯誤處理。
- 不改換新 token 本身（`refresh_google_calendar_token`）的錯誤處理：它已經把連不上轉成 502、`invalid_grant` 轉成重新連接。
- 不改重試遇到 401 以外的 4xx（例如 403）時的行為，照舊回 500。照第一次請求的規則改成 400 的話，前端會把 400 當成「還沒連接 Google Calendar」（`frontend/utils/errorMessages.ts` 的 `isNotLinkedError`），使用者已經連接卻看到未連接；Google 也可能用 403 回報限流。這兩件事都和 4xx 怎麼分類有關，另開 [#59](https://github.com/Chen-Yihua/auto-scheduling-system/issues/59) 處理（開發者決定）。
- 不改 `DELETE /manual-tasks/{task_id}` 的錯誤訊息：第一次請求失敗時本來就用 `_google_error` 的訊息，不是刪除專用的 `DELETE_RETRY_DETAIL`，這次維持一致。

## 驗收條件

| # | 條件 |
|---|---|
| AC1 | 換新 token 後重試行事曆列表，Google 回 5xx（例如 500、503）或 429 時，丟出 `ExternalServiceError`（API 回 502），不是未處理的例外（500） |
| AC2 | 換新 token 後重試行事曆列表時連不上 Google（連線錯誤、逾時），丟出 `ExternalServiceError`（API 回 502） |
| AC3 | 換新 token 後重試行事曆列表，Google 回 401 以外的 4xx（例如 403）時，照舊丟出原本的 `httpx.HTTPStatusError`（API 回 500），不轉成 `InvalidRequestError`（400） |
| AC4 | 換新 token 後重試仍回 401 時，照舊丟出 `ReauthRequiredError`（API 回 401 請使用者重新連接）；重試成功時照舊用新 token 繼續（保護既有行為） |

## 不適用的情境

| 情境 | 原因 |
|---|---|
| 空資料 | 行事曆列表為空、沒有 primary 的處理不經過這次改的分支，行為不變 |
| 載入中 | 沒有改前端；這次只會出現 500 → 502 的改變，前端對 500、502 都顯示「稍後再試」（4xx 照舊 500，見 AC3） |
| 未登入／無權限 | 登入驗證在 router 之前，沒有改；Google 的授權失效（401）由 AC4 涵蓋 |
| 資料處理 | 除了換新 token 時寫回的新 token（`refresh_google_calendar_token` 在重試前就寫入，修正前後相同），例外在其他寫資料庫或刪任務之前丟出；`DELETE /manual-tasks/{task_id}` 的「先刪事件、成功才刪任務」順序不變 |
| 安全性 | 不碰憑證；log 沿用 `_google_error` 既有的寫法（記錄狀態碼與 Google 回應內容），不新增記錄 token 的地方 |

## 實作計畫

1. 分支 `issue-24-refresh-retry-error-mapping`。
2. `backend/services/google_calendar.py` 的 `_fetch_calendar_list_after_refresh`：
   - `HTTPStatusError` 是 5xx 或 429 時，`raise _google_error(e, "取得行事曆列表失敗")`（和 `:75` 相同的訊息，回 502）；其他非 401 的 4xx 照舊 `raise`。在這個分支寫一行註解說明為什麼不交給 `_google_error`（它回 400，前端會當成未連接），附上 #59，避免之後被「簡化」成全部交給 `_google_error`。
   - 加上 `except httpx.RequestError`：記 log 後 `raise ExternalServiceError("無法連線至 Google，請稍後再試")`（和 `:76-78` 相同）。
   - 為什麼在這裡修，不在 `_get_access_token_and_calendars` 外層多包一層：在 except 區塊裡丟出的例外，同一個 try 的其他 except 接不到；在重試函式自己分類，和第一次請求的寫法對稱，也不必調整外層 try 的結構。
3. 測試加在 `backend/tests/unit/test_google_calendar_service.py`（模組 docstring 寫明 token 換新與錯誤處理透過 `get_free_slots_for_user` 測），沿用既有的 `_unauthorized_error()` 與 mock 方式：第一次抓列表回 401，`refresh_google_calendar_token` mock 成回傳新 token，第二次抓列表依情境丟錯。
4. 不用改 `docs/api.md`（沒有改 endpoint、路徑、登入需求、限流）、`frontend/types/`（沒有改回應格式）。

## 測試對應

| AC | 測試 | 改程式前是否失敗 |
|---|---|---|
| AC1 | `test_get_free_slots_maps_retry_errors_after_token_refresh`（parametrize 500、503、429 → `ExternalServiceError`），並確認第二次抓列表用的是新 token | 是（修正前丟出原始的 `httpx.HTTPStatusError`） |
| AC2 | 同一個 parametrize 加 `httpx.ConnectError`、`httpx.ReadTimeout` → `ExternalServiceError` | 是（修正前丟出原始的 `httpx.RequestError`） |
| AC3 | 同一個 parametrize 加 403 → 原始的 `httpx.HTTPStatusError` | 否（保護既有行為：防止實作把所有非 401 的錯誤都交給 `_google_error`） |
| AC4 | 既有的 `test_get_free_slots_requires_reauth_when_calendar_list_still_401_after_refresh`、`test_get_free_slots_refreshes_token_on_401` | 否（保護既有行為） |

## 修改紀錄

| 日期 | 修改 | 原因 | 確認者 |
|---|---|---|---|
| 2026-11-08 | 「不做」與實作計畫 2 補上 4xx 分類另開的 issue 編號 #59 | 核准時說明會另開 issue，建立後補上編號；AC、需求、測試對應都不用改 | 開發者（核准時決定另開 issue） |
