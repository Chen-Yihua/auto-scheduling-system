# 連續刪除最後兩個階段時，被擋下的階段不再被排程：審查第 1 輪

- 規格：[docs/specs/issue-37-concurrent-subtask-delete.md](../specs/issue-37-concurrent-subtask-delete.md)
- PR：#43
- 日期：2026-11-06
- 審查的版本：`6c295c5`（`git diff origin/main...HEAD`）
- 結果：有阻擋（Implementation Defect 1；另有不阻擋的 Improvement Suggestion 2）

## 審查報告

我跑過的檢查：`pyright` 0 errors；`pytest` 632 passed；`vitest run tests/components/TaskForm.actions.test.ts` 8 passed；`npm run lint`、`npm run typecheck` 都通過。

### 驗收條件

| AC | 結果 | 依據（檔案:行號） |
|---|---|---|
| AC1 | 通過 | `backend/routers/manual_task.py:293-301`：先記下 `delete_upcoming_calendar_events` 回傳的「這次刪掉的事件」，`delete_subtask` 丟出 `InvalidRequestError` 時清掉 `calendar_event_id`，再把同一個例外丟出去，所以 400 的提示文字不變。`backend/services/scheduler.py:234-237` 會跳過有 `calendar_event_id` 的任務，清掉後這個階段就會被排入。測試在 `backend/tests/unit/test_manual_task_router.py:746-765`：`_delete_concurrently`（`:709-732`）讓兩個請求都通過數量預檢、都刪完事件後才一起寫入，時序是固定的；這個測試會檢查提示文字、留下的子任務，以及 `build_schedule_suggestion` 有沒有排入它。 |
| AC2 | 通過 | `backend/crud/manual_task.py:419-424` 用 `_id`、`user_id`、`calendar_event_id` 三個條件篩選後清成 None。`backend/services/google_calendar.py:231-249` 只把真的呼叫刪除成功的事件 id 加進回傳清單；已開始、已過去、已取消、404/410 的事件都不會加進去。三種情況各有一個測試：被刪 → None 在 `test_manual_task_router.py:768-777`；保留 → 原值在 `:780-795`；原本沒有事件 → 不變在 `:798-808`。「只改這個使用者的這個子任務」在 `:811-824` 測。回傳值本身在 `backend/tests/unit/test_google_calendar_service.py:519-529` 測（`deleted == ["future"]`）。 |
| AC3 | 通過 | `frontend/components/tasks/TaskForm.vue:153-165`：用 `deletingSubtask` 當鎖，在 `finally` 解鎖；`:358` 讓每一列的「刪除」按鈕都依同一個 ref 停用。測試在 `frontend/tests/components/TaskForm.actions.test.ts:185-209`，成功、失敗兩種情況都測：刪除進行中兩顆按鈕都是 disabled，第二次點擊不會送出請求，結束後兩顆都恢復。 |

### 實作 agent 回報的兩點

1. **AC2 的使用者篩選改在 router 層測，用「別的使用者有記著同一個事件 id 的任務」來測**：這個做法成立，不列為發現。
   - `_id` 在 collection 裡本來就唯一，而且 router 在 `backend/routers/manual_task.py:284` 已經用 `get_manual_task_by_id(task_id, user_id)` 確認這是自己的任務。所以就算 `clear_calendar_event_id` 少了 `user_id` 條件，從外部也看不出差別。為它寫測試等於測一個走不到的防禦分支，違反 CLAUDE.md「測試範圍」。
   - 比較可能出錯的寫法是只用 `calendar_event_id` 篩選，或改用 `update_many`。這兩種寫法都會讓 `:811-824` 失敗，這個測試確實擋得住。
2. **鎖放在 `TaskForm.vue`，「在前面插入」刪除中沒有停用**：成立，不列為發現。
   - `onDeleteSubtask` 只有 `frontend/components/tasks/TaskForm.vue:160` 一個呼叫端，鎖放在元件層一樣涵蓋所有入口。規格「原因」寫的是 `useTaskForm.ts` 缺鎖，但 AC3 要求的只是按鈕行為，鎖放在哪裡不算違反規格。
   - 「在前面插入」（`TaskForm.vue:343-350`）只呼叫 `startAddSubtask` 打開表單，不會送出請求。之後真正送出新增時，後端用 `subtask_ids.{position-2}` 檢查插入位置還在不在（`backend/crud/manual_task.py:250-258`），位置不在了會回錯誤要使用者重新整理。這和 AC3 無關。

### 發現

| # | 分類 | 阻擋 | 涉及安全／架構 | 說明 | 依據（檔案:行號） | 建議 |
|---|---|---|---|---|---|---|
| 1 | Implementation Defect | 是 | 否 | 改到了規格範圍以外：`get_calendar_event_ends` 多了一行 `deleted = []`，這個變數之後完全沒用到，看起來是改 `delete_upcoming_calendar_events` 時誤加在上一個函式裡。它不影響行為，`pyright` 也沒報錯，但這是本 PR 新增、規格沒要求的改動，而且會讓人誤以為 `get_calendar_event_ends` 也要追蹤刪掉的事件。 | `backend/services/google_calendar.py:190` | 刪掉這一行。 |
| 2 | Improvement Suggestion | 否 | 否 | 規格「回歸測試」表的「改程式前是否失敗」欄只寫「預期失敗」，沒寫實際確認的結果。`docs/specs/README.md:92` 要求回歸測試要在改程式前先確認會失敗。我照 `origin/main` 的程式推算，結果和預期一致：AC1 會失敗，因為 main 上不會清 `calendar_event_id`，排程結果是空的；AC2 的「被刪 → None」會失敗，其餘三個會通過；AC3 會失敗，因為 main 上按鈕沒有 disabled。所以測試確實能重現 bug。但我是推算的，沒有實際在 main 上跑過，因為唯讀限制不能切分支。 | `docs/specs/issue-37-concurrent-subtask-delete.md:42-44` | 實作者在 main 上實際跑過這幾個測試後，把欄位改成實際結果（例如「是」、「否（保護既有行為）」），讓之後的讀者知道是確認過的，不只是預期。 |
| 3 | Improvement Suggestion | 否 | 否 | 這是 main 上原本就有的同類問題，不在 AC2 的觸發條件內。刪除子任務時，如果 Google 上的事件已經刪了，但接下來的 `delete_subtask` 是因為資料庫錯誤（`PyMongoError`）失敗，而不是被「只剩一個」擋下，子任務會留下來，`calendar_event_id` 還指向已刪除的事件。使用者重試時，那個事件會走 404/410，不會出現在「這次刪掉的事件」清單裡；如果這時又剛好被「只剩一個」擋下，這個階段就永遠不會再被排入，症狀和 issue #37 一樣。這次的修正只接 `InvalidRequestError`，所以涵蓋不到這條路徑。影響範圍只有刪除子任務的 endpoint，而且要碰上資料庫暫時失敗才會發生。 | `backend/routers/manual_task.py:294-301`、`backend/crud/manual_task.py:271-284`、`backend/services/google_calendar.py:242-244` | 可以併入 #42 一起處理（#42 處理的是「事件已不存在但任務還記著它」）。或另開 issue，決定 `delete_subtask` 遇到任何錯誤、而這次請求已經刪掉事件時，是不是都要清掉 `calendar_event_id`。這會改變失敗時的資料處理方式，需要開發者決定。 |

### 其他檢查

- 簡化格式的要求：AC1 對應重現步驟 1-4；修正可能影響的相關行為（事件保留、原本沒有事件、別的使用者的資料、前端的鎖）都有 AC2、AC3 涵蓋。回歸測試表的欄位有填（實際確認的部分見發現 #2）。
- 規格同步：新增的 5 個後端測試和 1 個前端測試都對應到 AC1-AC3。`test_ac28_only_events_that_have_not_started_are_deleted` 的修改是為了驗證 AC2 依賴的回傳值，算在 AC2 的範圍內。AC 沒有改，「修改紀錄」是空的，這樣正確。
- 前後端連動：endpoint 的路徑、登入需求、限流、回應格式都沒變，`docs/api.md:43` 不用改。沒有新增 collection 或服務。
- 安全：`clear_calendar_event_id` 的篩選條件有 `user_id`，router 也先確認了任務是自己的。沒有新的注入或權限問題，也沒有發現漏洞。
- 規格本身：看完實作後沒有發現規格層級的問題（Factual Error、Specification Defect、Missing Acceptance Criteria）。發現 #3 不在 AC2 的觸發條件內，規格已把 #42 列為不做，所以只列成建議。

## 處理結果

| # | 處理 | 決定者 | 根本原因 | commit / issue / advisory 編號 |
|---|---|---|---|---|
| 1 | 交回實作修正：刪掉多餘的 `deleted = []` | 規則（阻擋的 Implementation Defect） | 誤加的無用變數 | `a4ea082` |
| 2 | 「改程式前是否失敗」欄改成實作 agent 改程式前實際跑出的結果 | 主 session（文件同步） | — | `a4ea082` |
| 3 | 在既有的 #42 留言補充（同一類：任務記著已不存在的事件），不另開 issue | 規則（不阻擋的發現開 issue，已有相同問題時留言） | — | [#42 留言](https://github.com/Chen-Yihua/auto-scheduling-system/issues/42#issuecomment-6684748738) |
