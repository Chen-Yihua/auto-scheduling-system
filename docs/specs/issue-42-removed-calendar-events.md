# 在 Google 日曆刪掉事件後，讓使用者選擇重新排程或刪除任務

- 狀態：部分被 [標題列改成首頁、任務管理、排程、分析 4 個頁面](issue-178-nav-pages.md) 取代（AC26）
- 等級：高風險（改變和 Google 日曆同步的一致性：系統要依 Google 的回應清掉任務存的 Google 日曆事件編號、刪除 Google 上的事件或刪除任務，判斷錯會重複排入或誤刪）
- issue：[#42](https://github.com/Chen-Yihua/auto-scheduling-system/issues/42)
- PR：#124

## 簡短說明

使用者在 Google 日曆刪掉系統排入的事件後，進入排程精靈時，系統列出這些任務，讓使用者勾選要重新排程的；沒勾的手動任務從系統刪除。進入排程精靈前，先確認使用者已連接 Google 日曆。

## 背景

本規格的「Google 日曆事件編號」指任務上的 `calendar_event_id`：確認排程時系統把任務寫進 Google 日曆，Google 回傳這個事件的編號，系統存在任務上。有這個編號的任務就是「已排入」。

**重現步驟**

1. 建立一個手動任務，產生排程並確認，任務寫入 Google 日曆。
2. 在 Google 日曆刪掉這個事件。
3. 回首頁按「重新產生」，進入排程精靈。

**預期**：這個任務可以重新排程。**實際**：精靈第一步不列出它，產生排程也不會排它，系統裡沒有地方能改回來。

**原因**

- 確認排程後，任務存下 Google 日曆事件編號（`backend/services/google_calendar.py` 的 `create_calendar_events_for_scheduled_tasks` → `backend/crud/schedulable_items.py:203-210`）。之後系統沒有任何地方會查這個事件還在不在，也沒有地方會清掉這個編號。
- 有編號的任務一律當成「已排入」：
  - 精靈第一步不列出（`frontend/composables/useScheduleWizard.ts:73`）。
  - 後端排程跳過（`backend/services/scheduler.py:217-220`）。
  - 確認排程時擋下，原因寫「任務已經排入行事曆」（`scheduler.py:372-374`）。
  - 不能拆成階段（`backend/routers/manual_task.py:204-205`）。
- 唯一會查單一事件的地方，是階段任務排程時查前一個階段的結束時間（`get_calendar_event_ends`，`google_calendar.py:201-222`）：404、410 或狀態 `cancelled` 當成事件不存在，只讓後面的階段不受先後限制，前一個階段本身不重新排（[staged-tasks](staged-tasks.md) AC24）。這個函式遇到 401 會回 502 `UPSTREAM_ERROR`、沒有連接時回 409 `NOT_LINKED`（`google_calendar.py:78-79,214-218`；`backend/services/google_errors.py:36-46`）。
- 外部平台項目（GitHub、Jira、Moodle）也存 Google 日曆事件編號，走同一套排程與確認規則（`schedulable_items.py:73-95`）。

**同一類的情況**：刪除階段時，Google 上的事件已刪，但資料庫刪除失敗或回 409 `REQUEST_IN_PROGRESS`，階段留下來，編號指向已刪除的事件（`backend/routers/manual_task.py:315-329` 的 docstring）。這次的修正一起解決。

**相關的既有行為**

- 進入排程精靈的入口：首頁「排程建議」卡片的「產生排程建議」「重新產生」按鈕，導到 `/schedule`（`frontend/components/tasks/ScheduleSuggestion.vue:10-12,48-63`）。按鈕現在不檢查有沒有連接 Google；沒連接時，要到精靈最後產生建議，卡片才顯示「尚未連接 Google Calendar，請前往 帳號設定 連接。」（`ScheduleSuggestion.vue:72-75`）。
- 刪除任務（[issue-30](issue-30-delete-calendar-events.md)）：只刪那個任務和它自己在 Google 上的事件，不管事件時間與完成狀態；刪掉主任務唯一的子任務時，整個主任務一起刪（`backend/routers/manual_task.py:341-382`）。後面的階段編號往前遞補。
- 排程時，後面的階段一定排在前一個階段之後（staged-tasks AC21；`scheduler.py:262-273,327-339`）。
- 精靈載入任務清單用 `GET /schedule/tasks`（`frontend/composables/useSchedulableTasks.ts`），步驟定義在 `frontend/pages/schedule.vue:45-49`。
- 頁面自動查詢的結果顯示在畫面上，不跳 toast；toast 只留給使用者的操作（[issue-104](issue-104-calendar-card-states.md)）。現有的重新連接提示 toast 是 `reauthToast`（`frontend/composables/useGoogleCalendarAuth.ts:23-29`）。
- 錯誤狀態碼照 ADR 0002：授權失效 409 `REAUTH_REQUIRED`；Google 限流 503 `UPSTREAM_RATE_LIMITED`；Google 逾時 504 `UPSTREAM_TIMEOUT`；沒有主要行事曆 409 `NO_PRIMARY_CALENDAR`；Google 其他問題 502 `UPSTREAM_ERROR`；Google 回 400（系統送錯請求）500 `INTERNAL_ERROR`（`google_errors.py:36-66`、`google_calendar.py:104-106`、`backend/core/error_codes.py`）。
- 修改任務（`PUT /manual-tasks/{id}`）、調整截止日與時長（`PATCH /schedule/tasks/fields`）、標記完成（`PATCH /schedule/tasks/done`）都先讀出整筆任務、改完再整筆寫回（`update_manual_task_by_id`，`backend/crud/manual_task.py:462-470`；呼叫端 `backend/routers/manual_task.py:278-293`、`schedulable_items.py:163-171,186-193`），寫回的內容包含讀取當時的 Google 日曆事件編號。

## 需求

**進入排程精靈前**

1. 使用者按「產生排程建議」或「重新產生」時，前端先確認 Google 日曆的連接狀態。
2. 已連接：進入排程精靈。
3. 沒連接或授權已失效：不進入精靈，排程建議卡片顯示「Google Calendar 未連接或授權已失效，請前往 **帳號設定** 連接。」。卡片原本在產生建議回 `NOT_LINKED` 時顯示的「尚未連接 Google Calendar，請前往 帳號設定 連接。」也改成這段文字。
4. 直接打開 `/schedule` 時一樣先確認；沒連接或授權已失效時，精靈的位置顯示同一段提示，不顯示拖拉排序。
5. 確認連接狀態本身失敗（不知道有沒有連接）時，照常進入精靈。

**查詢哪些事件被刪除**

6. 進入精靈時，後端向 Google 查每個「已排入、還沒完成、不是主任務」的項目（手動任務與外部項目）的事件還在不在。
7. 只有 Google 回 404、410，或事件狀態是 `cancelled`，才算「事件已被刪除」。
8. 查詢依序進行；任何一個項目查詢失敗，整次查詢就算失敗。

**「處理已刪除的事件」步驟**

9. 查到事件已被刪除的項目時，精靈在拖拉排序之前多一個「處理已刪除的事件」步驟，列出這些項目。
10. 每一項顯示標題與「Google 日曆上的事件已被刪除」；階段任務另外標上主任務名稱與「階段 k/N」。
11. 每一項都有勾選框，預設全部勾選。
12. 外部項目的勾選框不能取消，旁邊說明「外部平台的項目會重新排程」。
13. 勾選的是階段任務、而且同一個主任務後面有「已排入、還沒完成、沒有列在這一步」的階段時，那一項下面寫「後面的階段 m、n 也會從 Google 日曆移除，一起重新排程」。取消勾選後這段說明消失。
14. 同一個主任務有好幾個階段列在這一步時，每個列出的階段照它自己的勾選處理；需求 13 的「一起移除」只套用在沒有列出的後面階段。
15. 沒有事件被刪除的項目時，不出現這個步驟，精靈從拖拉排序開始。

**按「下一步」**

16. 有沒勾的項目，或有需求 13 會被移除的後面階段時，先跳出確認對話框；按取消就留在這一步，什麼都不送出。
17. 對話框寫出「沒勾的 N 個任務會從系統刪除，無法復原，確定嗎？」（有沒勾的項目時）。
18. 沒勾的階段包含某個主任務目前所有的階段時，對話框另外寫明「主任務「X」會一起刪除」。
19. 對話框寫出「會從 Google 日曆移除 M 個後面階段的事件（包括時間已經過去的事件），一起重新排程」（有需求 13 的階段時）。同一個階段不重複計算。

**後端處理**

20. 後端依請求到達的順序處理，每一項都用處理當下的資料。同一個請求裡先處理要刪除的項目，再處理要重新排程的項目。
21. 處理每一項前，向 Google 確認任務目前存的事件仍然不存在。任務已經沒有 Google 日曆事件編號，或事件還在，這一項不處理，算成功。
22. 沒勾的手動任務：照 issue-30 的刪除規則刪除（只刪它自己；它是主任務唯一的子任務時，整個主任務一起刪），後面的階段編號往前遞補。
23. 有勾的項目：先刪掉需求 13 那些後面階段在 Google 日曆上的事件，再逐一清掉後面階段的 Google 日曆事件編號，最後清這一項的編號。已完成的階段不動。要一起移除的階段用處理當下的資料計算，數量可能和對話框不同。
24. 清除編號時，以「編號還是處理時讀到的那一個」為條件，一次寫入；不成立時這一項失敗，而且這一項自己的編號不清。
25. 不用資料庫交易。先刪 Google 事件、後清編號，所以中途失敗時只會留下「Google 上沒有事件、任務還有編號」的項目，下次查詢時會再列在這一步，預設勾選。
26. 要求刪除外部項目時，後端拒絕這一項，外部項目不變。
27. 單一項目的問題（編號已被換掉、不屬於自己或不存在、刪除階段時有其他請求在改同一個主任務）：這一項失敗，繼續處理下一項。
28. Google 或系統的錯誤（Google 回 5xx、429、400、找不到主要行事曆、逾時、連不上、其他 Google 錯誤，或授權失效）：停止，還沒處理的項目都不處理。授權失效時回 409 `REAUTH_REQUIRED`，其他照 ADR 0002 的狀態碼。
29. 已處理成功的項目生效，不復原。

**畫面上的結果**

30. 全部成功：精靈重新載入任務清單，進入拖拉排序。
31. 有任何失敗（包括後端回錯誤；需求 32 的授權失效除外）：留在這一步，上方顯示「處理失敗，請重試」，並重新查詢這一步的清單。還在的項目保留原本的勾選，新出現的項目預設勾選。清單是空的就重新載入任務清單，進入拖拉排序，不顯示這段提示。
32. 按「下一步」時授權失效：跳現有的 `reauthToast`，留在這一步，保留清單與勾選，不重新查詢，也不顯示「處理失敗，請重試」（toast 已說明原因並附重新連接的按鈕）。
33. 重新查詢本身失敗時，留在這一步，保留上一次的清單與勾選，顯示「處理失敗，請重試」；重新查詢遇到授權失效時另外跳 `reauthToast`。

**進入精靈時查詢失敗**

34. 查詢遇到授權失效（Google 回 401、權限不足，或已經沒有連接），後端回 409 `REAUTH_REQUIRED`；精靈上方顯示「Google Calendar 授權已失效」的提示，附「重新連接 Google Calendar」按鈕，不跳 toast；精靈從拖拉排序開始，已排入的項目維持原狀。
35. 查詢遇到其他任何錯誤，精靈從拖拉排序開始，已排入的項目維持原狀、不列出，精靈上方顯示「暫時無法確認 Google 日曆上的事件，排程未更新」。後端的狀態碼照 ADR 0002：Google 限流 503 `UPSTREAM_RATE_LIMITED`、逾時 504 `UPSTREAM_TIMEOUT`、沒有主要行事曆 409 `NO_PRIMARY_CALENDAR`、其他 Google 問題 502 `UPSTREAM_ERROR`、Google 回 400 時 500 `INTERNAL_ERROR`。

**同時修改任務**

36. 修改任務、調整截止日與時長、標記完成，都只寫入這個操作改到的欄位（加上 `updated`、`completed_at` 這類隨之改變的欄位），不寫回讀取當時的其他欄位；Google 日曆事件編號只由確認排程與這次的處理寫入或清除。

**排程規則（改寫 staged-tasks AC24）**

37. 前一個階段的事件被刪除、使用者勾選重新排程時，前一個階段與需求 23 的後面階段都回到待排，照一般的先後規則（staged-tasks AC21）依序排程。
38. 前一個階段的事件被刪除、使用者沒勾時，那個階段被刪除，後面的階段編號往前遞補。

## 不做

- 使用者重新連接時換了另一個 Google 帳號：舊帳號的事件在新帳號查不到（404），所有已排入的項目都會出現在這一步。開發者決定接受；使用者在這一步看得到，可以發現。系統沒有記錄事件屬於哪個帳號。
- 後端確認事件不存在、清掉編號之後，使用者又在 Google 復原這個事件，或把事件移到別的行事曆：下次確認排程時，Google 上會多一個重複的事件。不常見，開發者決定接受。
- 處理中途失敗時，不細分「哪幾項成功、哪幾項已經不需要處理」：只顯示「處理失敗，請重試」，沒處理完的項目重新查詢時會再列出（開發者決定縮小範圍）。
- 不回寫外部平台（GitHub、Jira、Moodle）的狀態。
- 外部項目的「不排程」狀態、「外部已結案」的顯示：#121。外部項目在這一步暫時不能取消勾選。
- 挑選這次要排程的任務：#120。
- 排程相關 API 的限流：#122。
- 同一個主任務的好幾個階段都列在這一步、都勾選重新排程，按「下一步」前使用者又在 Google 復原了後面某個階段的事件：處理時那個階段算成功、不處理，前面的階段回到待排，產生排程時順序可能顛倒，之後也不會再列出。很少發生，開發者決定接受（實作審查第 1 輪 #1）。
- 樂觀鎖（每筆任務帶版本號，根據舊畫面送出的修改被擋下）：#123。在那之前，確認對話框的數字是畫面載入時算的，後端處理時用當下的資料，兩者可能不同。
- 處理 API 收到重複的 id，或同一個 id 同時在兩份清單：正常前端不會發生，開發者決定不處理，發生時再開 issue。
- 事件還在、時間已過、任務卻沒完成：這次不處理。
- 不記錄「已查到被刪除」：每次進入精靈都重新查；使用者沒按「下一步」就關掉精靈，下次進入還會再列出。
- 不平行查詢 Google：已排入、還沒完成的項目變多、進入精靈變慢時，再另開 issue。
- 任務頁不顯示「事件已被刪除」，也不在任務頁查 Google。
- 產生排程建議（`POST /schedule/suggest`）的錯誤處理不改。

## 驗收條件

| # | 條件 |
|---|---|
| AC1 | 對應重現步驟：任務的事件在 Google 上已被刪除，進入排程精靈時，這個任務出現在「處理已刪除的事件」步驟 |
| AC2 | Google 對事件回 404、410，或事件狀態是 `cancelled` 時，才把項目列進這一步；事件存在時不列出 |
| AC3 | 已完成的項目、主任務、沒有 Google 日曆事件編號的項目都不查 Google，也不列出 |
| AC4 | 沒有事件被刪除的項目時，精靈不出現這一步，從拖拉排序開始 |
| AC5 | 這一步的每一項顯示標題與「Google 日曆上的事件已被刪除」；階段任務另外顯示主任務名稱與「階段 k/N」 |
| AC6 | 勾選框預設全部勾選；外部項目的勾選框不能取消，並顯示「外部平台的項目會重新排程」 |
| AC7 | 勾選的階段後面有已排入、還沒完成、沒有列在這一步的階段時，那一項顯示這些階段會一起從 Google 日曆移除、重新排程；取消勾選後這段說明消失 |
| AC8 | 有沒勾的項目或會被移除的後面階段時，按「下一步」先跳出確認對話框，寫出要刪除的任務數與要移除的事件數（註明包括時間已經過去的事件），同一個階段不重複計算；按取消時什麼都不送出 |
| AC9 | 沒勾的階段包含某個主任務目前所有的階段時，確認對話框寫明這個主任務會一起刪除 |
| AC10 | 確認後，有勾的項目沒有 Google 日曆事件編號，出現在拖拉排序的清單；產生排程時和從沒排過的項目一樣處理 |
| AC11 | 確認後，有勾的階段後面已排入、還沒完成、不在這次請求裡的階段，它們在 Google 日曆上的事件被刪除、編號被清掉；已完成的後面階段不變 |
| AC12 | 同一個主任務有好幾個階段列在這一步時，每個階段照它自己的勾選處理：勾了的重新排程、沒勾的刪除 |
| AC13 | 確認後，沒勾的一般任務、子任務從系統刪除；同一個主任務其他階段的資料與事件不變，只有後面的階段編號往前遞補 |
| AC14 | 確認後，沒勾的階段包含主任務目前所有的階段時，主任務一起刪除 |
| AC15 | 不變條件：後端處理時事件仍然在 Google 上，或任務已經沒有編號，這一項的編號不清、任務不刪 |
| AC16 | 不變條件：清除這一項或後面階段的編號時，編號已經被換成別的，不清除；這一項失敗，而且這一項自己的編號不清 |
| AC17 | 不變條件：後端處理途中遇到需求 28 的錯誤就停止，還沒處理的項目編號不清、任務不刪；已處理成功的項目維持結果 |
| AC18 | 不變條件：要求刪除外部項目時，後端拒絕這一項，外部項目不變 |
| AC19 | 不變條件：只能處理自己的項目；別人的或不存在的項目失敗，不透露是否存在 |
| AC20 | 全部成功時，精靈重新載入任務清單，進入拖拉排序 |
| AC21 | 有任何失敗時（授權失效除外），留在這一步，顯示「處理失敗，請重試」，並重新查詢清單；還在的項目保留勾選，新出現的項目預設勾選；清單是空的就進入拖拉排序 |
| AC22 | 按「下一步」時授權失效，跳 `reauthToast`，留在這一步，保留清單與勾選，不重新查詢，不顯示「處理失敗，請重試」 |
| AC23 | 重新查詢本身失敗時，留在這一步，保留上一次的清單與勾選，顯示「處理失敗，請重試」；授權失效時另外跳 `reauthToast` |
| AC24 | 進入精靈時查詢遇到授權失效，後端回 409 `REAUTH_REQUIRED`；精靈上方顯示授權失效的提示與「重新連接 Google Calendar」按鈕，不跳 toast，精靈從拖拉排序開始 |
| AC25 | 進入精靈時查詢遇到其他錯誤，精靈從拖拉排序開始，已排入的項目不列出，精靈上方顯示「暫時無法確認 Google 日曆上的事件，排程未更新」；後端狀態碼照需求 35 |
| AC26 | 按「產生排程建議」或「重新產生」時，沒連接或授權已失效，不進入精靈，排程建議卡片顯示「Google Calendar 未連接或授權已失效，請前往 帳號設定 連接。」 |
| AC27 | 直接打開 `/schedule` 時，沒連接或授權已失效，精靈的位置顯示 AC26 的提示，不顯示拖拉排序 |
| AC28 | 確認連接狀態失敗時，照常進入精靈 |
| AC29 | 前一個階段的事件被刪除、使用者勾選重新排程後，產生排程時，它和後面的階段依序排程，後面的階段排在它之後 |
| AC30 | 前一個階段被刪除（沒勾）後，後面的階段編號往前遞補，排程照遞補後的順序 |
| AC31 | 載入中：連接狀態或已刪除事件的查詢還沒回來時，精靈不顯示拖拉排序的內容，也不能按下一步 |
| AC32 | 不變條件：系統清掉 Google 日曆事件編號的同時，另一個分頁修改同一個任務（編輯、調整截止日與時長、標記完成），清掉的編號不會被寫回 |
| AC33 | 修改任務、調整截止日與時長、標記完成之後，任務其他沒改到的欄位維持資料庫裡目前的值，不被讀取當時的舊值蓋掉 |

## 不適用的情境

| 情境 | 原因 |
|---|---|
| 未登入 | 精靈本來就要登入才顯示（`schedule.vue:150-152`）；新的 API 照現有方式要求登入 |
| 輸入驗證、注入 | 新的處理 API 只收組合 id（來源前綴加上項目 id，例如 `manual:<任務 id>`、`github:42`）清單，照現有的組合 id 驗證（`schedulable_items.py:30-47`）；格式錯誤的項目失敗 |

## 實作計畫

**後端**

1. `backend/services/google_calendar.py`：新增函式，對一批 Google 日曆事件編號回傳哪些已被刪除。
   - 判斷規則和 `get_calendar_event_ends` 相同（404、410、`cancelled`），共用查詢與判斷，不各寫一份。
   - 錯誤：401、權限不足、沒有連接 → `ReauthRequiredError`（409 `REAUTH_REQUIRED`）；其他照 `_google_error` 與 `_unreachable` 的現有分類。`get_calendar_event_ends` 自己的錯誤處理不改。
2. `backend/crud/manual_task.py` 與 `backend/crud/schedulable_items.py`：
   - 新增「編號還是 X 時才清成 None」的條件式清除，手動任務與外部項目都要；filter 帶上原本的編號與 user_id，一次寫入（AC16）。
   - `update_manual_task_by_id` 改成只 `$set` 呼叫端傳入、這次操作改到的欄位；呼叫端（`backend/routers/manual_task.py` 的 `update_manual_task`、`schedulable_items.py` 的 `update_scheduling_fields`、`set_done`）改成只傳改到的欄位，不再傳整筆讀到的任務（AC32、AC33）。
3. `backend/routers/schedule.py`：新增兩支 API。
   - `GET /schedule/removed-events`：回傳事件已被刪除的項目（`SchedulableTaskOut` 清單），只查需求 6 的項目（AC3）。每一項另外帶上需求 13 的「會被一起移除的後面階段」（組合 id 與階段編號），給前端顯示與對話框使用。
   - `POST /schedule/removed-events/resolve`：body 是 `reschedule`、`delete` 兩份組合 id 清單，照需求 20～29 處理。
     - `delete`：重用 `backend/routers/manual_task.py` 的刪除流程（`_calendar_events_to_delete`、`delete_calendar_events`、`_delete_task_records`），不另寫一份。
     - 回應列出每一項成功或失敗；失敗帶原因與 `error_code`。授權失效或需求 28 的錯誤時，照 ADR 0002 回錯誤狀態碼。
4. `backend/schemas/schedule.py`：新增 request／response 的 schema。
5. 排程本身（`scheduler.py`）不用改：清掉編號的前一個階段與後面階段都回到待排，先後規則照 staged-tasks AC21 運作（AC29）。

**前端**

6. `frontend/types/schedule.ts`：新增對應的型別。
7. `frontend/components/tasks/ScheduleSuggestion.vue`：未連接的提示文字改成需求 3 的文字。`startWizard` 先確認連接狀態（沿用 `useGoogleCalendar` 的狀態查詢），照需求 2、3、5 處理（AC26、AC28）。判斷依據是這一次查詢的結果；這次查詢失敗時照常進入精靈，不沿用共用狀態裡上次的結果（`useGoogleCalendar.ts:83-88` 會沿用上次的結果）。
8. 新增處理「已刪除的事件」的 composable（或放進 `useScheduleWizard`），負責查詢、送出、失敗後重新查詢。
9. `frontend/pages/schedule.vue`：
   - 載入時先確認連接狀態（AC27），再同時取任務清單與已刪除的事件；查詢回來前顯示載入中（AC31）。
   - 有項目時顯示「處理已刪除的事件」步驟，步驟列也加上這一步；沒有時不顯示（AC4）。
   - 確認對話框照需求 16～19。
   - 結果照需求 30～33；查詢失敗的提示照需求 34、35。

**文件**

10. `docs/api.md`：排程一節加上兩支新 API，寫出錯誤回應。
11. `docs/architecture.md`：如果有描述排程與 Google Calendar 的資料流，補上這次的查詢。
12. `docs/specs/staged-tasks.md`：在現有的狀態（部分被 issue-30 取代）之外，加上「AC24 部分被這份規格取代」，連到這份規格；issue-30 的部分保留。AC24 只有「使用者在『處理已刪除的事件』步驟處理了」的情況被取代；查詢失敗、或使用者沒按「下一步」就離開時，產生排程建議仍照 AC24 原本的規則。

**考慮過、沒選的做法**

- 只在產生排程時查：精靈第一步看不到這個任務，產生的排程卻有它，前後不一致。
- 查到就直接清掉編號：後端產生排程用的是資料庫裡全部的項目，沒勾的也會被排進去；而且沒勾的要刪除，必須等使用者決定。
- 查詢併進 `GET /schedule/tasks`：Google 失敗時任務清單也載不出來，違反需求 35。
- 定時在背景查：要新增排程工作，目前 Cloud Run 帳單關閉，成本也較高。
- 處理時只信前端送來的清單、不重新向 Google 確認：畫面停留期間事件可能被復原，會造成重複排入或誤刪（AC15）。
- 重新排程的階段只加「要在下一個階段的事件開始前結束」的限制，或接受順序顛倒：開發者決定改成後面已排入的階段一起移除、整串重新排程（需求 23）。
- 先在一個資料庫交易裡清除編號、提交後再刪 Google 事件：要使用 MongoDB 交易（ADR 0001 決定不用：正式環境要 replica set，測試的 mongomock 不支援），刪 Google 事件失敗時還會留下重複事件，要另外存待刪清單重試。先刪 Google、後清編號，中途失敗時由這次的偵測自動列出，不需要交易與重試機制（需求 25）。
- 中途失敗時逐項回報「成功、已經不需要處理、失敗」並計算提示數字：開發者決定縮小範圍，只顯示「處理失敗，請重試」。
- 把「已查到被刪除」存進資料庫：要新增欄位，也要處理它何時清除；每次重新查就不需要。

## 測試對應

| AC | 測試 | 改程式前是否失敗 |
|---|---|---|
| AC1、AC2 | `backend/tests/unit/test_google_calendar_service.py`（404、410、`cancelled` 算刪除；200 不算）；`backend/tests/unit/test_schedule_router.py`（`removed-events` 回傳事件被刪除的項目） | 是 |
| AC3 | `backend/tests/unit/test_schedule_router.py`：已完成、主任務、沒有編號的項目不送去 Google 查 | 是 |
| AC4 | `frontend/tests/pages/schedule.test.ts` | 否（原本的程式就不會出現這一步） |
| AC5、AC6、AC7、AC31 | `frontend/tests/pages/schedule.test.ts` | 是 |
| AC8、AC9 | `frontend/tests/pages/schedule.test.ts`（或 composable 測試）：跳出確認的條件、數量、主任務一起刪的文字、取消時不送出 | 是 |
| AC10 | `backend/tests/unit/test_schedule_router.py`：`resolve` 後編號清空；`backend/tests/integration/test_schedule_scenario.py`：清空後出現在 `/schedule/tasks` 的待排項目 | 是 |
| AC11 | `backend/tests/unit/test_schedule_router.py`：後面已排入的階段的事件被刪、編號清空；已完成的不變 | 是 |
| AC12 | `backend/tests/unit/test_schedule_router.py`：同一個主任務兩個階段列出，勾前面、不勾後面，後面的被刪、前面的重新排程 | 是 |
| AC13、AC14 | `backend/tests/unit/test_schedule_router.py`：刪除一般任務、子任務、主任務所有的階段 | 是 |
| AC15、AC16、AC17 | `backend/tests/unit/test_schedule_router.py`：處理時事件存在、已經沒有編號、後面階段編號被換（這一項編號不清）、Google 5xx／授權失效時停止 | 是 |
| AC18、AC19 | `backend/tests/unit/test_schedule_router.py`：刪除外部項目、別人的項目、格式錯的 id 都失敗，其他項目照常處理 | 是 |
| AC20、AC21、AC22、AC23 | `frontend/tests/pages/schedule.test.ts`：全部成功進入拖拉排序；有失敗時顯示「處理失敗，請重試」並重新查詢、新項目預設勾選、空清單進入拖拉排序；授權失效跳 `reauthToast`；重新查詢失敗保留清單 | 是 |
| AC24、AC25 | `backend/tests/unit/test_google_calendar_service.py`（401、權限不足、沒有連接 → `REAUTH_REQUIRED`；429 → `UPSTREAM_RATE_LIMITED`；逾時 → `UPSTREAM_TIMEOUT`；5xx → `UPSTREAM_ERROR`）；`frontend/tests/pages/schedule.test.ts`（提示文字、不跳 toast、從拖拉排序開始） | 是 |
| AC26 | `frontend/tests/components/ScheduleSuggestion.test.ts`：沒連接時不導頁並顯示提示 | 是 |
| AC28 | `frontend/tests/components/ScheduleSuggestion.test.ts`：狀態查詢失敗時照常導頁 | 否（原本的按鈕一律進入精靈） |
| AC28 | `frontend/tests/pages/schedule.test.ts`、`frontend/tests/composables/useGoogleCalendar.test.ts`：這一次的查詢失敗時照常進入精靈 | 是 |
| AC27 | `frontend/tests/pages/schedule.test.ts` | 是 |
| AC29、AC30 | `backend/tests/integration/test_schedule_scenario.py`：重新排程後前一個階段在前、後面階段依序；刪除後的遞補 | 是 |
| AC32、AC33 | `backend/tests/unit/test_schedulable_items.py`（調整截止日與時長、標記完成）、`backend/tests/unit/test_manual_task_router.py`（修改任務）：讀取後、寫回前另一邊清掉編號（或改了其他欄位），寫回後編號仍是 None、其他欄位不被舊值蓋掉；修改任務、調整截止日與時長、標記完成各一 | 是 |
| 新 API 的接線 | `backend/tests/integration/test_schedule_api.py`：成功、典型錯誤、沒登入被擋 | — |

## 修改紀錄

| 日期 | 修改 | 原因 | 確認者 |
|---|---|---|---|
| 2026-11-17 | 需求 17：對話框文字補上「確定嗎？」 | 開發者在需求問答確認的文字有這句，寫規格時漏掉 → 需求 17；檢查過 AC8 不用改（只要求寫出數量） | 開發者 |
| 2026-11-17 | 「不做」：接受列出的後面階段在處理前被復原時順序可能顛倒 | 開發者決定接受（實作審查第 1 輪 #1）→「不做」；檢查過需求 14、21、AC12、AC15、AC29 不用改 | 開發者 |
| 2026-11-17 | 測試對應：AC4、AC28 的「改程式前是否失敗」照實際結果；AC32、AC33 補上修改任務的測試檔 | 實作後的實際結果（實作審查第 1 輪 #3）→ 測試對應；驗收條件不變 | 開發者 |

## 請你決定

無
