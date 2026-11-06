# 連續刪除最後兩個階段時，被擋下的階段不再被排程：審查第 2 輪

- 規格：[docs/specs/issue-37-concurrent-subtask-delete.md](../specs/issue-37-concurrent-subtask-delete.md)
- PR：#43
- 日期：2026-11-06
- 審查的版本：`a4ea082`（`git diff origin/main...HEAD`）
- 結果：沒有阻擋項目

## 審查報告

我跑過的檢查都通過：
- 後端：`pyright` 0 errors；`pytest` 632 passed
- 前端：`vitest run tests/components/TaskForm.actions.test.ts` 8 passed；`npm run lint`、`npm run typecheck` 都通過

### 驗收條件

| AC | 結果 | 依據（檔案:行號） |
|---|---|---|
| AC1 | 通過 | 這一輪程式沒有改。`backend/routers/manual_task.py:293-301` 會記下 `delete_upcoming_calendar_events` 回傳的「這次刪掉的事件」。遇到 `InvalidRequestError` 時，它會清掉 `calendar_event_id` 再把例外丟出去。測試在 `backend/tests/unit/test_manual_task_router.py:746-765`，`_delete_concurrently` 在 `:709-733`：檢查提示文字、留下的子任務，以及 `build_schedule_suggestion` 有沒有把它排入。 |
| AC2 | 通過 | `backend/crud/manual_task.py:419-424` 用 `_id`、`user_id`、`calendar_event_id` 三個條件篩選。`backend/services/google_calendar.py:230-248` 只把真的刪掉的事件放進回傳值。測試分成四種情況：被刪 → None 在 `test_manual_task_router.py:768-777`；保留 → 原值在 `:780-795`；原本沒有事件 → 不變在 `:798-808`；別的使用者不受影響在 `:811-824`。回傳值本身在 `backend/tests/unit/test_google_calendar_service.py:519-529` 測。 |
| AC3 | 通過 | 這一輪沒有改。`frontend/components/tasks/TaskForm.vue:154-163` 用 `deletingSubtask` 當鎖，在 `finally` 解鎖；每一列的刪除按鈕都依 `:358` 停用。測試在 `frontend/tests/components/TaskForm.actions.test.ts`，成功、失敗兩種情況都測，8 個測試通過。 |

### 前一輪的處理是否成立

| 第 1 輪 # | 確認結果 | 依據（檔案:行號） |
|---|---|---|
| 1（多出來的 `deleted = []`） | 成立。`a4ea082` 只刪了 `get_calendar_event_ends` 裡那一行；`deleted = []` 現在只在 `delete_upcoming_calendar_events` 裡出現一次。`get_calendar_event_ends` 和 `origin/main` 上的內容一樣，沒有帶進其他改動。 | `backend/services/google_calendar.py:180-198`、`:230` |
| 2（「改程式前是否失敗」欄只寫預期） | 成立。欄位改成實際結果：AC1「是」；AC2「被刪 → None」是、其餘三個否（保護既有行為）；AC3「是（成功、失敗兩種都失敗）」。我照 `origin/main` 的程式推算，結果和這些一致：<br>- main 的 router 不用 `delete_upcoming_calendar_events` 的回傳值，也不會清 `calendar_event_id`，所以 AC1 和 AC2 的「被刪 → None」會失敗。<br>- 「保留」「沒有事件」「別的使用者」這三個測試只要求值不變，在 main 上會通過。<br>- main 上的按鈕沒有 `disabled`，所以 AC3 會失敗。<br>受唯讀限制，我沒有實際在 main 上跑。 | `docs/specs/issue-37-concurrent-subtask-delete.md:42-44` |
| 3（資料庫錯誤時 `calendar_event_id` 留著已刪的事件） | 不在這個 PR 處理，已在 #42 留言。這一輪的改動沒有碰這條路徑，狀態和第 1 輪一樣，不重複列。 | `backend/routers/manual_task.py:294-301` |

### 發現

沒有新發現。`a4ea082` 改的只有三個檔案：
- `backend/services/google_calendar.py`：刪掉一行
- `docs/specs/issue-37-concurrent-subtask-delete.md`：回歸測試表的第三欄
- `docs/reviews/issue-37-concurrent-subtask-delete-round1.md`：新增第 1 輪的紀錄

這三處都沒有帶來新的行為改動，也沒有改到規格範圍以外的地方。

### 其他檢查

- 規格同步：AC 沒有改；只改了回歸測試表的「改程式前是否失敗」欄，那是事實紀錄，不是驗收條件，所以「修改紀錄」空著是正確的。新增的測試都對應到 AC1-AC3，和第 1 輪一樣。
- 簡化格式：AC1 對應重現步驟 1-4。回歸測試表三欄都有填，而且寫的是實際結果。
- 前後端連動：endpoint 的路徑、登入需求、限流、回應格式都沒變，不用改 `docs/api.md`。
- 安全與架構：這一輪沒有新的安全問題或架構影響；第 1 輪的結論（`clear_calendar_event_id` 有 `user_id` 篩選）不變。
- 文件狀態（不算發現）：工作目錄裡 `docs/reviews/issue-37-concurrent-subtask-delete-round1.md` 的修改還沒 commit。這個修改把「處理結果」#1、#2 的「（修正後補上）」換成 `a4ea082`，HEAD 上的版本仍是佔位文字。存檔第 2 輪紀錄時記得一起 commit。

## 處理結果

沒有阻擋項目，也沒有新發現；第 1 輪的處理結果已補上 commit 編號，和這份紀錄一起 commit。
