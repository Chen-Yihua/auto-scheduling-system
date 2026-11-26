# 刪除任務時一起刪除 Google Calendar 上的事件

- 狀態：已核准
- 等級：高風險（改變和外部系統 Google Calendar 同步的一致性、刪除中途失敗後的資料狀態，以及同時刪除時的資料狀態）
- issue：[#30](https://github.com/Chen-Yihua/auto-scheduling-system/issues/30)
- PR：[#111](https://github.com/Chen-Yihua/auto-scheduling-system/pull/111)

## 簡短說明

刪除一般任務、主任務、子任務時，系統裡的任務和它在 Google Calendar 上的事件一起刪掉，不管事件的時間、也不管任務有沒有完成。刪掉主任務唯一的子任務時，整個主任務一起刪除。刪除送出中停用刪除按鈕，避免重複送出。

## 背景

使用者刪掉一個已經排進 Google Calendar 的一般任務（沒有拆成階段的手動任務）後，任務從系統消失，但行事曆上的事件還在，對不到任何任務，使用者得自己去 Google 刪。

目前的行為（`main` `5591362`）：

- `DELETE /manual-tasks/{task_id}`（`backend/routers/manual_task.py:274-304`）分三種情況：
  - 主任務：先刪子任務在 Google Calendar 上還沒開始的事件，成功後刪主任務和所有子任務（[staged-tasks](staged-tasks.md) AC28）。
  - 子任務：先刪它還沒開始的事件，成功後刪子任務（staged-tasks AC29）。主任務只剩一個子任務時回 400「主任務只剩這一個子任務，不能刪除；要刪除請改刪主任務」（staged-tasks AC30，`backend/crud/manual_task.py:12`）。
  - 一般任務：只刪資料庫，不動行事曆（staged-tasks AC34）。
- 刪事件用 `delete_upcoming_calendar_events`（`backend/services/google_calendar.py:237-269`）：每個事件先向 Google 讀取，開始時間晚於現在才刪，已經開始或過去的保留；404／410 當作已刪除；一開始沒有連接時丟 `ReauthRequiredError`（409 `REAUTH_REQUIRED`），刪除迴圈中 Google 回 401 也轉成 `ReauthRequiredError`（`_delete_error`，`google_calendar.py:225-234`）；Google 5xx、429 或連不上丟 `ExternalServiceError`；其他錯誤走 `_google_error`。中途失敗時已刪的事件不復原。
- 一般任務與子任務排入行事曆時，事件 id 存在任務的 `calendar_event_id`。主任務本身不會排入行事曆。
- 只有一個子任務的主任務會出現：建立任務時只拆一個階段（`backend/schemas/manual_task.py:53`，`min_length=1`），或在一般任務上新增第一個階段。
- 階段編號是讀取時依主任務的 `subtask_ids` 順序算出來的（`backend/crud/manual_task.py:328-337`），刪掉一個子任務後，後面的階段自動往前遞補。不在 `subtask_ids` 裡的子任務文件，讀取清單時不會出現（`manual_task.py:67`）。
- `delete_subtask`（`manual_task.py:264-279`）把「至少還有 2 個」寫在更新主任務的 filter 裡，同時送出的刪除也不會刪到一個都不剩；被擋下時，若事件已經被這次請求刪掉，router 清掉它的 `calendar_event_id`（`backend/routers/manual_task.py:295-301`，[issue-37](issue-37-concurrent-subtask-delete.md) AC1、AC2）。
- 前端 `frontend/composables/useTaskForm.ts`：`onDelete`（主任務、一般任務）與 `onDeleteSubtask` 失敗時都走 `showDeleteError`，授權失效顯示重新連接 Google Calendar 的提示。主任務的確認文字是「這個主任務和底下 N 個子任務會一起刪除，確定嗎？」。`frontend/components/tasks/TaskForm.vue` 的子任務「刪除」按鈕用 `deletingSubtask` 一次只送一個刪除（issue-37 AC3）；主任務、一般任務的「刪除」按鈕（`TaskForm.vue:408-418`）沒有送出中的保護，連點會送出多次。

開發者在需求問答中決定，主任務和子任務也改成「事件不管時間一律刪除」，刪掉唯一的子任務等於刪除主任務，和一般任務一起在這份規格處理。這份規格取代：

- staged-tasks AC28（只刪還沒開始的事件、確認文字只寫子任務數量）、AC29（只刪還沒開始的事件）、AC30（只剩一個子任務時不能刪）、AC34（一般任務不刪事件）。
- issue-37 AC1（同時刪最後兩個子任務時一個回 400）、AC2（被擋下的子任務清事件 id）。

## 需求

1. 刪除一般任務時，一起刪除它在 Google Calendar 上的事件。
2. 刪除主任務時，一起刪除所有子任務，以及所有子任務在 Google Calendar 上的事件。
3. 刪除子任務時，一起刪除它在 Google Calendar 上的事件。
4. 要刪的事件不管已經開始、已經過去，或任務已經完成，都刪除。
5. 主任務有兩個以上子任務時，刪除其中一個只刪那一個；可以留下只有一個子任務的主任務。
6. 刪除主任務唯一的子任務，等於刪除整個主任務。
7. 要刪的事件都刪除成功（或已經不存在）後，才刪除資料庫裡的任務。
8. 需要刪事件但 Google 授權失效或沒有連接時，不刪任何任務，要求使用者重新連接。
9. 刪除事件中途失敗時，任務都保留，使用者可以重試。
10. 刪除主任務的確認對話框，依階段順序列出會一起刪除的子任務名稱，不提行事曆。
11. 刪除唯一子任務的確認對話框，說明整個任務都會刪除。
12. 一般任務和不是唯一的子任務，確認對話框文字不變。
13. 前端一次只送一個刪除：刪除送出中時，所有「刪除」按鈕停用。
14. 刪除流程的程式共用，不要三種任務各寫一份；刪除相關的函式用 docstring 寫清楚它做什麼、每個參數代表什麼。

## 不做

- Jira、Moodle、GitHub 匯入的任務：不能從這個 endpoint 刪除，不在範圍內。
- 刪除帳號（`DELETE /users/me`）時刪掉使用者的行事曆事件：行為不變。
- 刪除和「確認排程」同時送出時，排程剛寫入的事件可能來不及被刪：主任務、子任務刪除時就已經存在，這次不處理。
- 重新連接時選了另一個 Google 帳號：之後刪除時系統對新帳號操作，Google 回 404 被當作已刪除，原帳號上的事件會留下。系統沒有記錄事件屬於哪個帳號，要記錄得改資料結構和連接流程，開發者決定接受這個風險。
- Google 回其他錯誤（例如 400、不是限流也不是權限不足的 403、使用者沒有主要行事曆）：任務保留，回應沿用現有的錯誤分類；不提供略過事件、強制刪除的做法。
- 「事件已經從 Google 日曆刪除」的提示（使用者在 Google 上刪掉事件後，在任務上提示）：開發者決定放到 #42 一起做。
- 舊規則下留在 Google 上、已經對不到任務的過去事件：不清理。
- 刪除時資料庫的兩次寫入只完成第一次就失敗（回 500，但任務已從清單消失）：開發者決定另開 #110 處理；這時事件已經刪掉，AC15 仍成立。
- 刪除中途失敗後使用者不重試時，已刪掉事件的子任務仍保留事件 id，之後不會再被排入：`main` 原本就有，這次不改。

## 假設

1. 確認對話框列出的子任務，來自前端已經載入的任務清單；另一個分頁剛改過子任務時，列出的名稱可能和後端實際刪掉的不同（現在的確認文字也用前端資料）。
2. 刪除唯一的子任務成功後，主任務已經不在，編輯視窗關閉，和刪除主任務一樣（前端清單過期的情況由 AC26 涵蓋）。

## 驗收條件

| # | 條件 |
|---|---|
| AC1 | 刪除一個已排入行事曆的一般任務時，系統要刪除它在 Google Calendar 上的事件 |
| AC2 | 刪除主任務時，系統要刪除主任務和所有子任務 |
| AC3 | 刪除主任務時，系統要刪除每個子任務在 Google Calendar 上的事件 |
| AC4 | 主任務有兩個以上子任務時，刪除其中一個，系統只刪那一個子任務和它的事件；其他子任務的欄位與事件不變 |
| AC5 | AC4 刪除後，後面的階段編號依序往前遞補；剩一個子任務時，主任務照常存在 |
| AC6 | 刪除主任務唯一的子任務時，系統要刪除整個主任務、這個子任務，以及它的事件，回應成功 |
| AC7 | 要刪的事件已經開始、已經過去，或所屬任務已經完成時，系統仍要刪除該事件 |
| AC8 | 要刪的任務（主任務則是所有子任務）都沒有排入行事曆時，系統不呼叫 Google，沒有連接 Google 也刪得掉 |
| AC9 | 要刪的事件已經不存在（Google 回 404 / 410）時，系統要當作刪除成功，繼續刪任務 |
| AC10 | 需要刪事件，但 Google 授權失效或沒有連接時，系統不刪任何任務，回 409 `REAUTH_REQUIRED` |
| AC11 | 授權在刪到一半才失效時，已經刪掉的事件不復原；重新連接後重試，已經不存在的事件照 AC9 處理 |
| AC12 | 刪除任務收到 `REAUTH_REQUIRED` 時，前端顯示現有的重新連接 Google Calendar 提示 |
| AC13 | 刪除事件中途失敗（Google 5xx、429、網路錯誤）時，系統要保留所有任務，回應提示重試 |
| AC14 | AC13 的情況下，已經刪掉的事件不復原；重試時，已經不存在的事件照 AC9 處理 |
| AC15 | 不變條件：任何時候都不會出現「任務已刪，但它在 Google Calendar 上的事件還在」（刪除和確認排程同時送出的情況除外，見「不做」） |
| AC16 | 不變條件：刪除請求回失敗時，使用者看得到的任務都還在，可以重試；任務已經被另一個刪除請求刪掉的情況除外；這次請求的資料庫寫入做到一半失敗、任務已經從清單消失的情況，交由 #110 決定，這次不驗證 |
| AC17 | 不變條件：同時送出同一個主任務最後兩個子任務的刪除時，結果和依序刪除一樣：整個主任務、兩個子任務與它們的事件都刪掉，不會留下沒有子任務的主任務 |
| AC18 | 使用者刪除別人的任務時，系統回 404，不刪任何事件與任務 |
| AC19 | 刪除主任務時，確認對話框依階段順序列出所有子任務名稱，格式為第一行「這個主任務和底下 N 個子任務會一起刪除：」、每個子任務一行「k. 名稱」、最後一行「確定嗎？」 |
| AC20 | 刪除主任務唯一的子任務時（從主任務編輯視窗的階段列表，或從子任務自己的編輯視窗），確認對話框為「你確定要刪除「子任務名稱」這個階段嗎？」，下一行「這是最後一個階段，刪除後「主任務名稱」整個任務都會刪除。」 |
| AC21 | 刪除一般任務時，確認對話框維持「你確定要刪除這個任務嗎？」 |
| AC22 | 主任務有兩個以上子任務時，刪除子任務的確認對話框是「你確定要刪除「名稱」這個階段嗎？」（從階段列表刪除時維持原文字；從子任務自己的編輯視窗刪除時，由「你確定要刪除這個任務嗎？」改成這句） |
| AC23 | 一個刪除請求送出中時，編輯視窗裡所有「刪除」按鈕（任務本身與每個階段的）都停用；請求完成（成功或失敗）後恢復 |
| AC24 | 不變條件：主任務有兩個以上子任務時，同時或重複送出同一個子任務的刪除（例如兩個分頁、或資料庫中途失敗後重試），系統只刪除這個子任務和它的事件，其他子任務的欄位與事件不變，主任務照常存在；後到的請求回成功、404，或照 AC10、AC13 回錯誤。只有一個子任務時，重複刪除的結果照 AC6 |
| AC25 | 不變條件：子任務已經不在主任務的 `subtask_ids` 裡、但它的文件還在時（前一次刪除移出清單後，刪文件失敗），走到資料庫步驟第 3 步的刪除請求要刪掉這份文件 |
| AC26 | 從主任務編輯視窗的階段列表刪除成功、重新載入任務清單後，編輯中的主任務已經不在清單裡時（例如前端清單過期，刪掉的其實是唯一的子任務），系統要關閉編輯視窗 |

## 不適用的情境

| 情境 | 原因 |
|---|---|
| 載入中 | 由 AC23 涵蓋送出中的狀態；任務清單的載入流程沒有改 |
| 空資料 | 沒有事件的任務由 AC8 涵蓋；沒有子任務的主任務不會出現（AC6、AC17） |
| 未登入 | 登入驗證 `get_current_clerk_user` 沒有改 |
| 輸入驗證、注入 | 只有路徑參數 `task_id`，查詢條件與擁有者檢查沒有改；權限由 AC18 涵蓋 |
| 個資、token 保護 | 沿用既有取得 Google 權杖的函式與錯誤處理，不新增 log 或回應內容 |

## 實作計畫

### 後端

1. `backend/services/google_calendar.py`：把 `delete_upcoming_calendar_events` 改成 `delete_calendar_events(clerk_id, event_ids) -> None`。
   - 不再先讀取事件、不比對時間，直接對每個事件呼叫 Google 刪除（AC7）。移除 `now` 參數。
   - 404 / 410 當作已刪除（AC9）。
   - `event_ids` 是空的時直接回傳，不檢查連接、不呼叫 Google（AC8）。
   - 錯誤處理沿用連接檢查、`_delete_error`、`_unreachable`（AC10、AC11、AC13、AC14）。
   - docstring 寫清楚：函式做什麼、`clerk_id`、`event_ids` 代表什麼、會丟哪些例外、中途失敗時已刪的事件不復原（任務仍保留事件 id）、呼叫端要等它成功才刪任務。
2. `backend/routers/manual_task.py` 的 `delete_manual_task`：三種任務共用同一個順序：檢查擁有者 → 決定要刪的事件 → 刪事件 → 刪資料庫。
   - 「決定要刪的事件」抽成一個函式：主任務 → 所有子任務的事件；子任務、一般任務 → 自己的事件（AC1～AC6）。刪子任務時，不管最後是只刪它還是刪整個主任務，要刪的事件都只有它自己的：整個主任務被刪時，它一定是清單裡唯一的子任務，其他子任務的事件已經由它們各自的刪除請求在移出清單前刪掉。
   - 刪子任務的資料庫步驟，每一步都用條件更新，條件寫在同一次更新的 filter 裡（做法同 ADR 0001），依序嘗試（AC4～AC6、AC17、AC24）：
     1. 主任務的 `subtask_ids` 含這個子任務、而且至少 2 個 → 移出清單，再刪它的文件。
     2. 主任務的 `subtask_ids` 正好只有這個子任務 → 刪主任務，再刪 `parent_id` 是這個主任務的所有子任務文件。
     3. 兩個都不成立時重新讀取主任務：主任務不在、或這個子任務不在清單裡（前一次刪除已生效）→ 刪掉這個子任務的文件，回成功（擁有者檢查時它已經不在清單裡的請求，照現有規則在第一步就回 404）；還在清單裡（另一個請求剛好新增或刪除了階段）→ 回到第 1 步。三步總共嘗試 3 輪仍不成立，回 409 `REQUEST_IN_PROGRESS`（沿用既有代碼：另一個請求正在改動同一個主任務的階段），請使用者重新整理後再試；這時事件已刪、子任務還在清單裡，重試時事件照 AC9 處理。
   - 「唯一」一律用第 2 步的條件判斷（清單內容正好只有它），不用另外讀到的數量。
   - 移除 `LAST_SUBTASK_DETAIL` 的 400，以及被擋下時清事件 id 的邏輯（issue-37 AC2 不再適用）。
   - 函式 docstring 寫清楚三種任務各刪什麼、失敗時資料的狀態、參數代表什麼。
3. `backend/crud/manual_task.py`：
   - `delete_subtask` 改成第 2 點的第 1 步，回傳是否成功，不丟例外；新增第 2 步的「只剩它時刪整個主任務」函式，回傳是否成功。
   - `delete_manual_task_by_id` 同時以 `user_id` 篩選，和其他刪除函式一致。
   - 刪除相關函式的 docstring 寫參數意思。

### 前端

4. `frontend/composables/useTaskForm.ts`：
   - `onDelete`：主任務的確認文字用 `editingSubtasks` 依階段順序列出名稱（AC19）；一般任務不改（AC21）。
   - `onDeleteSubtask`：`editingSubtasks` 只有一個時用 AC20 的文字，成功後關閉編輯視窗（假設 2）；其他情況不改（AC22）。
   - `onDelete` 編輯的是子任務時（從子任務自己的編輯視窗刪除）：從已載入的清單找出同一個主任務的子任務數量與主任務名稱，用 AC20 或 AC22 的文字。兩個入口共用同一個產生確認文字的函式。
   - 新增共用的「刪除中」狀態，`onDelete`、`onDeleteSubtask` 送出中時為 true，已經是 true 時不再送出（AC23）。
   - 授權失效的提示沿用 `showDeleteError`（AC12）。
5. `frontend/components/tasks/TaskForm.vue`：任務本身與階段的「刪除」按鈕都用共用的「刪除中」狀態停用，取代 `deletingSubtask`（AC23）。

### 文件

6. `docs/api.md`：更新 `DELETE /manual-tasks/{task_id}` 的說明（三種任務都刪事件、不分時間；刪唯一子任務等於刪主任務；移除 400；同時改動階段、三輪都不成立時回 409 `REQUEST_IN_PROGRESS`）。
7. `docs/specs/staged-tasks.md` 狀態改成「部分被 [刪除任務時一起刪除 Google Calendar 上的事件](issue-30-delete-calendar-events.md) 取代（AC28、AC29、AC30、AC34）」；`docs/specs/issue-37-concurrent-subtask-delete.md` 狀態改成「部分被 [同上](issue-30-delete-calendar-events.md) 取代（AC1、AC2）」。其他內容不動。

### 考慮過、沒選的做法

- **先刪任務、再盡量刪事件**：任務一定刪得掉，但 Google 失敗時事件會留在行事曆上、再也對不到任務，違反 AC15。
- **保留「先讀取再刪」**：讀取是為了比對時間；現在不比對時間，多一次 API 呼叫沒有用途。
- **加一個「刪除中」狀態，由背景工作補刪事件**：要新增欄位與背景流程，範圍和風險都大；「先刪事件、成功才刪任務、失敗重試」已經能維持一致。
- **斷連時改刪任務、事件留著**：開發者選擇要求重新連接（AC10）。
- **剩一個子任務時自動合併成一般任務**：需求問答中討論過，開發者確認可以有只有一個階段的主任務後撤回。
- **同時刪最後兩個子任務時，後到的回 400（issue-37 的做法）**：開發者決定刪唯一的子任務等於刪主任務，依序刪除的結果是整個主任務刪掉，同時刪除也要得到相同結果（AC17）。
- **後端用 `Idempotency-Key` 擋重複刪除**：重複刪除的結果由 AC24 與現有的 404 規則決定，不會多刪東西；同一個畫面的重複送出由前端擋（AC23）。

## 測試對應

| AC | 測試 |
|---|---|
| AC1 | `backend/tests/unit/test_manual_task_router.py`：已排入的一般任務刪除後，事件被刪、任務不在（取代 `test_ac34_deleting_plain_task_does_not_touch_calendar`：舊規則被這份規格取代） |
| AC2、AC3 | `test_manual_task_router.py`：主任務刪除後，所有子任務與它們的事件都刪掉（改寫 `test_ac28_deleting_parent_deletes_subtasks_and_their_calendar_events`） |
| AC4、AC5 | `test_manual_task_router.py`：三個子任務刪一個，只有它的事件被刪、後面往前遞補；兩個刪一個，剩一個的主任務照常存在（改寫 `test_ac29_deleting_subtask_deletes_its_event_and_renumbers`） |
| AC6 | `test_manual_task_router.py`：刪唯一子任務 → 主任務、子任務、事件都刪（取代 `test_ac30_last_remaining_subtask_cannot_be_deleted`：舊規則被取代） |
| AC7 | `backend/tests/unit/test_google_calendar_service.py`：已經開始、已經過去的事件也被刪（取代 `test_ac28_only_events_that_have_not_started_are_deleted`）；`test_manual_task_router.py`：已完成子任務的事件也被刪 |
| AC8 | `test_google_calendar_service.py`：`test_issue30_ac8_no_events_to_delete_does_not_call_google`（由既有測試改名）；`test_manual_task_router.py`：沒排入的一般任務在沒連接 Google 時刪得掉 |
| AC9 | `test_google_calendar_service.py`：`test_issue30_ac9_event_already_gone_counts_as_deleted`（由既有 `test_ac31_...` 改名，依新函式調整） |
| AC10 | `test_manual_task_router.py`：已排入的一般任務在沒連接時回 409，任務還在；`test_google_calendar_service.py`：既有 `test_delete_events_without_connection_is_reauth_required` |
| AC11 | `test_google_calendar_service.py`：第二個事件回 401 → `ReauthRequiredError`，第一個已刪 |
| AC12 | `frontend/tests/composables/useTaskForm.test.ts`：刪除一般任務收到 `REAUTH_REQUIRED` 顯示重新連接提示 |
| AC13、AC14 | `test_google_calendar_service.py`：`test_issue30_ac13_ac14_failure_midway_asks_to_retry_and_keeps_already_deleted_events_deleted`（由既有 `test_ac33_...` 改名）；`backend/tests/integration/test_manual_task_scenario.py`：一般任務刪除時 Google 5xx → 任務還在 → 重試（事件已 404）→ 刪除成功；主任務刪除中途失敗後重試的情境，假的 Google 對已刪的事件回 404，實際走到 AC9 的處理；測試不留沒有被呼叫的假函式（#114） |
| AC15、AC16 | 由 AC1、AC3、AC6、AC10、AC13、AC17 的測試一起驗證：成功時檢查事件都被刪，失敗時檢查任務還在 |
| AC17 | `test_manual_task_router.py`：同時刪最後兩個子任務 → 主任務、子任務、兩個事件都不在（取代 `test_issue37_ac1_...`、`test_issue37_ac2_...`：舊規則被取代） |
| AC18 | `test_manual_task_router.py`：既有 `test_delete_manual_task_refuses_other_users_task_and_keeps_it`，補上不呼叫 Google 的檢查 |
| AC19 | `useTaskForm.test.ts`：確認文字依階段順序列出子任務名稱（改寫 `AC28：刪除主任務的確認文字寫出會一起刪除幾個子任務`） |
| AC20 | `useTaskForm.test.ts`：從階段列表、從子任務自己的編輯視窗刪唯一子任務，確認文字都是 AC20 的文字；成功後關閉編輯視窗 |
| AC21、AC22 | `useTaskForm.test.ts`：一般任務的確認文字不變；兩個入口刪不是唯一的子任務，都是「你確定要刪除「名稱」這個階段嗎？」 |
| AC24 | `test_manual_task_router.py`：同一個子任務同時刪兩次（三個子任務、兩個子任務各一例）→ 只有它被刪、其他子任務與事件還在、後到的請求回成功或 404；移出清單後刪文件失敗、重試 → 回 404，其他子任務不變；兩個子任務 A、B，同時刪 A 兩次、第二個請求在資料庫步驟前 A 已被移出 → B 和它的事件還在；第 1 步與第 2 步都不成立、重新讀取時另一個請求新增了階段 → 重試後只刪 A；三輪都不成立 → 回 409 `REQUEST_IN_PROGRESS`，A 與其他子任務都還在；只有 A 一個子任務時同時刪 A 兩次 → 主任務、子任務、事件都不在，兩個請求回成功或 404 |
| AC23 | `frontend/tests/components/TaskForm.actions.test.ts`：改寫 `#37 AC3：一個階段刪除中，所有階段的「刪除」都停用`，涵蓋任務本身的「刪除」按鈕 |
| AC25 | `test_manual_task_router.py`：`test_issue30_ac25_subtask_already_removed_from_list_has_its_document_deleted`（子任務已不在清單、文件還在，呼叫 `_delete_subtask_records` → 文件被刪掉；#112） |
| AC26 | `useTaskForm.test.ts`：前端清單顯示兩個階段、後端重新載入後主任務已不在 → 刪除成功後編輯視窗關閉；重新載入後主任務還在 → 編輯視窗保持開著（#113） |

## 修改紀錄

| 日期 | 修改 | 原因 | 確認者 |
|---|---|---|---|
| 2026-11-16 | 新增 AC25、AC26；AC13／AC14 的測試對應補上主任務情境的 404 與清掉沒用到的假函式；假設 2 註明清單過期由 AC26 涵蓋 | 開發者決定實作審查的 #112、#113、#114 在這個 PR 處理 → AC25（#112）、AC26（#113）、AC13／AC14 測試對應（#114，測試品質，不改行為）；檢查過 AC6、AC20、AC24 與假設 1 不用改 | 開發者 |

## 請你決定

無
