# API 錯誤回應第二階段：實作審查紀錄

- 規格：[docs/specs/issue-82-status-codes-phase2.md](../../specs/issue-82-status-codes-phase2.md)
- PR：#86
- 等級：高風險
- 輪數：2（第 1 輪 2026-11-12 `cfd2c0a`；第 2 輪 2026-11-13 `71ec1d8`）
- 最終結果：仍有阻擋（#6，待開發者確認）

## 摘要

- 發現：6 項（第 1 輪 5 項、第 2 輪 1 項）：Implementation Defect 1、Specification Defect 1、Improvement Suggestion 4；Minor 3、Info 3
- 開發者決策：1 項（#1）
- 尚未處理：1 項（#6）

## 各輪摘要

| 輪 | 日期／commit | 新發現（阻擋） | 這一輪之後改了什麼 |
|---|---|---|---|
| 1 | 2026-11-12 `cfd2c0a` | #1–#5（#1） | AC8 以外的 AC 通過；CORS 設定只多了 `expose_headers`、判斷本後端的規則、非本後端維持 ofetch 預設都確認正確；implementer 的 5 項實作選擇判斷符合規格；#2、#4、#5 開 issue；開發者決定 #1 改程式，規格 AC8 與需求 6 修改，修正在 `e2f6852`；#3 規格測試對應同步 |
| 2 | 2026-11-13 `71ec1d8` | #6（#6） | #1 確認已修正、新 AC8 通過；改寫的 unit 測試判斷合理（規格變更後跟著改）；PR diff 不含 #89 的流程文件；CORS 只多 `expose_headers` |

## 發現與處理

| # | 輪 | 標題 | 類型 | 嚴重程度 | 阻擋合併 | 涉及安全／架構 | 根本原因 | 處理 | 決定者 | 結果 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1 | `PATCH /schedule/tasks/fields` 沒帶任何欄位時，不存在的 id、不認得的前綴都回 200 | Implementation Defect | Minor | 是 | 否 | 沒有欄位時跳過檢查 | 開發者決定改程式：沒有欄位時也先檢查 id（前綴、格式、是否存在），規格 AC8、需求 6 修改並記進修改紀錄 | 開發者 | 已修正（`e2f6852`） |
| 2 | 1 | webhook 密鑰沒設定的啟動 error log 在 logging 設定前輸出，沒有等級、時間與 logger 名稱 | Improvement Suggestion | Minor | 否 | 安全 | — | 開 issue | 主 session | [#87](https://github.com/Chen-Yihua/auto-scheduling-system/issues/87) |
| 3 | 1 | 規格「測試對應」AC6 寫的測試檔和實際位置不同 | Improvement Suggestion | Info | 否 | 否 | — | 和 #1 一起同步規格的測試對應（文字同步，不改驗收條件） | 主 session | 已修正（規格隨 #1 交付） |
| 4 | 1 | Clerk JWKS 裡有非 RSA 的 key、token 指到它時回 500 | Improvement Suggestion | Info | 否 | 否 | — | 開 issue（和 #5 同一個） | 主 session | [#88](https://github.com/Chen-Yihua/auto-scheduling-system/issues/88) |
| 5 | 1 | Clerk JWKS 逾時回 `UPSTREAM_TIMEOUT`，前端會把同一個 GET 重送到 3 次，每次都同步卡住後端 | Improvement Suggestion | Info | 否 | 否 | — | 開 issue | 主 session | [#88](https://github.com/Chen-Yihua/auto-scheduling-system/issues/88) |
| 6 | 2 | 跨來源時，Cloud Run 平台自己回的 429 和沒有 `error_code` 的 500 沒有 CORS header，前端當成「沒有收到回應」而重送 | Specification Defect | Minor | 是 | 否 | 讀不到狀態碼的回應 | 待開發者確認 | 開發者 | 待定 |

## 問題說明

### #1 沒有欄位時跳過檢查

`backend/routers/schedule.py:63-65` 的 `if data:` 在 body 只有 `task_id` 時直接回 200，不會呼叫這次新增的檢查（`backend/crud/schedulable_items.py:170`）。`{"task_id": "foo:1"}`、`{"task_id": "github:999"}` 都回 200，和 AC8「外部 id 不存在回 404、前綴不認得回 400」不符。這個短路是 main 上既有的，手動任務在同樣情況下也回 200；前端不會送出沒有欄位的請求。既有測試都帶了 `duration`，沒測到。

### #6 讀不到狀態碼的回應

需求 7 的表格以前端讀得到狀態碼為前提。正式環境前端（Vercel）與後端（Cloud Run）不同來源，Cloud Run 平台自己回的回應不經過 FastAPI 的 `CORSMiddleware`（`backend/main.py:55-63`），沒有 `Access-Control-Allow-Origin`，瀏覽器丟網路錯誤，ofetch 呼叫 `onRequestError`、拿不到狀態碼，`frontend/utils/fetchRetry.ts:52-53` 照規格當成「沒有收到回應」重送。規格寫明不重送的 Cloud Run 429 與沒有 `error_code` 的 500，在這個條件下會被 GET 重送到總共 3 次；上限、間隔、方法限制仍在。Cloud Run 平台回應不帶 CORS header 是依平台一般行為推論，沒有在正式環境觀察。

## 開發者決策

| # | 問題 | 選項 | 開發者的決定 | 理由 |
|---|---|---|---|---|
| 1 | `fields` 沒帶欄位時不檢查 id | 改程式／改規格 | 改程式，沒有欄位時也先檢查 id | 改動小，AC8 與文件不用加例外，外部與手動一致 |

## 尚未處理

| # | 原因 | 後續（issue 編號或「無」） |
|---|---|---|
| 6 | 待開發者確認 | 無 |
