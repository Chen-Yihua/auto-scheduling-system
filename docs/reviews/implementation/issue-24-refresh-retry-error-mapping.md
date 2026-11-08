# 換新 Google token 後重試行事曆列表的錯誤分類：實作審查紀錄

- 規格：[docs/specs/issue-24-refresh-retry-error-mapping.md](../../specs/issue-24-refresh-retry-error-mapping.md)
- PR：[#60](https://github.com/Chen-Yihua/auto-scheduling-system/pull/60)
- 等級：輕量
- 輪數：1（第 1 輪 2026-11-08 `2e05045`）
- 最終結果：沒有阻擋項目

## 摘要

- 發現：0 項
- 開發者決策：0 項
- 尚未處理：0 項

## 各輪摘要

| 輪 | 日期／commit | 新發現（阻擋） | 這一輪之後改了什麼 |
|---|---|---|---|
| 1 | 2026-11-08 `2e05045` | 無 | 無 |

## 發現與處理

無

## 問題說明

無

## 開發者決策

無

## 尚未處理

無

## 各驗收條件的結果

| AC | 結果 | 依據 |
|---|---|---|
| AC1 | 通過 | `backend/services/google_calendar.py:51-52`；`test_get_free_slots_maps_retry_errors_after_token_refresh` 的 `[500]`、`[503]`、`[429]`，並確認重試用新 token |
| AC2 | 通過 | `backend/services/google_calendar.py:55-57`；同一支測試的 `[connect-error]`、`[read-timeout]` |
| AC3 | 通過 | `backend/services/google_calendar.py:53-54`；`[403]` 確認丟出的是原本的例外物件 |
| AC4 | 通過 | `backend/services/google_calendar.py:48-50` 沒動；既有的 `test_get_free_slots_requires_reauth_when_calendar_list_still_401_after_refresh`、`test_get_free_slots_refreshes_token_on_401` |

## 未經審查驗收條件的補查

AC3（規格審查第 1 輪後改寫）：

- 事實查證：正確。重試遇到 403 時，原本的 `httpx.HTTPStatusError` 往上傳，經過的 router 都沒有接住它：`backend/routers/schedule.py:100-115` 的 `except Exception` 只包住排程計算，`/schedule/confirm`（`:157-164`）沒有接，`backend/routers/manual_task.py:297` 只接 `InvalidRequestError`。最後由 `backend/core/exception_handlers.py:77-82` 回 500。前端不會把 500 當成未連接（`frontend/utils/errorMessages.ts:32-34` 只看 400）。
- 一致性：和 AC1、AC2、AC4，以及「不做」第 3 點沒有衝突。
- 情境：只保留既有行為，不寫資料，也不碰權限。

## 規格外的改動

測試檔既有的 `_http_error` helper 往前移，讓 parametrize 收集時能用到，內容不變；審查確認可以接受。
