# 實作審查：issue-87-webhook-logging

- 規格：[docs/specs/issue-87-webhook-logging.md](../../specs/issue-87-webhook-logging.md)
- 規格審查：[docs/reviews/specification/issue-87-webhook-logging.md](../specification/issue-87-webhook-logging.md)
- 等級：高風險
- PR：#137

## 審查範圍

- `backend/main.py` 的 logging 初始化與 router import 順序。
- `backend/tests/unit/test_logging.py` 的四種密鑰設定組合與啟動 log 斷言。
- `backend/tests/unit/test_pr_review_webhook.py` 的 GitHub request body 不洩漏斷言。
- 既有 webhook 驗證、只記一次與密鑰不洩漏測試。

## 驗收結果

| AC | 結果 | 證據 |
|---|---|---|
| AC1 | 通過 | `backend/main.py` 先呼叫 `setup_logging()`；啟動測試驗證兩筆錯誤、`routers.user`、`routers.pr_review_webhook`、時間、`ERROR` 與無第三筆密鑰錯誤。 |
| AC2 | 通過 | 啟動測試驗證只缺 Clerk 時只有 `routers.user` 錯誤。 |
| AC3 | 通過 | 啟動測試驗證只缺 GitHub 時只有 `routers.pr_review_webhook` 錯誤。 |
| AC4 | 通過 | 啟動測試驗證兩個密鑰都設定時無密鑰錯誤。 |
| AC5 | 通過 | 既有 router 啟動與 request 測試驗證只記一次且 request 不重複記 error。 |
| AC6 | 通過 | 啟動測試與兩個 router 的 configured-secret 測試驗證不洩漏密鑰。 |
| AC7 | 通過 | Clerk 與 GitHub request 測試驗證不洩漏簽章與 request body。 |
| AC8 | 通過 | 兩個密鑰都設定時的啟動與 router 測試驗證不洩漏密鑰。 |

## 發現與處理

| # | 分類 | 發現 | 結果 | 根本原因 |
|---|---|---|---|---|
| 1 | — | 未發現阻擋或非阻擋問題。 | 不適用 | 不適用 |

未發現漏洞，未開立額外 issue。

## 驗證

- 聚焦測試：42 passed。
- 後端 `pyright`：0 errors。
- 後端 `pytest`：1188 passed、3 warnings。
- CI：`backend-test`、`frontend-test`、`frontend-e2e-test` 全部通過。
