# API 錯誤回應第三階段：規格審查紀錄

- 規格：[docs/specs/issue-90-http-exception-to-app-error.md](../../specs/issue-90-http-exception-to-app-error.md)
- PR：#91
- 等級：一般
- 輪數：2（都在 2026-11-13，審 scratchpad 的規格草稿，commit 是當時的 main `eceb6d6`）
- 最終結果：沒有阻擋項目（阻擋項目都依查證依據修正）

## 摘要

- 發現：5 項（第 1 輪 4、第 2 輪 1）：Factual Error 3、Improvement Suggestion 2；Minor 3、Info 2
- 開發者決策：見「開發者決策」
- 尚未處理：0 項

## 各輪摘要

| 輪 | 日期／commit | 新發現（阻擋） | 這一輪之後改了什麼 |
|---|---|---|---|
| 1 | 2026-11-13 `eceb6d6` | #1–#4（#1–#3） | 背景寫明 `security.py:144` 只有直接呼叫才走得到，真實請求的登入失敗由 Clerk library 的 403 轉成 401；AC6 補 token 無效與完整 body；路徑改成 `/users/me/linked-accounts/{platform}`；測試對應指到正確的測試檔與行號；實作計畫補列會因換例外而失敗的測試 |
| 2 | 2026-11-13 `eceb6d6` | #5（無） | 第 1 輪的修正都確認正確 |

## 發現與處理

| # | 輪 | 標題 | 類型 | 嚴重程度 | 阻擋合併 | 涉及安全／架構 | 根本原因 | 處理 | 決定者 | 結果 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1 | 背景對登入失敗回應來源的描述不完整，`security.py:144` 走 HTTP 到不了 | Factual Error | Minor | 是 | 否 | 登入失敗的回應來源 | 依 `fastapi_clerk_auth/__init__.py:148-163` 與 `tests/integration/test_error_responses_api.py:41-48` 改背景、AC6、不適用的情境、測試對應 AC5 | 主 session | 已修正 |
| 2 | 1 | linked account 的路徑少了 `/users/me` | Factual Error | Minor | 是 | 否 | 路徑寫錯 | 依 `backend/routers/linked_account.py:8` 改背景、需求 3、AC3 | 主 session | 已修正 |
| 3 | 1 | 測試對應 AC6 引用的測試檔不對；`_ERROR_CODE_BY_HTTP_STATUS` 的行號不對 | Factual Error | Minor | 是 | 否 | 引用錯誤 | 改成 `test_error_responses_api.py` 的三個測試；AC1 加 `test_unhandled_error_handling.py:63-73`；行號改 `:50-59` | 主 session | 已修正 |
| 4 | 1 | 實作計畫的測試清單漏了幾個 `pytest.raises(HTTPException)` | Improvement Suggestion | Info | 否 | 否 | — | 補進實作計畫第 4 點，測試對應 AC2、AC4 指到具體位置 | 開發者 | 採用 |
| 5 | 2 | AC4「照舊記下例外的 log」沒有對應的測試斷言 | Improvement Suggestion | Info | 否 | 否 | — | 測試對應 AC4 補 `caplog` 斷言 ERROR 等級的 log | 開發者 | 採用 |

## 已接受的風險

- 不加測試或 lint 防止之後又寫 `raise HTTPException`，只靠文件與審查（規格「不做」第 1 條）。AC7 的 grep 也只抓得到字面上的 `raise HTTPException`。
- ADR 0011 第 21 行提到「router 裡的 `HTTPException`」，改完後不再符合現況；ADR 是歷史紀錄，不因過時改寫（規格「不做」）。
- 其他用 `HTTPException` 當 crud mock 的測試（例如 `tests/integration/test_manual_task_api.py`）不在範圍內；`http_exception_handler` 保留，這些測試仍然有效。
