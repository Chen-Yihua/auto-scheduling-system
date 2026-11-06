# 連續刪除最後兩個階段時，被擋下的階段不再被排程

- 狀態：已核准
- issue：[#37](https://github.com/Chen-Yihua/auto-scheduling-system/issues/37)
- PR：（實作後補上）


## 現象
使用者在任務頁編輯一個只剩兩個階段、兩個都已排進 Google Calendar（事件在未來）的主任務。前一個階段的刪除還在處理時，使用者又按了另一個階段的「刪除」（或在兩個分頁同時刪）。結果一個刪除成功；另一個顯示「主任務只剩這一個子任務，不能刪除；要刪除請改刪主任務」，那個階段還在，但它在 Google Calendar 上的事件已經被刪掉了。之後產生排程時，這個階段永遠不會被排入，畫面上也沒有任何提示，使用者可能到截止前才發現。

## 重現步驟
1. 建立一個有兩個階段的主任務，產生排程並確認，兩個階段都寫入 Google Calendar（事件開始時間在未來）。
2. 編輯主任務，對兩個階段幾乎同時送出刪除（同一個分頁連續按兩列的「刪除」，或兩個分頁各刪一個）。
3. 其中一個成功、另一個回 400。
4. 到排程頁產生排程。

## 預期行為／實際行為
- 預期：被擋下的階段如果事件已經被這次刪除刪掉，就要能重新排程；第 4 步會排入它。
- 實際：被擋下的階段 `calendar_event_id` 還指向已刪除的事件，第 4 步不會排入它，之後也永遠不會。

## 原因
- 刪除子任務的 router 先刪 Google 上的事件，再呼叫 `delete_subtask`（`backend/routers/manual_task.py:290-294`）。`delete_subtask` 的 `$pull` 條件「至少還有 2 個」（`backend/crud/manual_task.py:270-284`）會擋下後到的請求並丟 `InvalidRequestError`，但那個請求的事件已經刪了。
- router 的數量預檢（`manual_task.py:291`）在同時送出時兩邊都會通過，擋不住。
- 系統沒有地方會清掉 `calendar_event_id`；後端排程（`backend/services/scheduler.py:236-239`）與前端的待排清單（`frontend/composables/useScheduleWizard.ts:73`）都會跳過有 `calendar_event_id` 的任務。
- 前端 `onDeleteSubtask`（`frontend/composables/useTaskForm.ts:392-405`）沒有送出中的鎖，同一個分頁就能觸發。

## 驗收條件
| # | 條件 | 類型 |
|---|---|---|
| AC1 | 主任務剩兩個子任務、兩個都有未來的事件時，同時送出兩個子任務的刪除：一個成功、一個回 400（提示文字不變），主任務留下一個子任務；之後產生排程時，留下的子任務會被排入 | 使用者行為 |
| AC2 | 刪除子任務被「只剩一個」擋下（回 400）時，被擋下的子任務的 `calendar_event_id`：這次請求刪掉了它的事件 → 清成 None；事件已經開始或已經過去而保留 → 維持原值；原本就沒有事件 → 不變。只改這個使用者的這個子任務 | 不變條件（資料庫與 Google Calendar 一致） |
| AC3 | 前端一個階段正在刪除時，同一個主任務的所有階段「刪除」按鈕停用；刪除完成（成功或失敗）後恢復 | 使用者行為 |

## 不做
- 使用者在 Google 手動刪掉事件後任務卡住（main 上原本就有）：排程要把「事件已不存在」當成還沒排入，會改變排程規則並和 staged-tasks 規格 AC24 衝突。開發者決定另開 issue：#42。
- 同一個子任務被同時刪兩次時，後到的請求也會收到「只剩這一個子任務」的提示（文字不精確）：不在這次範圍。
- staged-tasks 規格 AC33（刪事件中途失敗時任務保留、已刪的事件不復原）的行為不變。

## 回歸測試
| AC | 測試 | 改程式前是否失敗 |
|---|---|---|
| AC1 | `backend/tests/unit/test_manual_task_router.py`：兩個刪除用 `asyncio.gather` 同時呼叫 `delete_manual_task`，一個成功、一個 `InvalidRequestError`，留下的子任務會被 `build_schedule_suggestion`（`backend/services/scheduler.py`）排入 | 預期失敗 |
| AC2 | 同上檔案：被擋下時事件被刪 → `calendar_event_id` 為 None；事件已開始而保留 → 維持原值；原本沒有事件 → 不變；另一個使用者的同 id 文件不受影響 | 「被刪 → None」預期失敗，其餘預期通過（保護既有行為） |
| AC3 | `frontend/tests/components/TaskForm.actions.test.ts`：刪除請求未完成時，其他階段的刪除按鈕 disabled；成功與失敗後都恢復 | 預期失敗 |

## 修改紀錄
| 日期 | 修改 | 原因 | 確認者 |
|---|---|---|---|
