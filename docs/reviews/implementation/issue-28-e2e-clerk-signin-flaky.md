# E2E 的 Clerk 登入間歇性失敗：實作審查紀錄

- 規格：[docs/specs/issue-28-e2e-clerk-signin-flaky.md](../../specs/issue-28-e2e-clerk-signin-flaky.md)
- PR：#45
- 輪數：3（第 1 輪 2026-11-06 `2ce4787`；第 2 輪 2026-11-06 `a34f4f3`；第 3 輪 2026-11-06 `eaa86d4`）
- 最終結果：仍有阻擋（#6 補測試中，待第 4 輪審查；根本原因「重試後兩步的測試不完整」已連續 2 輪阻擋）

## 摘要

- 發現：6 項（Missing AC 1、Implementation Defect 1、Test Gap 3、Improvement Suggestion 1；Minor 5、Info 1）
- 開發者決策：2 項（#1 在這個 PR 補 AC1；#2 另開 #46）
- 尚未處理：1 項（#2，#46）

## 發現與處理

| # | 輪 | 標題 | 類型 | 嚴重程度 | 阻擋合併 | 涉及安全／架構 | 根本原因 | 處理 | 決定者 | 結果 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1 | 重新載入後的等待／登入狀態檢查本身遇到導覽時，不重試、也不印診斷 | Missing AC | Minor | 是 | 否 | 重試後的檢查沒定義 | 規格 AC1 補上，交回實作 | 開發者 | `a34f4f3` |
| 2 | 1 | 相對路徑網址的 query string／hash 沒有被清掉，會印進 CI log | Implementation Defect | Minor | 是 | 安全 | 只清絕對網址 | 另開 issue，這個 PR 不修 | 開發者 | [#46](https://github.com/Chen-Yihua/auto-scheduling-system/issues/46) |
| 3 | 1 | 不重試、重試用完的錯誤會不會印診斷，沒有測試 | Test Gap | Minor | 是 | 否 | AC4 失敗路徑沒測 | 交回實作補測試 | 規則 | `a34f4f3` |
| 4 | 1 | 診斷沒有登入開始／失敗的時間點 | Improvement Suggestion | Info | 否 | 否 | — | 在 #28 留言 | 規則（不阻擋的發現，已有相同問題時留言） | [#28 留言](https://github.com/Chen-Yihua/auto-scheduling-system/issues/28#issuecomment-6688627170) |
| 5 | 2 | 重新載入後「等待頁面載入」遇到導覽的行為沒有測試 | Test Gap | Minor | 是 | 否 | 重試後兩步的測試不完整 | 交回實作補測試；規格回歸測試表補上這個情境（文件同步） | 規則 | `eaa86d4` |
| 6 | 3 | 重新載入後的兩步又遇到導覽時，沒有斷言「等待頁面載入」會再執行一次 | Test Gap | Minor | 是 | 否 | 重試後兩步的測試不完整 | 交回實作補斷言；規格回歸測試表的「改程式前是否失敗」補上（文件同步） | 規則 | （修正後補上） |

## 問題說明

### #1 重新載入後的等待／登入狀態檢查本身遇到導覽時，不重試、也不印診斷

- 問題：登入遇到導覽後，等待頁面載入與檢查 `window.Clerk.user` 這兩步如果又遇到 `Execution context was destroyed`，錯誤會直接丟出，不算進重試次數，也不印診斷。
- 情境：一次登入期間連續導覽多次（CI run 42235120764 在 54ms 內記到 4 次），第二次剛好落在檢查上。
- 影響：AC1 在還有重試次數時就失敗；AC4 的診斷不會印出。
- 技術原因：`frontend/tests/e2e/support/signInWithRetry.ts:54`、`:56` 在 catch 裡呼叫；AC1 的 2026-11-06 修改沒有定義這一步失敗時的行為。

### #2 相對路徑網址的 query string／hash 沒有被清掉，會印進 CI log

- 問題：清理只處理 `scheme://` 開頭的網址，console 訊息裡相對路徑的 query 與 hash 會原樣印出。
- 情境：登入期間 console 出現帶 query 的相對網址錯誤（例如 ofetch 的 `FetchError: [GET] "/path?x=..."`）。
- 影響：AC5 在這個情境不成立。目前首頁的 API 呼叫沒有帶 query，沒有實際外洩。
- 技術原因：`frontend/tests/e2e/support/signInWithRetry.ts:24`；AC5 的測試只放了絕對網址（`frontend/tests/e2e-support/signInWithRetry.test.ts:99`）。

### #3 不重試、重試用完的錯誤會不會印診斷，沒有測試

- 問題：AC4 的兩個失敗路徑沒有斷言 `onError` 被呼叫，把 `onError` 移到判斷之後的錯誤實作也會通過。
- 技術原因：`frontend/tests/e2e-support/signInWithRetry.test.ts:57`、`:67`。

### #5 重新載入後「等待頁面載入」遇到導覽的行為沒有測試

- 問題：AC1 規定等待與檢查兩步遇到導覽都算重試，但測試只讓檢查那一步丟錯，等待那一步固定成功；只在檢查那一步加重試的錯誤寫法也會通過。
- 影響：程式目前正確，測試保護不到 AC1、AC3、AC4 的這個情境。
- 技術原因：`frontend/tests/e2e-support/signInWithRetry.test.ts:19` 的 `setup()` 把 `waitForReady` 固定成一定成功。

### #6 重新載入後的兩步又遇到導覽時，沒有斷言「等待頁面載入」會再執行一次

- 問題：兩個測試都沒有斷言 `waitForReady` 第 2 次有被呼叫；第二次導覽後跳過等待、直接檢查登入狀態的錯誤寫法也會通過。
- 影響：程式目前正確，測試保護不到 AC1「等頁面載入完成後才檢查」。
- 技術原因：與 #5 同一根本原因，#5 的修正沒補完（`frontend/tests/e2e-support/signInWithRetry.test.ts:58-71`、`:73-89`）。

## 開發者決策

| # | 問題 | 選項 | 開發者的決定 | 理由 |
|---|---|---|---|---|
| 1 | 重新載入後的檢查遇到導覽時怎麼處理 | 這個 PR 補 AC1／另開 issue | 這個 PR 補 AC1 | 導覽錯誤不論發生在哪一步，處理方式一致；修改小 |
| 2 | 相對路徑 query 的清理（標成「安全」） | 這個 PR 修／另開 issue | 另開 issue（#46） | 開發者的條件：不影響其他功能或 issue 的操作就另開。e2e 只開首頁，首頁的 API 呼叫都沒有帶 query（唯一帶 query 的是 `/productivity` 的 `timezone`），目前不影響 |

## 尚未處理

| # | 原因 | 後續（issue 編號或「無」） |
|---|---|---|
| 2 | 開發者決定另開 issue | #46 |
