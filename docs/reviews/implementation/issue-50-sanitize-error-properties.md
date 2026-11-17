# e2e 錯誤的 actual／expected 與其他屬性沒有清理：實作審查紀錄

- 規格：[docs/specs/issue-50-sanitize-error-properties.md](../../specs/issue-50-sanitize-error-properties.md)
- PR：#126
- 等級：高風險
- 輪數：3（第 1 輪 2026-11-17 `2ed723e`；第 2 輪 2026-11-17 `0d36a73`；第 3 輪 2026-11-17 `e25b2bd`，第 2、3 輪重審整個功能）
- 最終結果：仍有阻擋（#9、#10）；「AC6 測試不足」連續 3 輪有阻擋，停止自動修改，等開發者決定

## 摘要

- 發現：8 項（規格內容互相矛盾或沒有依據 1、規格沒寫某個情境該怎麼做 1、程式沒照規格做 1、測試抓不到錯的程式 2、沒有錯但可以更好 3；影響小的問題 6、不影響功能只供參考 2）
- 開發者決策：2 項
- 尚未處理：3 項

## 各輪摘要

| 輪 | 日期／commit | 新發現（阻擋） | 這一輪之後改了什麼 |
|---|---|---|---|
| 1 | 2026-11-17 `2ed723e` | #1–#4（#1、#2） | 新增 AC12（清理途中出錯改丟清理過的新錯誤），改寫已接受的風險第 2 點；AC8 寫法修正；#2 補測試；#3 開 issue #129 後開發者決定在這個 PR 修（新增 AC13） |
| 2 | 2026-11-17 `0d36a73` | #5–#8（#5、#6、#7） | 改做法：清理結果放在新建的錯誤物件，不再寫回原本的錯誤（AC11 取代 #46 AC2 的「回傳同一個物件」）；AC12 補出錯訊息取不到的情況；補 AC6、AC7、AC12 測試；Proxy 寫法修正 |
| 3 | 2026-11-17 `e25b2bd` | #9–#11（#9、#10） | 待開發者決定 |

## 發現與處理

| # | 輪 | 標題 | 類型 | 嚴重程度 | 阻擋合併 | 涉及安全／架構 | 根本原因 | 處理 | 決定者 | 結果 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1 | 清理途中丟出的 TypeError 訊息帶有沒清理的原始 message | 規格內容互相矛盾或沒有依據 | 影響小的問題 | 是 | 安全 | 清理途中出錯 | 選 A：新增 AC12，`message`、`stack` 改用同一套寫回規則，`withSanitizedErrors` 接住清理途中的錯誤 | 開發者 | `150a8ec` |
| 2 | 1 | AC6 的測試沒涵蓋 cookie、secret、api_key | 測試抓不到錯的程式 | 影響小的問題 | 是 | 安全 | AC6 測試不足 | 請 feature-implementer 補 cookie、secret、api_key 的測試 | 規則 | `150a8ec` |
| 3 | 1 | Buffer、TypedArray 的內容以數字保留在複製品裡 | 沒有錯，但可以更好 | 影響小的問題 | 否 | 安全 | — | 先開 issue [#129](https://github.com/Chen-Yihua/auto-scheduling-system/issues/129)；開發者要求在這個 PR 修，新增 AC13（二進位資料換成 `[binary]`），PR 描述加 `Closes #129` | 開發者 | `202f229` |
| 4 | 1 | 寫法：規格 AC8 第一次出現 getter 時沒有白話說明 | 沒有錯，但可以更好 | 不影響功能，只供參考 | 否 | 否 | — | 規格 AC8 加白話說明（開發者確認，記在規格修改紀錄）；規格審查紀錄由主 session 修改 | 開發者 | `150a8ec`；規格審查紀錄 `13d93c1` |
| 5 | 2 | 寫回清理結果沒生效、也沒出錯時，沒清理的值照樣交給 vitest | 規格沒寫某個情境該怎麼做 | 影響小的問題 | 是 | 安全 | 寫回沒生效 | 選 C：改成建立清理過的新錯誤，不寫回原本的錯誤 | 開發者 | `0fb1419` |
| 6 | 2 | 清理失敗的原因轉成文字時又出錯，丟出沒清理的值 | 程式沒照規格做 | 影響小的問題 | 是 | 安全 | 清理途中出錯 | 請 feature-implementer 修正（AC12 補出錯訊息取不到的情況） | 規則 | `0fb1419` |
| 7 | 2 | AC6 的物件值、AC7 的非字串值、AC12 的出錯原因沒有測試 | 測試抓不到錯的程式 | 影響小的問題 | 是 | 安全 | AC6 測試不足（AC7、AC12 部分為新） | 請 feature-implementer 補測試 | 規則 | `0fb1419` |
| 8 | 2 | 寫法：「已撤銷的 Proxy」沒有白話說明 | 沒有錯，但可以更好 | 不影響功能，只供參考 | 否 | 否 | — | 規格加白話說明（開發者確認，記在規格修改紀錄）；規格審查紀錄由主 session 修改 | 開發者 | `0fb1419`；規格審查紀錄 `9fc7fcc` |
| 9 | 3 | AC12「出錯訊息經過 #46 清理」沒有測試 | 測試抓不到錯的程式 | 影響小的問題 | 是 | 安全 | AC6 測試不足（#7 的 AC12 部分） | 待開發者決定（連續 3 輪） | 開發者 | — |
| 10 | 3 | 原型本身是錯誤物件時，新錯誤沿用它沒清理的 message、stack 與屬性 | 規格內容互相矛盾或沒有依據 | 影響小的問題 | 是 | 安全 | 原型上的內容沒清理 | 待開發者決定 | 開發者 | — |
| 11 | 3 | #28 AC2 的 4 個測試拿掉同一物件比對後，抓不到 signInWithRetry 改丟新錯誤 | 測試抓不到錯的程式 | 影響小的問題 | 否 | 否 | — | 待開發者決定（預設開 issue） | — | — |

## 問題說明

### #1 清理途中丟出的 TypeError 訊息帶有沒清理的原始 message
錯誤的 `message` 是唯讀屬性時，`sanitizeError` 直接賦值寫回（`frontend/tests/e2e/support/signInWithRetry.ts:150`）會丟出 `TypeError`，V8 會把原本錯誤的字串形式（含沒清理的 `message`）放進這個 `TypeError` 的訊息；`withSanitizedErrors`（`:174-175`）原樣丟給 vitest。最外層、`cause`、`AggregateError` 內層錯誤都會發生（Node 20 實測）。規格「已接受的風險」第 2 點寫「不會外洩」，和實際不符。目前查不到會產生這種錯誤的來源。

### #2 AC6 的測試沒涵蓋 cookie、secret、api_key
AC6 列了 9 個字詞，`#50 AC6`、`#50 AC7` 的測試資料只用到 6 個（`frontend/tests/e2e-support/signInWithRetry.test.ts:484-522`）；判斷字詞的正規表示式漏掉這三個字時測試仍會通過。

### #3 Buffer、TypedArray 的內容以數字保留在複製品裡
`Buffer`、`Uint8Array` 有以數字為名稱的自有屬性，複製品變成 `{ "0": 47, … }`（`frontend/tests/e2e/support/signInWithRetry.ts:117`、`:127-142`），內容可還原。所有 AC 都成立；目前 e2e 沒有比對二進位資料的 assertion。

### #4 寫法：規格 AC8 第一次出現 getter 時沒有白話說明
`docs/specs/issue-50-sanitize-error-properties.md` 的 AC8 用了「getter」，白話說明寫在後面的「已接受的風險」第 1 點；規格審查紀錄問題說明 #4 也一樣。

### #5 寫回清理結果沒生效、也沒出錯時，沒清理的值照樣交給 vitest
`replaceProperty`（`frontend/tests/e2e/support/signInWithRetry.ts:166-170`）寫回後不確認。屬性是不可重新定義的 getter 加上不存值的 setter，或丟出的錯誤是攔截定義屬性卻不寫入的 Proxy 時，寫回沒生效也不出錯，vitest 印出原本的值（Node 20 實測）。不會出錯，所以也不會走到 AC12。目前查不到來源。

### #6 清理失敗的原因轉成文字時又出錯，丟出沒清理的值
`withSanitizedErrors` 的 `catch` 裡 `String(reason)`（`frontend/tests/e2e/support/signInWithRetry.ts:183-184`）沒有保護；出錯原因不是 `Error`、而且它的 `toString` 丟出錯誤時，丟出的是沒清理的值，AC12 不成立（實測丟出原樣的字串）。

### #7 AC6 的物件值、AC7 的非字串值、AC12 的出錯原因沒有測試
測試資料沒涵蓋「不論值是什麼類型」與「加上出錯訊息」（`frontend/tests/e2e-support/signInWithRetry.test.ts:485-509`、`:513-533`、`:609-613`）；改成只遮字串、或只丟固定文字的錯誤實作仍會通過。目前的實作本身符合 AC6、AC7。

### #9 AC12「出錯訊息經過 #46 清理」沒有測試
兩個 AC12 測試，一個的出錯原因本來就不含機密，一個走 `[unserializable]` 分支（`frontend/tests/e2e-support/signInWithRetry.test.ts:654-686`）；拿掉 `describeCleanupError` 裡的 `sanitizeForLog`，測試仍通過。

### #10 原型本身是錯誤物件時，新錯誤沿用它沒清理的 message、stack 與屬性
錯誤用 `Object.create(另一個錯誤)` 建立時，新錯誤沿用同一個原型、只處理自有屬性（`frontend/tests/e2e/support/signInWithRetry.ts:147-165`），vitest 會從原型讀到沒清理的 `message`、`stack`、`actual`（`frontend/node_modules/@vitest/utils/dist/error.js:72-83`、`:95-104`）。main 上 `message` 會被清理，所以比 main 退步。目前查不到來源。

### #11 #28 AC2 的 4 個測試拿掉同一物件比對後，抓不到 signInWithRetry 改丟新錯誤
輔助函式只檢查 `instanceof Error` 與訊息（`frontend/tests/e2e-support/signInWithRetry.test.ts:37-42`），`signInWithRetry` 改成重新包一個訊息相同的新錯誤時測試仍通過。這個 PR 沒改 `signInWithRetry`。

## 開發者決策

| # | 問題 | 選項 | 開發者的決定 | 理由 |
|---|---|---|---|---|
| 1 | 清理途中出錯時 TypeError 帶出沒清理的原始 message | A：接住清理途中的錯誤改丟清理過的新錯誤，message／stack 改用同一套寫回規則（新增 AC12）；B：只改 message／stack 寫回；C：不改，列為會外洩的風險並開 issue | A | 不用列舉會出錯的情況就能保證不外洩，成本低 |
| 3 | Buffer、TypedArray 的內容 | 在這個 PR 修／開 issue；修的話 A：換成 `[binary]`、B：解碼後清理 | 在這個 PR 修，A | 看不懂的內容整個丟掉；B 會讓清理規則管不到的內容原樣印出 |
| 4 | 修正已核准規格 AC8 的寫法 | 修正／不修正 | 修正 | 符合 CLAUDE.md 寫作規則第 2 條，意思不變 |
| 5 | 寫回沒生效、也沒出錯 | A：寫回後讀回比對（新增 AC14）；B：列為會外洩的已接受風險；C：改成建立清理過的新錯誤，不寫回原本的錯誤 | C | 第 1、2 輪的問題都出在寫回原本的錯誤，C 拿掉這一步，不用再列舉會出錯的寫法 |
| 8 | 修正已核准規格「已撤銷的 Proxy」的寫法 | 修正／不修正 | 修正 | 符合 CLAUDE.md 寫作規則第 2 條，意思不變 |

## 尚未處理

| # | 原因 | 後續（issue 編號或「無」） |
|---|---|---|
| 9 | 同一根本原因連續 3 輪有阻擋，等開發者決定 | 無 |
| 10 | 等開發者選擇做法 | 無 |
| 11 | 等開發者決定開 issue 或在這個 PR 修 | 無 |
