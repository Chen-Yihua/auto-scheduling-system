# API 錯誤回應第二階段：實作審查紀錄

- 規格：[docs/specs/issue-82-status-codes-phase2.md](../../specs/issue-82-status-codes-phase2.md)
- PR：#86
- 等級：高風險
- 輪數：1（第 1 輪 2026-11-12 `cfd2c0a`）
- 最終結果：仍有阻擋（#1，待開發者決定改程式或改規格）

## 摘要

- 發現：5 項：Implementation Defect 1、Improvement Suggestion 4；Minor 2、Info 3
- 開發者決策：0 項（#1 待決定）
- 尚未處理：2 項（#1、#3）

## 各輪摘要

| 輪 | 日期／commit | 新發現（阻擋） | 這一輪之後改了什麼 |
|---|---|---|---|
| 1 | 2026-11-12 `cfd2c0a` | #1–#5（#1） | AC8 以外的 AC 通過；CORS 設定只多了 `expose_headers`、判斷本後端的規則、非本後端維持 ofetch 預設都確認正確；implementer 的 5 項實作選擇判斷符合規格；#2、#4、#5 開 issue |

## 發現與處理

| # | 輪 | 標題 | 類型 | 嚴重程度 | 阻擋合併 | 涉及安全／架構 | 根本原因 | 處理 | 決定者 | 結果 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1 | `PATCH /schedule/tasks/fields` 沒帶任何欄位時，不存在的 id、不認得的前綴都回 200 | Implementation Defect | Minor | 是 | 否 | 沒有欄位時跳過檢查 | 待開發者決定：改程式（沒有欄位時也先檢查 id）或改規格（AC8 寫明例外） | 開發者 | 待定 |
| 2 | 1 | webhook 密鑰沒設定的啟動 error log 在 logging 設定前輸出，沒有等級、時間與 logger 名稱 | Improvement Suggestion | Minor | 否 | 安全 | — | 開 issue | 主 session | [#87](https://github.com/Chen-Yihua/auto-scheduling-system/issues/87) |
| 3 | 1 | 規格「測試對應」AC6 寫的測試檔和實際位置不同 | Improvement Suggestion | Info | 否 | 否 | — | 和 #1 的修正一起同步規格的測試對應（文字同步，不改驗收條件） | 主 session | 待修正 |
| 4 | 1 | Clerk JWKS 裡有非 RSA 的 key、token 指到它時回 500 | Improvement Suggestion | Info | 否 | 否 | — | 開 issue（和 #5 同一個） | 主 session | [#88](https://github.com/Chen-Yihua/auto-scheduling-system/issues/88) |
| 5 | 1 | Clerk JWKS 逾時回 `UPSTREAM_TIMEOUT`，前端會把同一個 GET 重送到 3 次，每次都同步卡住後端 | Improvement Suggestion | Info | 否 | 否 | — | 開 issue | 主 session | [#88](https://github.com/Chen-Yihua/auto-scheduling-system/issues/88) |

## 問題說明

### #1 沒有欄位時跳過檢查

`backend/routers/schedule.py:63-65` 的 `if data:` 在 body 只有 `task_id` 時直接回 200，不會呼叫這次新增的檢查（`backend/crud/schedulable_items.py:170`）。`{"task_id": "foo:1"}`、`{"task_id": "github:999"}` 都回 200，和 AC8「外部 id 不存在回 404、前綴不認得回 400」不符。這個短路是 main 上既有的，手動任務在同樣情況下也回 200；前端不會送出沒有欄位的請求。既有測試都帶了 `duration`，沒測到。

## 開發者決策

無。

## 尚未處理

| # | 原因 | 後續（issue 編號或「無」） |
|---|---|---|
| 1 | 待開發者決定改程式或改規格 | 無 |
| 3 | 和 #1 的修正一起處理 | 無 |
