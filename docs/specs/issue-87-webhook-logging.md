# Webhook 密鑰未設定時的啟動錯誤 log

- 來源 issue：[Issue #87](https://github.com/Chen-Yihua/auto-scheduling-system/issues/87)
- 狀態：已核准
- 等級：高風險（涉及 webhook 憑證／token 不出現在 log 的安全保證）
- issue：#87
- PR：#137

## 簡短說明

修正後端在未設定 webhook 簽章密鑰時的啟動錯誤 log，讓 log 使用既有的時間、等級與 logger 名稱格式，同時保留只記一次且不洩漏密鑰值的行為。

## 背景

部署維護者未設定 `CLERK_WEBHOOK_SIGNING_SECRET` 或 `GITHUB_WEBHOOK_SECRET` 後啟動後端時，`routers.user` 與 `routers.pr_review_webhook` 會在模組載入時記錄錯誤。`backend/main.py` 目前先 import routers，之後才在 `setup_logging()` 初始化 root logger，因此這些錯誤使用 Python 的 lastResort handler，只輸出純文字，缺少時間、`ERROR` 等級與 logger 名稱。這使依 log 等級或文字篩選的監控可能無法發現 webhook 會一律回 401 的部署設定問題。

目前兩個 router 都已在模組載入時各記錄一次錯誤，且請求處理不會重複記錄；既有測試也驗證錯誤訊息不包含密鑰值。

## 需求

1. 在 import routers 前初始化既有 logging 設定，讓模組載入期間產生的既有 warning/error 使用標準格式。
2. 未設定 `CLERK_WEBHOOK_SIGNING_SECRET` 或 `GITHUB_WEBHOOK_SECRET` 時，保留各自於啟動時只記錄一次錯誤的行為。
3. 不改變 webhook 驗證失敗的回應行為，也不讓任何 webhook 密鑰值出現在 log。

## 不做

- 不調整 Cloud Run 監控條件。
- 不修改 webhook 的 401 回應、錯誤碼或簽章驗證規則。
- 不修改既有 log 訊息文字或其他環境變數的設定檢查時機。

## 假設

1. `backend/core/logging_config.py` 的既有格式 `%(asctime)s %(levelname)s %(name)s: %(message)s` 是所有啟動 log 應使用的標準格式。
2. 本次只需保留既有兩個 webhook router 的設定檢查，不需為其他模組新增環境變數檢查。

## 驗收條件

| # | 條件 | 改程式前是否失敗 |
|---|---|---|
| AC1 | 啟動時兩個密鑰都未設定，系統只記錄兩筆密鑰設定錯誤：一筆 logger 名稱為 `routers.user`，另一筆為 `routers.pr_review_webhook`；每筆 log 包含時間與 `ERROR` 等級，且不產生第三筆密鑰設定錯誤。 | 是；目前 router import 早於 `setup_logging()`，只輸出純文字。 |
| AC2 | 啟動時只有 `CLERK_WEBHOOK_SIGNING_SECRET` 未設定，系統只記錄 `routers.user` 的一筆錯誤 log，不記錄 `routers.pr_review_webhook` 的密鑰錯誤。 | 是；目前沒有涵蓋單一密鑰缺少的啟動輸出。 |
| AC3 | 啟動時只有 `GITHUB_WEBHOOK_SECRET` 未設定，系統只記錄 `routers.pr_review_webhook` 的一筆錯誤 log，不記錄 `routers.user` 的密鑰錯誤。 | 是；目前沒有涵蓋單一密鑰缺少的啟動輸出。 |
| AC4 | 啟動時兩個密鑰都已設定，系統不因密鑰檢查記錄錯誤。 | 否；既有測試已通過。 |
| AC5 | 在 AC1–AC3 的啟動情境下，每個缺少的密鑰各只記錄一次；收到對應 webhook 請求不會因密鑰缺少而再次記錄錯誤。 | 否；既有測試已通過。 |
| AC6 | 在 AC1–AC3 的啟動情境下，錯誤 log 不包含任何已設定的 webhook 密鑰值。 | 否；既有測試已通過。 |
| AC7 | 在 AC1–AC3 的啟動情境下，收到 webhook 請求時，錯誤 log 不包含簽章值或 request body。 | 部分是；GitHub webhook 現有測試尚未檢查 request body。 |
| AC8 | 在 AC4 的啟動情境下，log 不包含任一 webhook 密鑰值。 | 否；既有測試已通過。 |

## 不適用的情境

| 情境 | 原因 |
|---|---|
| 空資料、載入中、未登入／無權限、資料處理 | 本次只改後端啟動時的 logging 初始化順序，不改 API 資料、登入流程或權限。 |
| 外部系統狀態與資料一致性 | 本次不改 webhook 驗證、外部服務呼叫或資料寫入。 |

## 實作計畫

1. 調整 `backend/main.py` 的 import 與初始化順序，先載入並呼叫 `setup_logging()`，再 import routers 與其他會在 import 時執行設定檢查的模組。
2. 在 `backend/tests/unit/test_logging.py` 補充隔離 subprocess 啟動回歸測試，以四種環境變數組合載入實際 `backend.main`，驗證錯誤數量、logger 名稱、時間與 `ERROR` 等級；測試不只單獨 reload router。
3. 補充 GitHub webhook request body 不進錯誤 log 的測試，並保留既有 webhook 啟動記錄、請求不重複記錄與密鑰不洩漏測試。
4. 完成安全檢查：確認所有新增或調整的 log 路徑不輸出密鑰、簽章或 request body，且 webhook 401 回應與錯誤碼不變。
5. 確認只調整 logging 初始化順序，不改變其他模組 import-time log 的訊息內容與觸發時機。

### 未採用的方案

- **只在兩個 router 的 `logger.error` 前暫時設定 handler**：不採用，會重複 logging 初始化邏輯，且其他模組載入時的既有 log 仍會缺少標準格式。
- **把密鑰檢查移到 `lifespan`**：不採用，會改變設定檢查從模組載入時到 app lifespan 的時機，且可能讓 router import 後才發現錯誤；本次只需修正 logging 初始化順序。

## 測試對應

| AC | 測試 |
|---|---|
| AC1 | `backend/tests/unit/test_logging.py` 的實際 `backend.main` subprocess 啟動測試：Clerk 缺少、GitHub 缺少；斷言兩筆錯誤、logger 分別為 `routers.user` 與 `routers.pr_review_webhook`、等級為 `ERROR`、時間符合既有 logging 格式，且沒有第三筆密鑰錯誤；改程式前失敗。 |
| AC2 | 同一啟動測試的組合：Clerk 缺少、GitHub 已設定；斷言只有 `routers.user` 一筆錯誤；改程式前失敗。 |
| AC3 | 同一啟動測試的組合：Clerk 已設定、GitHub 缺少；斷言只有 `routers.pr_review_webhook` 一筆錯誤；改程式前失敗。 |
| AC4 | 同一啟動測試的組合：Clerk 已設定、GitHub 已設定；斷言沒有密鑰設定錯誤；改程式前通過。 |
| AC5 | `backend/tests/unit/test_user_webhook.py` 與 `backend/tests/unit/test_pr_review_webhook.py` 的缺少密鑰啟動及請求測試；改程式前通過。 |
| AC6 | `backend/tests/unit/test_logging.py` 的四組 subprocess 啟動測試：斷言輸出不包含任一已設定密鑰值；既有 webhook 密鑰不洩漏測試改程式前通過。 |
| AC7 | `backend/tests/unit/test_user_webhook.py` 與 `backend/tests/unit/test_pr_review_webhook.py` 的 request log 不洩漏測試；補上 GitHub request body 斷言，改程式前該涵蓋不足。 |
| AC8 | `backend/tests/unit/test_logging.py` 的兩個密鑰已設定 subprocess 啟動測試，以及兩個 webhook router 的已設定密鑰測試；改程式前通過。 |

## 修改紀錄

| 日期 | 修改 | 原因 | 確認者 |
|---|---|---|---|
| 2026-11-18 | 建立草稿；將 issue 建議驗收條件拆為 AC1–AC4。 | 讓 log 格式、只記一次與不洩漏密鑰各自可驗證。 | 開發者已確認 Q1、Q2 |
| 2026-11-18 | 升級為高風險；補上四種密鑰設定組合，將啟動 log 與 request log 的不洩漏條件拆分為 AC1–AC8，並補安全檢查與未採用方案。 | 開發者接受規格審查建議 Q3–Q5；確認憑證保護與完整設定矩陣。 | 開發者已確認 Q3、Q4、Q5 |
| 2026-11-18 | 明確列出 `routers.user` 與 `routers.pr_review_webhook`，指定以 subprocess 載入 `backend.main` 驗證四種設定組合與完整 log 欄位。 | 依第二輪規格審查補強實際啟動入口與可驗證斷言；不改變需求行為。 | 規格審查修正 |

## 請你決定

無
