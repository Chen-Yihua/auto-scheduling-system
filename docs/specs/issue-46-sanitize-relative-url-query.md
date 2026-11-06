# e2e 診斷 log 沒有清掉相對路徑網址的 query string

- 狀態：已核准
- issue：[#46](https://github.com/Chen-Yihua/auto-scheduling-system/issues/46)
- PR：[#49](https://github.com/Chen-Yihua/auto-scheduling-system/pull/49)

## 現象
開發者開 PR 或合併到 `main` 後，`frontend-e2e-test` 的 Clerk 登入遇到錯誤時，測試會把登入期間的診斷（導覽、console error、pageerror）和重試標記印進公開的 CI log。console 訊息裡如果有帶 query string 的相對路徑網址（例如 ofetch 的 `FetchError: [GET] "/v1/client?__clerk_db_jwt=dvb_xxx#h"`），`?`、`#` 之後的內容會原樣印出；query 裡如果有 token，就會公開。目前 e2e 只開首頁，首頁的 API 呼叫都沒有帶 query，還沒有實際外洩。

## 重現步驟
1. 呼叫 `sanitizeForLog('[GET] "/v1/client?__clerk_db_jwt=dvb_xxx#h": 404', [])`。
2. 輸出仍含 `?__clerk_db_jwt=dvb_xxx#h`。

## 預期行為／實際行為
- 預期：相對路徑網址只留 path，`?`、`#` 之後到網址結束為止的內容都拿掉。
- 實際：只有 `scheme://` 開頭的完整網址會被清理。

## 原因
`frontend/tests/e2e/support/signInWithRetry.ts:25` 的正規表示式只比對 `scheme://` 開頭的網址；`:29-31` 另外遮 email 與 `eyJ` 開頭的 JWT，`dvb_` 這類非 JWT 的 token 抓不到。AC5 的測試只放了絕對網址（`frontend/tests/e2e-support/signInWithRetry.test.ts:175`、`:203`）。

## 驗收條件
| # | 條件 | 類型 |
|---|---|---|
| AC1 | 印進 log 的文字裡，以 `/` 開頭的相對路徑網址帶 query 或 hash 時（例如 `/v1/client?__clerk_db_jwt=dvb_xxx#h`、`/oauth/callback?code=abc`），輸出只剩 path（`/v1/client`、`/oauth/callback`），不含 `?`、`#` 之後到網址結束（空白、引號、括號）為止的內容 | 不變條件（安全：CI log 公開） |
| AC2 | 完整網址（`scheme://`）的清理行為不變：只留 host＋path | 不變條件 |
| AC3 | 不是網址的 `?`、`#` 不受影響，例如句子結尾的問號、`#28` 這種 issue 編號、沒有 query 的路徑與 stack trace 的 `檔案:行:欄` | 不變條件（診斷內容要保持可讀） |

## 不做
- 不改診斷收集的內容與時機（#28 的範圍）。
- 不新增其他 token 格式的遮蔽規則：query 整段拿掉後，`dvb_` 這類值不會再出現在網址裡。

## 回歸測試
| AC | 測試 | 改程式前是否失敗 |
|---|---|---|
| AC1 | `frontend/tests/e2e-support/signInWithRetry.test.ts` 的 `sanitizeForLog`：ofetch 格式 `[GET] "/v1/client?__clerk_db_jwt=dvb_xxx#h": 404` → 含 `/v1/client`，不含 `dvb_xxx`、`?`、`#h`；`Failed GET /oauth/callback?code=abc#state=xyz` → 不含 `code=abc`、`state=xyz` | 預期失敗 |
| AC2 | 同檔：`https://a.b/c?x=1#y` → `a.b/c` | 預期通過（保護既有行為） |
| AC3 | 同檔：`為什麼失敗?`、`見 #28`、`/_nuxt/app.js:19:22` 原樣保留 | 預期通過（保護既有行為） |

## 修改紀錄
| 日期 | 修改 | 原因 | 確認者 |
|---|---|---|---|
