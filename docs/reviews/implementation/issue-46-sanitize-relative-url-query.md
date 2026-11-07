# e2e 診斷 log 沒有清掉相對路徑網址的 query string：實作審查紀錄

- 規格：[docs/specs/issue-46-sanitize-relative-url-query.md](../../specs/issue-46-sanitize-relative-url-query.md)
- PR：#49
- 輪數：2（第 1 輪 2026-11-07 `76d3458`；第 2 輪 2026-11-07 `1ee3af8`；第 3 輪 2026-11-07 `7885604`）
- 最終結果：沒有阻擋項目（第 3 輪沒有發現）

## 摘要

- 發現：6 項（Test Gap 2、Specification Defect 1、Missing AC 1、Improvement Suggestion 2；Minor 5、Info 1）
- 開發者決策：2 項（#2、#3：開發者改提新做法，規格重寫）
- 尚未處理：0 項

## 發現與處理

| # | 輪 | 標題 | 類型 | 嚴重程度 | 阻擋合併 | 涉及安全／架構 | 根本原因 | 處理 | 決定者 | 結果 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1 | 「不是網址的 `?`」的兩條規則沒有測試 | Test Gap | Minor | 是 | 否 | AC3 分辨規則沒測 | 規格改寫後由新規格 AC5 的完整輸出測試涵蓋，交回實作 | 規則 | `1ee3af8` |
| 2 | 1 | AC1 與 AC3 在「`/路徑?` 後面緊接非空白字元」時衝突 | Specification Defect | Minor | 是 | 否 | 網址邊界與 AC3 衝突 | 規格改寫：安全優先（新規格假設 1、AC6） | 開發者 | 規格 2026-11-07 修改紀錄 |
| 3 | 1 | 其他相對網址形式（路徑含括號、`./`、沒寫 scheme 的 host）的 query 仍會印出 | Missing AC | Minor | 是 | 安全 | 相對網址形式沒定義完 | 規格改寫：開發者提出用 `new URL()` 並封裝輸出，其他格式在這個 PR 一起處理（新規格 AC3、AC4） | 開發者 | 規格 2026-11-07 修改紀錄 |
| 4 | 2 | 外層錯誤清理的包裝函式與非 Error 的 `cause` 沒有被測到 | Test Gap | Minor | 是 | 安全 | 外層錯誤清理沒測 | 交回實作：`withSanitizedErrors` 移到 support 檔並直接測試、補字串 `cause` 測試；規格測試對應同步（文件同步） | 規則 | `7885604` |
| 5 | 2 | vitest 印出的 `actual`／`expected` diff 與其他屬性沒有清理 | Improvement Suggestion | Minor | 否 | 安全 | — | 開 issue | 規則 | [#50](https://github.com/Chen-Yihua/auto-scheduling-system/issues/50) |
| 6 | 2 | 非 Error 的 `cause` 轉成 `[object Object]` | Improvement Suggestion | Info | 否 | 否 | — | 開 issue | 規則 | [#51](https://github.com/Chen-Yihua/auto-scheduling-system/issues/51) |

## 問題說明

### #1 「不是網址的 `?`」的兩條規則沒有測試

- 問題：實作用「`/` 前面緊接字元不算網址」「`?`／`#` 後面至少 1 個字元才清理」避免誤刪，但 AC3 的測試沒有「`/` 開頭的字後面接 `?`」的輸入；拿掉這兩條規則的寫法也會通過。
- 技術原因：`frontend/tests/e2e-support/signInWithRetry.test.ts:233-237`。

### #2 AC1 與 AC3 在「`/路徑?` 後面緊接非空白字元」時衝突

- 問題：`路徑 /help?。`、`見 /#28`、`/_nuxt/app.js?v=abc:19:22` 照 AC1 要清掉、照 AC3 要保留，實作選了 AC1，這些內容會被刪。
- 影響：診斷可讀性下降，沒有安全影響。
- 技術原因：規格沒定義兩者分不出來時以哪條為準（`frontend/tests/e2e/support/signInWithRetry.ts:27`）。

### #3 其他相對網址形式的 query 仍會印出

- 問題：`/wiki/Foo_(bar)?token=x`、`./v1/a?token=x`、`localhost:3000/v1/a?token=x` 這類格式的 query 原樣印出。
- 影響：規格要防的 token 外洩在這些格式不成立；目前找不到會產生這些格式的輸入，main 上同樣會漏，本 PR 沒有讓情況變差。
- 技術原因：AC1 只定義「以 `/` 開頭、遇到空白、引號、括號就結束」（`frontend/tests/e2e/support/signInWithRetry.ts:27`）。

### #4 外層錯誤清理的包裝函式與非 Error 的 `cause` 沒有被測到

- 問題：`withSanitizedErrors` 在 `frontend/tests/e2e/dashboard.e2e.ts:31-39`，主 vitest 設定不跑 `tests/e2e/**`；unit 測試用的是副本 `rejectionAfterOuterCleanup`（`frontend/tests/e2e-support/signInWithRetry.test.ts:37-44`）。字串 `cause` 也沒有測試。
- 影響：包裝改成原樣丟出、新測試忘了包、`cause` 只在是 Error 時才清理，這些錯的實作都會通過測試，未清理的錯誤會進公開 CI log。實作目前正確。

## 開發者決策

| # | 問題 | 選項 | 開發者的決定 | 理由 |
|---|---|---|---|---|
| 2 | AC1 與 AC3 衝突時以哪條為準 | 安全優先，改 AC3 文字／其他 | 安全優先，規格改寫 | log 公開，誤刪只少幾個字 |
| 3 | 其他相對網址形式 | A 本 PR 擴充／B 另開 issue／C 接受風險 | 改用開發者提出的做法（`new URL()`＋封裝輸出），在本 PR 處理；bug 改用完整格式並做規格審查（`docs/reviews/specification/issue-46-sanitize-relative-url-query.md`） | 開發者提出 |

## 尚未處理

無。
