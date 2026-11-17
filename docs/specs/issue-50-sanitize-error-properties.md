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
4. 清理結果放在新建的物件裡：屬性的值是物件或陣列時換成清理過的複製品，錯誤本身也換成清理過的新錯誤；原本的物件與錯誤都不改。
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
| AC3 | AC1、AC2 的屬性值是 `Error` 以外的物件或陣列時，換成一份複製品：每一層的字串都經過同一個清理；內層的 `Error` 照 AC1、AC2、AC11 換成清理過的新錯誤（例如 `AggregateError.errors[0]`）；沒有自有屬性可讀的物件（例如 `Map`、`Set`）變成空物件，不保留內容 | 不變條件（安全） |
| AC4 | 清理時，原本的物件、陣列與錯誤（包括最外層與內層的錯誤）內容都不變 | 不變條件 |
| AC5 | 清理遇到循環參照時會結束（物件與錯誤都一樣，例如錯誤的 `cause` 指回自己），清理結果保留同樣的參照關係 | 不變條件 |
| AC6 | 要清理的錯誤自己的屬性（`message`、`stack`、`cause` 以外），以及 AC3 複製品裡的屬性，名稱（不分大小寫）含有 `authorization`、`cookie`、`password`、`token`、`secret`、`apikey`、`api_key`、`jwt`、`session` 任一個字的，值整個換成 `[redacted]`，不論值是什麼類型 | 不變條件（安全） |
| AC7 | AC3 清理時，物件的 `name` 是字串、而且含有 AC6 的任一個字（不分大小寫）時，同一個物件的 `value` 整個換成 `[redacted]`，不論值是什麼類型 | 不變條件（安全） |
| AC8 | 清理時讀某個屬性出錯（例如 getter（讀取時才算出值的屬性）丟出錯誤），該屬性的值換成 `[unserializable]`，其他屬性照常清理；`withSanitizedErrors` 照常丟出 AC11 的清理過的錯誤，不改丟 AC12 的錯誤 | 不變條件（安全） |
| AC9 | 清理後，要清理的錯誤的 `actual`、`expected`、`message`、`stack` 仍可寫入（vitest 之後會寫入 `actual`、`expected`） | 不變條件 |
| AC10 | `dashboard.e2e.ts` 的 `secrets` 清單包含 `NUXT_CLERK_SECRET_KEY` 的值，log 與錯誤裡出現這個值時遮成 `[redacted]` | 不變條件（安全） |
| AC11 | 取代 #46 規格 AC2 的「回傳同一個錯誤物件」：`sanitizeError` 回傳一個新的錯誤物件，原型和原本的錯誤相同（`instanceof` 與類型名稱不變），只帶清理過的屬性；`message`、`stack`、`cause` 照 #46 的規則清理；不是 `Error` 的值照 #46 轉成字串清理後包成 `Error` | 不變條件（安全） |
| AC12 | 清理途中出錯（例如判斷型別時出錯）時，`withSanitizedErrors` 丟出一個新的 `Error`，訊息是固定文字加上經過 #46 清理的出錯訊息；出錯訊息本身取不到（例如轉成文字時又出錯）時，只用固定文字加 `[unserializable]`。丟出的內容不含原本錯誤沒清理的內容 | 不變條件（安全） |
| AC13 | AC1～AC3 清理時，值是二進位資料（`ArrayBuffer.isView` 為真，例如 `Buffer`、`Uint8Array`）時，整個換成 `[binary]`，不保留內容 | 不變條件（安全） |
| AC14 | #28 規格 AC2「照原本的錯誤讓測試失敗」不變：`signInWithRetry` 丟出的錯誤經過 `withSanitizedErrors` 後，清理結果的 `stack` 等於原本那個錯誤的 `stack` 經過 #46 清理後的值 | 不變條件 |
| AC15 | 原本的錯誤的原型本身是帶內容的物件時（例如 `Object.create(另一個錯誤)`），從原本的錯誤沿原型鏈往上、到第一個有自有 `constructor` 的物件（類別的原型）之前，途中每一層的屬性也照 AC11 的規則清理後定義在新錯誤上；同名時離原本的錯誤越近的優先 | 不變條件（安全） |

## 不適用的情境
| 情境 | 原因 |
|---|---|
| 未登入／無權限、空資料、載入中 | 只改 e2e 測試程式的錯誤清理，沒有使用者畫面與 API |
| 資料處理、併發 | 不讀寫資料庫；清理是同步處理一個錯誤物件 |
| 失敗 | 讀屬性出錯時見 AC8；清理途中其他出錯見 AC12；錯誤沒有 `actual`、`expected` 或其他屬性時，照 AC11 只清理 `message`、`stack`、`cause` |

## 已接受的風險
- 錯誤類別在原型上定義的 getter，vitest 會讀出來印，這次不處理：`AssertionError` 原型上的 `name`、`ok` 回傳固定值；Playwright `TimeoutError` 沒有原型 getter。
- 值是已撤銷的 Proxy（包住另一個物件、攔截讀寫的物件；撤銷後任何操作都會出錯）時，判斷型別就會出錯，`withSanitizedErrors` 改丟 AC12 的新錯誤：不會外洩，但看不到原本的失敗原因。目前查不到會產生這種值的來源。
- 測試程式如果還留著原本那個錯誤的參照，讀到的是沒清理的內容（AC4 不改原本的錯誤）：交給 vitest 的只有新錯誤，`withSanitizedErrors` 之後沒有程式會再讀原本的錯誤。
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
     - 二進位資料（`ArrayBuffer.isView` 為真）：回傳 `[binary]`（AC13）。要在一般物件之前判斷：`Buffer` 有以數字為名稱的自有屬性，當成一般物件複製會保留每個位元組。
     - `Error`：交給 `sanitizeError`，換成清理過的新錯誤。
     - 陣列：建立新陣列，每個元素遞迴處理。
     - 其他物件：建立新的一般物件，逐一處理 `Object.getOwnPropertyNames` 的每個屬性：名稱敏感的值換成 `[redacted]`；物件有字串的 `name` 而且名稱敏感時，`value` 換成 `[redacted]`（AC7）；其餘遞迴處理。
     - 物件與陣列在遞迴前先放進 `seen`；遇到已在 `seen` 的物件直接回傳它的清理結果（AC5）。
     - 其他型別（數字、布林、`null`、`undefined`、函式、symbol）照原樣回傳。
   - `sanitizeError` 改成建立新的錯誤，不改原本的錯誤（AC4、AC11）：
     - `const copy = new Error()`，再 `Object.setPrototypeOf(copy, Object.getPrototypeOf(error))`：用 `new Error()` 建立，`copy` 才是真的錯誤物件；換原型，`instanceof` 與類型名稱才和原本相同。`new Error()` 會自帶 `stack`，原本的錯誤沒有 `stack` 時要刪掉。
     - 先 `seen.set(error, copy)`，再處理屬性（AC5）。
     - 逐一處理原本錯誤的 `Object.getOwnPropertyNames`（包括 `message`、`stack`、`cause`），接著沿原型鏈往上處理每一層，直到遇到有自有 `constructor` 的物件就停（AC15）；已處理過的屬性名稱不再處理。原型鏈上的物件也一樣，讀取一律用安全讀取：`message`、`stack` 是字串時 `sanitizeForLog`；`cause` 照 #46 的規則（`Error` 遞迴、不是 `Error` 時轉成字串清理後包成 `Error`）；其他屬性名稱敏感的換成 `[redacted]`，其餘交給 `sanitizeValue`。
     - 用 `Object.defineProperty` 定義在 `copy` 上：`writable: true`、`configurable: true`，保留原本的 `enumerable`（AC2、AC9）。`copy` 是自己建立的一般物件，寫入一定生效，不必處理 setter、唯讀屬性或 Proxy 攔截寫入的情況。
     - 回傳 `copy`。
   - `sanitizeError` 的 `seen` 與 `sanitizeValue` 共用同一份記錄，同一個錯誤不會處理兩次。
   - `withSanitizedErrors` 的 `catch` 裡，`sanitizeError` 自己丟出錯誤時，接住它，改丟 `new Error('[e2e] 錯誤清理失敗：' + sanitizeForLog(出錯訊息, secrets))`（AC12）。不能原樣丟出：Node 的 `TypeError` 訊息可能附上原本錯誤的字串形式。取出錯誤訊息並轉成文字的步驟也要用 `try` 包住，失敗時用 `[unserializable]`。
   - 更新第 91 行的註解，寫出 vitest 還會印 `actual`／`expected` 的 diff 與其他屬性。
2. `docs/specs/issue-46-sanitize-relative-url-query.md`：狀態行改成「部分被 [issue-50-sanitize-error-properties](issue-50-sanitize-error-properties.md) 取代（AC2）」，其他內容不改（`docs/specs/README.md`「規格和目前系統的關係」）。
3. `frontend/tests/e2e/dashboard.e2e.ts`：`secrets` 改成 `[process.env.E2E_CLERK_TEST_EMAIL ?? '', process.env.NUXT_CLERK_SECRET_KEY ?? '']`。`sanitizeForLog` 已會略過空字串。

### 考慮過、沒選的做法
- **把物件轉成字串再清理**：diff 會變成兩段文字的比對，比較難讀；而且要用 vitest 內部的轉換函式，vitest 升級時可能失效。
- **不處理非字串的值**：之後只要有人寫比對物件的 assertion，就可能外洩。
- **自訂 reporter，在印出前清理**：vitest 送到 reporter 的 diff 已經是帶 ANSI 色碼的字串，色碼緊接在網址前面，#46 的網址起點規則會認不出網址；而且要重寫印錯誤的方式。
- **改用精簡的 reporter（例如 `dot`）或 `--silent`**：`dot` 仍會在最後印出失敗的錯誤與 diff；`--silent` 只隱藏測試自己的 `console` 輸出，而 #28 需要印重試標記。
- **在 `setupFiles` 註冊 `unhandledRejection`**：只接得到沒被接住的錯誤，測試失敗的錯誤由 vitest 接住，接不到。
- **把清理結果寫回原本的錯誤**（第 1 版的做法）：寫回會遇到唯讀屬性、不存值的 setter、假裝寫入成功的 Proxy，有的會出錯、有的不出錯卻沒寫進去，要一一列舉處理（實作審查第 1 輪 #1、第 2 輪 #5）；寫回後再讀一次比對也能抓到，但仍是在寫回上補檢查。
- **錯誤加上 `toJSON`**：vitest 序列化時會用 `toJSON`，但 diff 是在那之前算的，而且依賴 vitest 內部的順序。

## 測試對應
測試都放在 `frontend/tests/e2e-support/signInWithRetry.test.ts` 的 `sanitizeError` 區塊，名稱用 `#50 ACn：` 開頭。

| AC | 測試 |
|---|---|
| AC1 | 用 `expect(...).toBe(...)` 產生真正的 `AssertionError`，`actual` 與 `expected` 都是帶 query 與 email 的字串；清理後兩者都不含 query 的值與 email，`[redacted]` 出現在原本 email 的位置。另一例：外層錯誤的 `cause` 是同樣的 `AssertionError`，清理後 `cause.actual` 也不含。另一例：錯誤的 `message` 唯讀而且不可重新定義、帶 query 與 email，清理結果的 `message` 不含 |
| AC2 | 錯誤加上一個可列舉、一個不可列舉（`Object.defineProperty`，`enumerable: false`）的字串屬性，都帶 query 與 JWT；清理後都不含，`enumerable` 不變；另一例：錯誤有一個自有 getter（`configurable: true`），回傳帶 query 的字串，清理後讀到的值不含 query。另一例：錯誤有一個不可重新定義的 getter 加上不存值的 setter，回傳帶 query 的字串，清理結果的值不含 query |
| AC3 | `actual` 是 `{ url: '/cb?code=abc', nested: [{ note: EMAIL }] }`，清理後是 `{ url: '/cb', nested: [{ note: '[redacted]' }] }`；`new AggregateError([new Error('/v1/a?t=1 ' + JWT)])` 清理後 `errors[0].message` 不含 `t=1` 與 JWT；`actual` 是 `new Map([['k', EMAIL]])` 時清理後是 `{}` |
| AC4 | AC3 的例子，清理後原本的 `actual` 物件仍是 `{ url: '/cb?code=abc', … }`；原本錯誤的 `message`、原本 `AggregateError.errors[0]` 的 `message` 都不變，清理結果的 `errors[0]` 是另一個物件、已清理 |
| AC5 | 物件自己參照自己（`obj.self = obj`）當 `actual`，清理會結束，複製品的 `self` 指向複製品；錯誤的 `cause` 指回自己時，清理會結束，清理結果的 `cause` 指向清理結果 |
| AC6 | `actual` 是 `{ headers: { Authorization: 'Bearer opaque123' }, apiKey: 'k', items: [{ password: 1 }], sessionId: 's' }`，清理後四個值都是 `[redacted]`；`{ session: { id: 'abc' } }` 的 `session` 整個是 `[redacted]`；錯誤本身的 `token` 屬性（值是數字 `12345`）也是 `[redacted]` |
| AC7 | `actual` 是 `[{ name: '__clerk_db_jwt', value: 'dvb_abc' }, { name: 'Authorization', value: 'Bearer opaque123' }, { name: 'theme', value: 'dark' }]`，清理後前兩個 `value` 是 `[redacted]`，`theme` 的 `value` 仍是 `dark`；`{ name: 'session', value: { id: 'abc' } }` 的 `value` 整個是 `[redacted]` |
| AC8 | 錯誤有一個會丟出錯誤的 getter（用 `configurable: true` 建立），`actual` 物件裡也有一個；`withSanitizedErrors` 丟出的是 AC11 的清理結果（訊息不以 `[e2e] 錯誤清理失敗：` 開頭），兩個值都是 `[unserializable]`，其他屬性照常清理 |
| AC9 | 原本錯誤的 `expected` 是只有 getter 的屬性：清理結果對 `actual`、`expected`、`message`、`stack` 賦值不會丟出錯誤，讀回來是新的值 |
| AC10 | 不寫 unit 測試：PR 描述附上 `dashboard.e2e.ts` `secrets` 那一行的內容。遮蔽本身已有 #46 AC7 的測試 |
| AC11 | #46 既有的 `sanitizeError`、`withSanitizedErrors` 測試保留；斷言「回傳同一個物件」（`toBe(error)`）的改成「不是原本的物件、`instanceof` 原本的類別、`name` 相同、內容已清理」。另一例：丟出的錯誤是攔截定義屬性卻不寫入的 Proxy，清理結果的 `message` 不含 query |
| AC12 | 三個例子：（1）丟出的值是已撤銷的 Proxy：丟出的錯誤訊息以 `[e2e] 錯誤清理失敗：` 開頭，而且含有出錯原因（`revoked`）。（2）丟出 `{ toString() { throw '/cb?code=abc ' + EMAIL } }`：清理時轉成文字丟出的是一個帶 query 與 email 的字串，這個字串就是出錯原因，丟出的錯誤訊息**完全等於** `'[e2e] 錯誤清理失敗：/cb [redacted]'`。（3）丟出的值的 `toString` 丟出一個物件，那個物件的 `toString` 又丟出帶 query 與 email 的字串：出錯原因轉不成文字，丟出的錯誤訊息**完全等於** `'[e2e] 錯誤清理失敗：[unserializable]'` |
| AC13 | `actual` 是 `Buffer.from('/cb?code=SECRET')`、`expected` 是 `new Uint8Array([1, 2])`、錯誤的其他屬性是 `{ body: Buffer.from(EMAIL) }`：清理後分別是 `[binary]`、`[binary]`、`{ body: '[binary]' }` |
| AC14 | #28 AC2 的 4 個測試共用的輔助函式 `expectOriginalMessageWithEmailRedacted` 加一行：清理結果的 `stack` 完全等於 `sanitizeForLog(原本錯誤.stack, [EMAIL])`。把 `signInWithRetry` 改成重新丟出訊息相同的新錯誤時，4 個測試都會失敗 |
| AC15 | 兩個例子：（1）`inner` 是 `message` 為 `'/cb?code=abc ' + EMAIL`、`actual` 為 `'/x?token=1 ' + EMAIL` 的錯誤，丟出 `Object.create(inner)`：清理結果的 `message` 完全等於 `'/cb [redacted]'`，`actual` 完全等於 `'/x [redacted]'`，`stack` 不含 `code=abc` 與 EMAIL，`instanceof Error` 為真。（2）`inner = new Error('/i?q=1 ' + EMAIL)`；`middle = Object.create(inner)`，自有 `actual` 為 `'/m?q=1 ' + EMAIL`、自有 `message` 為 `'/m?q=2'`；`error = Object.create(middle)`，自有 `message` 為 `'/e?q=1'`：清理結果的 `message` 完全等於 `'/e'`，`actual` 完全等於 `'/m [redacted]'`，`stack` 的第一行完全等於 `'Error: /i [redacted]'`。用「只清理一層原型」的錯誤實作確認例子（2）會失敗 |

## 修改紀錄
| 日期 | 修改 | 原因 | 確認者 |
|---|---|---|---|
| 2026-11-17 | 新增 AC12；改寫「已接受的風險」第 2 點；實作計畫 `message`、`stack` 寫回方式與 `withSanitizedErrors` 的處理 | 開發者決定清理途中出錯時改丟清理過的新錯誤（實作審查第 1 輪 #1，選 A）→ AC12、已接受的風險第 2 點、實作計畫 1、測試對應 AC12；檢查過 AC8（讀取出錯仍丟原本的錯誤，不衝突）、AC9（除外條件仍指第 2 點）、AC11（正常情況仍回傳同一個錯誤）不用改 | 開發者 |
| 2026-11-17 | AC8 第一次出現 getter 時加白話說明，「已接受的風險」第 1 點拿掉重複的說明 | 開發者確認修正寫法（實作審查第 1 輪 #4）→ AC8；意思不變，其他 AC 不用改 | 開發者 |
| 2026-11-17 | 新增 AC13；實作計畫 `sanitizeValue` 加二進位資料；測試對應 AC13 | 開發者決定在這個 PR 修實作審查第 1 輪 #3，二進位資料整個換成 `[binary]`（選 A）→ AC13、實作計畫 1、測試對應 AC13；檢查過 AC3（Map、Set 規則不變，二進位資料另由 AC13 處理）、AC4、AC5、AC6、AC7 不用改 | 開發者 |
| 2026-11-17 | 改成建立清理過的新錯誤，不改原本的錯誤：改寫需求 4、AC3、AC4、AC5、AC8、AC9、AC11、AC12，「已接受的風險」第 2 點，實作計畫 1、2（#46 規格狀態），測試對應 AC1、AC2、AC4～AC9、AC11、AC12 | 開發者決定改做法（實作審查第 2 輪 #5，選 C）→ AC11 取代 #46 AC2 的「回傳同一個物件」、AC4 拿掉 `Error` 例外、已接受的風險第 2 點只剩已撤銷的 Proxy；第 2 輪 #6 → AC12 補「出錯訊息取不到」；第 2 輪 #7 → 測試對應 AC6、AC7、AC12；第 2 輪 #8（開發者確認）→ 已撤銷的 Proxy 加白話說明。檢查過 AC1、AC2、AC6、AC7、AC10、AC13 的條件不用改 | 開發者 |
| 2026-11-17 | AC11 補原型鏈上的內容；新增 AC14；測試對應 AC11、AC12 寫出完整的預期字串，新增 AC14 | 開發者決定：實作審查第 3 輪 #10 選 A（原型鏈到類別原型之前的每一層都清理）→ AC11、實作計畫 1、測試對應 AC11；#9 補「出錯原因經過清理」的測試，預期字串寫死 → 測試對應 AC12；#11 在這個 PR 修 → AC14、測試對應 AC14。檢查過 AC4（原型鏈上的物件只讀不寫）、AC5（原型鏈不會循環，不用記進 `seen`）、AC8（讀取出錯換 `[unserializable]`）、AC12 的條件不用改 | 開發者 |
| 2026-11-17 | 測試對應 AC11 的 `actual` 例子改成 `'/x?token=1 '`；修正測試對應 AC11 的表格格式；修正上一筆修改紀錄的 AC5 說明 | 開發者確認修正規格錯誤（feature-implementer 回報：`x?token=1` 不是 #46 的網址候選，原本的預期值照規則做不出來）→ 測試對應 AC11；行為不變，其他 AC 不用改 | 開發者 |
| 2026-11-17 | AC11 的原型鏈規則拆成新的 AC15；測試對應 AC15 新增三層原型的例子（原本 AC11 的 `Object.create(inner)` 例子移到 AC15）；刪掉實作計畫重複的半句 | 開發者確認：實作審查第 4 輪 #12 補多層原型的測試 → 測試對應 AC15；#13 拆 AC11、刪重複 → AC11、AC15、實作計畫 1。行為不變，其他 AC 不用改 | 開發者 |

## 請你決定
無
