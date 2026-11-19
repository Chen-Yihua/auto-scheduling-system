# e2e 失敗時 vitest 印出的內容用 reporter 清理：實作審查紀錄

- 規格：[docs/specs/issue-50-sanitize-vitest-output.md](../../specs/issue-50-sanitize-vitest-output.md)
- PR：#142
- 等級：高風險
- 輪數：1（第 1 輪 2026-11-19 `a068f2e`）
- 最終結果：仍有阻擋（#1，Clerk 的 `__refresh` cookie 的值不會被清理，等開發者選擇）

## 摘要

- 發現：5 項（規格沒寫某個情境該怎麼做 1、沒有錯但可以更好 4；一般操作就會遇到的錯 1、影響小 1、只供參考 3）
- 開發者決策：2 項（#1 需要選擇、#3 需要確認）
- 尚未處理：5 項

## 各輪摘要

| 輪 | 日期／commit | 新發現（阻擋） | 這一輪之後改了什麼 |
|---|---|---|---|
| 1 | 2026-11-19 `a068f2e` | #1–#5（#1） | （待開發者決定 #1、#3） |

## 發現與處理

| # | 輪 | 標題 | 類型 | 嚴重程度 | 阻擋合併 | 涉及安全／架構 | 根本原因 | 處理 | 決定者 | 結果 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1 | Clerk 的 `__refresh` cookie 的值不會被清理 | 規格沒寫某個情境該怎麼做 | 一般操作就會遇到的錯 | 是 | 安全 | 敏感名稱沒有對照 Clerk 實際的 cookie 名稱 | 待選擇（建議 A：敏感名稱加 `refresh`） | 開發者 | 未處理 |
| 2 | 1 | 很長、沒有空白的字串，清理時間會隨長度平方成長 | 沒有錯，但可以更好 | 影響小的問題 | 否 | 否 | — | 開 issue | 主 session | 未處理 |
| 3 | 1 | 規則 6 找不到對應的 `]` 時遮到字串結尾 | 沒有錯，但可以更好 | 不影響功能，只供參考 | 否 | 否 | — | 建議寫進規格「已接受的風險」 | 開發者 | 未處理 |
| 4 | 1 | 整合測試分不出備援的幾個 reporter 方法 | 沒有錯，但可以更好 | 不影響功能，只供參考 | 否 | 否 | — | 不改 | 主 session | — |
| 5 | 1 | 主行程自己的 `Error`，`cause` 不會被清理 | 沒有錯，但可以更好 | 不影響功能，只供參考 | 否 | 安全 | — | 不改（找不到實際會走到的路徑） | 主 session | — |

## 問題說明

### #1 Clerk 的 `__refresh` cookie 的值不會被清理
Clerk 用 `__refresh` cookie 存 refresh token（`frontend/node_modules/@clerk/backend/dist/chunk-LFAHZTE6.mjs:38-45`、`:3036`）。這個名稱不含敏感名稱，值也不是 JWT 或 `dvb_`，所以測試失敗時如果印出 cookie 物件，值會原樣出現在 CI log，AC2 不成立。目前 e2e 只印 cookie 名稱，還沒有實際外洩；這個 cookie 在 e2e 會不會出現待確認。

### #2 很長、沒有空白的字串，清理時間會隨長度平方成長
3 萬字元約 2 秒、10 萬字元約 21 秒。原因是規則 3 的 regex（`sanitizingReporter.ts:36`）與 main 上原本就有的 `sanitizeForLog`（`signInWithRetry.ts:67-89`）。

### #3 規則 6 找不到對應的 `]` 時遮到字串結尾
`sanitizingReporter.ts:99-101`。只會多遮，規格沒定義這個情況。

### #4 整合測試分不出備援的幾個 reporter 方法
拿掉 `onCollected`、只拿掉 `onTestRunEnd` 或 `onFinished`、`onTaskUpdate` 改成 `async`，在 vitest 3.1.3 都不會外洩，測試也照樣通過。會外洩的改法，測試都抓得到（`cli-api.Bti1vevt.js:8181-8196`）。

### #5 主行程自己的 `Error`，`cause` 不會被清理
`sanitizingReporter.ts:159-162` 只處理 `message`、`stack`。主行程建立帶 `cause` 的錯誤的地方都在測試開始前（`cli-api.Bti1vevt.js:6923`、`:7372`）。

## 開發者決策

| # | 問題 | 選項 | 開發者的決定 | 理由 |
|---|---|---|---|---|
| 1 | `__refresh` cookie 的值要不要遮、怎麼遮 | A 敏感名稱加 `refresh`／B 只把 `__refresh` 開頭的 cookie 名稱當成敏感名稱／C 另開 issue | （待決定） | |
| 3 | 規則 6 遮到字串結尾的行為要不要寫進規格 | 寫進「已接受的風險」／不寫 | （待決定） | |

## 尚未處理

| # | 原因 | 後續（issue 編號或「無」） |
|---|---|---|
| 1 | 等開發者選擇 | 無 |
| 2 | 不阻擋 | 待開 issue |
| 3 | 等開發者確認 | 無 |
