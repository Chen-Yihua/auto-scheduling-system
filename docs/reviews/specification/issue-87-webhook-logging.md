# 規格審查：issue-87-webhook-logging

- 規格：[docs/specs/issue-87-webhook-logging.md](../../specs/issue-87-webhook-logging.md)
- 等級：高風險
- PR：#137

## 審查輪次

### 第一輪

- 結果：阻擋
- 發現：
  - 規格涉及憑證／token 不進 log 的安全保證，原一般等級不足。
  - 未定義兩個密鑰都缺少、只缺其中一個、兩個都設定的啟動行為與測試矩陣。
  - 啟動 log 與 request log 的不洩漏條件混在同一驗收條件。
- 處理：開發者確認升為高風險、補四種設定組合，並拆分不洩漏條件；規格補上安全檢查、未採用方案與 AC1–AC8。
- 決定者：開發者

### 第二輪

- 結果：阻擋
- 發現：
  - 啟動回歸測試未指定實際 `backend.main` 啟動入口與完整斷言。
  - AC1 未明確列出 `routers.user` 與 `routers.pr_review_webhook`。
- 處理：規格指定 `backend/tests/unit/test_logging.py` 以四種環境變數組合在隔離 subprocess 載入 `backend.main`，驗證數量、logger、時間、等級與密鑰不洩漏；AC1 補上兩個 logger 名稱。測試矩陣與其他 import-time log 不變條件一併補強。
- 決定者：規格審查修正；不改變已核准的需求行為。

## 最終結論

- 高風險規格已獲開發者核准。
- 規格審查阻擋項目已處理。
- 未發現漏洞、未開立額外 issue。
