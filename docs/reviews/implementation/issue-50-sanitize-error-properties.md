# e2e 錯誤的 actual／expected 與其他屬性沒有清理：實作審查紀錄

- 規格：[docs/specs/issue-50-sanitize-error-properties.md](../../specs/issue-50-sanitize-error-properties.md)
- PR：#126
- 等級：高風險
- 輪數：7（第 1 輪 2026-11-17 `2ed723e`；第 2 輪 2026-11-17 `0d36a73`；第 3 輪 2026-11-17 `e25b2bd`；第 4 輪 2026-11-17 `329653c`；第 5 輪 2026-11-17 `66c273b`；第 6 輪 2026-11-17 `2aadab9`；第 7 輪 2026-11-17 `ec9a2b2`，第 2～7 輪重審整個功能）
- 最終結果：#18、#19 交給 feature-implementer 修正，待第 8 輪；開發者決定收尾：Proxy 攔截行為前後不一致一律列已接受的風險（`message`、`stack`、`cause` 除外）；「原型上的內容沒清理」已沒有阻擋；「原型上的內容沒清理」連續 3 輪有阻擋，開發者決定改成和 vitest 相同的清理範圍；「AC6 測試不足」「清理途中出錯」已沒有阻擋

## 摘要

- 發現：8 項（規格內容互相矛盾或沒有依據 1、規格沒寫某個情境該怎麼做 1、程式沒照規格做 1、測試抓不到錯的程式 2、沒有錯但可以更好 3；影響小的問題 6、不影響功能只供參考 2）
- 開發者決策：2 項
- 尚未處理：2 項

## 各輪摘要

| 輪 | 日期／commit | 新發現（阻擋） | 這一輪之後改了什麼 |
|---|---|---|---|
| 1 | 2026-11-17 `2ed723e` | #1–#4（#1、#2） | 新增 AC12（清理途中出錯改丟清理過的新錯誤），改寫已接受的風險第 2 點；AC8 寫法修正；#2 補測試；#3 開 issue #129 後開發者決定在這個 PR 修（新增 AC13） |
| 2 | 2026-11-17 `0d36a73` | #5–#8（#5、#6、#7） | 改做法：清理結果放在新建的錯誤物件，不再寫回原本的錯誤（AC11 取代 #46 AC2 的「回傳同一個物件」）；AC12 補出錯訊息取不到的情況；補 AC6、AC7、AC12 測試；Proxy 寫法修正 |
| 3 | 2026-11-17 `e25b2bd` | #9–#11（#9、#10） | AC11 補原型鏈上的內容；新增 AC14（#28 AC2 的 stack 比對）；測試對應 AC11、AC12 寫出完整預期字串 |
| 4 | 2026-11-17 `329653c` | #12–#14（#12） | AC11 拆出 AC15（原型鏈）；測試對應 AC15 加三層原型的例子；PR 描述修正 |
| 5 | 2026-11-17 `66c273b` | #15（#15） | AC15 拿掉停止條件，沿原型鏈清理到 `Object.prototype` 之前；刪掉原型 getter 的已接受風險；測試對應 AC15 加舊式寫法的例子 |
| 6 | 2026-11-17 `2aadab9` | #16–#17（#16） | 規格「已接受的風險」加上會說謊的 Proxy；PR 描述測試數修正 |
| 7 | 2026-11-17 `ec9a2b2` | #18–#19（#18、#19） | AC11 補三個固定名稱一律直接讀取；陣列 `length` 用安全讀取；Proxy 的已接受風險改成一般性寫法 |

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
| 9 | 3 | AC12「出錯訊息經過 #46 清理」沒有測試 | 測試抓不到錯的程式 | 影響小的問題 | 是 | 安全 | AC6 測試不足（#7 的 AC12 部分） | 開發者確認補測試，規格測試對應寫出完整預期字串 | 開發者 | `c593904` |
| 10 | 3 | 原型本身是錯誤物件時，新錯誤沿用它沒清理的 message、stack 與屬性 | 規格內容互相矛盾或沒有依據 | 影響小的問題 | 是 | 安全 | 原型上的內容沒清理 | 選 A：原型鏈到類別原型之前的每一層都清理（AC11） | 開發者 | `c593904` |
| 11 | 3 | #28 AC2 的 4 個測試拿掉同一物件比對後，抓不到 signInWithRetry 改丟新錯誤 | 測試抓不到錯的程式 | 影響小的問題 | 否 | 否 | — | 開發者要求在這個 PR 修：新增 AC14 | 開發者 | `c593904` |
| 12 | 4 | AC11 的原型鏈測試只有一層，改成「只清理一層原型」的程式也會通過 | 測試抓不到錯的程式 | 影響小的問題 | 是 | 安全 | 原型上的內容沒清理 | 開發者確認：測試對應 AC15 加三層原型的例子 | 開發者 | `831e0d2` |
| 13 | 4 | 寫法：規格 AC11 一句話寫了好幾件事；實作計畫「安全讀取」那句重複 | 沒有錯，但可以更好 | 不影響功能，只供參考 | 否 | 否 | — | 開發者確認：AC11 拆出 AC15、刪重複半句 | 開發者 | `831e0d2` |
| 14 | 4 | PR 描述說 AC6 測試 9 個字詞都有資料，實際 jwt 只在 AC7 測試 | 沒有錯，但可以更好 | 不影響功能，只供參考 | 否 | 否 | — | 主 session 改 PR 描述 | 主 session | PR 描述已更新 |
| 15 | 5 | 原型本身是帶自有 constructor 的錯誤物件時，新錯誤從原型讀到沒清理的 stack、message | 規格內容互相矛盾或沒有依據 | 影響小的問題 | 是 | 安全 | 原型上的內容沒清理 | 選 A：AC15 改成走到 `Object.prototype` 之前 | 開發者 | `88ac547` |
| 16 | 6 | 原型鏈上有會說謊的 Proxy 時，新錯誤經由原型讀到沒清理的值 | 規格沒寫某個情境該怎麼做 | 影響小的問題 | 是 | 安全 | Proxy 隱藏屬性 | 選 A：列成已接受的風險，不改程式 | 開發者 | `c3fe3ab` |
| 17 | 6 | PR 描述的前端測試數量是 616，CI 實際是 617 | 沒有錯，但可以更好 | 不影響功能，只供參考 | 否 | 否 | — | 主 session 改 PR 描述 | 主 session | PR 描述已更新 |
| 18 | 7 | 「會說謊的 Proxy」已接受風險寫「main 上同樣會外洩」，但 stack、cause 在 main 會清理；列出的不成立 AC 也不完整 | 規格內容互相矛盾或沒有依據 | 影響小的問題 | 是 | 安全 | Proxy 隱藏屬性 | 選 B：`message`、`stack`、`cause` 一律直接讀取；其餘列已接受的風險（一般性寫法） | 開發者 | 修正中 |
| 19 | 7 | 陣列是讀 length 會出錯的 Proxy 時，丟出 AC12 的錯誤，不是 AC8 的 [unserializable] | 程式沒照規格做 | 影響小的問題 | 是 | 否 | 讀 length 沒用安全讀取 | 請 feature-implementer 修正並補測試 | 規則 | 修正中 |

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

### #12 AC11 的原型鏈測試只有一層
唯一的原型鏈測試只有一層帶內容的原型（`frontend/tests/e2e-support/signInWithRetry.test.ts:642-653`）；把迴圈改成只清理一層，測試仍通過，第二層沒清理的內容會被 vitest 讀到（`frontend/node_modules/@vitest/utils/dist/error.js:63-80`）。目前的程式在兩層的情況正確。目前查不到來源。

### #15 原型本身是帶自有 constructor 的錯誤物件時，新錯誤從原型讀到沒清理的 stack、message
AC15 規定沿原型鏈往上到第一個有自有 `constructor` 的物件就停（`frontend/tests/e2e/support/signInWithRetry.ts:159`）。舊式寫法 `MyErr.prototype = new Error(...)` 加上 `MyErr.prototype.constructor = MyErr` 時，停下的那一層本身帶 `message`、`stack`；錯誤自己沒有 `stack` 時，vitest 經由原型讀到沒清理的值（`frontend/node_modules/@vitest/utils/dist/error.js:69-80`、`:94-96`）。main 上會清理，所以比 main 退步。e2e 直接用到的套件查不到這種寫法。

### #16 原型鏈上有會說謊的 Proxy 時，新錯誤經由原型讀到沒清理的值
清理只處理列舉得到的屬性名稱（`frontend/tests/e2e/support/signInWithRetry.ts:158-159`），新錯誤沿用原本的原型（`:153`）。原型鏈上的 Proxy 列舉時藏起 `actual`、讀取時卻回傳值，或丟出的錯誤是每次回報不同原型的 Proxy 時，vitest 直接讀 `err.actual`（`frontend/node_modules/@vitest/utils/dist/error.js:100-101`），讀到沒清理的值。main 上同樣會外洩。e2e 用到的套件裡的 Proxy 都不是錯誤，查不到來源。

### #18 「會說謊的 Proxy」已接受風險的前提不正確
原型鏈上的 Proxy 藏起 `stack`、`cause` 時，這個分支只處理列得到的名稱（`frontend/tests/e2e/support/signInWithRetry.ts:158-169`），vitest 經原型讀到沒清理的值（`frontend/node_modules/@vitest/utils/dist/error.js:94-96`、`:118-123`）；main 直接讀寫 `error.stack`、`error.cause`，會清理。所以規格寫的「main 上同樣會外洩」只對 `actual` 這類屬性成立，`stack`、`cause` 是這個 PR 的退步。列出的不成立 AC 也漏了 AC3、AC6、AC7、AC11、AC13。查不到來源。

### #19 陣列是讀 length 會出錯的 Proxy 時，丟出 AC12 的錯誤
`sanitizeValue` 讀 `value.length` 沒用安全讀取（`frontend/tests/e2e/support/signInWithRetry.ts:125`），讀取出錯時整個清理中斷，改丟 AC12 的錯誤，和 AC8 不符。不會外洩。查不到來源。

## 開發者決策

| # | 問題 | 選項 | 開發者的決定 | 理由 |
|---|---|---|---|---|
| 1 | 清理途中出錯時 TypeError 帶出沒清理的原始 message | A：接住清理途中的錯誤改丟清理過的新錯誤，message／stack 改用同一套寫回規則（新增 AC12）；B：只改 message／stack 寫回；C：不改，列為會外洩的風險並開 issue | A | 不用列舉會出錯的情況就能保證不外洩，成本低 |
| 3 | Buffer、TypedArray 的內容 | 在這個 PR 修／開 issue；修的話 A：換成 `[binary]`、B：解碼後清理 | 在這個 PR 修，A | 看不懂的內容整個丟掉；B 會讓清理規則管不到的內容原樣印出 |
| 4 | 修正已核准規格 AC8 的寫法 | 修正／不修正 | 修正 | 符合 CLAUDE.md 寫作規則第 2 條，意思不變 |
| 5 | 寫回沒生效、也沒出錯 | A：寫回後讀回比對（新增 AC14）；B：列為會外洩的已接受風險；C：改成建立清理過的新錯誤，不寫回原本的錯誤 | C | 第 1、2 輪的問題都出在寫回原本的錯誤，C 拿掉這一步，不用再列舉會出錯的寫法 |
| 8 | 修正已核准規格「已撤銷的 Proxy」的寫法 | 修正／不修正 | 修正 | 符合 CLAUDE.md 寫作規則第 2 條，意思不變 |
| 9 | 同一根本原因連續 3 輪有阻擋 | 繼續補測試並寫死預期字串／其他 | 繼續補測試，預期字串寫進規格 | 前幾輪交辦只寫要測什麼、沒寫完整預期輸出 |
| 10 | 原型本身是錯誤物件 | A：原型鏈每一層都清理；B：只補 message、stack；C：列已接受的風險 | A | 不用列舉特殊情況，也不比 main 退步 |
| 12 | 原型鏈測試只有一層 | 補測試／不補 | 補 | 「只清理一層」的錯誤實作也會通過 |
| 15 | 原型鏈停止條件漏掉舊式寫法（連續 3 輪） | A：走到 `Object.prototype` 之前；B：保留停止條件、另外一定帶 message／stack；C：列已接受的風險 | A | 和 vitest 讀取的範圍一致，不用再判斷哪一層是類別的原型 |
| 16 | 原型鏈上有會說謊的 Proxy | A：列成已接受的風險；B：開 issue；C：在這個 PR 修（固定名稱從原本的錯誤讀） | A | 要刻意寫出說謊的 Proxy 才會發生，查不到來源，main 上也一樣；C 依賴 vitest 內部寫法 |
| 18 | 會說謊的 Proxy 已接受風險的前提不正確 | A：只修文字；B：三個固定名稱一律直接讀取；C：vitest 會讀的固定名稱都讀 | B，並收尾：Proxy 攔截行為前後不一致一律列已接受的風險 | 不比 main 退步；第 6、7 輪都是刻意寫出的 Proxy，查不到來源 |
| 13 | 修正已核准規格 AC11 的寫法 | 修正／不修正 | 修正 | 符合寫作規則第 1 條，意思不變 |
| 11 | #28 AC2 測試保護變弱 | 開 issue／在這個 PR 修 | 在這個 PR 修 | 只多一行斷言 |

## 尚未處理

| # | 原因 | 後續（issue 編號或「無」） |
|---|---|---|
| 18 | feature-implementer 修正中 | 無 |
| 19 | feature-implementer 修正中 | 無 |
