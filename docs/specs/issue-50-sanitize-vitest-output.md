# e2e 失敗時 vitest 印出的內容用 reporter 清理

- 狀態：已核准
- 等級：高風險（改的是「token、email 不出現在公開的 CI log」這項保證）
- issue：[#50](https://github.com/Chen-Yihua/auto-scheduling-system/issues/50)、[#129](https://github.com/Chen-Yihua/auto-scheduling-system/issues/129)
- PR：#142

## 簡短說明
e2e 測試失敗時，vitest 會把 diff、錯誤的其他屬性、hook 錯誤、沒被接住的錯誤和測試的 `console` 輸出印進公開的 CI log，目前只有 `message`、`stack`、`cause` 經過清理。這份規格在 `vitest.e2e.config.ts` 加一個 reporter（vitest 裡負責把測試結果印出來的模組），在其他 reporter 印出之前，先清理要印的內容。

## 背景
開發者開 PR 或合併到 `main` 時，`frontend-e2e-test` 的測試如果失敗，vitest 會把錯誤印進 CI log。這個 repo 是公開的，CI log 也是公開的。GitHub 會把 `${{ secrets.X }}` 的值在 log 裡遮成 `***`，但遮不到測試執行時才產生的 token（例如 Clerk 的 `__clerk_db_jwt`、session JWT），也遮不到被編碼過的值。

#46（PR #49）用 `withSanitizedErrors` 包住每個測試函式，丟出的錯誤經過 `sanitizeError` 清理（`frontend/tests/e2e/support/signInWithRetry.ts:91-111`），只清理 `message`、`stack`、`cause`。vitest 3.1.3 還會印出下面這些內容，目前都沒有清理：
- `actual`／`expected` 的 diff。
- 「Serialized Error:」：錯誤的其他屬性，例如 `AggregateError.errors`。
- `afterAll` 這類 hook 丟出的錯誤、測試檔最上層（收集階段）丟出的錯誤、沒被接住的 Promise 錯誤：這些都不經過 `withSanitizedErrors`。
- CI 裡的 `github-actions` reporter 把同樣的內容印成 `::error` 附註，顯示在 PR 頁面上。

目前 e2e 有三個 assertion，畫面也不顯示 email，所以還沒有實際外洩。

`dashboard.e2e.ts` 登入失敗時印的「登入後診斷」（#28 用來除錯）有 `hasSession`、`cookieNames` 兩個欄位（`frontend/tests/e2e/dashboard.e2e.ts:54-69`），名稱含有敏感名稱，照文字規則 3 會被遮掉；兩個值本身不是機密（一個是布林值，一個只有 cookie 名稱）。

### vitest 怎麼把錯誤交給 reporter（vitest 3.1.3）
- 測試在 worker（另外開的執行環境）裡失敗時，vitest 先把錯誤序列化成單純的資料，再送回主行程（`@vitest/runner` 的 `failTask` 呼叫 `processError`）。
- 主行程把收到的結果直接存成同一份資料，再照設定的順序逐一呼叫每個 reporter 的同一個方法（`frontend/node_modules/vitest/dist/chunks/cli-api.Bti1vevt.js:8126-8131`、`:9613-9617`）。所以排在第一個的 reporter 如果在方法裡**同步**改掉資料，後面的 reporter 印出的就是改過的內容；如果用 `await`，後面的 reporter 會先執行。
- 收集完成（`onCollected`）、結果更新（`onTaskUpdate`）與測試的 `console` 輸出（`onUserConsoleLog`）在執行期間交錯發生，最後是結束（`onTestRunEnd`、`onFinished`，帶著沒被接住的錯誤）（`cli-api.Bti1vevt.js:8171-8196`、`frontend/node_modules/vitest/dist/chunks/console.K1NMVOSc.js:43-55`）。收集階段的錯誤之後也會經過 `onTaskUpdate`。
- worker 裡的錯誤都經過序列化；主行程自己丟出的錯誤（例如 worker 啟動失敗）不經過序列化，是原本的 `Error` 物件，`message`、`stack` 是不可列舉的屬性（`cli-api.Bti1vevt.js:9262-9264`）。
- 設定檔沒有列出 `reporters` 時，vitest 預設用 `default`，在 `GITHUB_ACTIONS=true` 時再自動加上 `github-actions`；設定檔一旦列出 `reporters`，就不會自動加（`frontend/node_modules/vitest/dist/chunks/coverage.87S59-Sl.js:8231-8235`）。

### reporter 拿到的資料長什麼樣子（2026-11-19 在 Node 20、vitest 3.1.3 實測）
- `message`、`stack`、`diff`、`actual`、`expected` 都是字串；`diff` 帶 ANSI 色碼（終端機的顏色控制碼）。色碼緊接在網址前面時，`sanitizeForLog` 的網址起點規則會認不出網址。
- 錯誤的其他屬性保留結構，是物件與陣列：
  - `headers: { Authorization: 'Bearer abc' }` 照原樣保留。
  - `Buffer` 變成 `{ type: 'Buffer', data: [104, 105] }`。
  - `Uint8Array` 變成一般物件：每個位元組是 `"0"`、`"1"` 這類欄位，另外有 `constructor: 'Function<Uint8Array>'`。
- diff 和訊息裡的二進位資料長這樣：
  - 訊息：`expected Buffer[ 47, 99, 98, …(-86) ] to deeply equal Buffer[ 120 ]`、`Uint8Array[ 47, 99, 98 ]`。
  - `Buffer` 的 diff：`"data": [` 底下一行一個數字，後面接 `"type": "Buffer"`。
  - `Uint8Array` 的 diff：`Uint8Array [` 底下一行一個數字。
- vitest 的 diff 預設只印改動前後各 5 行，前面用 ` -28,11 +28,11 ` 這類標頭帶過（`frontend/node_modules/@vitest/utils/dist/diff.js:1402`、`:1420`）。這時 `"name"`、`"data": [`、`Uint8Array [` 這些開頭行可能不在畫面上，例如比對 4 個 cookie 的陣列只有最後一個不同時，前一個 cookie 的 `"value": "dvb_…"` 會印出、它的 `"name"` 不會。設定 `test.diff: { expand: true }` 後，測試與 hook 的錯誤會完整印出（`frontend/node_modules/vitest/dist/chunks/reporters.d.DG9VKi4m.d.ts:1866`、`frontend/node_modules/@vitest/runner/dist/index.js:1212`、`:1374-1387`）；沒被接住的錯誤和測試檔收集階段的錯誤組 diff 時不帶這個設定，仍然只印改動附近的行（`frontend/node_modules/vitest/dist/chunks/execute.BpmIjFTD.js:557`、`frontend/node_modules/@vitest/runner/dist/index.js:1142-1143`）。
- Playwright cookie 這類物件在 diff 裡是多行，欄位照字母排序：`"domain"`、`"name"`、`"path"`、`"value"`。在訊息裡是同一行：`{ name: '__clerk_db_jwt', …(3) }`。
- reporter 在 `onTaskUpdate`、`onTestRunEnd`、`onFinished` 原地改掉這些資料之後，diff、Serialized Error、`::error` 附註、沒被接住的錯誤、hook 錯誤裡執行時產生的機密都不再出現（實驗：44 次 → 0 次）。剩下的是原始碼節錄裡寫死的字串。

## 需求
1. `vitest.e2e.config.ts` 加一個清理用的 reporter，排在所有 reporter 的第一個。
2. `GITHUB_ACTIONS=true` 時，`vitest.e2e.config.ts` 自己加上 `github-actions` reporter，排在 `default` 後面。
3. 清理用的 reporter 在其他 reporter 印出之前，清理每個測試、hook、測試檔收集階段的錯誤。
4. 清理用的 reporter 在其他 reporter 印出之前，清理沒被接住的錯誤。
5. 清理用的 reporter 在其他 reporter 印出之前，清理測試用 `console` 印的內容。
6. 字串照「文字規則」清理（見 AC6～AC11、AC19、AC21）。
7. 物件與陣列逐層處理：欄位名稱敏感、`{ name, value }`、二進位資料照「結構規則」清理（見 AC12～AC14），其餘的字串照文字規則清理。
8. 敏感名稱是 `authorization`、`cookie`、`password`、`token`、`secret`、`apikey`、`api_key`、`jwt`、`session`、`refresh`：名稱不分大小寫，含有其中任一個字就算。
9. 清理清單（要換成 `[redacted]` 的固定值）是環境變數 `E2E_CLERK_TEST_EMAIL`、`NUXT_CLERK_SECRET_KEY`、`E2E_CLERK_TEST_PASSWORD` 的值；沒有設定或是空字串的不放進清單。
10. `dashboard.e2e.ts` 的 `secrets` 和清理用的 reporter 用同一個函式取得清理清單。
11. 加一個整合測試：真的執行一次 vitest，確認清理用的 reporter 在 vitest 現在的版本仍然有效，vitest 升級時這個測試會抓到失效。
12. `vitest.e2e.config.ts` 設定 `test.diff: { expand: true }`，測試與 hook 錯誤的 diff 一定完整印出，文字規則 4、6 要看的開頭行才一定在畫面上。
13. `dashboard.e2e.ts` 登入後診斷的欄位 `hasSession` 改名為 `hasClerkSid`、`cookieNames` 改名為 `browserStorageNames`，值不變。
14. 只印出一部分的 diff（沒被接住的錯誤、收集階段的錯誤）整段不印。

## 不做
- 防護範圍只有環境變數、Clerk、Playwright、Nuxt app 實際產生的值。測試程式刻意寫出的特殊物件或格式（例如 Proxy、自訂原型、刻意把機密拆開再接起來的字串）不防。審查遇到這類情況照「不做」處理，不列為阻擋。
- 原始碼節錄（vitest 印在錯誤下面的那幾行原始碼）不處理：內容是 repo 裡已公開的原始碼。
- 測試名稱不處理：寫在原始碼裡。
- Nuxt server 自己的輸出不處理。
- vitest 在測試開始前自己印的錯誤（例如設定檔載入失敗）不處理：不經過 reporter，那時也還沒有執行時產生的值。
- `cause` 不是 `Error` 時的顯示不改（#51）。
- #46 的 `withSanitizedErrors`、`sanitizeError`、`createDiagnosticLogger`、`sanitizeForLog` 保留不動。
- unit 測試的設定（`vitest.config.ts`）不加清理用的 reporter：unit 測試不接觸真的帳號與 token。
- 不改正式程式與 `.github/workflows/`。

## 假設
無。

## 驗收條件
「要印的內容」指：其他 reporter 會印出的每個測試、hook、測試檔的錯誤，沒被接住的錯誤，以及測試用 `console` 印的內容。

文字規則用的清理清單，下面的例子都用 `['fixture-user@example.com', 'sk_test_FIXTURESECRET', 'fixture-password']`。

| # | 條件 | 類型 |
|---|---|---|
| AC1 | 執行 `npm run test:e2e` 時，`GITHUB_ACTIONS` 是 `true`，reporter 依序是清理用的 reporter、`default`、`github-actions`；不是 `true` 時，依序是清理用的 reporter、`default` | 不變條件 |
| AC2 | 測試失敗時，`default` 與 `github-actions` 印出的 `message`、`stack`、diff 和 Serialized Error，執行時才產生的機密都已經過清理 | 不變條件（安全） |
| AC3 | hook 丟出的錯誤、測試檔收集階段丟出的錯誤，兩個 reporter 印出時都已經過清理 | 不變條件（安全） |
| AC4 | 沒被接住的錯誤，兩個 reporter 印出時都已經過清理 | 不變條件（安全） |
| AC5 | 測試用 `console` 印的內容，`default` 印出時已經過清理 | 不變條件（安全） |
| AC6 | 文字規則 1、2：先拿掉 ANSI 色碼，再套用 `sanitizeForLog`。`'\x1b[32m+   "url": "/cb?code=abc",\x1b[39m'` 清理後完全等於 `'+   "url": "/cb",'`；`'+   "who": "fixture-user@example.com",'` 清理後完全等於 `'+   "who": "[redacted]",'` | 不變條件（安全） |
| AC7 | 文字規則 3：名稱（英數字、`_`、`.`、`-` 組成，前後可以有引號）是敏感名稱，後面接著 `:` 或 `=`（中間可以有空白）時，分隔符號與後面的空白保留，之後到行尾換成 `[redacted]`。`'+     "authorization": "Bearer opaqueTOKEN9",'` 完全等於 `'+     "authorization": [redacted]'`；`'x?token=1'` 完全等於 `'x?token=[redacted]'`；`'apiKey=abc; theme=dark'` 完全等於 `'apiKey=[redacted]'`；`'+     "theme": "dark",'` 不變 | 不變條件（安全） |
| AC8 | 文字規則 4：`name` 的值含有敏感名稱時，之後、遇到 `}` 之前出現的 `value`，照 AC7 處理（`name`、`value` 在同一行或不同行都一樣）。`'+     "name": "__clerk_db_jwt",\n+     "path": "/",\n+     "value": "dvb_X",\n+   },'` 完全等於 `'+     "name": "__clerk_db_jwt",\n+     "path": "/",\n+     "value": [redacted]\n+   },'`；`"expected [ { name: '__clerk_db_jwt', value: 'dvb_X' } ] to deeply equal []"` 完全等於 `"expected [ { name: '__clerk_db_jwt', value: [redacted]"`；`'+     "name": "__refresh_AbCd",\n+     "path": "/",\n+     "value": "opaqueREFRESH99",\n+   },'` 完全等於 `'+     "name": "__refresh_AbCd",\n+     "path": "/",\n+     "value": [redacted]\n+   },'`；`name` 是 `theme` 時 `value` 不變 | 不變條件（安全） |
| AC9 | 文字規則 5：`Bearer ` 後面接的非空白字串換成 `[redacted]`。`'request failed with Bearer abc.def-ghi'` 完全等於 `'request failed with Bearer [redacted]'` | 不變條件（安全） |
| AC10 | 文字規則 6（訊息的形式）：二進位類型（`Buffer`、`ArrayBuffer`、`SharedArrayBuffer`、`DataView`、`Int8Array`、`Uint8Array`、`Uint8ClampedArray`、`Int16Array`、`Uint16Array`、`Int32Array`、`Uint32Array`、`Float32Array`、`Float64Array`、`BigInt64Array`、`BigUint64Array`，以下稱「AC10 的二進位類型」）的名稱，接著 `[`（中間可以有空白）到對應的 `]`，整段換成 `[binary]`，可以跨行。`'expected Buffer[ 47, 99, 98, …(-86) ] to deeply equal Buffer[ 120 ]'` 完全等於 `'expected [binary] to deeply equal [binary]'`；`'  Uint8Array [\n-   1,\n+   47,\n  ]'` 完全等於 `'  [binary]'`；`'  Float32Array [\n+   1.5,\n  ]'` 完全等於 `'  [binary]'` | 不變條件（安全） |
| AC11 | 文字規則 6（`Buffer` 的 diff 形式）：`"data": [` 之後到對應的 `]` 之間，每一行去掉 diff 的 `+`、`-` 與空白後只有整數和逗號時，從 `[` 到 `]` 換成 `[binary]`。`'    "data": [\n-     120,\n+     47,\n    ],'` 完全等於 `'    "data": [binary],'`；`'    "data": [\n      "a",\n    ],'` 不變 | 不變條件（安全） |
| AC12 | 結構規則 1：物件的欄位名稱是敏感名稱時，值整個換成 `'[redacted]'`，不論值的型別。`{ headers: { Authorization: 'Bearer abc' }, token: 123, note: '/cb?code=abc fixture-user@example.com' }` 清理後等於 `{ headers: { Authorization: '[redacted]' }, token: '[redacted]', note: '/cb [redacted]' }`；`{ cookies: [{ name: 'theme', value: 'dark' }] }` 清理後等於 `{ cookies: '[redacted]' }` | 不變條件（安全） |
| AC13 | 結構規則 2：物件的 `name` 是字串而且含有敏感名稱時，同一個物件的 `value` 整個換成 `'[redacted]'`。`{ items: [{ name: '__clerk_db_jwt', value: 'dvb_X' }, { name: 'theme', value: 'dark' }] }` 清理後等於 `{ items: [{ name: '__clerk_db_jwt', value: '[redacted]' }, { name: 'theme', value: 'dark' }] }`；`{ items: [{ name: '__refresh_AbCd', value: 'opaque' }] }` 清理後等於 `{ items: [{ name: '__refresh_AbCd', value: '[redacted]' }] }` | 不變條件（安全） |
| AC14 | 結構規則 3：二進位資料整個換成 `'[binary]'`。判斷方式：`type` 是 `'Buffer'` 而且 `data` 是陣列的物件，或 `constructor` 是 `'Function<名稱>'`、名稱是 AC10 的二進位類型的物件。`{ body: { type: 'Buffer', data: [104, 105] }, u8: { '0': 1, '1': 2, constructor: 'Function<Uint8Array>', length: 2 } }` 清理後等於 `{ body: '[binary]', u8: '[binary]' }` | 不變條件（安全） |
| AC15 | 要清理的資料有循環參照（例如物件的欄位指回自己）時，清理會結束，不丟出錯誤，參照關係保留；同一份二進位資料被多個欄位參照時，每個欄位都換成 `'[binary]'` | 不變條件（安全） |
| AC16 | 清理清單取自 `E2E_CLERK_TEST_EMAIL`、`NUXT_CLERK_SECRET_KEY`、`E2E_CLERK_TEST_PASSWORD`：三個都有值時，清單是這三個值；只設定 `E2E_CLERK_TEST_EMAIL`、其他沒設定或是空字串時，清單只有 email | 不變條件（安全） |
| AC17 | `dashboard.e2e.ts` 的 `secrets` 和清理用的 reporter 拿到的清理清單相同 | 不變條件（安全） |
| AC18 | 執行 `npm run test:e2e` 時，`test.diff.expand` 是 `true`：diff 只差在長陣列尾端時，仍從第一行完整印出 | 不變條件（安全） |
| AC19 | 文字規則 7：`dvb_`（Clerk dev browser token 的開頭）前面不是英數字或 `_`、後面接英數字時，`dvb_` 和後面的英數字換成 `[redacted]`。`"expected 'dvb_2abcXYZ' to be 'x'"` 完全等於 `"expected '[redacted]' to be 'x'"` | 不變條件（安全） |
| AC20 | 登入失敗時印出的登入後診斷，經過清理後仍看得到 session 有沒有建立、有哪些 cookie 名稱：`'{\n  "clerkState": {\n    "hasClerkSid": true\n  },\n  "browserStorageNames": [\n    "__clerk_db_jwt",\n    "__session"\n  ]\n}'` 經過 `sanitizeReportText` 後不變 | 使用者行為（開發者看 CI log） |
| AC21 | 文字規則 8（拿掉 ANSI 色碼之後、其他規則之前）：字串裡有一行符合 ` -<數字>,<數字> +<數字>,<數字> `（diff 只印出一部分的標頭）時，整個字串換成 `[diff omitted]`。`'- Expected\n+ Received\n\n -18,8 +18,16 \n+     84,\n+     79,\n    ],'` 完全等於 `'[diff omitted]'`；`'  Uint8Array [\n+   1,\n  ]'` 不受這條規則影響（照 AC10 處理） | 不變條件（安全） |

## 不適用的情境
| 情境 | 原因 |
|---|---|
| 未登入／無權限、空資料、載入中 | 只改 e2e 測試的輸出，沒有使用者畫面與 API |
| 資料處理、併發 | 不讀寫資料庫；reporter 在主行程裡同步處理，同一時間只處理一個事件 |
| 失敗 | 沒有要清理的內容時，文字原樣保留（AC7 的 `theme`、AC11 的字串陣列）；循環參照見 AC15；reporter 拿到的大多是 vitest 序列化過的單純資料（字串、數字、布林、`null`、陣列、一般物件），主行程自己的錯誤是原本的 `Error` 物件，見實作計畫 2；兩者都沒有測試刻意寫的 getter、Proxy，不另外處理讀取出錯 |

## 已接受的風險
- 會多遮的情況（偏向多刪不漏刪，和 #46 相同）：
  - 名稱含 `token`、`session` 這類字的一般欄位（例如 `tokenCount`）會被遮。
  - stack 裡的檔名如果含敏感名稱（例如 `session.ts:3:5`），那一行之後的內容會被遮。
  - 名稱叫 `data` 的一般整數陣列會被遮。
  - vitest 訊息裡的 `// Object.is equality` 會被清成 `[url] Object.is equality`。
  - AC8 同一行的例子，`value` 之後的整行內容（包括 `to deeply equal []`）會被遮。
  - 名稱叫 `cookies` 這類含敏感名稱的欄位，整個值都會被遮，看不到裡面的內容（AC12）。
  - 名稱含 `refresh` 的一般欄位（例如 `refreshCount`）也會被遮：Clerk 的 refresh token 存在 `__refresh` cookie，名稱只有這個字可以判斷。
  - 二進位類型的名稱接著 `[`、卻找不到對應的 `]` 時（例如內容被截斷，或訊息文字剛好含有 `Buffer[`），從那裡到字串結尾都換成 `[binary]`。
- 前面接著英數字或 `_` 的 `dvb_`（例如 `xdvb_abc`）不會被 AC19 遮。
- `github-actions` reporter 只在 stack 裡找得到測試檔那一行時才印 `::error` 附註（`frontend/node_modules/vitest/dist/chunks/index.De2FqGmR.js:1594-1600`）。那一行被規則 3 或清理清單遮掉時，附註會整個不見。現在的 e2e 路徑 `frontend/tests/e2e/dashboard.e2e.ts` 不含敏感名稱。
- diff 一律完整印出（AC18），大物件比對失敗時 log 會變長。
- 很長、沒有空白的字串（3 萬字元以上），清理時間會隨長度平方成長（3 萬字元約 2 秒、10 萬字元約 21 秒），原因是規則 3、`sanitizeForLog` 的網址規則與 email regex 從每個位置開始比對。e2e 沒有這種字串的來源（實作審查第 1 輪 #2、第 2 輪 #7）。
- 沒被接住的錯誤、收集階段的錯誤，diff 只印出一部分時整段換成 `[diff omitted]`（AC21），開發者只看得到訊息與 stack；要看 diff 時，把 assertion 改到有 `await` 的地方。
- diff 的顏色會不見；兩個只差在 query 的網址，清理後一樣，diff 看不出差異。
- 清理用的 reporter 依賴 vitest 內部怎麼呼叫 reporter（背景「vitest 怎麼把錯誤交給 reporter」）。vitest 升級改了這個行為時，由需求 11 的整合測試抓出來。

## 實作計畫
1. 新增 `frontend/tests/e2e/support/e2eSecrets.ts`：`e2eSecrets(env)` 回傳 AC16 的清單。`env` 用參數傳入，測試才不用改 `process.env`。
2. 新增 `frontend/tests/e2e/support/sanitizingReporter.ts`：
   - `sanitizeReportText(text, secrets)`：先套用文字規則 1（拿掉 ANSI 色碼），接著規則 8（AC21，符合就直接回傳 `[diff omitted]`），再依序套用規則 2～7（AC6～AC11、AC19）。規則 2 用 `signInWithRetry.ts` 既有的 `sanitizeForLog`，不另外寫一份。
   - `sanitizeReportValue(value, secrets)`：原地處理 vitest 交來的資料，回傳清理後的值。
     - 字串用 `sanitizeReportText` 清理。
     - 陣列與物件：先判斷 AC14，是二進位資料就回傳 `'[binary]'`，這個判斷要在下面的 `WeakSet` 檢查之前，同一份二進位資料被第二個欄位參照時才不會被跳過（AC15）；不是的話逐一處理每個元素或欄位，把結果寫回原本的位置。
     - `Error` 物件（主行程自己的錯誤）：`message`、`stack` 不可列舉，除了可列舉的欄位，另外直接處理這兩個欄位（AC4）。
     - 物件欄位名稱敏感的換成 `'[redacted]'`（AC12）；物件 `name` 含敏感名稱時，`value` 換成 `'[redacted]'`（AC13）。
     - 用 `WeakSet` 記錄處理過的物件，遇到就跳過（AC15）。
     - 其他型別照原樣回傳。
   - 預設匯出 `SanitizingReporter` 類別，建構時傳入 `{ secrets }`。下面每個方法都是同步的，不能用 `async` 或 `await`：`await` 之後，後面的 reporter 會先印出沒清理的內容（背景「vitest 怎麼把錯誤交給 reporter」）。
     - `onCollected(files)`：逐層處理每個測試檔與底下每個 suite、測試的 `result.errors`（AC3 的收集階段錯誤）。
     - `onTaskUpdate(packs)`：處理每個 `result.errors`（AC2、AC3 的 hook 錯誤）。
     - `onUserConsoleLog(log)`：處理 `log.content`（AC5）。
     - `onTestRunEnd(modules, errors)`、`onFinished(files, errors)`：逐層處理所有測試的 `result.errors`，也處理 `errors`（AC4）。
3. `frontend/vitest.e2e.config.ts`：`reporters` 依序是 `new SanitizingReporter({ secrets: e2eSecrets(process.env) })`、`'default'`，`process.env.GITHUB_ACTIONS === 'true'` 時再加 `'github-actions'`（AC1）；另外設定 `diff: { expand: true }`（AC18）。註解寫出三件事：清理用的 reporter 為什麼要排第一個；為什麼要自己加 `github-actions`；為什麼 diff 要完整印出。
4. `frontend/tests/e2e/dashboard.e2e.ts`：`secrets` 改成 `e2eSecrets(process.env)`（AC17）；`printPostSignInDiagnostics` 的 `hasSession` 改名為 `hasClerkSid`、`cookieNames` 改名為 `browserStorageNames`（AC20）。
5. 整合測試（需求 11）：
   - 新增 `frontend/tests/e2e-support/fixtures/` 底下兩個範例測試檔，檔名用 `.fixture.ts` 結尾，主設定與 e2e 設定才不會把它們當成測試執行：
     - `leaks.fixture.ts`：涵蓋 assertion 失敗（字串與物件的 diff）、帶自訂屬性與 `cause` 的錯誤、`afterAll` 丟出錯誤、沒被接住的 Promise 錯誤、`console.log`，以及改動只在長陣列尾端的 diff：4 個 cookie 的陣列只有最後一個不同、只差在尾端的長 `Buffer`，另外在沒被 `await` 的 Promise 裡做同樣的長陣列比對（沒被接住的 assertion 錯誤，AC21）。
     - `collect-error.fixture.ts`：在測試檔最上層丟出錯誤。
     - 範例裡的機密都在執行時才組出來（例如 `['sk_test_', 'FIXTURESECRET'].join('')`），原始碼節錄裡就不會出現完整的機密。
   - 新增 `frontend/tests/e2e-support/sanitizingReporter.integration.test.ts`，開頭用 `// @vitest-environment node`：
     - 用 `vitest/node` 的 `startVitest` 執行這兩個範例。設定 `config: false`、`watch: false`、`include` 設成兩個範例的路徑（預設的 `include` 只找 `*.test.*`、`*.spec.*`），`reporters` 是 `[new SanitizingReporter({ secrets }), 'default', 'github-actions']`，`stdout`、`stderr` 放在 `startVitest` 第 5 個參數（`vitestOptions`），傳入自己的 `Writable`，收下全部輸出。
     - 執行完 `close()`。`startVitest` 會在範例失敗時設定 `process.exitCode`，要還原成執行前的值，外層的 `npm run test` 才不會因此失敗。
     - 兩次執行都設定 `diff: { expand: true }`，和 `vitest.e2e.config.ts` 相同。
     - 另外用 `['default', 'github-actions']` 跑一次（沒有清理用的 reporter）。
6. `frontend/README.md`「測試」的 E2E 項目加一句：印進 CI log 的錯誤與 `console` 輸出由 `tests/e2e/support/sanitizingReporter.ts` 清理，改 `reporters` 時要保留它排第一個。
7. PR 描述加上 `Closes #50`、`Closes #129`。

### 考慮過、沒選的做法
- **diff 不完整印出，改加「開頭行不在畫面上」的文字規則**：規則變多，一般的數字陣列也會被遮（開發者選擇設定 `expand: true`；`expand` 管不到的兩種錯誤，開發者選擇整段不印）。
- **沒被接住的錯誤、收集階段的錯誤列成已接受的風險**：沒有機制擋住之後有人在沒有 `await` 的 callback 裡寫 assertion。
- **`dashboard.e2e.ts` 的診斷欄位維持原名、列成已接受的風險**：#28 除錯要用的資訊會被遮掉（開發者選擇改名）。
- **在 `withSanitizedErrors` 裡清理還沒序列化的錯誤物件**（PR #126 的做法）：要處理 getter、原型鏈、Proxy 等物件特性，實作審查 8 輪的阻擋大多是這類查不到實際來源的寫法；而且 hook 錯誤、沒被接住的錯誤、`console` 輸出不經過它。
- **把 reporter 的方法寫成 `async`**：vitest 用 `Promise.all` 同時呼叫所有 reporter，`await` 之後的清理會比 `default` 印出還晚。
- **改用 `dot` 這類精簡的 reporter，或加 `--silent`**：`dot` 最後仍會印出失敗的錯誤與 diff；`--silent` 會把 #28 需要的重試標記也藏起來。
- **只寫清理函式的 unit 測試**：抓不到 vitest 升級後 reporter 失效。
- **移除 `withSanitizedErrors`**：reporter 失效時就完全沒有清理（開發者決定保留）。

## 測試對應
文字規則與結構規則的測試放在 `frontend/tests/e2e-support/sanitizingReporter.test.ts`，名稱用 `#50 ACn：` 開頭。預期值都用 `toBe`／`toEqual` 寫出完整的結果，不用「不含某某」。

| AC | 測試 |
|---|---|
| AC1、AC18 | `sanitizingReporter.test.ts`：讀 `vitest.e2e.config.ts` 匯出的設定，`test.diff.expand` 是 `true`；`GITHUB_ACTIONS` 是 `'true'` 時 `reporters` 的第一個是 `SanitizingReporter` 的實例，接著是 `'default'`、`'github-actions'`；不是 `'true'` 時只有前兩個。用 `vi.stubEnv` 與 `vi.resetModules` 重新載入設定檔；每次 `vi.resetModules` 後，設定檔和 `sanitizingReporter.ts` 都重新動態 import，再用 `instanceof` 比對，否則兩次載入的類別不同 |
| AC2～AC5 | 整合測試：有清理用的 reporter 的輸出裡，每個執行時才組出來的機密（email、secret key、密碼、網址 query 的值、JWT、`Bearer` 後面的 token、cookie 的值，包括改動只在長陣列尾端的範例裡的 `dvb_` 值與 `Buffer` 尾端的位元組，以及沒被接住的長陣列比對錯誤裡的值）出現 0 次。位元組用 diff 印出的形式檢查（例如 `TOKENXYZ` 的每個位元組各成一行的那幾行）。沒有清理用的 reporter 的輸出裡，每個機密至少出現 1 次，證明範例真的會外洩、測試抓得到。AC5 只檢查 `default` 的輸出：`github-actions` 不印 `console` 內容 |
| AC6～AC11、AC19～AC21 | `sanitizingReporter.test.ts`：每條 AC 的例子，`sanitizeReportText` 的結果用 `toBe` 比對 AC 寫的完整字串 |
| AC12～AC14 | `sanitizingReporter.test.ts`：每條 AC 的例子，`sanitizeReportValue` 的結果用 `toEqual` 比對 AC 寫的完整物件 |
| AC15 | `sanitizingReporter.test.ts`：`const a = { note: '/cb?code=abc' }; a.self = a`，清理會結束，結果的 `note` 是 `'/cb'`，`self` 指向結果本身；`const u8 = { '0': 1, constructor: 'Function<Uint8Array>' }; const v = { a: u8, b: { c: u8 } }` 清理後等於 `{ a: '[binary]', b: { c: '[binary]' } }` |
| AC16 | `sanitizingReporter.test.ts`：`e2eSecrets({ E2E_CLERK_TEST_EMAIL: 'a@example.com', NUXT_CLERK_SECRET_KEY: 'sk_test_x', E2E_CLERK_TEST_PASSWORD: 'p' })` 等於 `['a@example.com', 'sk_test_x', 'p']`；`e2eSecrets({ E2E_CLERK_TEST_EMAIL: 'a@example.com', NUXT_CLERK_SECRET_KEY: '' })` 等於 `['a@example.com']` |
| AC17 | 不寫 unit 測試：PR 描述附上 `dashboard.e2e.ts` 的 `secrets` 那一行，和 `vitest.e2e.config.ts` 的 `reporters` 那一段 |
| AC20（改名） | 除了上面 `sanitizeReportText` 的測試，PR 描述附上 `printPostSignInDiagnostics` 改名後的那幾行：診斷要登入失敗才會印出，unit 測試碰不到 |

#46 既有的 `signInWithRetry.test.ts` 不改，全部要通過。

## 修改紀錄
| 日期 | 修改 | 原因 | 確認者 |
|---|---|---|---|
| 2026-11-19 | 需求 8 的敏感名稱加 `refresh`；AC8、AC13 各補 `__refresh_AbCd` 的例子；「已接受的風險」加 `refresh` 會多遮的情況 | 開發者決定（實作審查第 1 輪 #1，選 A）：Clerk 的 `__refresh` cookie 存 refresh token，名稱不含既有的敏感名稱 → 需求 8、AC8、AC13、已接受的風險。檢查過 AC7（例子不含 refresh）、AC12（例子不變）、AC20（`browserStorageNames` 的元素後面沒有 `:`、`=`，不受影響）不用改 | 開發者 |
| 2026-11-19 | 「已接受的風險」加「二進位類型找不到對應的 `]` 時遮到字串結尾」 | 開發者確認（實作審查第 1 輪 #3）→ 已接受的風險；程式已是這個行為，AC10、AC11 不用改 | 開發者 |
| 2026-11-19 | 新增 AC22；「不做」改寫 `sanitizeForLog` 那一項；新增實作計畫 8；實作計畫 7 加 `Closes #143`；測試對應 AC22 | 開發者決定（實作審查第 1 輪 #2）在這個 PR 修長字串變慢：規則 3 與 email regex 加 lookbehind、不設長度上限 → AC22、不做、實作計畫 7、8、測試對應。檢查過 AC6～AC21 與 #46 規格 AC3～AC7 的清理結果不變（只改比對起點，結果相同），不用改 | 開發者 |
| 2026-11-19 | 撤回 AC22 與實作計畫 8；「不做」的 `sanitizeForLog` 那一項改回「保留不動」；實作計畫 7 拿掉 `Closes #143`；「已接受的風險」加長字串變慢 | 開發者決定撤回上一筆（實作審查第 2 輪 #6、#7）：e2e 沒有很長、沒有空白的字串的來源，而且 email regex 加 lookbehind 讓相連的 email 漏遮 → 不做、實作計畫 7、已接受的風險；#143 以 not planned 關閉。檢查過 AC6～AC21 與 #46 規格 AC3～AC7：`signInWithRetry.ts` 回到和 main 相同，規則 3 回到 `ab42ffa` 的寫法，清理結果都和撤回前的核准版本相同 | 開發者 |
| 2026-11-19 | 「已接受的風險」長字串變慢的原因補上網址規則 | 開發者確認（實作審查第 3 輪 #9）：`'a+'` 這類字串會讓網址規則也從每個位置重新比對 → 已接受的風險；只改描述，驗收條件與程式不用改 | 開發者 |

## 請你決定
無
