# 刪除任務時一起刪除 Google Calendar 上的事件：實作審查紀錄

- 規格：[docs/specs/issue-30-delete-calendar-events.md](../../specs/issue-30-delete-calendar-events.md)
- PR：#111
- 等級：高風險
- 輪數：1（第 1 輪 2026-11-16 `c207810`）
- 最終結果：仍有阻擋（#1，修正中）

## 摘要

- 發現：5 項（程式沒照規格做 1、測試抓不到錯的程式 1、沒有錯但可以更好 3；影響小 2、只供參考 3）
- 開發者決策：0 項
- 尚未處理：1 項（#1）

## 各輪摘要

| 輪 | 日期／commit | 新發現（阻擋） | 這一輪之後改了什麼 |
|---|---|---|---|
| 1 | 2026-11-16 `c207810` | #1–#5（#1） | #1 請 feature-implementer 補 docstring；#5 更正規格「測試對應」的測試名稱；#2–#4 開 issue |

## 發現與處理

| # | 輪 | 標題 | 類型 | 嚴重程度 | 阻擋合併 | 涉及安全／架構 | 根本原因 | 處理 | 決定者 | 結果 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1 | 前端 `onDelete`、`onDeleteSubtask`、`isOnlySubtask` 沒有 docstring | 程式沒照規格做 | 影響小 | 是 | 否 | 前端刪除函式缺說明 | 請 feature-implementer 補 JSDoc | 規則 | 修正中 |
| 2 | 1 | 第 3 步「已不在清單 → 刪掉剩下的子任務文件」沒有測試會在刪錯時失敗 | 測試抓不到錯的程式 | 只供參考 | 否 | 否 | — | 開 issue | 規則 | [#112](https://github.com/Chen-Yihua/auto-scheduling-system/issues/112) |
| 3 | 1 | 前端清單過期時，刪掉實際上唯一的子任務後，編輯視窗沒關閉 | 沒有錯，但可以更好 | 影響小 | 否 | 否 | — | 開 issue | 規則 | [#113](https://github.com/Chen-Yihua/auto-scheduling-system/issues/113) |
| 4 | 1 | 刪除相關測試留下不會被呼叫的假函式與輔助函式 | 沒有錯，但可以更好 | 只供參考 | 否 | 否 | — | 開 issue | 規則 | [#114](https://github.com/Chen-Yihua/auto-scheduling-system/issues/114) |
| 5 | 1 | 規格「測試對應」寫的還是改名前的測試名稱 | 沒有錯，但可以更好 | 只供參考 | 否 | 否 | — | 在這個 PR 更正規格的測試名稱（AC 不變） | 主 session | 修正中 |

## 問題說明

### #1 前端刪除函式沒有 docstring

規格需求 14 要求刪除相關函式用 docstring 寫清楚做什麼與每個參數。後端的刪除函式都有寫；前端 `frontend/composables/useTaskForm.ts:395`（`onDeleteSubtask`）只有一行 `//` 註解，`:449-450`（`onDelete`）、`:454`（`isOnlySubtask`）沒有說明。

### #2 第 3 步沒有測試保護

`backend/routers/manual_task.py:314-316` 的第 3 步改成「直接回成功、不刪文件」時，現有測試照樣通過：走到第 3 步的 AC24 測試，文件都已被第一個請求刪掉；「刪文件失敗後重試」在擁有者檢查回 404，走不到第 3 步。

### #3 清單過期時編輯視窗沒關閉

`useTaskForm.ts:450-451` 在送出前用已載入的清單判斷是不是唯一的子任務；另一個分頁剛刪掉其他階段時，後端照 AC6 刪掉整個主任務，前端卻不關視窗（`:439-440`）。不違反 AC，假設 2 在這個情境不成立。

### #4 測試留著舊流程的假函式

`backend/tests/integration/test_manual_task_scenario.py:173-183` 的 `fake_get_event` 不會被呼叫，`fake_delete_event` 對已刪的事件不回 404；`backend/tests/unit/test_google_calendar_service.py:527` 的 `_event` 沒有人呼叫。404 路徑另有測試涵蓋。

### #5 規格的測試名稱過時

規格「測試對應」AC8、AC9、AC13／AC14 寫的是改名前的名稱；實際是 `test_issue30_ac8_...`、`test_issue30_ac9_...`、`test_issue30_ac13_ac14_...`（`test_google_calendar_service.py:569`、`:612`、`:624`）。

## 開發者決策

無。
