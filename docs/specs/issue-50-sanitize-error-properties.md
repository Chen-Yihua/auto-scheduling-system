# e2e 錯誤的 actual／expected 與其他屬性沒有清理

- 狀態：已核准
- 等級：高風險（改的是「token、email 不出現在公開的 CI log」這項保證）
- issue：[#50](https://github.com/Chen-Yihua/auto-scheduling-system/issues/50)
- PR：[#126](https://github.com/Chen-Yihua/auto-scheduling-system/pull/126)

## 簡短說明
e2e 測試失敗時，vitest 會把錯誤的 `actual`／`expected` diff 與其他屬性印進公開的 CI log。這份規格讓這些內容在交給 vitest 前，和 `message`、`stack`、`cause` 一樣經過 #46 的清理。

## 背景
開發者開 PR 或合併到 `main` 時，`frontend-e2e-test` 的 assertion 失敗或函式庫丟出帶自訂屬性的錯誤，vitest 會把錯誤印進 CI log。這個 repo 是公開的，CI log 也是公開的。

#46（PR #49）在每個測試函式外層用 `withSanitizedErrors` 包住，丟出的錯誤經過 `sanitizeError` 清理（`frontend/tests/e2e/support/signInWithRetry.ts:92-111`）。`sanitizeError` 只處理 `message`、`stack`、`cause`。

vitest 3.1.3 拿到錯誤後還會印出下面兩種內容，目前都沒有清理：
- **diff**：錯誤有 `actual` 與 `expected` 時，用這兩個值算出 diff 印出；不是字串的值也會轉成文字（`frontend/node_modules/@vitest/utils/dist/error.js:100-109`）。
- **Serialized Error**：vitest 把錯誤物件與原型鏈（繼承來源）上的每個屬性都複製出來，包括不可列舉的屬性（`getOwnPropertyNames`），內層的物件、陣列一起展開（`frontend/node_modules/@vitest/utils/dist/error.js:51-83`）；印的時候略過 `message`、`stack`、`cause`、`actual`、`expected` 等固定名稱，其餘印在「Serialized Error:」下面（`frontend/node_modules/vitest/dist/chunks/index.De2FqGmR.js:257-290`、`:352-355`）。例如 `AggregateError.errors` 的每個錯誤都會印出。

測試本身失敗時，預設的 reporter 不印最外層錯誤的「Serialized Error」；CI 裡 vitest 自動加上的 `github-actions` reporter 會印，而且會變成 PR 頁面上的附註（annotation）。`cause` 的「Serialized Error」兩種 reporter 都會印。

vitest 是在錯誤丟出之後才讀這些屬性，所以在 `withSanitizedErrors` 裡清理就有效。

GitHub Actions 會把用 `${{ secrets.X }}` 帶入的值在 log 裡遮成 `***`，但遮不到測試執行時才產生的 token（例如 Clerk 的 `__clerk_db_jwt`、session JWT），也遮不到被編碼過的值。

目前 e2e 有三個 assertion：兩個比對頁面 body 文字，一個比對按鈕數量，畫面不顯示 email；Playwright 的 `TimeoutError` 沒有額外屬性，所以還沒有實際外洩。`frontend/tests/e2e/dashboard.e2e.ts:27` 的 `secrets` 清單目前只有測試帳號 email。

## 需求
1. 錯誤的 `actual`、`expected` 在交給 vitest 前經過 #46 的清理。
2. 錯誤物件自己的其他屬性（不論可不可列舉）也經過同一個清理。
3. 需求 1、2 適用於丟出的錯誤，以及沿著 `cause`、往屬性內層找到的每個 `Error`。
4. 屬性的值是物件或陣列時，換成一份清理過的複製品，原本的物件不改。
5. 欄位名稱看起來是機密（authorization、cookie、password、jwt、session 等）的值，不論內容，整個遮掉。
6. `{ name, value }` 格式（Playwright 的 header、cookie）的 `name` 看起來是機密時，`value` 整個遮掉。
7. 清理時讀某個屬性出錯，不讓沒清理的錯誤交給 vitest。
8. `secrets` 清單加上 Clerk 的 secret key。

## 不做
- 只處理 `withSanitizedErrors` 包住的測試函式丟出的錯誤，和 #46 相同。`setup()`、hook、背景事件（例如 `page.on`）丟出而沒被接住的錯誤不處理：目前查不到會產生這種錯誤的來源。
- 不改 `cause` 不是 `Error` 時轉成字串的行為（#51 的範圍）。
- 不改 vitest 的 reporter 與執行參數。
- 不改正式程式與 `.github/workflows/`。

## 假設
無。

## 驗收條件
下面的「要清理的錯誤」指：`withSanitizedErrors` 包住的函式丟出的錯誤，以及從任一個要清理的錯誤沿著 `cause` 或 AC3 往內層找到的每個 `Error`。

| # | 條件 | 類型 |
|---|---|---|
| AC1 | 要清理的錯誤，`actual`、`expected` 是字串時，丟給 vitest 前經過 #46 規格 AC3～AC7 的清理 | 不變條件（安全） |
| AC2 | 要清理的錯誤自己的其他屬性（`message`、`stack`、`cause` 以外，包括不可列舉的屬性）是字串時，經過同一個清理 | 不變條件（安全） |
| AC3 | AC1、AC2 的屬性值是 `Error` 以外的物件或陣列時，換成一份複製品：每一層的字串都經過同一個清理；內層的 `Error` 照 AC1、AC2、AC11 清理（例如 `AggregateError.errors[0]`）；沒有自有屬性可讀的物件（例如 `Map`、`Set`）變成空物件，不保留內容 | 不變條件（安全） |
| AC4 | AC3 清理時，原本的物件與陣列內容不變；`Error` 例外，和最外層的錯誤一樣直接清理 | 不變條件 |
| AC5 | AC3 遇到循環參照時會結束，複製品保留同樣的參照關係 | 不變條件 |
| AC6 | 要清理的錯誤自己的屬性（`message`、`stack`、`cause` 以外），以及 AC3 複製品裡的屬性，名稱（不分大小寫）含有 `authorization`、`cookie`、`password`、`token`、`secret`、`apikey`、`api_key`、`jwt`、`session` 任一個字的，值整個換成 `[redacted]`，不論值是什麼類型 | 不變條件（安全） |
| AC7 | AC3 清理時，物件的 `name` 是字串、而且含有 AC6 的任一個字（不分大小寫）時，同一個物件的 `value` 整個換成 `[redacted]`，不論值是什麼類型 | 不變條件（安全） |
| AC8 | 清理時讀某個屬性出錯（例如 getter（讀取時才算出值的屬性）丟出錯誤），該屬性的值換成 `[unserializable]`，其他屬性照常清理；`withSanitizedErrors` 丟出的仍是原本那個清理過的錯誤 | 不變條件（安全） |
| AC9 | 清理後，要清理的錯誤的 `actual`、`expected`、`message`、`stack` 仍可寫入（vitest 之後會寫入 `actual`、`expected`）；「已接受的風險」第 2 點列的情況除外 | 不變條件 |
| AC10 | `dashboard.e2e.ts` 的 `secrets` 清單包含 `NUXT_CLERK_SECRET_KEY` 的值，log 與錯誤裡出現這個值時遮成 `[redacted]` | 不變條件（安全） |
| AC11 | #46 規格 AC2 的行為不變：回傳同一個錯誤物件、類型不變，`message`、`stack`、`cause` 照舊清理 | 不變條件 |
| AC12 | 清理途中出錯（例如寫回屬性失敗）時，`withSanitizedErrors` 丟出一個新的 `Error`，訊息是固定文字加上經過 #46 清理的出錯訊息，不含原本錯誤沒清理的內容 | 不變條件（安全） |

## 不適用的情境
| 情境 | 原因 |
|---|---|
| 未登入／無權限、空資料、載入中 | 只改 e2e 測試程式的錯誤清理，沒有使用者畫面與 API |
| 資料處理、併發 | 不讀寫資料庫；清理是同步處理一個錯誤物件 |
| 失敗 | 讀屬性出錯時見 AC8；清理途中其他出錯見 AC12；錯誤沒有 `actual`、`expected` 或其他屬性時，維持 #46 的行為（AC11） |

## 已接受的風險
- 錯誤類別在原型上定義的 getter，vitest 會讀出來印，這次不處理：`AssertionError` 原型上的 `name`、`ok` 回傳固定值；Playwright `TimeoutError` 沒有原型 getter。
- 下面幾種情況，清理途中會出錯，`withSanitizedErrors` 改丟 AC12 的新錯誤：不會外洩，但看不到原本的失敗原因。目前查不到會產生這些值的來源。
  - 自有屬性不可寫、也不可重新定義（`writable: false` 而且 `configurable: false`），包括 `message`、`stack`。
  - `message` 或 `stack` 只有 getter、沒有 setter，而且不可重新定義。
  - 值是已撤銷的 Proxy（判斷型別時就會出錯）。
- 複製品是一般物件，diff 裡的類別名稱會變成 `Object`（例如原本是 `Response {`）；`Map`、`Set`、`Date`、`URL`、`Headers` 這類沒有自有屬性的物件變成空物件，看不到內容。
- 兩個只差在 query 的網址，清理後變成一樣的字串，diff 看不出差異。
- 物件有 `toJSON`、而且回傳的不是自有屬性時，vitest 會印 `toJSON` 的結果：和原型上的 getter 同一類，這次不處理。
- 名稱含 `token`、`session` 等字的一般欄位（例如 `tokenCount`、`sessionCount`）也會被遮掉；`{ name, value }` 的 `name` 是這類一般名稱時（例如 `{ name: 'sessionCount', value: 3 }`），`value` 也會被遮掉：和 #46「偏向多刪不漏刪」的取向相同。

## 實作計畫
1. `frontend/tests/e2e/support/signInWithRetry.ts`
   - 新增一個判斷名稱是否敏感的函式：名稱轉小寫後含 AC6 列的任一個字就算。屬性名稱（AC6）與 `name` 欄位的值（AC7）都用它。
   - 新增一個安全讀取屬性的函式：讀取時出錯就回傳 `[unserializable]`（AC8）。下面讀屬性的地方都用它；`Object.getOwnPropertyNames` 本身出錯時（例如已撤銷的 Proxy），整個值換成 `[unserializable]`。
   - 新增 `sanitizeValue(value, secrets, seen)`，`seen` 是「原本的物件 → 清理結果」的 `Map`：
     - 字串：`sanitizeForLog`。
     - `Error`：交給 `sanitizeError`（直接清理，和 `cause` 相同）。
     - 陣列：建立新陣列，每個元素遞迴處理。
     - 其他物件：建立新的一般物件，逐一處理 `Object.getOwnPropertyNames` 的每個屬性：名稱敏感的值換成 `[redacted]`；物件有字串的 `name` 而且名稱敏感時，`value` 換成 `[redacted]`（AC7）；其餘遞迴處理。
     - 物件與陣列在遞迴前先放進 `seen`；遇到已在 `seen` 的物件直接回傳它的清理結果（AC5）。
     - 其他型別（數字、布林、`null`、`undefined`、函式、symbol）照原樣回傳。
   - `sanitizeError` 在處理完 `message`、`stack`、`cause` 之後，逐一處理錯誤的 `Object.getOwnPropertyNames`（略過這三個）：名稱敏感的換成 `[redacted]`，其餘交給 `sanitizeValue`。寫回時：屬性可重新定義（`configurable: true`）的，用 `Object.defineProperty` 寫回成一般屬性，`writable: true`、`configurable: true`，保留原本的 `enumerable`，才換得掉 getter，vitest 之後也寫得進去（AC9）；不可重新定義但可寫的，直接賦值；兩者都不行的，見「已接受的風險」。
   - `sanitizeError` 的 `seen` 與 `sanitizeValue` 共用同一份記錄，同一個錯誤不會處理兩次。
   - `message`、`stack` 寫回時也用上面同一套規則（可重新定義的用 `Object.defineProperty`，否則可寫就直接賦值），不再一律直接賦值：唯讀但可重新定義的 `message` 才清得掉。
   - `withSanitizedErrors` 的 `catch` 裡，`sanitizeError` 自己丟出錯誤時，接住它，改丟 `new Error('[e2e] 錯誤清理失敗：' + sanitizeForLog(出錯訊息, secrets))`（AC12）。不能原樣丟出：Node 的 `TypeError` 訊息會附上原本錯誤的字串形式，例如 `Cannot assign to read only property 'message' of object 'Error: <原本的 message>'`。
   - 更新第 91 行的註解，寫出 vitest 還會印 `actual`／`expected` 的 diff 與其他屬性。
2. `frontend/tests/e2e/dashboard.e2e.ts`：`secrets` 改成 `[process.env.E2E_CLERK_TEST_EMAIL ?? '', process.env.NUXT_CLERK_SECRET_KEY ?? '']`。`sanitizeForLog` 已會略過空字串。

### 考慮過、沒選的做法
- **把物件轉成字串再清理**：diff 會變成兩段文字的比對，比較難讀；而且要用 vitest 內部的轉換函式，vitest 升級時可能失效。
- **不處理非字串的值**：之後只要有人寫比對物件的 assertion，就可能外洩。
- **自訂 reporter，在印出前清理**：vitest 送到 reporter 的 diff 已經是帶 ANSI 色碼的字串，色碼緊接在網址前面，#46 的網址起點規則會認不出網址；而且要重寫印錯誤的方式。
- **改用精簡的 reporter（例如 `dot`）或 `--silent`**：`dot` 仍會在最後印出失敗的錯誤與 diff；`--silent` 只隱藏測試自己的 `console` 輸出，而 #28 需要印重試標記。
- **在 `setupFiles` 註冊 `unhandledRejection`**：只接得到沒被接住的錯誤，測試失敗的錯誤由 vitest 接住，接不到。
- **錯誤加上 `toJSON`**：vitest 序列化時會用 `toJSON`，但 diff 是在那之前算的，而且依賴 vitest 內部的順序。

## 測試對應
測試都放在 `frontend/tests/e2e-support/signInWithRetry.test.ts` 的 `sanitizeError` 區塊，名稱用 `#50 ACn：` 開頭。

| AC | 測試 |
|---|---|
| AC1 | 用 `expect(...).toBe(...)` 產生真正的 `AssertionError`，`actual` 與 `expected` 都是帶 query 與 email 的字串；清理後兩者都不含 query 的值與 email，`[redacted]` 出現在原本 email 的位置。另一例：外層錯誤的 `cause` 是同樣的 `AssertionError`，清理後 `cause.actual` 也不含 |
| AC2 | 錯誤加上一個可列舉、一個不可列舉（`Object.defineProperty`，`enumerable: false`）的字串屬性，都帶 query 與 JWT；清理後都不含，`enumerable` 不變；另一例：錯誤有一個自有 getter（`configurable: true`），回傳帶 query 的字串，清理後讀到的值不含 query |
| AC3 | `actual` 是 `{ url: '/cb?code=abc', nested: [{ note: EMAIL }] }`，清理後是 `{ url: '/cb', nested: [{ note: '[redacted]' }] }`；`new AggregateError([new Error('/v1/a?t=1 ' + JWT)])` 清理後 `errors[0].message` 不含 `t=1` 與 JWT；`actual` 是 `new Map([['k', EMAIL]])` 時清理後是 `{}` |
| AC4 | AC3 的例子，清理後原本的 `actual` 物件仍是 `{ url: '/cb?code=abc', … }`；`AggregateError.errors[0]` 是同一個物件、已清理 |
| AC5 | 物件自己參照自己（`obj.self = obj`）當 `actual`，清理會結束，複製品的 `self` 指向複製品 |
| AC6 | `actual` 是 `{ headers: { Authorization: 'Bearer opaque123' }, apiKey: 'k', items: [{ password: 1 }], sessionId: 's' }`，清理後四個值都是 `[redacted]`；錯誤本身的 `token` 屬性（值是數字 `12345`）也是 `[redacted]` |
| AC7 | `actual` 是 `[{ name: '__clerk_db_jwt', value: 'dvb_abc' }, { name: 'Authorization', value: 'Bearer opaque123' }, { name: 'theme', value: 'dark' }]`，清理後前兩個 `value` 是 `[redacted]`，`theme` 的 `value` 仍是 `dark` |
| AC8 | 錯誤有一個會丟出錯誤的 getter（用 `configurable: true` 建立），`actual` 物件裡也有一個；`withSanitizedErrors` 丟出的仍是原本的錯誤，兩個值都是 `[unserializable]`，其他屬性照常清理 |
| AC9 | AC2、AC8 的例子清理後，對 `actual`、`expected`、`message`、`stack` 賦值不會丟出錯誤，讀回來是新的值 |
| AC10 | 不寫 unit 測試：PR 描述附上 `dashboard.e2e.ts` `secrets` 那一行的內容。遮蔽本身已有 #46 AC7 的測試 |
| AC11 | #46 既有的 `sanitizeError`、`withSanitizedErrors` 測試保留並通過 |
| AC12 | 錯誤的 `message` 唯讀而且不可重新定義、內容帶 query 與 email：`withSanitizedErrors` 丟出的錯誤訊息以 `[e2e] 錯誤清理失敗：` 開頭，不含 query 的值與 email。另一例：`message` 唯讀但可重新定義時，丟出的是原本那個錯誤，`message` 已清理 |

## 修改紀錄
| 日期 | 修改 | 原因 | 確認者 |
|---|---|---|---|
| 2026-11-17 | 新增 AC12；改寫「已接受的風險」第 2 點；實作計畫 `message`、`stack` 寫回方式與 `withSanitizedErrors` 的處理 | 開發者決定清理途中出錯時改丟清理過的新錯誤（實作審查第 1 輪 #1，選 A）→ AC12、已接受的風險第 2 點、實作計畫 1、測試對應 AC12；檢查過 AC8（讀取出錯仍丟原本的錯誤，不衝突）、AC9（除外條件仍指第 2 點）、AC11（正常情況仍回傳同一個錯誤）不用改 | 開發者 |
| 2026-11-17 | AC8 第一次出現 getter 時加白話說明，「已接受的風險」第 1 點拿掉重複的說明 | 開發者確認修正寫法（實作審查第 1 輪 #4）→ AC8；意思不變，其他 AC 不用改 | 開發者 |

## 請你決定
無
