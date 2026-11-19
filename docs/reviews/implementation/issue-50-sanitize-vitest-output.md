# e2e 失敗時 vitest 印出的內容用 reporter 清理：實作審查紀錄

- 規格：[docs/specs/issue-50-sanitize-vitest-output.md](../../specs/issue-50-sanitize-vitest-output.md)
- PR：#142
- 等級：高風險
- 輪數：2（第 1 輪 2026-11-19 `a068f2e`；第 2 輪 2026-11-19 `4511c66`）
- 最終結果：仍有阻擋（#6 lookbehind 改寫後少遮 email；#7 AC22 的一般敘述不成立），等開發者決定

## 摘要

- 發現：8 項（第 1 輪 5、第 2 輪 3）：規格沒寫某個情境該怎麼做 1、規格內容互相矛盾或沒有依據 1、規格對現有系統的描述和程式不符 1、沒有錯但可以更好 5
- 開發者決策：7 項（第 1 輪 #1–#5；第 2 輪 #6、#7 待決定）
- 尚未處理：2 項（#6、#7）

## 各輪摘要

| 輪 | 日期／commit | 新發現（阻擋） | 這一輪之後改了什麼 |
|---|---|---|---|
| 1 | 2026-11-19 `a068f2e` | #1–#5（#1） | 敏感名稱加 `refresh`（`ab42ffa`）；「已接受的風險」補找不到 `]` 的情況；規則 3 與 email regex 加 lookbehind（AC22） |
| 2 | 2026-11-19 `4511c66` | #6–#8（#6、#7） | （待開發者決定 #6、#7） |

## 發現與處理

| # | 輪 | 標題 | 類型 | 嚴重程度 | 阻擋合併 | 涉及安全／架構 | 根本原因 | 處理 | 決定者 | 結果 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1 | Clerk 的 `__refresh` cookie 的值不會被清理 | 規格沒寫某個情境該怎麼做 | 一般操作就會遇到的錯 | 是 | 安全 | 敏感名稱沒有對照 Clerk 實際的 cookie 名稱 | 敏感名稱加 `refresh`，AC8、AC13 補例子 | 開發者（選 A） | `ab42ffa` |
| 2 | 1 | 很長、沒有空白的字串，清理時間會隨長度平方成長 | 沒有錯，但可以更好 | 影響小的問題 | 否 | 否 | — | 在這個 PR 修：規則 3 與 email regex 加 lookbehind、不設長度上限（AC22）；#143 由這個 PR 關閉 | 開發者 | `4511c66`（[#143](https://github.com/Chen-Yihua/auto-scheduling-system/issues/143)） |
| 3 | 1 | 規則 6 找不到對應的 `]` 時遮到字串結尾 | 沒有錯，但可以更好 | 不影響功能，只供參考 | 否 | 否 | — | 寫進規格「已接受的風險」 | 開發者 | `ab42ffa` |
| 4 | 1 | 整合測試分不出備援的幾個 reporter 方法 | 沒有錯，但可以更好 | 不影響功能，只供參考 | 否 | 否 | — | 不改 | 開發者 | — |
| 5 | 1 | 主行程自己的 `Error`，`cause` 不會被清理 | 沒有錯，但可以更好 | 不影響功能，只供參考 | 否 | 安全 | — | 不改（找不到實際會走到的路徑） | 開發者 | — |
| 6 | 2 | email regex 加 lookbehind 後，緊接在上一個 email 後面的 email 不會被遮 | 規格內容互相矛盾或沒有依據 | 影響小的問題 | 是 | 安全 | lookbehind 改寫的結果和原本不同 | （待開發者選擇） | 開發者 | — |
| 7 | 2 | 英數字和 `+` 組成的長字串，網址規則仍然隨長度平方變慢 | 規格對現有系統的描述和程式不符 | 影響小的問題 | 是 | 否 | AC22 的一般敘述沒有對照網址規則 | （待開發者確認） | 開發者 | — |
| 8 | 2 | email regex 的 lookbehind 沒有註解說明為什麼不能拿掉 | 沒有錯，但可以更好 | 不影響功能，只供參考 | 否 | 否 | — | 隨 #6 的修正處理 | 主 session | — |

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

### #6 email regex 加 lookbehind 後，緊接在上一個 email 後面的 email 不會被遮
兩個 email 中間只隔一個 `+` 或 `.` 時（例如 `x@a.b+y@c.d`），main 清理成 `[email][email]`，這個 PR 清理成 `[email]+y@c.d`。原因是 `/g` 的比對結束在 email 的 domain 之後，下一次比對的起點前一個字元是英數字，被 lookbehind 擋掉。這和規格「不做」、實作計畫 8 寫的「清理結果不變」，以及 #46 AC7 不符。規則 3 的 lookbehind 結果相同（隨機比對 30 萬個字串 0 處不同）。依據 `frontend/tests/e2e/support/signInWithRetry.ts:87`。

### #7 英數字和 `+` 組成的長字串，網址規則仍然隨長度平方變慢
`'a+'` 重複到 10 萬字元時，清理約 6 秒，AC22「清理時間和長度大致成正比」不成立；AC22 的兩個例子都通過。原因是 main 上原本就有的網址規則：`+` 後面的每個位置都會重新掃一次 scheme（`signInWithRetry.ts:14-15`、`:67-76`）。和實作計畫 8 第 4 點的描述不符。和 #2 同類，#2 的修正沒有涵蓋。

### #8 email regex 的 lookbehind 沒有註解
`sanitizingReporter.ts:36` 為規則 3 的 lookbehind 寫了不能拿掉的理由，`signInWithRetry.ts:87` 沒有。

## 開發者決策

| # | 問題 | 選項 | 開發者的決定 | 理由 |
|---|---|---|---|---|
| 1 | `__refresh` cookie 的值要不要遮、怎麼遮 | A 敏感名稱加 `refresh`／B 只把 `__refresh` 開頭的 cookie 名稱當成敏感名稱／C 另開 issue | A | 改動最小，和偏向多刪不漏刪一致 |
| 2 | 長字串變慢要不要在這個 PR 修 | A 另開 issue／B 這個 PR 修／C 不處理 | B；規則 3 與 email regex 都加 lookbehind、不設長度上限 | 結果不變、時間和長度成正比；長度上限會讓長名稱漏遮 |
| 3 | 規則 6 遮到字串結尾的行為要不要寫進規格 | 寫進「已接受的風險」／不寫 | 寫進 | 只會多遮 |
| 4、5 | 備援的 reporter 方法、主行程錯誤的 `cause` | 修／不修 | 不修 | 少一個方法不會外洩；`cause` 沒有實際來源 |

## 尚未處理

| # | 原因 | 後續（issue 編號或「無」） |
|---|---|---|
| 6 | 待開發者選擇 | 無 |
| 7 | 待開發者確認 | 無 |
