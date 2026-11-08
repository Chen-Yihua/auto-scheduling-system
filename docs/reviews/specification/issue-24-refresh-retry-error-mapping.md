# 換新 Google token 後重試行事曆列表的錯誤分類：規格審查紀錄

- 規格：[docs/specs/issue-24-refresh-retry-error-mapping.md](../../specs/issue-24-refresh-retry-error-mapping.md)
- PR：[#60](https://github.com/Chen-Yihua/auto-scheduling-system/pull/60)
- 等級：輕量
- 輪數：1（第 1 輪 2026-11-08 草稿）
- 最終結果：沒有阻擋項目（#1 由開發者選定，#2 已修正）

## 摘要

- 發現：3 項（Specification Defect 1、Factual Error 1、Improvement Suggestion 1；Minor 2、Info 1）
- 開發者決策：1 項（#1）
- 尚未處理：0 項（#3 併入 #59）

## 各輪摘要

| 輪 | 日期／commit | 新發現（阻擋） | 這一輪之後改了什麼 |
|---|---|---|---|
| 1 | 2026-11-08 草稿 | #1–#3（#1、#2） | 拿掉「重試的 4xx 回 400」的假設，AC3 改寫成 4xx 照舊回 500；修正「修正前後都不寫入」的敘述；4xx 分類另開 #59 |

## 發現與處理

| # | 輪 | 標題 | 類型 | 嚴重程度 | 阻擋合併 | 涉及安全／架構 | 根本原因 | 處理 | 決定者 | 結果 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1 | 原 AC3（重試的 4xx 回 400）會讓前端把已連接的使用者顯示成「尚未連接」，規格沒寫到 | Specification Defect | Minor | 是 | 否 | 4xx 的前端影響沒評估 | 選 B：這次只修 5xx／429 與連線錯誤，4xx 照舊 500（AC3 改寫），4xx 分類另開 issue | 開發者 | 規格已修改；[#59](https://github.com/Chen-Yihua/auto-scheduling-system/issues/59) |
| 2 | 1 | 「修正前後都不寫入」不精確：重試前已把新 token 寫回資料庫 | Factual Error | Minor | 是 | 否 | — | 等級理由與「資料處理」改寫成「除了換新 token 時寫回的新 token」 | 主 session（依查證依據，不改變行為） | 規格已修改 |
| 3 | 1 | Google 用 403 回報限流時，`_google_error` 一律回 400（main 上原本就是這樣） | Improvement Suggestion | Info | 否 | 否 | — | 和 #1 同樣是 4xx 分類的問題，併進同一個 issue | 開發者（選 B 時一併決定） | [#59](https://github.com/Chen-Yihua/auto-scheduling-system/issues/59) |

## 問題說明

### #1 重試的 4xx 改成 400 的前端影響

- 問題：草稿假設重試遇到非 401 的 4xx 時回 400，和第一次請求一樣。但前端的 `isNotLinkedError` 把 400 當成「還沒連接」（`frontend/utils/errorMessages.ts:32-34`）：`useGoogleCalendar.ts:81` 不跳錯誤、直接顯示未連接，`useSchedule.ts:51` 進入「尚未連接」狀態。修正前這個情境是 500，顯示「稍後再試」。
- 影響：已經連接的使用者，在這個少見的情境下會看到「尚未連接」。

## 開發者決策

| # | 問題 | 選項 | 開發者的決定 | 理由 |
|---|---|---|---|---|
| 1 | 換新 token 後重試遇到非 401 的 4xx 要怎麼處理 | A：回 400，和第一次請求對齊，接受前端顯示「未連接」；B：這次只修 5xx／429 與連線錯誤，4xx 照舊 500，另開 issue | B | 不把「錯誤顯示成未連接」擴大到新的情境；4xx 分類和 403 限流一起在 #59 處理 |

## 尚未處理

無

## 未經審查的驗收條件

| AC | 改了什麼 |
|---|---|
| AC3 | 從「重試的 4xx 丟出 `InvalidRequestError`（400）」改成「照舊丟出原本的 `httpx.HTTPStatusError`（500），不轉成 400」；測試對應改成保護既有行為 |

## 查證紀錄

| 規格中的事實 | 結果 | 依據（檔案:行號） |
|---|---|---|
| 背景：`_fetch_calendar_list_after_refresh` 只把 401 轉成 `ReauthRequiredError`，其他 `HTTPStatusError` 原樣 raise，沒接 `RequestError` | 正確 | `backend/services/google_calendar.py:43-51` |
| 背景：重試在 `_get_access_token_and_calendars` 的 `except HTTPStatusError` 裡呼叫，`:76` 的 `except RequestError` 接不到 | 正確 | `backend/services/google_calendar.py:68-78`（呼叫在 :73） |
| 背景：沒處理的例外由兜底回 500，記成未預期的例外 | 正確 | `backend/core/exception_handlers.py:77-82` |
| 背景：第一次請求 5xx／429 回 502、其他 4xx 回 400、連不上回 502 | 正確 | `backend/services/google_calendar.py:34-40`、`:75-78`；`backend/core/exception_handlers.py:26`、`:32` |
| 背景：影響的 endpoint | 正確 | `backend/routers/google_calendar.py:68-70`；`backend/routers/schedule.py:95-97`、`:159-164`；`backend/routers/manual_task.py:273-294` |
| 背景：使用者在 500 和 502 時都看到「稍後再試」 | 正確（400 的情況見 #1） | `frontend/composables/useGoogleCalendar.ts:83-93`；`frontend/composables/useSchedule.ts`；`frontend/composables/useTaskForm.ts:177-184` |
| 不做：換新 token 已把連不上轉成 502、`invalid_grant` 轉成重新連接 | 正確 | `backend/services/google_oauth.py:54-66` |
| 不做：DELETE 第一次請求失敗時用 `_google_error` 的訊息 | 正確 | `backend/services/google_calendar.py:75`、`:226` |
| AC4：重試仍 401 時丟 `ReauthRequiredError`；重試成功時用新 token | 正確（既有測試通過） | `backend/services/google_calendar.py:48-50`；`backend/tests/unit/test_google_calendar_service.py:54-89`、`:322-342` |
| 資料處理：換新 token 在重試前寫回資料庫 | 正確（第 1 輪修正後） | `backend/services/google_oauth.py:84-86` |
| DELETE 先刪事件、成功才刪任務 | 正確 | `backend/routers/manual_task.py:286-299` |
| `httpx.ConnectError`、`httpx.ReadTimeout` 都是 `httpx.RequestError` 的子類 | 正確 | 實際執行確認 |
| `fetch_google_calendar_list` 不接 httpx 例外 | 正確 | `backend/services/google_calendar_client.py:8-14` |

## 已接受的風險

- 「不做」列出的範圍（第一次請求、FreeBusy、寫入／刪除事件、換新 token 本身的錯誤處理，以及 DELETE 的錯誤訊息）不在這次範圍。
- 重試遇到非 401 的 4xx 照舊回 500，log 仍記成未預期的例外，直到 #59 處理。
