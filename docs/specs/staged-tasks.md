# 階段任務（主任務拆成子任務）

- 狀態：已核准
- PR：（實作後填）

## 背景

使用者想把一件手動任務拆成幾個階段，例如一份報告拆成三個階段。每個階段是一個子任務，可以在不同時間完成、有不同的優先序，但都連到主任務上，類似 Jira 把 Epic 拆成 Story。目前手動任務只有單層，排程以一筆任務為單位。

需求釐清：/feature-grill（實驗），問答 6 輪

## 需求

1. 手動任務可以有 1～10 個子任務（只有兩層）。新增任務時可以一起建立子任務；主任務建立後，也可以在任意位置插入或刪除子任務。
2. 主任務只當容器：本身沒有優先序和時長、不排程、不計入統計，狀態依子任務自動計算。
3. 子任務是有順序的階段：排程時，後面的階段一定排在前一個階段結束之後；後面階段的優先序不能高於前面的階段，截止日也有先後限制。
4. 刪除主任務或子任務時，一併刪除 Google Calendar 上還沒開始的事件。
5. 任務列表與排程頁顯示主任務和子任務之間的關係。

## 不做

- AI 自動拆分階段；一鍵把所有子任務標成完成。
- 子任務建立後調整階段順序（要改順序就刪掉再插入）。
- 拆分 GitHub / Jira / Moodle 項目；子任務移到別的主任務，或脫離主任務變成一般任務。
- 一般任務刪除時一起刪事件，見 #30（一般任務的刪除行為不變）。
- 刪除事件中途失敗時，不補建已刪掉的事件，也不在刪除前預先檢查。

## 假設

由開發者交給我決定的細節，以及我為了寫規格另外做的判斷：

1. **資料模型**：不新增 collection，在 `manual_tasks` 加三個欄位：子任務有 `parent_id`、`stage`（從 1 開始的階段編號），主任務有 `is_parent: true`。主任務的狀態與進度在讀取時才計算，不存進資料庫，避免和子任務的狀態不一致。
2. **前一個階段的事件時間（D19）**：產生排程建議時，用 Google Calendar 的 events.get 取得最新的事件時間，不另外存。使用者在 Google 上拖動事件，也會反映到排程。
3. **沒有截止日的前面階段（D20）**：期限是「下一個階段的期限 − 下一個階段的時長」，從最後一個有截止日的階段往前遞推。這個期限只用在排程，不寫進資料庫，畫面上也不顯示。
4. **一次建立的原子性（D26）**：測試用的 mongomock 不支援交易。做法是先完成所有驗證與 AI 推斷，再一次 `insert_many`；寫入失敗時，刪掉這次已經寫入的文件。
5. **AI 推斷失敗**：沿用現有行為，套用預設值（中、60 分鐘），不算建立失敗（`infer_missing_task_fields` 本來就不會丟例外）。
6. **主任務帶了優先序或時長**：建立或修改主任務時，如果請求帶了 `priority`、`duration`、`inference_hint`、`status`，回 400，不靜默忽略。
7. **確認排程（從 D18 推出）**：寫入行事曆時，前一個階段寫入失敗或已經失效，同一個主任務後面的階段也不寫入，原因寫「前一個階段寫入失敗」。
8. **排程精靈也要驗證（從 D16 推出）**：`PATCH /schedule/tasks/fields` 修改子任務的截止日時，也要受 AC8 的限制。
9. **緩衝時間**：排程偏好的 `buffer_minutes` 照樣套用在相鄰的階段之間。
10. **「還沒開始」的判斷**：事件的開始時間晚於現在才算還沒開始。系統只會建立有時間的事件，沒有全天事件的情況。
11. **不需要 Google 時就不呼叫**：要刪除的子任務都沒有行事曆事件時，刪除完全不呼叫 Google，沒有連接 Google 的使用者也能刪。
12. **新增子任務的 API**：`POST /manual-tasks/{task_id}/subtasks`，body 是子任務欄位加 `position`（1～N+1，預設是最後）。AI 推斷參考主任務的標題和描述，限流 20/分。
13. **一次建立的 API**：`POST /manual-tasks/` 的 `ManualTaskInput` 加選填的 `subtasks`。沒有這個欄位時，行為和現在完全相同；有這個欄位時，`Idempotency-Key` 重送會回傳第一次建立的主任務與子任務。
14. **首頁的筆數上限**：Dashboard 用 `TaskForm limit` 限制顯示筆數時，主任務算一筆，子任務預設收合、不另外計算。

## 驗收條件

| # | 條件 |
|---|---|
| **建立** | |
| AC1 | 新增任務時加了 1～10 個子任務，送出後建立 1 個主任務和對應的子任務；子任務依填寫順序成為階段 1～N，回應包含主任務與子任務 |
| AC2 | 不加子任務時，新增任務的行為、欄位、AI 推斷都和現在一樣 |
| AC3 | 子任務超過 10 個、帶了 `subtasks` 但是空的，或有子任務沒有標題時，不建立任何資料，回 422 / 400 |
| AC4 | 任何一筆子任務驗證失敗，或寫入資料庫失敗時，主任務和子任務都不建立；前端保留表單內容並顯示錯誤 |
| AC5 | 需要 AI 推斷的子任務只呼叫一次 Gemini，推斷時參考主任務的標題和描述；呼叫失敗時套用預設值，不算建立失敗 |
| AC6 | AI 推斷出的優先序比前一個階段高時，自動調成和前一個階段一樣；建立成功的提示會說明哪些階段被調整 |
| AC7 | 使用者自己填的優先序比前一個階段高時，擋下並指出是哪一個階段（高 > 中 > 低） |
| AC8 | 有填截止日時：子任務晚於主任務，或後面的階段早於前面的階段，擋下並指出是哪一個階段 |
| AC9 | 一次建立主任務加子任務，只算一次請求，套用現有的 20/分限流 |
| **新增子任務、轉換既有任務** | |
| AC10 | 對既有的主任務新增子任務，可以指定插入位置（預設是最後）；插入後，後面的階段編號依序加 1。新的子任務要同時符合前後兩個階段的優先序（AC7）與截止日（AC8）限制，AI 推斷的優先序照 AC6 調整 |
| AC11 | 已經有 10 個子任務的主任務，不能再新增 |
| AC12 | 對一般任務新增第 1 個子任務後，它變成主任務：本身的優先序、時長、AI 推斷理由清空。新增表單預先填入原本的優先序和時長，使用者可以修改 |
| AC13 | 已完成或已寫入行事曆的一般任務，不能新增子任務，擋下並說明原因 |
| AC14 | 不能對子任務再新增子任務 |
| AC15 | 只能對自己的任務新增子任務；別人的任務 id 回 404，和現有的查詢行為一致 |
| **狀態與編輯** | |
| AC16 | 主任務的狀態依子任務計算：全部完成 → Done；有任何一個已完成或進行中 → In Progress；其他 → To Do。回應附上進度（已完成數 / 總數） |
| AC17 | 主任務的狀態不能手動改：`PUT` 帶了 `status`，或對主任務呼叫 `PATCH /schedule/tasks/done`，回 400；列表上主任務的完成勾選框不能按 |
| AC18 | 子任務標記完成不限順序，第 1 階段還沒完成也可以先完成第 2 階段 |
| AC19 | 主任務只能修改標題、描述、截止日；帶了優先序或時長回 400。把主任務的截止日改到早於任何一個子任務的截止日時，擋下 |
| AC20 | 子任務可以修改的欄位和一般任務一樣。透過 `PUT`、排程精靈（`/schedule/tasks/fields`），或排程頁拖拉（`/schedule/reorder`）修改時，只要違反 AC7 或 AC8，就回 400，資料保持不變 |
| **排程** | |
| AC21 | 排程建議不排主任務；子任務照階段順序排，第 k 階段的開始時間不早於第 k−1 階段的結束時間加上緩衝時間 |
| AC22 | 前一個階段排不進去時，後面的階段都列進「無法安排」，原因寫「前一個階段還沒排入」 |
| AC23 | 前一個階段已完成時，後面的階段不受先後限制 |
| AC24 | 前一個階段已寫入行事曆但還沒完成時，後面的階段排在那個事件（Google 上最新的時間）結束之後；事件已經不存在時，不受先後限制，前一個階段也不重新排 |
| AC25 | 前面的階段沒有截止日、後面的階段有時，前面的階段依假設 3 的期限排程；放不進期限內就照 AC22 處理 |
| AC26 | 確認排程時，前一個階段寫入失敗或已失效，同一個主任務後面的階段也不寫入，原因寫「前一個階段寫入失敗」 |
| AC27 | 排程頁不出現主任務；子任務標上主任務名稱和「階段 k/N」。拖拉時，只要會讓後面的階段優先序高於前面的階段，或在同一欄內把後面的階段拖到前面的階段上面，前端就直接擋下並提示原因，不送出請求 |
| **刪除** | |
| AC28 | 刪除主任務時，刪掉主任務和所有子任務，並刪除子任務在 Google Calendar 上還沒開始的事件；已經開始或已經過去的事件保留。確認對話框寫出會一起刪除幾個子任務 |
| AC29 | 刪除子任務時，也刪除它還沒開始的事件；後面階段的編號依序往前遞補 |
| AC30 | 主任務只剩一個子任務時，這個子任務不能刪，回 400，並提示改刪主任務 |
| AC31 | 要刪的事件已經不存在（Google 回 404 / 410）時，當作刪除成功 |
| AC32 | 需要刪事件，但 Google 授權失效或沒有連接時，什麼都不刪，回應要求重新連接，前端沿用現有的重新連接提示 |
| AC33 | 刪除事件中途失敗（Google 5xx、429、網路錯誤）時，所有任務都保留，已經刪掉的事件不復原，回應提示重試；重試時，已經不存在的事件照 AC31 處理 |
| AC34 | 一般任務的刪除行為不變（不刪行事曆事件） |
| **顯示與統計** | |
| AC35 | 任務列表上主任務佔一列，顯示進度（例如 1/3），可以展開看子任務；子任務標上「階段 k/N」 |
| AC36 | 生產力統計（`/analytics/productivity`）不計入主任務，只算子任務和一般任務 |
| **登入與資料** | |
| AC37 | 沒登入時呼叫新增子任務的 API 回 401，沿用現有的登入驗證 |
| AC38 | `parent_id`、`stage`、`is_parent` 只能由後端寫入；`ManualTaskUpdate` 不接受這三個欄位，client 沒辦法把子任務掛到別人的主任務上，也沒辦法竄改階段編號 |

## 不適用的情境

| 情境 | 原因 |
|---|---|
| 載入中 | 沿用現有任務列表的 Skeleton，以及送出中按鈕停用的機制，沒有新的載入狀態 |
| 空資料 | 沒有任何主任務時，列表和現在一樣；帶空的 `subtasks` 的情況已列在 AC3 |
| 無權限（非本人） | 已列在 AC15、AC38，其他沿用現有「只能操作自己的任務」的檢查 |

## 實作計畫

**後端**

1. `schemas/manual_task.py`：
   - 加 `SubtaskInput`。`ManualTaskInput` 加 `subtasks: Optional[list[SubtaskInput]]`（1～10 個）。
   - `ManualTaskOut` 加 `parent_id`、`stage`、`is_parent`、`progress`；`priority`、`duration` 對主任務可以是空值。
   - 加 `SubtaskCreate`（子任務欄位加 `position`）。
2. `crud/manual_task.py`：
   - 主任務的狀態與進度計算。
   - 階段鏈的驗證（優先序與截止日），新增子任務、建立後的 PUT、reorder、`/schedule/tasks/fields` 都共用同一個函式。
   - 一次建立：`insert_many` 加寫入失敗時的清除（假設 4）。
   - 插入或刪除子任務時，調整階段編號。
3. `services/task_inference.py` 與 `prompts/`：加批次推斷函式，一次推斷多個子任務，參考主任務的標題和描述；失敗時全部套用預設值。
4. `routers/manual_task.py`：
   - `POST /` 支援 `subtasks`。
   - 新增 `POST /{task_id}/subtasks`。
   - `PUT` 檢查主任務與子任務各自可以改的欄位。
   - `DELETE` 依主任務、子任務、一般任務分開處理。
5. `services/google_calendar_client.py`：加 `get_calendar_event`、`delete_calendar_event`。
   `services/google_calendar.py`：加「刪除還沒開始的事件」，404 / 410 當作成功，其他錯誤照 AC32、AC33 處理；權杖取得沿用 `_get_access_token_and_primary_calendar_id`。
6. `crud/schedulable_items.py`、`schemas/schedule.py`：
   - `SchedulableTaskOut` 加 `parent_id`、`parent_title`、`stage`、`stage_count`、`is_parent`。
   - `set_done` 對主任務擋下（AC17）。
   - `reorder_schedulable_items`、`update_scheduling_fields` 呼叫階段鏈驗證。
7. `services/scheduler.py`：`build_schedule_suggestion` 跳過主任務，並加階段鏈限制：
   - 處理順序：前一個階段一定先處理。
   - 最早開始時間：前一個階段的結束時間加上緩衝；前一個階段已寫入行事曆時，用事件的結束時間。
   - 推遞期限（假設 3），以及 AC22～AC25。
   - 事件時間由 `routers/schedule.py` 的 `_compute_suggestion` 先向 Google 查好，再傳進去，scheduler 本身維持純函式。
   - `check_suggestion_still_valid` 與 confirm 加上 AC26。
8. `services/productivity.py`（或 analytics router）：排除主任務（AC36）。
9. `core/database.py`：加 `(user_id, parent_id)` 索引。

**前端**

10. `types/manualTask.ts`、`types/schedulableTask.ts`：同步後端的新欄位（CLAUDE.md 規定要手動同步）。
11. `composables/useTaskForm.ts`、`components/tasks/TaskForm.vue`：
    - 表單加「拆成階段」區塊，可以新增或移除子任務列，最多 10 個。
    - 編輯主任務時顯示子任務清單，可以在指定位置插入、刪除。
    - 一般任務新增子任務時，預先填入原本的值（AC12）。
    - 列表顯示主任務列，含進度、可展開、勾選框停用；子任務標上階段。
    - 刪除主任務的確認文字（AC28）。
    - 刪除需要重新連接 Google 時，沿用 `useGoogleCalendarAuth` 的 `reauthToast`。
12. `pages/schedule.vue`：過濾掉主任務；子任務加上主任務名稱與階段標籤；拖拉的前端檢查（AC27）。

**文件**

13. `docs/api.md`：新增 `POST /manual-tasks/{task_id}/subtasks`（限流 20/分），更新 `POST /`、`PUT`、`DELETE` 的說明。

## 測試對應

| AC | 測試 |
|---|---|
| AC1–AC4、AC9 | `tests/integration/test_manual_task_api.py`（一次建立的成功、驗證失敗、限流）；`tests/unit/test_manual_task_crud.py`（寫入失敗時的清除） |
| AC5、AC6 | `tests/unit/test_task_inference.py`（批次推斷、失敗時套用預設值）；`tests/unit/test_manual_task_router.py`（優先序自動調整） |
| AC7、AC8、AC10、AC19、AC20 | `tests/unit/test_manual_task_crud.py`（階段鏈驗證：插入位置、前後比對）；`tests/unit/test_schedule_router.py`（reorder、fields 被擋下） |
| AC11–AC15、AC37、AC38 | `tests/integration/test_manual_task_api.py`（新增子任務的成功、10 個上限、轉換、已完成或已排入被擋、子任務不能再拆、別人的任務 404、沒登入 401、Update 不接受這三個欄位） |
| AC16–AC18 | `tests/unit/test_manual_task_crud.py`（狀態計算）；`tests/unit/test_schedule_router.py`（對主任務 set_done 回 400） |
| AC21–AC25 | `tests/unit/test_scheduler.py`（先後順序、緩衝時間、前一個排不進、已完成、已排入用事件時間、事件不存在、推遞期限） |
| AC26 | `tests/unit/test_scheduler.py`（`check_suggestion_still_valid`）；`tests/unit/test_schedule_router.py`（confirm） |
| AC28–AC34 | `tests/unit/test_google_calendar_service.py`（只刪還沒開始的、404 / 410 當成功、授權失效、中途失敗）；`tests/integration/test_manual_task_scenario.py`（建立 → 排入 → 刪除主任務 → 重試） |
| AC36 | `tests/unit/test_productivity.py` |
| AC2、AC4、AC12、AC17、AC35 | `frontend/tests/composables/useTaskForm.test.ts`、`frontend/tests/components/TaskForm.test.ts`（拆成階段的表單、失敗時保留內容、預先填入原本的值、主任務列與勾選框停用） |
| AC27 | `frontend/tests/pages/` 的 schedule 頁測試（過濾主任務、拖拉被擋） |
| AC28、AC32 | `frontend/tests/components/TaskForm.actions.test.ts`（確認文字、重新連接提示） |

## 驗證方式

- 後端：`cd backend && pyright && pytest`。
- 前端：`cd frontend && npm run lint && npm run typecheck && npm run test`。
- 開發者的 dev server 開著，所以不在本機跑 e2e，交給 CI（e2e 有既有的間歇性失敗，見 #28）。

## 修改紀錄

| 日期 | 修改 | 原因 | 確認者 |
|---|---|---|---|
