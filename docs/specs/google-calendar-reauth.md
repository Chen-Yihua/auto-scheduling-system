# Google Calendar 授權失效時跳兩個「稍後再試」toast，沒有引導重新連接

- 狀態：已核准
- issue：無（開發者直接回報）
- PR：（建立後填入）

## 現象
Google Calendar 的 token 失效、需要重新連接時，首頁同時跳出兩個 toast：「Google Calendar 資料暫時無法取得／伺服器暫時連不上 Google 或發生錯誤，請稍後再試一次」。使用者照著等、稍後再試，問題也不會好，因為實際上要重新連接 Google Calendar。

## 重現步驟
1. 登入，已連接 Google Calendar，但資料庫裡的 Google token 已經不能用，例如：refresh token 是別的 OAuth client 發的（正式和開發環境共用同一個 Atlas），或是用別把 `SECRET_ENCRYPTION_KEY` 加密的。
2. 打開首頁。

## 預期行為／實際行為
- 預期：只跳一個 toast，說 Google Calendar 授權已失效，toast 上有「重新連接」按鈕；行事曆卡片改成顯示「授權已失效，請重新連接」。
- 實際：跳兩個「稍後再試」的 toast；行事曆卡片顯示「尚未連接」。

## 原因
1. **兩個 toast**：首頁的 [Dashboard.vue:26](frontend/components/dashboard/Dashboard.vue#L26) 和 header 的 [AccountSettings.vue:11](frontend/components/header/AccountSettings.vue#L11) 掛載時都會呼叫 `fetchGoogleCalendars`。這是共用的 composable（[useGoogleCalendar.ts](frontend/composables/useGoogleCalendar.ts)），但兩次呼叫會各自發出請求，失敗時各自跳一個 toast。
2. **「稍後再試」而不是「重新連接」**：前端只有收到 401 才顯示重新連接（[useGoogleCalendar.ts:72](frontend/composables/useGoogleCalendar.ts#L72)）。後端只有在 Google 回 `invalid_grant`，或是 DB 裡沒有 refresh token 時才回 401（[google_oauth.py:31,53](backend/services/google_oauth.py#L53)）。開發者看到的是「資料暫時無法取得」，所以後端回的是 500 或 502。後端 log 已經看不到這次的錯誤，具體是哪一條路徑**待確認**。程式碼裡「token 不能用、卻不回 401」的路徑有三條：
   - Google 換新 token 時回 `invalid_grant` / `invalid_client` 以外的 4xx，例如 refresh token 是別的 client 發的時候回 `unauthorized_client`。現在一律當成暫時性錯誤，回 502（[google_oauth.py:65](backend/services/google_oauth.py#L65)）。
   - `decrypt_secret` 解不開 token，丟出 `ValueError`。這個例外沒被接住，回 500（[google_tokens.py:46,55](backend/crud/google_tokens.py#L46)）。
   - 換新 token 後重試行事曆列表，Google 還是回 401。這個 `HTTPStatusError` 在 except 區塊裡丟出、沒被接住，回 500（[google_calendar.py:48-49](backend/services/google_calendar.py#L48)）。

   這三條都改成回 401（`ReauthRequiredError`），但**不刪 DB 裡的 token**：正式環境共用同一個 DB，那份 token 在正式環境可能還能用。使用者重新連接時，`save_google_calendar_token` 會直接覆蓋。

## 驗收條件
| # | 條件 |
|---|---|
| AC1 | 照重現步驟操作時（後端因為 token 不能用而回 401），首頁只跳**一個** toast，標題「Google Calendar 授權已失效」，說明請使用者重新連接，toast 上有「重新連接 Google Calendar」按鈕，按下後導到 Google 授權頁（和帳號設定裡的按鈕一樣，用同一組 OAuth 參數）；行事曆卡片顯示「Google Calendar 授權已失效，請重新連接」，不顯示「尚未連接」 |
| AC2 | 後端 `/oauth/calendars` 和 `/schedule/suggest` 遇到下面三種情況時，回 401，`detail` 請使用者重新連接 Google Calendar，而且**不刪除** DB 裡的 token：(a) Google 換 token 時回 `unauthorized_client`；(b) 存的 access token 或 refresh token 解密失敗；(c) 換新 token 後重試行事曆列表，Google 還是回 401 |
| AC3 | 既有行為不變：Google 回 `invalid_grant` 時仍回 401 並刪除 token；回 `invalid_client` 時仍回 500「伺服器設定錯誤」；Google 5xx、429 或連不上時仍回 502；前端在這些暫時性錯誤時仍顯示「稍後再試」，而且只跳一個 toast |
| AC4 | 同一個頁面上，多個元件同時呼叫 `fetchGoogleCalendars`，而前一次還沒結束時，前端共用同一個請求：`/oauth/status`、`/oauth/calendars` 各只發一次，失敗時最多跳一個 toast |
| AC5 | 在排程頁產生排程建議時，如果後端回 401（Google 授權失效），toast 和 AC1 一樣，有「重新連接 Google Calendar」按鈕 |
| AC6 | 重新連接成功後（`connectedCount` 遞增、重新抓取成功），行事曆卡片恢復顯示行事曆，不再顯示「授權已失效」 |

## 不做
- **任務列表載入失敗**：開發者重現時看到的另一個錯誤，和 Google token 無關。這次不處理，實作完成後另外調查，再照規則開 issue。
- **Clerk 登入過期也回 401**：前端的 `isAuthError` 分不出是 Clerk 還是 Google 的 401，Clerk 過期時也會顯示「Google 授權已失效」。要改後端的錯誤格式（例如加 `error_code`），範圍較大，另開 issue。
- FreeBusy 或建立事件時才遇到 401（行事曆列表剛換新 token，很少發生），維持現在的處理方式。
- 自動刪除解不開或不屬於這個 client 的 token。

## 回歸測試
| AC | 測試 | 改程式前是否失敗 |
|---|---|---|
| AC1 | `frontend/tests/composables/useGoogleCalendar.test.ts`：401 時只跳一個 toast，toast 有重新連接按鈕，按下後導到 Google 授權網址；`needsReconnect` 為 true。`frontend/tests/components/GoogleCalendarEmbed.test.ts`：`needsReconnect` 時顯示「授權已失效」文字 | 是 |
| AC2 | `backend/tests/unit/test_google_oauth.py`：`unauthorized_client` → `ReauthRequiredError`，不呼叫 delete。`backend/tests/unit/test_google_calendar_service.py`：解密失敗 → `ReauthRequiredError`；換新後重試仍 401 → `ReauthRequiredError`。`backend/tests/integration/test_google_calendar_api.py`：`/oauth/calendars` 在 (a)(b)(c) 時回 401 | 是 |
| AC3 | 既有測試維持通過（`test_google_oauth.py` 的 invalid_grant、invalid_client、5xx 測試；`useGoogleCalendar.test.ts` 的「稍後再試」測試） | 否（保護既有行為） |
| AC4 | `useGoogleCalendar.test.ts`：兩次呼叫 `fetchGoogleCalendars` 卻不 await，`$fetch` 的 `/oauth/status`、`/oauth/calendars` 各只被呼叫一次，`toast.add` 最多一次 | 是 |
| AC5 | `frontend/tests/composables/useSchedule.test.ts`：suggest 回 401 時，toast 有重新連接按鈕 | 是 |
| AC6 | `useGoogleCalendar.test.ts`：先 401，再成功抓取，`needsReconnect` 變回 false、`isConnected` 為 true | 是 |

### 實作提示（給 implementer，不是驗收條件）
- 把 `AccountSettings.vue` 的 `goToGoogleAuth`（組 OAuth 網址）移到 composable（例如 `useGoogleCalendarAuth`），讓 toast 和帳號設定共用同一個函式。
- 在 `useGoogleCalendar` 裡，執行中的 `fetchGoogleCalendars` 用一個共用的 promise 表示，同時間的呼叫都等這個 promise，不另外發請求。
- `GoogleCalendarEmbed` 的 props 加上 `needsReconnect`，由 `Dashboard.vue` 傳入。
- 後端：解密的 `ValueError` 在 `services/google_calendar.py`（讀 access token）和 `services/google_oauth.py`（讀 refresh token）轉成 `ReauthRequiredError`，不要在 `core/crypto.py` 做，其他平台的金鑰也會用到它。
- 文件：`docs/api.md` 如有記錄 `/oauth/calendars`、`/schedule/suggest` 的錯誤碼，補上 401 的這些情況。

## 修改紀錄
| 日期 | 修改 | 原因 | 確認者 |
|---|---|---|---|
