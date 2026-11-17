# e2e 錯誤的 actual／expected 與其他屬性沒有清理：實作審查紀錄

- 規格：[docs/specs/issue-50-sanitize-error-properties.md](../../specs/issue-50-sanitize-error-properties.md)
- PR：#126
- 等級：高風險
- 輪數：1（第 1 輪 2026-11-17 `2ed723e`）
- 最終結果：仍有阻擋（#1、#2 交給 feature-implementer 修正，待第 2 輪）

## 摘要

- 發現：4 項（規格內容互相矛盾或沒有依據 1、測試抓不到錯的程式 1、沒有錯但可以更好 2；影響小的問題 3、不影響功能只供參考 1）
- 開發者決策：2 項
- 尚未處理：2 項（修正中）

## 各輪摘要

| 輪 | 日期／commit | 新發現（阻擋） | 這一輪之後改了什麼 |
|---|---|---|---|
| 1 | 2026-11-17 `2ed723e` | #1–#4（#1、#2） | 新增 AC12（清理途中出錯改丟清理過的新錯誤），改寫已接受的風險第 2 點；AC8 寫法修正；#2 補測試；#3 開 issue |

## 發現與處理

| # | 輪 | 標題 | 類型 | 嚴重程度 | 阻擋合併 | 涉及安全／架構 | 根本原因 | 處理 | 決定者 | 結果 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1 | 清理途中丟出的 TypeError 訊息帶有沒清理的原始 message | 規格內容互相矛盾或沒有依據 | 影響小的問題 | 是 | 安全 | 清理途中出錯 | 選 A：新增 AC12，`message`、`stack` 改用同一套寫回規則，`withSanitizedErrors` 接住清理途中的錯誤 | 開發者 | 修正中 |
| 2 | 1 | AC6 的測試沒涵蓋 cookie、secret、api_key | 測試抓不到錯的程式 | 影響小的問題 | 是 | 安全 | AC6 測試不足 | 請 feature-implementer 補 cookie、secret、api_key 的測試 | 規則 | 修正中 |
| 3 | 1 | Buffer、TypedArray 的內容以數字保留在複製品裡 | 沒有錯，但可以更好 | 影響小的問題 | 否 | 安全 | — | 開 issue | 規則 | [#129](https://github.com/Chen-Yihua/auto-scheduling-system/issues/129) |
| 4 | 1 | 寫法：規格 AC8 第一次出現 getter 時沒有白話說明 | 沒有錯，但可以更好 | 不影響功能，只供參考 | 否 | 否 | — | 規格 AC8 加白話說明（開發者確認，記在規格修改紀錄）；規格審查紀錄由主 session 修改 | 開發者 | 規格修改中；規格審查紀錄已修改 |

## 問題說明

### #1 清理途中丟出的 TypeError 訊息帶有沒清理的原始 message
錯誤的 `message` 是唯讀屬性時，`sanitizeError` 直接賦值寫回（`frontend/tests/e2e/support/signInWithRetry.ts:150`）會丟出 `TypeError`，V8 會把原本錯誤的字串形式（含沒清理的 `message`）放進這個 `TypeError` 的訊息；`withSanitizedErrors`（`:174-175`）原樣丟給 vitest。最外層、`cause`、`AggregateError` 內層錯誤都會發生（Node 20 實測）。規格「已接受的風險」第 2 點寫「不會外洩」，和實際不符。目前查不到會產生這種錯誤的來源。

### #2 AC6 的測試沒涵蓋 cookie、secret、api_key
AC6 列了 9 個字詞，`#50 AC6`、`#50 AC7` 的測試資料只用到 6 個（`frontend/tests/e2e-support/signInWithRetry.test.ts:484-522`）；判斷字詞的正規表示式漏掉這三個字時測試仍會通過。

### #3 Buffer、TypedArray 的內容以數字保留在複製品裡
`Buffer`、`Uint8Array` 有以數字為名稱的自有屬性，複製品變成 `{ "0": 47, … }`（`frontend/tests/e2e/support/signInWithRetry.ts:117`、`:127-142`），內容可還原。所有 AC 都成立；目前 e2e 沒有比對二進位資料的 assertion。

### #4 寫法：規格 AC8 第一次出現 getter 時沒有白話說明
`docs/specs/issue-50-sanitize-error-properties.md` 的 AC8 用了「getter」，白話說明寫在後面的「已接受的風險」第 1 點；規格審查紀錄問題說明 #4 也一樣。

## 開發者決策

| # | 問題 | 選項 | 開發者的決定 | 理由 |
|---|---|---|---|---|
| 1 | 清理途中出錯時 TypeError 帶出沒清理的原始 message | A：接住清理途中的錯誤改丟清理過的新錯誤，message／stack 改用同一套寫回規則（新增 AC12）；B：只改 message／stack 寫回；C：不改，列為會外洩的風險並開 issue | A | 不用列舉會出錯的情況就能保證不外洩，成本低 |
| 4 | 修正已核准規格 AC8 的寫法 | 修正／不修正 | 修正 | 符合 CLAUDE.md 寫作規則第 2 條，意思不變 |

## 尚未處理

| # | 原因 | 後續（issue 編號或「無」） |
|---|---|---|
| 1 | feature-implementer 修正中 | 無 |
| 2 | feature-implementer 修正中 | 無 |
