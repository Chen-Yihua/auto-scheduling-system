# staged-tasks：審查第 1 輪

- 規格：[docs/specs/staged-tasks.md](../specs/staged-tasks.md)
- PR：#31
- 日期：2026-11-05
- 審查的版本：`088948f`（`origin/main...HEAD`）
- 結果：有阻擋（Missing Acceptance Criteria 3、Test Gap 1；不阻擋：Improvement Suggestion 4）

## 審查報告

我依規格審查了 088948f，沒有修改任何檔案。本機檢查全部通過：
- 後端：`pyright` 0 errors，`pytest` 609 passed
- 前端：`npm run lint`、`npm run typecheck` 通過，`vitest` 295 passed

沒有 e2e 的結果，因為開發者的 dev server 開著，這次沒跑。

### 驗收條件

| AC | 結果 | 依據（檔案:行號） |
|---|---|---|
| AC1 | 通過 | backend/routers/manual_task.py:67-97；backend/crud/manual_task.py:149-175；backend/tests/integration/test_manual_task_api.py（test_ac1_create_with_subtasks_returns_parent_and_stages） |
| AC2 | 通過 | backend/schemas/manual_task.py:44-59（沒有 subtasks 時 status 仍必填）；backend/routers/manual_task.py:128；test_manual_task_api.py（test_ac2_…） |
| AC3 | 通過（422） | backend/schemas/manual_task.py:19-35、54；test_manual_task_api.py（test_ac3_…，參數化四種情況） |
| AC4 | 通過 | 驗證都在寫入前：backend/routers/manual_task.py:72-77；寫入失敗時清除：backend/crud/manual_task.py:160-171；backend/tests/unit/test_manual_task_crud.py:410；前端保留表單：frontend/composables/useTaskForm.ts:313-317 |
| AC5 | 通過 | backend/services/task_inference.py:61-106；backend/routers/manual_task.py:42-64 |
| AC6 | 通過（重送時例外，見 #3） | backend/crud/manual_task.py:99-112；frontend/composables/useTaskForm.ts:237-245 |
| AC7 | 通過 | backend/crud/manual_task.py:83-90 |
| AC8 | 通過 | backend/crud/manual_task.py:64-80 |
| AC9 | 通過 | backend/routers/manual_task.py:107-108；test_manual_task_api.py（test_ac9_…） |
| AC10 | 通過（規格沒涵蓋的情境見 #2） | backend/routers/manual_task.py:188-205；backend/crud/manual_task.py:178-184 |
| AC11 | 通過 | backend/routers/manual_task.py:177-180 |
| AC12 | 通過（另外多清了一些欄位，見 #4） | backend/crud/manual_task.py:187-195；frontend/composables/useTaskForm.ts:180-191 |
| AC13 | 通過 | backend/routers/manual_task.py:181-185 |
| AC14 | 通過 | backend/routers/manual_task.py:175-176 |
| AC15 | 通過 | backend/routers/manual_task.py:174（`get_manual_task_by_id` 帶 user_id 查） |
| AC16 | 通過 | backend/crud/manual_task.py:20-48；backend/tests/unit/test_manual_task_crud.py:320、329 |
| AC17 | 通過 | backend/routers/manual_task.py:237-238；backend/crud/schedulable_items.py:130-131；frontend/components/tasks/TaskForm.vue:495-497 |
| AC18 | 通過 | backend/crud/schedulable_items.py:122-140（沒有限制完成順序） |
| AC19 | 通過 | backend/routers/manual_task.py:237-239；backend/crud/manual_task.py:305-308 |
| AC20 | 通過 | backend/crud/manual_task.py:285-313；backend/crud/schedulable_items.py:110-113 |
| AC21 | 通過 | backend/services/scheduler.py:233-236、275-290、343-352 |
| AC22 | 通過 | backend/services/scheduler.py:292-296 |
| AC23 | 通過 | backend/services/scheduler.py:283-284 |
| AC24 | 通過 | backend/routers/schedule.py:78-96；backend/services/google_calendar.py:180-202；backend/services/scheduler.py:285-287 |
| AC25 | 字面上通過，但行為有缺口（見 #6） | backend/services/scheduler.py:25-52、299 |
| AC26 | 通過（和 AC23 有個邊界衝突，見 #8） | backend/services/scheduler.py:371-399；backend/services/google_calendar.py:141-146 |
| AC27 | 實作通過，測試不足（見 #7） | frontend/composables/useScheduleWizard.ts:73；frontend/utils/stages.ts:9-53；frontend/pages/schedule.vue:470-492 |
| AC28 | 通過 | backend/routers/manual_task.py:263-266；backend/services/google_calendar.py:215-244；frontend/composables/useTaskForm.ts:409-412 |
| AC29 | 通過 | backend/routers/manual_task.py:267-273；backend/crud/manual_task.py:198-204 |
| AC30 | 通過 | backend/routers/manual_task.py:270-271 |
| AC31 | 通過 | backend/services/google_calendar.py:240-242 |
| AC32 | 通過 | backend/services/google_calendar.py:226-227、205-209；frontend/composables/useTaskForm.ts:223-230 |
| AC33 | 通過 | backend/services/google_calendar.py:210-212、243-246；先刪事件再刪任務：backend/routers/manual_task.py:265-273 |
| AC34 | 通過 | backend/routers/manual_task.py:274-275 |
| AC35 | 通過 | frontend/components/tasks/TaskForm.vue:53-80、456-505 |
| AC36 | 通過 | backend/services/productivity.py:44 |
| AC37 | 和規格文字不符（實際回 403），見 #1 | backend/core/security.py:20；.venv/lib/python3.12/site-packages/fastapi_clerk_auth/__init__.py:153；backend/tests/integration/test_manual_task_api.py:393-398 |
| AC38 | 通過 | backend/schemas/manual_task.py:61-69（ManualTaskUpdate 沒有這三個欄位，多帶會被忽略）；test_manual_task_api.py（test_ac38_…） |

### 發現

| # | 分類 | 阻擋 | 涉及安全／架構 | 說明 | 依據（檔案:行號） | 建議 |
|---|---|---|---|---|---|---|
| 1 | Missing Acceptance Criteria | 是（開發者可決定只改規格文字） | 否 | AC37 寫「沒登入回 401」，但專案現有的登入驗證（`ClerkHTTPBearer(auto_error=True)`）沒帶或帶無效 token 時回 **403**，`docs/api.md:3` 也寫 403。實作照現有行為走，這樣是對的，錯的是驗收條件。另外，測試寫 `status_code in (401, 403)`，等於沒有固定住任何一個值。缺的情境：未登入時的實際狀態碼。影響範圍：只有規格文字和測試的斷言。不涉及未定義的產品行為，安全性也不受影響（請求照樣被擋）。 | backend/core/security.py:20；fastapi_clerk_auth/__init__.py:153；docs/api.md:3；docs/specs/staged-tasks.md:94；backend/tests/integration/test_manual_task_api.py:398 | 建議驗收條件改成「沒登入時呼叫新增子任務的 API 回 403，沿用現有的登入驗證」，並記進「修改紀錄」；測試改成斷言 `== 403`。 |
| 2 | Missing Acceptance Criteria | 是（開發者決定另開 issue 才解除） | 否 | 使用者沒填優先序、由 AI 推斷時，規格只定義了「推斷結果比**前一個**階段高 → 調低」（AC6）。推斷結果比**後一個**階段低時，`validate_stage_priorities` 會回 400，訊息寫「階段 k+1 的優先序不能高於階段 k」，但階段 k 的優先序不是使用者填的。兩條路徑都會遇到：(a) 在中間插入子任務（AC10），新的階段推斷成「低」、後一個階段是「中」；(b) 一次建立時，前面的階段留空讓 AI 推斷，後面的階段使用者填了較高的優先序，例如階段 1 留空推斷成「中」、階段 2 使用者填「高」。結果是使用者沒做錯任何事，建立卻失敗，而且已經花掉一次 Gemini 呼叫。實作 agent 回報的第 2 點就是這個，這裡確認是規格缺漏，不是實作錯誤。涉及未定義的產品行為。 | backend/routers/manual_task.py:76-77、196-197；backend/crud/manual_task.py:99-112、83-90 | 建議驗收條件：「AI 推斷的優先序要落在前後兩個階段之間：比前一個階段高就調成前一個，比後一個階段低就調成後一個；兩種調整都在成功提示裡說明」。前後階段之間本來就保證「前 ≥ 後」，所以一定找得到合法的值。 |
| 3 | Improvement Suggestion | 否 | 否 | 建立任務的回應裡，`priority_adjusted_stages`（AI 推斷的優先序被調成和前一個階段一樣的階段編號）只出現在第一次的回應裡，沒有存進資料庫。如果第一次回應因為網路問題沒收到，前端用同一個 Idempotency-Key 重送，會拿到已建立的主任務和子任務，但這個欄位是空的，成功提示就不會說明哪些階段被自動調整。影響範圍只有重送時的提示文字，資料本身正確。 | backend/schemas/manual_task.py:108-110；backend/routers/manual_task.py:121-123 | 可以在被調整的子任務文件上記一個標記（例如在 `inferred_fields` 加一個值，或另存一個欄位），重送時再組回 `priority_adjusted_stages`；或在規格寫明重送時不提供這個資訊。 |
| 4 | Improvement Suggestion | 否 | 否 | 一般任務轉成主任務時（`convert_to_parent`），除了 AC12 列的優先序、時長、AI 推斷理由，還清掉了 `status`、`completed_at`、`inferred_fields`。這和假設 1（主任務的狀態不存資料庫）、AC13（已完成的不能轉）一致，不算違反規格。但有兩件事規格沒寫：(a) 原本是 In Progress 的任務，轉換後狀態依子任務重新計算，新的子任務預設是 To Do，所以主任務會從 In Progress 變回 To Do，而且畫面上沒有提示；(b) `inference_hint` 沒有被清掉，主任務的 API 回應裡還會帶著它，但主任務照理不能有「給 AI 的提醒」（假設 6）。 | backend/crud/manual_task.py:187-195；backend/routers/manual_task.py:27（PARENT_ONLY_FROM_SUBTASKS 包含 inference_hint） | 建議 `$unset` 也清掉 `inference_hint`；新增表單預先填入原本狀態，或在規格補一句「轉換後狀態依子任務重新計算」；這些多清的欄位記進規格的假設或修改紀錄。 |
| 5 | Improvement Suggestion | 否 | 否 | 插入、刪除子任務時，調整階段編號和寫入是分開的幾次資料庫操作。插入是 `update_many $inc` 再 `insert_one`；刪除是 `delete_one` 再 `update_many`；一般任務轉換是 `convert_to_parent` 再 `insert_subtask`。中途失敗會留下空號，或留下沒有子任務的主任務（進度 0/0）。兩個分頁同時用預設位置新增子任務，會出現重複的階段編號，也可能超過 10 個上限。這個 endpoint 沒有 Idempotency-Key，前端只靠 `submitting` 防連點。影響比看起來大：排程和確認都用「(parent_id, stage − 1)」精確查前一個階段，所以只要有空號或重號，那兩個階段之間的先後限制就會在沒有任何提示的情況下消失（AC21），排程頁也可能顯示「階段 4/3」。規格的假設 4 只處理了一次建立的原子性。 | backend/crud/manual_task.py:178-204；backend/routers/manual_task.py:199-202、273；backend/services/scheduler.py:18-21、233；backend/routers/schedule.py:80-85；backend/crud/schedulable_items.py:71-78 | 可以考慮：正式環境用 MongoDB 交易（mongomock 不支援，測試可以另外處理）；或在排程和驗證時改用「依 stage 排序後的相鄰關係」，不依賴編號連續；或在 `(user_id, parent_id, stage)` 加唯一索引，擋下重號。 |
| 6 | Missing Acceptance Criteria | 是（開發者決定另開 issue 才解除） | 否 | 推遞期限（假設 3）只拿來當「必須在這之前排完」的截止點，沒有參與現有的「24 小時內到期的任務一律先排」規則。有截止日的後面階段雖然會排到最前面，但它要等前一個階段先排，所以緊急性也跟著失效。我用 `python -I -c` 實際跑了一次：3 小時的空檔，兩個 60 分鐘的 High 一般任務，加上一個兩階段的任務（階段 1 沒有截止日、Low；階段 2 Low、3 小時後到期）。結果是 X1、X2 先排，階段 1「截止日前沒有足夠的空檔」，階段 2「前一個階段還沒排入」。條件相同的單一任務（Low、3 小時後到期）則會排在最前面。所以拆成階段反而讓快到期的工作排不進去。AC25「依假設 3 的期限排程」沒說推遞期限算不算進緊急排序。涉及未定義的產品行為。 | backend/services/scheduler.py:240-249（sort_key 只看 `due_date`）、299（推遞期限只用在截止點）、343-352（後面的階段等前一個處理完） | 建議驗收條件：「推遞期限和使用者填的截止日一樣，適用 24 小時內優先排的規則；後面的階段是緊急的時候，它前面還沒排的階段也跟著提前處理」，並加對應的 scheduler 測試。 |
| 7 | Test Gap | 是 | 否 | AC27 說「只要會讓後面的階段優先序高於前面的階段」，前端就要擋下、不送出請求。這包括兩個方向：把後面的階段拖到更高的欄，以及把**前面的**階段拖到比後面階段更低的欄。前端測試只測了前者（把階段 2 拖到 High 欄）。`frontend/utils/stages.ts:39-41` 處理後者的分支沒有任何測試，也沒有 stages.ts 自己的單元測試。如果實作只檢查被拖的階段和它前面的階段，測試照樣全部通過，請求會被送出，再被後端 400 擋下，這違反 AC27 的「不送出請求」。 | frontend/utils/stages.ts:32-42；frontend/tests/pages/schedule.test.ts（AC27 的三個拖拉測試都是拖階段 2） | 補一個測試：階段 1、2 都在 Medium，把階段 1 拖到 Low 欄，斷言 `moveTask` 沒被呼叫，而且出現提示。 |
| 8 | Improvement Suggestion | 否 | 否 | 產生排程建議之後、按下確認之前，如果使用者把前一個階段標成完成，確認時前一個階段會被列為「任務已經完成」並加入失敗清單，導致後面的階段也被擋下，原因寫「前一個階段寫入失敗」。但 AC23 說前一個階段已完成時不受先後限制。前一個階段「已經排入行事曆」也一樣：它其實已經在行事曆上了，卻會擋住後面的階段。影響是使用者要重新產生排程才能寫入後面的階段。 | backend/services/scheduler.py:384-399 | `failed_ids` 只加入真的「寫入失敗或時段失效」的項目；「任務已經完成」「已經排入行事曆」不要連帶擋下後面的階段。或在規格裡寫明 AC26 的「已失效」包含這兩種情況。 |

### 實作 agent 自己回報的 5 點，判定如下

1. **AC37 回 401 還是 403**：屬於 #1，是規格的驗收條件寫錯（Missing Acceptance Criteria），會阻擋，但只要改規格文字並記進修改紀錄就能解除。實作沿用現有行為是對的；測試應該改成斷言 403。
2. **插入時 AI 推斷的優先序比後一個階段低，被 AC7 擋下**：屬於 #2，是規格缺漏，會阻擋。除了插入，一次建立也會遇到（前面的階段推斷、後面的階段使用者自己填）。
3. **重送時 `priority_adjusted_stages` 是空的**：屬於 #3，Improvement Suggestion，不阻擋。
4. **轉換時另外清掉 `status`、`completed_at`、`inferred_fields`**：屬於 #4，Improvement Suggestion，不阻擋。和假設 1 一致；另外發現 `inference_hint` 沒清，原本的 In Progress 狀態也會被重新計算掉。
5. **調整階段編號和寫入不是原子操作**：屬於 #5，Improvement Suggestion，不阻擋。不過有空號或重號時，排程會在沒有提示的情況下丟掉先後限制，建議另開 issue 處理。

### 其他檢查

- **安全**：沒發現漏洞。新的 endpoint 和 crud 都用 `user_id` 限定只查自己的資料；`parent_id`、`stage`、`is_parent`、`calendar_event_id` 都不能由 client 寫入；Google 事件 id 只來自資料庫；LLM 的輸出都經過 `_validated_inference` 驗證。
- **架構**：沒有新增服務或 collection。新增了 `(user_id, parent_id)` 索引，`docs/architecture.md` 已同步。
- **CLAUDE.md 要求的同步**：`docs/api.md` 已更新新 endpoint 和 PUT、DELETE、reorder、fields、done 的說明；`frontend/types/` 已同步新欄位。
- **規格同步**：新增的測試都對應得到某條驗收條件或假設，例如假設 6、11、13。驗收條件沒有被修改，所以修改紀錄是空的，這沒有不一致；但如果 #1 改了 AC37，就要記進修改紀錄。

## 處理結果

| # | 處理 | 決定者 | 根本原因 | commit / issue / advisory 編號 |
|---|---|---|---|---|
| 1 | 這個 PR 補：AC37 改成 403，測試只接受 403 | 開發者 | 登入狀態碼寫錯 | （待實作） |
| 2 | 這個 PR 補：AC6 加上「比後一個階段低時調成和後一個一樣」 | 開發者 | AI 推斷優先序的上下界 | （待實作） |
| 3 | 不阻擋，開 issue，不在這個 PR 修 | 規則 | — | #32 |
| 4 | 原本開 issue，開發者決定在這個 PR 修：清掉 `inference_hint`，AC12 補上轉換時清空的欄位；主任務狀態維持 AC16 | 開發者 | — | #33（PR 合併時關閉） |
| 5 | 原本開 issue，開發者決定在這個 PR 修：新增 AC39（原子性）、AC40（Idempotency-Key） | 開發者 | — | #34（PR 合併時關閉） |
| 6 | 這個 PR 補：AC25 加上推算期限也適用 24 小時規則 | 開發者 | 推算期限的緊急性 | （待實作） |
| 7 | 交回實作補測試 | 規則 | 拖拉驗證的測試不足 | （待實作） |
| 8 | 原本開 issue，開發者決定在這個 PR 修：AC26 改成已完成或已排入的前一個階段不擋後面的階段 | 開發者 | — | #35（PR 合併時關閉） |
