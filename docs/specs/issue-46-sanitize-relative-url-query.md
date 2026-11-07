# e2e 診斷 log 沒有清掉網址的 query string

- 狀態：已核准（2026-11-07 改版，見修改紀錄）
- issue：[#46](https://github.com/Chen-Yihua/auto-scheduling-system/issues/46)
- PR：[#49](https://github.com/Chen-Yihua/auto-scheduling-system/pull/49)

## 背景
開發者開 PR 或合併到 `main` 後，`frontend-e2e-test` 的 Clerk 登入遇到錯誤時，測試把登入期間的診斷（導覽、console error、pageerror、轉址）和重試標記印進 CI log（#28、PR #45）；測試失敗時，vitest 也會印出往上丟的錯誤訊息、stack 與 `cause`。repo 與 CI log 都是公開的，網址的 query 與 hash 可能帶 token（例如 Clerk dev 的 `__clerk_db_jwt`、OAuth 的 `code`）。

PR #49 第 1 版只用正規表示式處理 `scheme://` 與 `/` 開頭的網址。實作審查第 1 輪（`docs/reviews/implementation/issue-46-sanitize-relative-url-query.md`）找出還會漏的格式：路徑含括號、`./`、沒寫 scheme 的 `host:port/路徑`。另外查到兩條輸出路徑沒經過清理：登入後逾時的 `clerkState` 錯誤訊息直接 `console.error`（`frontend/tests/e2e/dashboard.e2e.ts:48-63`），以及往上丟給 vitest 的錯誤（`frontend/tests/e2e/support/signInWithRetry.ts:61`、`frontend/tests/e2e/dashboard.e2e.ts:128`）。

目前 e2e 只開首頁，首頁的 API 呼叫都沒有帶 query，還沒有實際外洩。

## 需求
1. 測試程式自己印進 CI log 的內容（診斷、重試標記、Clerk 專案網域）都經過同一個輸出函式，在那裡統一清理。
2. e2e 測試裡任何步驟往上丟給 vitest 的錯誤，在測試函式最外層統一清理 `message`、`stack` 與 `cause` 後再丟出。
3. 網址用 `new URL()` 拆開，只留 host＋path（有 host 的網址）或 path（相對網址），不印 query 與 hash。自由文字裡的網址先依 AC3 的規則找出來，再交給同一個函式。

## 不做
- 不改診斷收集的項目與時機（#28 的範圍）；轉址記錄只改用同一個網址處理（計畫 2）。
- 不在 `afterEach` 統一輸出：重試標記在測試通過時也要印（#28 AC3 用它統計發生次數），診斷也是每次重試當下就印，`afterEach` 只看得到最後結果。封裝改用單一輸出函式與最外層的錯誤清理（需求 1、2）。
- 不保留被清掉的 query 裡的任何內容，例如 stack trace `/_nuxt/app.js?v=abc:19:22` 的 `:19:22` 會一起拿掉（假設 1）。
- 不處理 Nuxt server 自己的 stdout／stderr（`@nuxt/test-utils` 以 `stdio: "inherit"` 啟動），本規格只處理測試程式自己的輸出。

## 假設
1. 以不外洩為優先：分不出是不是網址的文字，只要符合 AC3 的網址候選規則就當成網址清理（依據：實作審查第 1 輪 #2 的建議，log 公開，誤刪只少幾個字，漏刪可能公開 token；開發者決定安全優先）。
2. CI 的 e2e 跑的是建置後的 Nuxt（`@nuxt/test-utils` 的 `setup`，沒設 `NUXT_TEST_DEV`），stack trace 的網址通常不帶 Vite 的 `?v=`，所以「不做」第 3 點實際很少發生。這點是推論，沒有在 CI 實測。

## 驗收條件
| # | 條件 | 類型 |
|---|---|---|
| AC1 | `frontend/tests/e2e/` 裡所有印到 log 的內容（重試標記、登入診斷、登入後逾時的診斷、Clerk 專案網域）都經過同一個輸出函式；除了這個函式內部，`frontend/tests/e2e/` 沒有其他 `console.*` 呼叫 | 不變條件（安全） |
| AC2 | `dashboard.e2e.ts` 每個測試函式裡任何步驟丟出的錯誤，丟給 vitest 前 `message`、`stack` 與 `cause`（遞迴）都經過 AC3～AC7 的清理；錯誤的類型不變。不是 `Error` 的值轉成字串清理後包成 `Error` | 不變條件（安全） |
| AC3 | 文字裡的網址候選帶 query 或 hash 時只留 host＋path 或 path。**分隔**：空白、`"`、`'`、`` ` ``、`<`、`>`，以及字面上的 `\n`、`\t`（JSON 跳脫序列）。**起點**：片段開頭，或片段中任何不是 ASCII 英數字元（`A-Z`、`a-z`、`0-9`）、`.`、`~`、`-`、`_` 的字元之後（例如 `=`、`:`、`(`、`[`、`{`、`,`、中文、全形標點）。**候選**：從起點開始符合下列之一：`scheme://`（scheme 是英文字母開頭，後接英數字元、`+`、`.`、`-`）；`/`、`./`、`../`；`host[:port]/`（host 是 `localhost`、4 段十進位數字的 IPv4，或由英數字元與 `-` 組成、用 `.` 分段的網域；port 是 1 位以上數字）。**結尾**：去掉候選尾端的 `` . , ; : ! ) ] } ``，`?`、`#` 與全形標點不去掉；路徑中的括號不視為結尾（例如 `/wiki/Foo_(bar)?token=x`） | 不變條件（安全） |
| AC4 | 輸出形式：`scheme://` 開頭的一律輸出 host＋path，不論有沒有 query；`host[:port]/` 開頭的輸出 host＋path；開頭連續的 `./`、`../` 整段保留；路徑的非 ASCII 字元輸出成原本的字。路徑其餘部分依 URL 標準正規化（`.`／`..` 段、`\`、`//host`）。導覽與轉址記錄的網址不屬於 AC3 的候選種類時（例如 `about:blank`、`data:…`、`javascript:…`），只輸出 scheme（`about:`、`data:`）。例：`./v1/a?token=x` → `./v1/a`、`../../v1/a?token=x` → `../../v1/a`、`localhost:3000/v1/a?token=x` → `localhost:3000/v1/a`、`api.example.com/v1/a?token=x` → `api.example.com/v1/a`、`url=https://h/a?token=x` → `url=h/a`、`redirect=/cb?code=abc` → `redirect=/cb`、`/任務?x=1` → `/任務`、`{url:/v1/a?t=x}` → `{url:/v1/a}`、`(https://h/a.js?v=1:2:3)` → `(h/a.js)`、`/cb?code=abc.` → `/cb.` | 不變條件 |
| AC5 | 不是網址的文字不受影響：`and/or? ok`、`1/2?對嗎`、`見 #28`、`為什麼失敗?`；相對網址或沒寫 scheme 的網址，`?` 後面沒有內容時保留（`是 /help? 嗎`）；沒有 query 的相對路徑與 stack trace 保留（`/_nuxt/app.js:19:22`）；`(http://127.0.0.1:3000/_nuxt/a.js:1:2)` → `(127.0.0.1:3000/_nuxt/a.js:1:2)` | 不變條件（診斷可讀） |
| AC6 | 符合網址候選、而且 `?`／`#` 後面有內容的，一律清理（假設 1），例如 `/help?。` → `/help`、`/#28` → `/`、`路徑/help?x=1` → `路徑/help` | 不變條件（安全優先） |
| AC7 | email、`eyJ` 開頭的 JWT、`secrets` 清單裡的值，照舊遮成 `[email]`、`[token]`、`[redacted]` | 不變條件 |

## 不適用的情境
| 情境 | 原因 |
|---|---|
| 未登入／無權限、空資料、載入中 | 只改測試程式的 log 輸出，沒有使用者畫面與 API |
| 資料處理、併發 | 不讀寫資料庫，清理是同步的字串處理 |

## 已接受的風險
- 路徑依 URL 標準正規化（`./a/../b` → `./b`、`//evil.com/a` → `/a`）、預設 port 被拿掉、host 轉小寫、原文已是 JSON 跳脫時反斜線被併進網址：只影響診斷可讀性。
- `decodeURI` 會把路徑中的 `%0A`、`%22` 還原成換行、引號；目前 e2e 只連自己的 app 與 Clerk。
- query 尾端的 `` . , ; : ! ) ] } `` 會接回輸出（`/a?t=sec.` → `/a.`）。
- 沒寫 scheme 的 IPv6（`[::1]:3000/a?t=x`）、跳脫過的 `?`（`?`、`%3F`）不處理：測試伺服器固定用 `127.0.0.1`，目前查不到會產生這些格式的來源。
- 一個片段裡用逗號連在一起的多個網址，從第一個 query 到片段結尾都拿掉（偏向安全）。

## 實作計畫（解決做法）
1. `frontend/tests/e2e/support/signInWithRetry.ts`
   - 新增 `toSafeUrl(candidate)`：依 AC3 的候選種類分開處理，每一種都用 `new URL()` 拆出 pathname。
     - `scheme://`：`new URL(candidate)`，輸出 `host + pathname`。
     - `host[:port]/`：`new URL('http://' + candidate)`，輸出 `host + pathname`（直接解析會把 `localhost:` 當成 scheme）。
     - `/`：`new URL(candidate, 'http://relative.invalid')`，輸出 `pathname`。
     - `./`、`../`：去掉開頭連續的整段前綴後當成 `/` 開頭解析，輸出時把整段前綴接回（`new URL` 會把它們展開成絕對路徑）。
     - 相對網址與沒寫 scheme 的網址，`search` 與 `hash` 都是空的時回傳原字串（AC5 的 `/help?`）。
     - pathname 用 `decodeURI` 還原非 ASCII 字元；解析或還原失敗回傳 `[url]`。
   - 新增 `toSafeNavigationUrl(url)`：給導覽與轉址用，屬於候選種類時交給 `toSafeUrl`，否則只回傳 scheme（AC4）。
   - `sanitizeForLog` 改成：依 AC3 找出候選，每個交給 `toSafeUrl`，再照舊遮 email、JWT、secrets（AC7）。原本兩條網址正規表示式移除。
   - 新增 `sanitizeError(error, secrets)`：清理 `message`、`stack`，`cause` 遞迴處理，回傳同一個物件；不是 `Error` 的值轉成清理後的 `Error`（AC2）。
   - 新增 `createDiagnosticLogger({ secrets, write })`：唯一的輸出函式，`write` 預設是 `console`；`info`／`warn`／`error` 都先經過 `sanitizeForLog`（AC1）。
   - `createSignInDiagnostics` 的導覽記錄改用 `toSafeNavigationUrl`。
2. `frontend/tests/e2e/dashboard.e2e.ts`
   - 建立一個 logger：`assertClerkKeysLookRight` 的 `console.info`、`signInWithRetry` 的 `log`、`onError` 的診斷、`printPostSignInDiagnostics` 的兩段輸出都改用它（AC1）。`clerkState.error` 在放進 JSON 之前先經過 `sanitizeForLog`。
   - 兩個測試函式的內容都包進同一個外層 `try`／`catch`，`catch` 裡 `throw sanitizeError(error, secrets)`（AC2）；內層不再各自清理。
   - 3xx 轉址記錄改用 `toSafeNavigationUrl`。
3. `docs/specs/issue-28-e2e-clerk-signin-flaky.md`：AC2 的「錯誤訊息保留原本的內容」改成「錯誤訊息保留原本的內容，網址與 secrets 依 #46 規格清理」，記進那份規格的修改紀錄。
4. 不改 `.github/workflows/`、不改正式程式。

## 測試對應
| AC | 測試 |
|---|---|
| AC1 | `frontend/tests/e2e-support/signInWithRetry.test.ts`：logger 的 `info`／`warn`／`error` 傳入帶 query 的網址、email、JWT，`write` 收到的內容都已清理；PR 描述附上 `grep -rn "console\." frontend/tests/e2e/` 的結果，只剩 logger 內部 |
| AC2 | 同檔：`sanitizeError` 對 `message`、`stack`、兩層 `cause`（含字串 `cause`）都清理，仍是原本的錯誤類型；不是 `Error` 的值會包成清理過的 `Error`。外層包裝 `withSanitizedErrors` 放在 support 檔並直接測試：包住的函式丟出帶 query 與 email 的錯誤時，reject 出來的錯誤已清理；PR 描述附上 `dashboard.e2e.ts` 每個 `it(` 都用 `withSanitizedErrors` 的檢查結果。#28 既有的 AC2 測試（`signInWithRetry.test.ts:95`、`:106`、`:121`、`:142`）改名稱，斷言改成丟出的錯誤經過外層清理後 `message` 含 `[redacted]`、不含測試帳號 email |
| AC3 | 同檔，比對完整輸出：每個分隔（空白、`"`、`'`、`` ` ``、`<`、`>`、字面 `\n`、字面 `\t`）、每個起點（`=`、`:`、`(`、`[`、`{`、`,`、中文）、尾端每個去掉的字元至少一例；`[GET] "/v1/client?__clerk_db_jwt=dvb_xxx#h": 404` → `[GET] "/v1/client": 404`；`/wiki/Foo_(bar)?token=x` → `/wiki/Foo_(bar)` |
| AC4 | 同檔：AC4 列的每個例子比對完整輸出；`toSafeNavigationUrl('about:blank')` → `about:`、`toSafeNavigationUrl('data:text/html,<p>x</p>')` → `data:` |
| AC5 | 同檔：AC5 列的每個例子比對完整輸出 |
| AC6 | 同檔：AC6 列的每個例子比對完整輸出 |
| AC7 | 既有的 #28 AC5 測試保留並通過 |

## 修改紀錄
| 日期 | 修改 | 原因 | 確認者 |
|---|---|---|---|
| 2026-11-07 | 改用完整格式並重寫：需求改為單一輸出函式＋最外層錯誤清理＋`new URL()` 處理網址；AC 改為 AC1～AC7；#28 規格 AC2 一併修改 | 實作審查第 1 輪 #1～#3；開發者提出用 `new URL()` 與封裝輸出的做法，並決定 bug 也用完整格式；規格審查第 1 輪 #1（A）、#5（B），第 2 輪 #1（ASCII）、#2（B）、#3（外層統一清理）、#4（只印 scheme）。影響檢查：PR #49 第 1 版的 `sanitizeForLog` 與 4 個測試要改寫；#28 規格 AC2 改文字，#28 的 4 個 AC2 測試改名稱與斷言；#28 AC5 的行為由本規格 AC3 起點規則與 AC7 維持，不退步 | 開發者 |
