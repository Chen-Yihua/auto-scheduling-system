# 重送時保留優先序自動調整的說明，並寫出調整內容

- 狀態：已核准
- 等級：一般（改的是回應格式與提示文字，另外新增一個選填欄位；舊資料沒有這個欄位照常讀得出來，重送不改任務資料的保證不變）
- issue：[#32](https://github.com/Chen-Yihua/auto-scheduling-system/issues/32)、[#39](https://github.com/Chen-Yihua/auto-scheduling-system/issues/39)
- PR：#119

## 簡短說明

AI 推斷的階段優先序被自動調整時，成功提示要寫出「哪個階段、從什麼改成什麼、為什麼」；用同一個 `Idempotency-Key` 重送時，回傳的調整清單要和第一次相同。

## 背景

使用者建立有多個階段的主任務，或在主任務裡新增一個階段時，沒填的優先序交給 AI 推斷。AI 推斷的值如果讓後面的階段比前面高，後端會把它調到前後階段之間（[staged-tasks 規格](staged-tasks.md) AC6，`backend/crud/manual_task.py` 的 `adjust_inferred_priorities`），回應的 `priority_adjusted_stages` 列出被調整的階段編號，前端提示寫「已把階段 2、3 調成落在前後階段之間」（`frontend/composables/useTaskForm.ts` 的 `adjustedStagesText`）。

目前有兩個問題：

1. **重送時提示不見**。`priority_adjusted_stages` 只在當次算出來，不存資料庫（`backend/schemas/manual_task.py` 的 `ManualTaskWithSubtasksOut`）。第一次回應遺失、前端用同一個 key 重送時，後端回傳已建立的資料，這個欄位是空的，提示不說明有階段被調整。會拿到空清單的路徑：
   - 一次建立：查到 key 已用過、直接回傳（`backend/routers/manual_task.py` 的 `create_manual_task`）；兩個請求同時送達、其中一個撞上唯一索引（`backend/crud/manual_task.py` 的 `create_manual_task_with_subtasks`）。後者的 router 還會把這次重新推斷出的清單蓋上去，和實際寫入的資料不一定一致。
   - 新增單一階段：查到 key 已用過、或同時送達時（`backend/routers/manual_task.py` 的 `_subtask_result_for_key`）。前端新增階段時目前沒帶 key（#38），所以使用者現在還碰不到，但後端是同一個欄位。
2. **提示看不懂**。使用者不記得「階段 2」是哪一個，也不知道改成什麼、為什麼改。

另外，`priority_adjusted_stages` 的註解（後端 schema、`frontend/types/manualTask.ts`）還寫著舊規則「被調成和前一個階段一樣」，實際上往上、往下都會調整（#39）。

任務資料本身都是正確的，只影響提示。

## 需求

1. 自動調整的規則不變：照 `adjust_inferred_priorities` 現有的做法調整（staged-tasks 規格 AC6 的實際做法，比較對象見需求 3、4），不重問 AI，也不改成各階段共用一個優先序。
2. 回應裡被調整的資訊改成每個被調整的階段一筆，每筆有：被調整的子任務 id、AI 原本推斷的值、調整後的值、比較的子任務 id。
3. AI 推斷的值比前一個階段高、被調低時，比較的子任務是前一個階段。
4. AI 推斷的值比後面的階段低、被調高時，比較的子任務是「後面的階段中，這次不是由 AI 推斷優先序的那些（一次建立時是使用者填的；新增單一階段時是所有既有階段）裡優先序最高的那一個；同樣高時取最前面的」。
5. 新欄位取代 `priority_adjusted_stages`，舊欄位與它的註解一起移除。
6. 一次建立主任務和階段時，被調整的清單存在資料庫裡主任務那筆資料上。
7. 新增單一階段時，被調整的清單存在資料庫裡這次新增的那個階段的資料上。
8. 用同一個 `Idempotency-Key` 重送時，回傳存在資料庫裡的清單，不重新計算。
9. 前端提示的標題照舊（「已建立主任務和 N 個階段」、「已新增階段」），有被調整的階段時，說明文字的第一行是「因後面階段比前面優先序高，已自動調整優先序：」，接著每個被調整的階段一行。
10. 被調低的那一行寫：「「<階段標題>」：AI 判斷為「<原本的值>」，但前一個階段「<比較的階段標題>」是「<比較的階段的值>」，已改成「<調整後的值>」」。
11. 被調高的那一行寫：「「<階段標題>」：AI 判斷為「<原本的值>」，但後面的階段「<比較的階段標題>」是「<比較的階段的值>」，已改成「<調整後的值>」」。
12. 「<比較的階段的值>」用清單裡的調整後的值，不讀比較的階段目前的值：調整就是改成比較對象當時的值，兩者相同。
13. 優先序在提示裡用中文（高、中、低），照 `frontend/utils/labels.ts` 的 `priorityLabel`。
14. 階段標題由前端從同一個回應的 `subtasks` 依 id 找出，用的是目前的標題。
15. 被調整或被比較的階段已經不在回應的 `subtasks` 裡（例如重送前在別的分頁刪掉了）時，那一行不顯示；所有行都不顯示時，不出現調整說明。
16. 新增單一階段的回應只帶這次新增的清單：這次沒有階段被調整時是空清單，不會出現主任務建立時存的清單。

## 不做

- 在 AI 的 prompt 加上「後面的階段不能比前面高」：另開 #115。
- 前端新增階段時帶 `Idempotency-Key`：#38。
- 階段任務的提示說明 AI 補了哪些值、顯示 AI 的理由（`inference_reason` 可能和調整後的值矛盾）：另開 #117。
- 另外記錄請求送出的時間：key 存在任務那筆資料上、有唯一索引，只靠 key 就能找到第一次的結果；任務已有 `created`。
- 同一個 key 先用在新增階段、再用在建立任務時，建立任務回傳那個階段的資料（原本就有的行為）：另開 #118。
- 重送前在被調低的階段前面插入新階段時，提示的「前一個階段」指的是調整當時的前一個階段，不一定是現在緊鄰的那一個：開發者接受這個情況，不另外處理。
- 查詢任務的 API（`GET /manual-tasks/me`、`GET /manual-tasks/{id}`）不帶這份清單。

## 驗收條件

| # | 條件 |
|---|---|
| AC1 | 一次建立主任務和階段、有階段的 AI 推斷優先序被調整時，回應的清單每筆寫出被調整的子任務 id、AI 原本的值、調整後的值、比較的子任務 id |
| AC2 | 被調低時，比較的子任務是前一個階段；被調高時，是需求 4 定義的那個階段 |
| AC3 | 一次建立後，用同一個 `Idempotency-Key` 重送，回應的清單和第一次相同 |
| AC4 | 同一個 `Idempotency-Key` 的兩個一次建立請求同時送達、其中一個撞上重複時，兩個回應的清單都和實際寫入的資料一致（是先寫入成功的那次的清單） |
| AC5 | 新增單一階段、它的 AI 推斷優先序被調整時，回應的清單寫出這個階段的調整內容 |
| AC6 | 新增單一階段後，用同一個 `Idempotency-Key` 重送，或同時送達且回應成功時，回應的清單和第一次新增時相同；不會拿到主任務建立時存的清單 |
| AC7 | 沒有階段被調整，或是在這次修改之前建立、資料庫裡沒有這份清單的資料重送時，回應的清單是空的，不報錯 |
| AC8 | 重送不改變任何任務資料（優先序、階段順序、筆數都和第一次一樣） |
| AC9 | 查詢任務的 API 回應不包含這份清單 |
| AC10 | 前端收到有調整的回應時，提示的說明文字第一行是「因後面階段比前面優先序高，已自動調整優先序：」，接著每個被調整的階段一行，寫法照需求 10～12，使用階段標題與中文優先序 |
| AC11 | 新增單一階段時，提示照 AC10 的格式說明調整內容 |
| AC12 | 沒有階段被調整時，提示不出現調整說明 |
| AC13 | 回應裡不再有 `priority_adjusted_stages` 欄位；後端 schema 與前端型別的新欄位註解寫的是目前的規則（調高、調低都可能發生） |
| AC14 | 新增單一階段、這次沒有階段被調整時，第一次的回應、用同一個 `Idempotency-Key` 重送的回應，以及同時送達且回應成功時的回應，清單都是空的；主任務建立時存的清單不會出現 |
| AC15 | 前端收到的清單裡，被調整或被比較的子任務不在回應的 `subtasks` 裡時，那一行不顯示；所有行都不顯示時，提示不出現調整說明 |

## 不適用的情境

| 情境 | 原因 |
|---|---|
| 載入中 | 提示在請求成功後才顯示，沒有改到載入中的畫面 |
| 同時新增、另一個請求還在處理 | 照原本的做法回 409 `REQUEST_IN_PROGRESS`，回應沒有清單；這次不改 |
| 未登入、無權限 | 沒有改到登入與權限檢查；重送查 key 時本來就限定同一個使用者 |
| AI 呼叫失敗 | 失敗時套用預設值（staged-tasks AC5），調整規則照舊，清單照樣產生，不需要另外的條件 |
| 安全性（輸入驗證、注入） | 沒有新增使用者輸入；新欄位由後端產生 |

## 實作計畫

**後端**

1. `backend/schemas/manual_task.py`：新增 `PriorityAdjustment`（`subtask_id`、`from_priority`、`to_priority`、`compared_subtask_id`）；`ManualTaskWithSubtasksOut` 移除 `priority_adjusted_stages`，加上 `priority_adjustments: list[PriorityAdjustment] = []`，註解寫目前的規則。`ManualTaskOut` 不加這個欄位，所以查詢 API 的 `response_model` 會把資料庫裡存的清單濾掉（AC9）。
2. `backend/crud/manual_task.py` 的 `adjust_inferred_priorities`：回傳每個被調整階段的 index、原本的值、調整後的值、比較的階段 index，比較對象照需求 3、4。驗證與調整規則不變。
3. `backend/routers/manual_task.py` 的 `_create_with_subtasks`：子任務的 id 在 `_subtask_doc` 才產生，所以先產生子任務文件，再把 index 換成 id，組成清單存進主任務文件的 `priority_adjustments` 欄位，一起寫入。
4. 同時送達撞上重複時，`create_manual_task_with_subtasks` 回傳的是先寫入的那筆；router 回傳它存的清單，不用這次重新算的蓋過去（AC4）。可以讓 crud 回傳是否為既有資料，或讓 router 一律讀回主任務文件上的清單，由實作決定。
5. `create_manual_task` 查到 key 已用過時，回傳主任務文件上存的清單；舊資料沒有這個欄位時回空清單（AC3、AC7）。
6. `add_subtask`：把這次的清單存在新子任務文件的 `priority_adjustments`；第一次的回應一律用這份清單（包括空清單），不用主任務文件上的（AC14）。
7. `_subtask_result_for_key`：一律回傳既有子任務文件上存的清單（沒有或空的就是空清單），蓋掉主任務文件上的（AC6、AC14）。
8. 新欄位是選填，不需要轉換既有資料，也不加索引。

**前端**

9. `frontend/types/manualTask.ts`：新增 `PriorityAdjustment` 型別；`TaskWithSubtasks` 移除 `priority_adjusted_stages`，加上 `priority_adjustments`，註解照後端。
10. `frontend/composables/useTaskForm.ts`：`adjustedStagesText` 改成接收回應，依 id 從 `subtasks` 找出標題，組成需求 9～12 的文字，找不到的照需求 15 略過；`buildStagedSummary` 與 `onAddSubtask` 都用它。比較的階段在被調整的階段前面時是被調低，否則是被調高。
11. 提示的說明文字要真的分行顯示（目前是單一字串），由實作確認 Nuxt UI 的 toast 怎麼顯示換行。

**文件**

12. staged-tasks 規格 AC6 寫的是「建立成功的提示會說明哪些階段被調整」，這次只是改寫說明的內容，沒有改變它定義的行為，所以不標記取代。
13. `docs/api.md` 只列回應的型別名稱，不用改。

## 測試對應

| AC | 測試 |
|---|---|
| AC1、AC2 | `backend/tests/unit/test_manual_task_crud.py`（`adjust_inferred_priorities` 被調低、被調高時的比較對象；被調高時同樣高取最前面；新增單一階段時既有階段都算在比較範圍）；`backend/tests/unit/test_manual_task_router.py`（一次建立的回應帶出子任務 id；改寫現有 `priority_adjusted_stages` 的斷言） |
| AC3 | `backend/tests/integration/test_manual_task_api.py`：建立時觸發調整，用同一個 key 重送，比較兩次回應的清單 |
| AC4 | `backend/tests/unit/test_manual_task_router.py`：模擬撞上重複時，回應是先寫入那筆存的清單，不是這次算的 |
| AC5 | `backend/tests/unit/test_manual_task_router.py`：新增單一階段的回應帶出調整內容（改寫現有斷言） |
| AC6 | `backend/tests/integration/test_manual_task_api.py`：主任務建立時有調整，再新增一個也被調整的階段，用同一個 key 重送新增，回應是新增那次的清單；`backend/tests/unit/test_manual_task_router.py`：同時送達（`insert_subtask` 回 False）時回應是先寫入那筆存的清單 |
| AC7 | `backend/tests/unit/test_manual_task_router.py`：資料庫裡的主任務沒有這個欄位時重送建立、子任務沒有這個欄位時重送新增，都回空清單 |
| AC8 | 併入 AC3、AC6 的測試：重送後查詢任務，優先序、順序、筆數不變 |
| AC9 | `backend/tests/integration/test_manual_task_api.py`：建立有調整的主任務，再新增一個被調整的階段後，`GET /manual-tasks/me` 與 `GET /manual-tasks/{id}` 的回應（主任務與子任務）都沒有 `priority_adjustments` |
| AC10、AC12 | `frontend/tests/composables/useTaskForm.test.ts`：被調低、被調高各一行，用階段標題與中文優先序；沒有調整時不出現說明（改寫現有 AC6 的測試）；分行是否真的顯示，由實作在開 PR 前人工確認畫面並寫在 PR 描述 |
| AC11 | `frontend/tests/composables/useTaskForm.test.ts`：新增單一階段的提示（改寫現有 AC10 / AC6 的測試） |
| AC13 | 型別檢查（pyright、`npm run typecheck`）；人工檢查兩處註解 |
| AC14 | `backend/tests/unit/test_manual_task_router.py`：主任務文件上有清單，新增一個不會被調整的階段，第一次的回應與重送的回應清單都是空的（同時送達走同一個 `_subtask_result_for_key`，由重送的測試涵蓋） |
| AC15 | `frontend/tests/composables/useTaskForm.test.ts`：清單裡的 id 不在 `subtasks` 裡時，那一行不顯示；全部找不到時沒有調整說明 |

## 修改紀錄

| 日期 | 修改 | 原因 | 確認者 |
|---|---|---|---|

## 請你決定

無
