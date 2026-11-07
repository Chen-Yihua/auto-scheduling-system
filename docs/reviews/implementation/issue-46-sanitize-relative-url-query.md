# e2e 診斷 log 沒有清掉相對路徑網址的 query string：實作審查紀錄

- 規格：[docs/specs/issue-46-sanitize-relative-url-query.md](../../specs/issue-46-sanitize-relative-url-query.md)
- PR：#49
- 輪數：1（第 1 輪 2026-11-07 `76d3458`）
- 最終結果：仍有阻擋（規格已改寫，依新規格重新實作中，待第 2 輪審查）

## 摘要

- 發現：3 項（Test Gap 1、Specification Defect 1、Missing AC 1；Minor 3）
- 開發者決策：2 項（#2、#3：開發者改提新做法，規格重寫）
- 尚未處理：0 項

## 發現與處理

| # | 輪 | 標題 | 類型 | 嚴重程度 | 阻擋合併 | 涉及安全／架構 | 根本原因 | 處理 | 決定者 | 結果 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1 | 「不是網址的 `?`」的兩條規則沒有測試 | Test Gap | Minor | 是 | 否 | AC3 分辨規則沒測 | 規格改寫後由新規格 AC5 的完整輸出測試涵蓋，交回實作 | 規則 | （修正後補上） |
| 2 | 1 | AC1 與 AC3 在「`/路徑?` 後面緊接非空白字元」時衝突 | Specification Defect | Minor | 是 | 否 | 網址邊界與 AC3 衝突 | 規格改寫：安全優先（新規格假設 1、AC6） | 開發者 | 規格 2026-11-07 修改紀錄 |
| 3 | 1 | 其他相對網址形式（路徑含括號、`./`、沒寫 scheme 的 host）的 query 仍會印出 | Missing AC | Minor | 是 | 安全 | 相對網址形式沒定義完 | 規格改寫：開發者提出用 `new URL()` 並封裝輸出，其他格式在這個 PR 一起處理（新規格 AC3、AC4） | 開發者 | 規格 2026-11-07 修改紀錄 |

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

## 開發者決策

| # | 問題 | 選項 | 開發者的決定 | 理由 |
|---|---|---|---|---|
| 2 | AC1 與 AC3 衝突時以哪條為準 | 安全優先，改 AC3 文字／其他 | 安全優先，規格改寫 | log 公開，誤刪只少幾個字 |
| 3 | 其他相對網址形式 | A 本 PR 擴充／B 另開 issue／C 接受風險 | 改用開發者提出的做法（`new URL()`＋封裝輸出），在本 PR 處理；bug 改用完整格式並做規格審查（`docs/reviews/specification/issue-46-sanitize-relative-url-query.md`） | 開發者提出 |

## 尚未處理

無。
