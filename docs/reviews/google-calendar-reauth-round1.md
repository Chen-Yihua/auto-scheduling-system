# google-calendar-reauth：審查第 1 輪

- 規格：[docs/specs/google-calendar-reauth.md](../specs/google-calendar-reauth.md)
- PR：#22
- 日期：2026-11-04
- 審查的版本：`0db469d`（`origin/main...HEAD`）
- 結果：有阻擋（漏洞 1；不阻擋：Improvement Suggestion 4、Test Gap 1）

## 審查報告

我在本機跑了「完成的定義」的檢查，全部通過：
- backend：`pyright` 0 errors，`pytest` 509 passed。
- frontend：`npm run lint`、`npm run typecheck` 沒有錯誤，`vitest` 29 files / 273 tests passed。

連動檢查：
- `docs/api.md` 沒有逐一列出各 endpoint 的錯誤碼，只有 docs/api.md:54、docs/api.md:69 兩行列出 endpoint，所以不用同步。
- 這次沒有改 `backend/schemas/`，不用連動 `frontend/types/`。
- 沒有新增服務或 collection，不用連動 `docs/architecture.md`。

### 驗收條件

| AC | 結果 | 依據（檔案:行號） |
|---|---|---|
| AC1 | 通過 | 收到 401 時設 `needsReconnect`、只跳一個 toast：frontend/composables/useGoogleCalendar.ts:83-86。toast 內容和按鈕：frontend/composables/useGoogleCalendarAuth.ts:22-28。OAuth 參數從 AccountSettings 搬過來、內容沒變：frontend/composables/useGoogleCalendarAuth.ts:8-20，AccountSettings 改用共用函式：frontend/components/header/AccountSettings.vue:14。卡片文字：frontend/components/dashboard/GoogleCalendarEmbed.vue:45-50，Dashboard 傳入 prop：frontend/components/dashboard/Dashboard.vue:77。測試：frontend/tests/composables/useGoogleCalendar.test.ts:138、frontend/tests/components/GoogleCalendarEmbed.test.ts:42、frontend/tests/components/Dashboard.test.ts:188 |
| AC2 | 通過 | (a) backend/services/google_oauth.py:67-70；(b) backend/services/google_calendar.py:49-54、backend/services/google_oauth.py:31-36；(c) backend/services/google_calendar.py:33-41、63。三條路徑都沒有呼叫 delete。測試：backend/tests/unit/test_google_oauth.py:262、backend/tests/unit/test_google_calendar_service.py:278、298、322、backend/tests/integration/test_google_calendar_api.py:111（/oauth/calendars）、126（/schedule/suggest） |
| AC3 | 通過 | invalid_grant 仍刪 token 並回 401：backend/services/google_oauth.py:59-66。invalid_client 仍回 500：backend/services/google_oauth.py:71-74。5xx/429 仍回 502：backend/services/google_oauth.py:76、backend/services/google_calendar.py:24-30。既有測試 backend/tests/unit/test_google_oauth.py:64、240、251 仍通過。前端遇到暫時性錯誤仍顯示「稍後再試」，而且只跳一次：frontend/tests/composables/useGoogleCalendar.test.ts:121、173-192。注意：換新 token 後重試時遇到 5xx 會回 500（見發現 #3），main 上原本就是這樣，不是本 PR 造成的退化 |
| AC4 | 通過 | 共用 in-flight promise：frontend/composables/useGoogleCalendar.ts:98-112。測試 frontend/tests/composables/useGoogleCalendar.test.ts:173 有計算 `/oauth/status`、`/oauth/calendars` 的呼叫次數，如果改成每次都發請求，這個測試會失敗 |
| AC5 | 通過 | frontend/composables/useSchedule.ts:56-59；測試 frontend/tests/composables/useSchedule.test.ts:124 |
| AC6 | 通過 | 成功時重設 `needsReconnect`：frontend/composables/useGoogleCalendar.ts:68-71。重新連接前發出的舊請求晚回來時，不會寫回狀態：frontend/composables/useGoogleCalendar.ts:31、47、53、68、76。測試 frontend/tests/composables/useGoogleCalendar.test.ts:207、224 |

### implementer 回報的規格外調整

1. **重新連接後不共用舊請求，舊請求晚回來的結果丟掉、不跳 toast**：合理。要同時滿足 AC4（共用請求）和 AC6（重新連接後顯示新結果），就需要這個細節；如果重新連接後還共用舊請求，AC6 會被破壞。frontend/tests/composables/useGoogleCalendar.test.ts:224 有測到。不用新增 AC，但建議在規格「回歸測試」表的 AC6 欄補上這個測試（見發現 #6）。
2. **toast description 改成「…請重新連接 Google Calendar」**：符合 AC1「說明請使用者重新連接」。舊文案「重新點擊『連接 Google Calendar』」和新按鈕的名稱對不上，改了比較好。不用補 AC。
3. **補 useRuntimeConfig / useState 的 stub**：只是測試環境需要，合理。
4. **補 /schedule/suggest 的 integration 測試、Dashboard 傳 prop 的測試**：分別對應 AC2（規格寫的是 `/oauth/calendars` 和 `/schedule/suggest`）和 AC1（卡片顯示），沒有超出 AC 範圍。只是規格的「回歸測試」表還沒列出，見發現 #6。

### 發現

| # | 分類 | 阻擋 | 涉及安全／架構 | 說明 | 依據（檔案:行號） | 建議 |
|---|---|---|---|---|---|---|
| 1 | Improvement Suggestion | 是（標成漏洞一律阻擋） | 漏洞（main 已有） | 〔已改寫〕main 上原本就有的程式有一項可被利用的漏洞，不是本 PR 造成的。細節只回報給開發者，等開發者決定處理方式。 | 〔不公開〕 | 〔不公開〕 |
| 2 | Improvement Suggestion | 否 | 否 | 先遇到 401（`needsReconnect=true`），之後重新抓取時遇到暫時性錯誤（502、500、網路錯誤），或 `/oauth/status` 檢查失敗時，`needsReconnect` 不會重設：卡片繼續顯示「授權已失效」，toast 卻是「稍後再試」，兩邊的訊息互相矛盾。只有在成功，或 status 回 `connected:false` 時才會重設。影響的是授權失效後、第一次重試剛好碰上 Google 暫時性錯誤的使用者。不過這時授權也還沒確認恢復，維持「授權已失效」也說得通，屬於規格沒有定義的產品行為 | frontend/composables/useGoogleCalendar.ts:45-50、76-92 | 請開發者決定暫時性錯誤時卡片要顯示什麼（維持「授權已失效」，或改回一般錯誤狀態），決定後補一條 AC 和測試 |
| 3 | Improvement Suggestion | 否 | 否 | 換新 token 後重試行事曆列表時，如果 Google 回 5xx、429 或連不上，例外是在 except 區塊裡丟出的，同一個 try 的其他 except 接不到，所以回 500，不是 502。main 上原本就是這樣（`git show origin/main:backend/services/google_calendar.py` 第 46-49 行），本 PR 只處理了 401。前端兩種狀況都顯示「稍後再試」，使用者看到的一樣；影響的是 log 和監控的分類，而且 500 會讓人誤以為是程式錯誤 | backend/services/google_calendar.py:33-41（不是 401 就直接 `raise`）、61-67 | 在 `_fetch_calendar_list_after_refresh` 裡，其他 `HTTPStatusError` 交給 `_google_error`，`RequestError` 轉成 `ExternalServiceError`，並補一個「換新後重試遇到 5xx 回 502」的 unit 測試 |
| 4 | Improvement Suggestion | 否 | 否 | `/schedule/confirm` 也走 `_get_access_token_and_calendars`，所以 AC2 的三種情況現在也會回 401。但前端 `confirmSchedule` 沒有處理 401，仍跳「確認排程失敗／稍後再試」，沒有重新連接按鈕。通常產生建議時就會先碰到 401（AC5），實際上很少發生；規格的「不做」只排除了 FreeBusy 和建立事件時的 401 | frontend/composables/useSchedule.ts:118-123、backend/services/google_calendar.py:127 | `confirmSchedule` 收到 401 時也用 `reauthToast()`，或在規格的「不做」寫明不處理的原因 |
| 5 | Test Gap | 否 | 否 | GoogleCalendarEmbed 的 AC6 測試，名稱寫「即使 needsReconnect 還沒更新也顯示行事曆」，傳入的卻是 `needsReconnect: false`，沒有測到 `connect=true` 和 `needsReconnect=true` 同時成立時要顯示 iframe。把 `needsReconnect` 分支移到 `connect` 前面的錯誤實作也會通過。AC6 的主要行為已經有 composable 測試 frontend/tests/composables/useGoogleCalendar.test.ts:207 涵蓋，所以不阻擋 | frontend/tests/components/GoogleCalendarEmbed.test.ts:53-61 | props 改成 `connect: true, needsReconnect: true`，測試內容才和名稱一致 |
| 6 | Improvement Suggestion | 否 | 否 | 規格同步：(a) 「回歸測試」表沒有列出新增的測試：frontend/tests/components/Dashboard.test.ts:188（AC1）、frontend/tests/composables/useGoogleCalendar.test.ts:194（AC4，前一次結束後重發）、224（AC6，舊請求不覆蓋）、backend/tests/integration/test_google_calendar_api.py:126（AC2，/schedule/suggest）、frontend/tests/components/GoogleCalendarEmbed.test.ts:53；(b) 規格開頭的「PR」欄位還是「（建立後填入）」，應該填 #22。AC 本身沒有改，所以「修改紀錄」不用新增 | docs/specs/google-calendar-reauth.md:5、48-55 | 補上回歸測試表和 PR 編號 |

### 其他確認過、沒有問題的項目

- 解密失敗的 `ValueError` 在 service 層接住，沒有改 `core/crypto.py`，符合規格的實作提示：backend/services/google_calendar.py:49-54、backend/services/google_oauth.py:31-36。
- 新增的 log 只記 clerk_id 和 Google 錯誤回應的內容，沒有記 token 明文：backend/services/google_oauth.py:35、69，backend/services/google_calendar.py:39、53。
- 註解寫的都是原因（例如「不刪 token：…共用 DB」），符合 CLAUDE.md。
- 測試都對應到 AC，沒有為了覆蓋率而寫的測試。

### 總結

六條 AC 都通過，實作和規格一致。唯一阻擋的是 #1：main 上原本就有的漏洞〔細節已改寫〕。照規則，標成漏洞就要阻擋；但它不是本 PR 造成的，處理方式由開發者決定。#2–#6 都不阻擋，其中 #2 需要開發者決定產品行為。

## 處理結果

| # | 處理 | 決定者 | 根本原因 | commit / issue / advisory 編號 |
|---|---|---|---|---|
| 1 | 建立 private security advisory（草稿），不在本 PR 修 | 開發者 | main 既有漏洞 | GHSA-rvfq-623f-hwjf |
| 2 | 開 issue | 規則 | — | #23 |
| 3 | 開 issue | 規則 | — | #24 |
| 4 | 開 issue | 規則 | — | #25 |
| 5 | 開 issue | 規則 | — | #26 |
| 6 | 在本 PR 補規格的回歸測試表與 PR 編號 | 開發者 | — | 932a90e |
