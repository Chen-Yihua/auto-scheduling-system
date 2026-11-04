# google-calendar-reauth：審查第 2 輪

- 規格：[docs/specs/google-calendar-reauth.md](../specs/google-calendar-reauth.md)
- PR：#22
- 日期：2026-11-04
- 審查的版本：`2d9ca38`（`origin/main...HEAD`）
- 結果：沒有阻擋項目

## 審查報告

### 審查範圍與檢查

- `git diff 0db469d HEAD --stat`：0db469d 之後只改了 `docs/specs/google-calendar-reauth.md`（+6/-3），另外新增了 `docs/reviews/google-calendar-reauth-round1.md`；程式碼和測試都沒動。所以第 1 輪對實作和測試的結論都還成立，這一輪主要看規格同步。
- 本機跑了「完成的定義」的檢查，全部通過：
  - backend：`pyright` 0 errors，`pytest` 509 passed。
  - frontend：`npm run lint`、`npm run typecheck` 沒有錯誤，`vitest` 29 files / 273 tests passed。

### 規格同步

我把 `git diff origin/main...HEAD` 裡新增的測試，和規格 docs/specs/google-calendar-reauth.md:44-54 的「回歸測試」表逐一對過，每個新增的測試都對應到一條 AC：

| 新增的測試 | 規格的對應列 |
|---|---|
| frontend/tests/composables/useGoogleCalendar.test.ts:138 | AC1（docs/specs/google-calendar-reauth.md:46） |
| frontend/tests/components/GoogleCalendarEmbed.test.ts:42 | AC1（:46） |
| frontend/tests/components/Dashboard.test.ts:188 | AC1（:46，這輪補上） |
| backend/tests/unit/test_google_oauth.py:262 | AC2（:47） |
| backend/tests/unit/test_google_calendar_service.py:278、298、322 | AC2（:47） |
| backend/tests/integration/test_google_calendar_api.py:111 | AC2（:47） |
| backend/tests/integration/test_google_calendar_api.py:126 | AC2（:47，這輪補上 `/schedule/suggest`） |
| frontend/tests/composables/useGoogleCalendar.test.ts:173 | AC4（:49） |
| frontend/tests/composables/useGoogleCalendar.test.ts:194 | AC4（:50，這輪補上，標「否（保護用）」） |
| frontend/tests/composables/useSchedule.test.ts:124 | AC5（:51） |
| frontend/tests/composables/useGoogleCalendar.test.ts:207 | AC6（:52） |
| frontend/tests/composables/useGoogleCalendar.test.ts:224 | AC6（:53，這輪補上） |
| frontend/tests/components/GoogleCalendarEmbed.test.ts:53 | AC6（:54，這輪補上，標「否（保護用）」） |

- 「改程式前是否失敗」：新增的列填得合理。
  - :50、:54 是保護用的測試，標「否」。
  - :53 標「是」：改程式前沒有 `needsReconnect` 狀態，也沒有丟掉舊請求結果的邏輯。
- :54 的描述是「`connect=true` 時顯示行事曆，不顯示『授權已失效』」，和這個測試實際傳入的 props（`needsReconnect: false`）一致。測試名稱和內容對不上的問題，第 1 輪 #5 已經開成 issue #26。
- PR 欄位已經填 `#22`（docs/specs/google-calendar-reauth.md:5）。
- AC 本身沒改（`git diff 0db469d HEAD -- docs/specs/` 只動了 PR 欄位和回歸測試表），所以「修改紀錄」（docs/specs/google-calendar-reauth.md:65-67）不用新增。
- 第 1 輪紀錄最後一節的處理結果表，#1–#6 的處理方式和編號都填了。#6 對應的 commit 932a90e 和 `git log` 一致。

### 安全確認

〔已改寫〕本 PR 沒有帶進新的漏洞，GHSA-rvfq-623f-hwjf 的性質和範圍也沒有因為本 PR 改變。新增的 log 沒有記 token 明文（第 1 輪已確認，之後程式碼沒動）。

### 驗收條件

| AC | 結果 | 依據（檔案:行號） |
|---|---|---|
| AC1 | 通過 | frontend/composables/useGoogleCalendar.ts:83-86；frontend/composables/useGoogleCalendarAuth.ts:7-28；frontend/components/header/AccountSettings.vue:14；frontend/components/dashboard/GoogleCalendarEmbed.vue:45-50；frontend/components/dashboard/Dashboard.vue:77。測試：frontend/tests/composables/useGoogleCalendar.test.ts:138、frontend/tests/components/GoogleCalendarEmbed.test.ts:42、frontend/tests/components/Dashboard.test.ts:188 |
| AC2 | 通過 | (a) backend/services/google_oauth.py:67-70；(b) backend/services/google_calendar.py:49-54、backend/services/google_oauth.py:31-36；(c) backend/services/google_calendar.py:33-41、63。三條路徑都沒有呼叫 delete。測試：backend/tests/unit/test_google_oauth.py:262、backend/tests/unit/test_google_calendar_service.py:278、298、322、backend/tests/integration/test_google_calendar_api.py:111、126 |
| AC3 | 通過 | backend/services/google_oauth.py:59-66（invalid_grant）、71-74（invalid_client）、76，以及 backend/services/google_calendar.py:24-30（5xx/429）。測試：backend/tests/unit/test_google_oauth.py:64、240、251，frontend/tests/composables/useGoogleCalendar.test.ts:109、173。換新 token 後重試遇到 5xx 會回 500，這是 main 原本就有的行為，已開 issue #24 |
| AC4 | 通過 | frontend/composables/useGoogleCalendar.ts:98-112；測試 frontend/tests/composables/useGoogleCalendar.test.ts:173、194 |
| AC5 | 通過 | frontend/composables/useSchedule.ts:56-59；測試 frontend/tests/composables/useSchedule.test.ts:124 |
| AC6 | 通過 | frontend/composables/useGoogleCalendar.ts:31、47、53、68-71、76；測試 frontend/tests/composables/useGoogleCalendar.test.ts:207、224 |

### 發現

這一輪沒有新發現。第 1 輪各項的處理：
- #1：已建立 GHSA-rvfq-623f-hwjf。
- #2–#5：已開 issue #23–#26。
- #1–#5 都由開發者決定不在本 PR 處理。
- #6：已在 932a90e 修正，上面「規格同步」一節確認修正正確。

### 總結

0db469d 之後程式碼沒有變動，AC1–AC6 都通過，所有檢查也都通過。第 1 輪 #6（規格同步）已經正確補上，AC 沒改，所以不用寫修改紀錄。這一輪沒有阻擋項目。

## 處理結果

| # | 處理 | 決定者 | 根本原因 | commit / issue / advisory 編號 |
|---|---|---|---|---|
| — | 沒有發現，不用處理 | — | — | — |
