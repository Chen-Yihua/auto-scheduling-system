# staged-tasks：審查第 2 輪

- 規格：[docs/specs/staged-tasks.md](../specs/staged-tasks.md)
- PR：#31
- 日期：2026-11-05
- 審查的版本：`e76041b`（`origin/main...HEAD`）
- 結果：沒有阻擋項目（不阻擋：Improvement Suggestion 4）

## 審查報告

- 架構決策：`docs/decisions/0004-subtask-order-on-parent.md`

我沒有修改任何檔案。本機檢查全部通過：
- 後端：`pyright` 0 errors，`pytest` 627 passed
- 前端：`npm run lint`、`npm run typecheck` 通過，`vitest` 298 passed

沒有 e2e 的結果，因為開發者的 dev server 開著，這次沒跑。

### 第 1 輪項目的處理確認

| 第 1 輪 # | 處理情形 | 依據（檔案:行號） |
|---|---|---|
| #1（阻擋） | 已處理。AC37 改成 403，記進修改紀錄；測試改成斷言 `== 403` | docs/specs/staged-tasks.md:94、185；backend/tests/integration/test_manual_task_api.py:393-398 |
| #2（阻擋） | 已處理。AC6 改了，`adjust_inferred_priorities` 現在上下限都會調整。一次建立和中間插入兩條路徑都有測試；如果實作只處理上限，測試會失敗 | backend/crud/manual_task.py:116-136；backend/tests/unit/test_manual_task_crud.py（test_ac6_inferred_priority_lower_than_next_stage_is_raised_to_next、test_ac6_inferred_priority_is_kept_between_previous_and_next_stage）；backend/tests/unit/test_manual_task_router.py（test_ac6_…、test_ac10_inferred_priority_of_inserted_subtask_is_raised_to_next_stage） |
| #4（開發者決定在這個 PR 修） | 已處理。轉換時 `$unset` 多清了 `inference_hint`、`status`、`completed_at`，並把 `inferred_fields` 設成 `[]`，AC12 也同步修改。測試確認原本是 In Progress 的任務轉換後狀態是 To Do | backend/crud/manual_task.py:239-246；docs/specs/staged-tasks.md:64、187；backend/tests/unit/test_manual_task_router.py（test_ac12_first_subtask_turns_plain_task_into_parent_and_clears_own_fi…） |
| #5（開發者決定在這個 PR 修） | 已處理。改成依 ADR 0004 實作：插入用 `$push` 加 `$position`，上限與插入位置的條件寫在同一次更新的 filter 裡；刪除用 `$pull`，「至少 2 個」也寫在 filter 裡；轉換和放入第一個子任務在同一次更新完成。新增了 AC39、AC40 和對應的測試 | backend/crud/manual_task.py:208-286；backend/tests/unit/test_manual_task_crud.py（test_ac39_* 共 7 個）；backend/tests/integration/test_manual_task_api.py（test_ac40_…） |
| #6（阻擋） | 已處理。`sort_key` 也拿推算的期限來判斷是否緊急，測試用的就是第 1 輪重現問題的情境 | backend/services/scheduler.py:241-243；backend/tests/unit/test_scheduler.py（test_ac25_derived_deadline_counts_as_urgent_so_earlier_stage_is_scheduled_first） |
| #7（阻擋） | 已處理。補了「把階段 1 拖到 Low 欄」的測試。如果實作只檢查被拖的階段和它前面的階段，這個測試會失敗 | frontend/tests/pages/schedule.test.ts:346-356；frontend/utils/stages.ts:39-41 |
| #8（開發者決定在這個 PR 修） | 已處理。前一個階段「已經完成」「已經排入行事曆」時，`blocks_later_stages=False`，不擋後面的階段。另外快照會記下每一筆的 `parent_id`，所以前一個階段被刪掉後，確認時一樣擋得住後面的階段 | backend/services/scheduler.py:378-410；backend/routers/schedule.py:126-129、155-158；backend/tests/unit/test_scheduler.py（test_ac26_previous_stage_done_or_already_on_calendar_…、test_ac26_previous_stage_gone_or_time_passed_…、test_ac26_scheduled_items_remember_their_parent_…） |

### ADR 0004：用到階段順序的地方都以 `subtask_ids` 為準

我在 backend、frontend 用 grep 找了所有用到 `stage` 的地方，沒有任何一處用子任務自己存的欄位排序，也沒有發現退化：

- **來源**：`stage` 只在 `_ordered_subtasks` 依 `subtask_ids` 的位置算出來（backend/crud/manual_task.py:41-53）。列表會濾掉不在任何主任務陣列裡的子任務（backend/crud/manual_task.py:56-65）；查單筆時也一樣，查不在陣列裡的子任務回 404（backend/crud/manual_task.py:335-344）。
- **驗證**：PUT 和 `/schedule/tasks/fields` 用 `validate_task_change` → `get_subtasks`（backend/crud/manual_task.py:393-406；backend/crud/schedulable_items.py:106-117）。reorder 用依計算出的 stage 排序的 `own_tasks`（backend/crud/manual_task.py:378-390）。新增子任務用 `get_subtasks`（backend/routers/manual_task.py:181、196）。
- **排程**：`by_stage` 的 stage 來自 `get_all_schedulable_items` → `get_manual_tasks_by_user_id` 算出的值（backend/services/scheduler.py:233；backend/routers/schedule.py:78-88）。
- **確認排程**：不再用 stage 找前一個階段，改用快照裡的順序加 `parent_id`（backend/services/scheduler.py:374-410）。
- **顯示**：`stage_count` 用濾掉殘留文件後的清單計算（backend/crud/schedulable_items.py:71-78）。前端的列表、編輯表單、排程頁標籤都用 API 回的 `stage`（frontend/components/tasks/TaskForm.vue:61、333、513；frontend/composables/useTaskForm.ts:117；frontend/pages/schedule.vue:79）。
- **統計**：analytics 用的是 `get_all_schedulable_items`，所以殘留的子任務不會被計入（backend/routers/analytics.py:24）。
- **拖拉**：用排程清單的 `stage`（frontend/utils/stages.ts:32-50）。
- 有測試刻意讓 `s2` 比 `s1` 先寫入，確認順序以 `subtask_ids` 為準（backend/tests/unit/test_schedulable_items.py:453-460）。

### 驗收條件

| AC | 結果 | 依據（檔案:行號） |
|---|---|---|
| AC1 | 通過 | backend/routers/manual_task.py:67-94；backend/crud/manual_task.py:178-205 |
| AC2 | 通過 | backend/routers/manual_task.py:125-155；backend/schemas/manual_task.py（`_status_required_without_subtasks`） |
| AC3 | 通過 | backend/schemas/manual_task.py（`subtasks` 的 min_length=1、max_length=10；`_title_not_blank`） |
| AC4 | 通過 | backend/routers/manual_task.py:72-77（驗證都在寫入前）；backend/crud/manual_task.py:189-200 |
| AC5 | 通過 | backend/routers/manual_task.py:42-64 |
| AC6 | 通過 | backend/crud/manual_task.py:116-136；frontend/composables/useTaskForm.ts（`adjustedStagesText`） |
| AC7 | 通過 | backend/crud/manual_task.py:100-107 |
| AC8 | 通過 | backend/crud/manual_task.py:81-97 |
| AC9 | 通過 | backend/routers/manual_task.py:104-105 |
| AC10 | 通過 | backend/routers/manual_task.py:191-200；backend/crud/manual_task.py:249-258 |
| AC11 | 通過 | backend/routers/manual_task.py:182-183；backend/crud/manual_task.py:250（寫入當下再檢查一次） |
| AC12 | 通過 | backend/crud/manual_task.py:232-247；frontend/composables/useTaskForm.ts（`startAddSubtask` 預先填入原本的優先序和時長） |
| AC13 | 通過 | backend/routers/manual_task.py:185-188；backend/crud/manual_task.py:233-238 |
| AC14 | 通過 | backend/routers/manual_task.py:178-179 |
| AC15 | 通過 | backend/routers/manual_task.py:173 |
| AC16 | 通過 | backend/crud/manual_task.py:21-38 |
| AC17 | 通過 | backend/routers/manual_task.py:258-259；backend/crud/schedulable_items.py:130-131；frontend/components/tasks/TaskForm.vue（`:disabled="task.is_parent"`） |
| AC18 | 通過 | backend/crud/schedulable_items.py:122-137 |
| AC19 | 通過 | backend/routers/manual_task.py:258-260；backend/crud/manual_task.py:398-401 |
| AC20 | 通過 | backend/crud/manual_task.py:378-406；backend/crud/schedulable_items.py:110-116 |
| AC21 | 通過 | backend/services/scheduler.py:280-291、339-355 |
| AC22 | 通過 | backend/services/scheduler.py:293-297 |
| AC23 | 通過 | backend/services/scheduler.py:284-285 |
| AC24 | 通過 | backend/routers/schedule.py:78-96；backend/services/scheduler.py:286-288 |
| AC25 | 通過 | backend/services/scheduler.py:25-52、241-243、301 |
| AC26 | 通過 | backend/services/scheduler.py:374-410；backend/services/google_calendar.py:141-145、155 |
| AC27 | 通過 | frontend/utils/stages.ts:9-53；frontend/pages/schedule.vue:57-76；frontend/composables/useScheduleWizard.ts:73 |
| AC28 | 通過 | backend/routers/manual_task.py:286-289；backend/crud/manual_task.py:289-292；frontend/composables/useTaskForm.ts（`onDelete` 的確認文字） |
| AC29 | 通過 | backend/routers/manual_task.py:290-294；backend/crud/manual_task.py:271-286 |
| AC30 | 通過 | backend/routers/manual_task.py:291-292；backend/crud/manual_task.py:279、283-284 |
| AC31 | 通過 | backend/services/google_calendar.py（`delete_upcoming_calendar_events` 的 `_EVENT_GONE_STATUSES`） |
| AC32 | 通過 | backend/services/google_calendar.py（`is_google_calendar_connected`、`_delete_error` 的 401）；frontend/composables/useTaskForm.ts（`showDeleteError`） |
| AC33 | 通過 | backend/services/google_calendar.py（`_delete_error` 的 5xx/429、`RequestError`）；backend/routers/manual_task.py:288-289、293-294（先刪事件，成功後才刪任務） |
| AC34 | 通過 | backend/routers/manual_task.py:295-296 |
| AC35 | 通過 | frontend/components/tasks/TaskForm.vue:53-80（`topLevelTasks`、`subtasksByParent`、`progressText`） |
| AC36 | 通過 | backend/services/productivity.py:44 |
| AC37 | 通過 | backend/tests/integration/test_manual_task_api.py:393-398 |
| AC38 | 通過 | backend/schemas/manual_task.py（`ManualTaskUpdate` 沒有這四個欄位）；backend/crud/manual_task.py:423（寫回時也排除）；backend/tests/integration/test_manual_task_api.py:406-421 |
| AC39 | 通過（極少見的連續失敗與同時操作，見 #1、#2） | backend/crud/manual_task.py:184-188、208-292；backend/crud/manual_task.py:41-65 |
| AC40 | 通過（後端；前端沒有帶 key，見 #3） | backend/routers/manual_task.py:174-177、207-209、215-226；backend/crud/manual_task.py:221-229 |

### 發現

| # | 分類 | 阻擋 | 涉及安全／架構 | 說明 | 依據（檔案:行號） | 建議 |
|---|---|---|---|---|---|---|
| 1 | Improvement Suggestion | 否 | 否 | 實作 agent 回報的第 1 點。<br><br>**現象**：新增子任務（`POST /manual-tasks/{task_id}/subtasks`）時，先寫入子任務文件，再更新主任務的 `subtask_ids`。如果更新主任務時發生資料庫例外，接著刪除剛寫入的子任務也失敗，就會留下一筆帶著 Idempotency-Key、但不在 `subtask_ids` 裡的子任務文件。之後用同一個 key 重送，`_subtask_result_for_key` 找到這筆文件，又發現它不在順序裡，就判定成「同一個請求還在處理中」，**永遠回 409**，也永遠不會重新嘗試寫入。<br><br>刪除時也會留下殘留文件：`$pull` 成功、但刪除子任務文件失敗。不過那時第一次新增早就成功了，用舊的 key 重送本來就不太會發生。<br><br>**影響範圍**：照 ADR 0004 的讀取規則，殘留的文件不會顯示、不會排程、也不會計入統計，所以 AC39 成立。要兩次資料庫寫入接連失敗才會發生；目前的前端也沒有帶這個 key（見 #3），只有自己帶 key 重送的 API client 會遇到。ADR 0004「影響」一節已經接受會有殘留文件，只是沒有清理的機制。<br><br>不算 Missing AC：規格沒有定義「第一次請求失敗後，用同一個 key 重送」的結果。這個情況比較接近重送行為的改善。 | backend/crud/manual_task.py:221-229、260-264、285-286；backend/routers/manual_task.py:174-177、215-226；docs/decisions/0004-subtask-order-on-parent.md:31 | (a) `_subtask_result_for_key` 遇到「不在順序裡」的文件時，如果它的 `created` 已經超過合理的處理時間（例如 1 分鐘），就刪掉它，照新請求繼續處理；或 (b) 加一個定期清理的機制，刪掉不在任何主任務 `subtask_ids` 裡的子任務。 |
| 2 | Improvement Suggestion | 否 | 否 | 實作 agent 回報的第 2 點。<br><br>**現象**：刪除子任務時，router 先用讀到的數量檢查「不是最後一個」，再刪 Google Calendar 上的事件，最後才 `$pull`。兩個請求同時刪除主任務僅剩的兩個子任務 A、B 時，兩邊都通過第一步的檢查，也都刪掉了自己還沒開始的事件，但只有一邊的 `$pull` 成功。另一邊回 400「只剩這一個子任務」，它的子任務還在，`calendar_event_id` 卻指向一個已經刪掉的事件。<br><br>**影響**：系統裡沒有任何地方會清掉 `calendar_event_id`（grep backend 只找到寫入的 `set_calendar_event_id`），排程又會跳過有 `calendar_event_id` 的任務（backend/services/scheduler.py:236-239），所以這個子任務之後**再也不會被排程**，畫面上看起來卻像已經排入行事曆。要解開，使用者得先插入一個新的階段，再刪掉它。後面的階段不受影響：事件不存在時，`get_calendar_event_ends` 回 None，不加先後限制。<br><br>**觸發條件**：同一個分頁也做得到，因為 `onDeleteSubtask` 沒有送出中的鎖，前一個刪除還在進行時，可以確認刪除下一列。<br><br>**分類理由**：AC39 的「同時操作不少於 1 個」成立；「規格不做」也已經接受 AC33 那種「事件刪了、任務留著」的結果；main 上使用者在 Google 手動刪掉事件，也會造成同樣「卡住」的狀態。所以列為改善，不阻擋。 | backend/routers/manual_task.py:290-294；backend/crud/manual_task.py:276-284；backend/services/scheduler.py:236-239；frontend/composables/useTaskForm.ts:392-405 | (a) `delete_subtask` 丟 `InvalidRequestError` 時，如果這次確實刪了這個子任務的事件，就把它的 `calendar_event_id` 清成 None，讓它能重新排程；並且 (b) 前端的 `onDeleteSubtask` 在送出中時停用其他刪除按鈕。另外可以考慮讓排程把「事件已不存在」的任務當成未排入（這也能處理 main 上原本就有的情況），可以另開 issue。 |
| 3 | Improvement Suggestion | 否 | 否 | **現象**：AC40 讓新增子任務的 API 支援 Idempotency-Key，但前端的 `onAddSubtask` 只帶 `Authorization`，沒有帶 `Idempotency-Key`。一次建立的流程（`onSubmit`）則有帶。<br><br>**影響**：目前前端只靠 `submitting` 防連點，沒有自動重試（`$fetch` 預設不會重試 POST），所以不會重複新增。但如果請求其實成功、回應在網路上遺失，使用者再按一次，就會多一個子任務；第 1 輪 #5 想透過 AC40 避免的就是這個情況，目前前端沒有用到這個保護。規格只要求 API 支援 key，所以不算違反 AC。 | frontend/composables/useTaskForm.ts:363-372（對照 :87-90、:301） | 和 `onSubmit` 一樣，在打開新增子任務草稿時產生一個 key，成功後再換一個新的；失敗時保留原本的 key 重送。 |
| 4 | Improvement Suggestion | 否 | 否 | AC6 改成「上下都會調整」之後，有兩處註解和一處實作計畫沒有跟著更新，讀者會誤以為只有「比前一個階段高」才會調整，或以為階段編號存在子任務上：<br>(a) `ManualTaskWithSubtasksOut.priority_adjusted_stages` 的註解寫「比前一個階段高、被調成和前一個階段一樣」；<br>(b) 前端型別 `priority_adjusted_stages` 的註解寫「被調成和前一個階段一樣」；<br>(c) 規格「實作計畫」第 2 點還寫「插入或刪除子任務時，調整階段編號」，和 ADR 0004 的做法不一致。 | backend/schemas/manual_task.py:109；frontend/types/manualTask.ts:31；docs/specs/staged-tasks.md:119 | (a)、(b) 改成「AI 推斷的優先序被調到前後階段之間的階段編號」；(c) 改成「插入、刪除只改主任務的 `subtask_ids`（ADR 0004）」。 |

### 其他檢查

- **安全**：沒有發現漏洞。
  - `subtask_ids`、`parent_id`、`is_parent` 只由後端寫入。PUT 時，`ManualTaskUpdate` 不接受這些欄位，`update_manual_task_by_id` 寫回時也排除了它們（backend/crud/manual_task.py:423）。
  - `get_subtasks` 用 `user_id` 限定查詢，`_ordered_subtasks` 也會比對 `parent_id`，所以就算陣列裡出現別人的 id，也讀不到（backend/crud/manual_task.py:41-53、167-175）。
  - Idempotency-Key 依使用者查詢；同一個 key 用在別的主任務時回 409（backend/routers/manual_task.py:216-220）。
- **架構**：ADR 0004 已加進 `docs/decisions/README.md`，`docs/architecture.md` 的 `manual_tasks` 說明也已更新。沒有新增 collection、服務或外部依賴，也沒有用交易。這個功能還沒合併進 main，沒有線上資料要搬移。
- **CLAUDE.md 要求的同步**：`docs/api.md` 已經寫上新增子任務的 API 支援 `Idempotency-Key`；`frontend/types/` 和後端的 schema 一致。
- **規格同步**：第 1 輪後改的 AC6、AC12、AC25、AC26、AC37、AC38、AC39、AC40 和假設 1 都記進了「修改紀錄」（docs/specs/staged-tasks.md:185-191）。新增的測試都對應得到某條驗收條件。

### 實作 agent 回報的 2 點，判定如下

1. **新增或刪除中途連續失敗留下的子任務文件，讓同一個 key 一直回 409**：見 #1。Improvement Suggestion，不阻擋，不涉及安全。照 ADR 0004 的讀取規則，使用者看到的結果正確，所以 AC39 成立；規格沒有定義「第一次失敗後用同一個 key 重送」的結果；前端目前也沒有帶這個 key（#3）。
2. **同時刪除最後兩個子任務，敗的一方事件已經刪掉**：見 #2。Improvement Suggestion，不阻擋，不涉及安全。AC39 的數量限制成立，結果也和規格已經接受的 AC33（事件刪了、任務留著）同一類。不過留下來的子任務會一直帶著失效的 `calendar_event_id`、不再被排程，建議清掉這個欄位，並在前端加送出中的鎖。

## 處理結果

| # | 處理 | 決定者 | 根本原因 | commit / issue / advisory 編號 |
|---|---|---|---|---|
| 1 | 不阻擋，開 issue，不在這個 PR 修 | 規則 | — | #36 |
| 2 | 不阻擋，開 issue，不在這個 PR 修 | 規則 | — | #37 |
| 3 | 不阻擋，開 issue，不在這個 PR 修 | 規則 | — | #38 |
| 4 | (c) 規格的實作計畫改成 ADR 0004 的做法（文件同步）；(a)、(b) 程式註解開 issue | 主 session（文件同步）；規則 | — | (c) 同一個 commit；(a)(b) #39 |
