# e2e 診斷 log 沒有清掉網址的 query string：規格審查紀錄

- 規格：[docs/specs/issue-46-sanitize-relative-url-query.md](../../specs/issue-46-sanitize-relative-url-query.md)
- PR：#49
- 輪數：2（第 1 輪 2026-11-07 草稿；第 2 輪 2026-11-07 草稿）
- 最終結果：第 2 輪仍有阻擋，依 `/feature` 第 1 節不再自動審查，6 項決策由開發者選定後核准

這份規格原本用 bug 簡化格式核准、PR #49 已實作第 1 版；實作審查第 1 輪後，開發者提出用 `new URL()` 與封裝輸出的做法，並決定 bug 也用完整格式，所以重寫並做規格審查。

## 摘要

- 發現：17 項（第 1 輪 9 項、第 2 輪 8 項）：Specification Defect 10、Missing AC 3、Factual Error 1、Improvement Suggestion 3；Major 1、Minor 11、Info 5
- 開發者決策：6 項（第 1 輪 #1、#5；第 2 輪 #10、#11、#12、#13）
- 尚未處理：0 項（2 項不採用的建議列為已接受的風險）

## 發現與處理

| # | 輪 | 標題 | 類型 | 嚴重程度 | 阻擋合併 | 涉及安全／架構 | 根本原因 | 處理 | 決定者 | 結果 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1 | 網址候選只在片段開頭，`url=…`、JSON 的 `\n` 會漏，比第 1 版退步 | Specification Defect | Major | 是 | 安全 | 網址判斷規則沒定義完 | 選 A：任何非英數字元之後都可起點，`\n`、`\t` 當分隔 | 開發者 | 規格已修改 |
| 2 | 1 | AC3 的標點、括號、IP 沒定義 | Specification Defect | Minor | 是 | 否 | 網址判斷規則沒定義完 | 寫明分隔、起點、結尾、IPv4 | 主 session（依審查建議） | 規格已修改 |
| 3 | 1 | `new URL(raw, base)` 做不出 `./`、`host:port/` 的預期輸出；測試只驗 token | Specification Defect | Minor | 是 | 否 | `new URL` 實際行為與預期不符 | 計畫改成依候選種類分開處理；AC4 寫完整預期輸出 | 主 session（依審查建議） | 規格已修改 |
| 4 | 1 | 不帶 query 的完整網址：計畫與 AC4 例子相反 | Specification Defect | Minor | 是 | 否 | `new URL` 實際行為與預期不符 | `scheme://` 一律輸出 host＋path | 主 session（依審查建議） | 規格已修改 |
| 5 | 1 | 往上丟的錯誤不經過輸出函式 | Missing AC | Minor | 是 | 安全 | 輸出路徑沒列完 | 選 B：也清理，同時修改 #28 AC2 | 開發者 | 規格已修改 |
| 6 | 1 | AC1 與 grep 檢查衝突（`dashboard.e2e.ts:42`） | Specification Defect | Minor | 是 | 否 | 輸出路徑沒列完 | logger 涵蓋 `console.info` | 主 session（文字一致性） | 規格已修改 |
| 7 | 1 | 「不做」第 1 點引用錯誤 | Specification Defect | Minor | 是 | 否 | — | 改寫引用 | 主 session | 規格已修改 |
| 8 | 1 | 背景的出處與行號 | Factual Error | Info | 是 | 否 | — | 依查證依據改寫 | 主 session（不改變行為） | 規格已修改 |
| 9 | 1 | Nuxt server 的 stdout／stderr 不經過清理 | Improvement Suggestion | Info | 否 | 安全 | — | 寫進「不做」 | 主 session | 規格已修改 |
| 10 | 2 | 「英數字元」沒寫是 ASCII 還是 Unicode；scheme、host、port 字元沒定義 | Specification Defect | Minor | 是 | 安全 | 網址判斷規則沒定義完 | 限定 ASCII，寫明 scheme、host、port | 開發者 | 規格已修改 |
| 11 | 2 | `new URL()` 改寫路徑（多層 `../`、`.`／`..`、`//host`） | Specification Defect | Minor | 是 | 否 | `new URL` 實際行為與預期不符 | 選 B：開頭連續的 `./`、`../` 整段保留，其餘正規化列為已接受的風險 | 開發者 | 規格已修改 |
| 12 | 2 | 需求 2 與 AC2 範圍不一致；`cause` 沒定義 | Missing AC | Minor | 是 | 安全 | 輸出路徑沒列完 | 測試函式最外層統一清理 `message`、`stack`、`cause` | 開發者 | 規格已修改 |
| 13 | 2 | `about:`、`data:` 等導覽網址輸出沒定義 | Missing AC | Minor | 是 | 安全 | 網址判斷規則沒定義完 | 只印 scheme | 開發者 | 規格已修改 |
| 14 | 2 | AC3 測試只驗 token、沒涵蓋各分隔／起點／結尾 | Specification Defect | Minor | 是 | 安全 | `new URL` 實際行為與預期不符 | 測試對應改成每種字元至少一例、比對完整輸出 | 主 session（依審查建議） | 規格已修改 |
| 15 | 2 | `sanitizeError` 改原物件讓 #28 斷言一定通過 | Improvement Suggestion | Info | 否 | 否 | — | 影響檢查列入 #28 的 4 個 AC2 測試，改名稱與斷言 | 主 session | 規格已修改 |
| 16 | 2 | `decodeURI` 會還原 `%0A`、`%22` | Improvement Suggestion | Info | 否 | 安全 | — | 不採用，列為已接受的風險 | 主 session（開發者核准規格時一併確認） | 已接受的風險 |
| 17 | 2 | 可讀性小變化（反斜線、預設 port、host 小寫、無效 `%`） | Improvement Suggestion | Info | 否 | 否 | — | 不採用，列為已接受的風險 | 主 session（開發者核准規格時一併確認） | 已接受的風險 |

## 問題說明

### #1 網址候選只在片段開頭

- 問題：草稿只在空白切開後的片段開頭找網址，`url=https://h/a?token=x`、`redirect=/cb?code=abc`、錯誤訊息轉成 JSON 後的 `\n/v1/a?token=x` 的 token 會原樣印出；PR #49 第 1 版會清掉前幾種。
- 技術原因：起點規則比第 1 版的正規表示式窄（`frontend/tests/e2e/support/signInWithRetry.ts:25`、`:27`）。

### #5、#12 往上丟的錯誤

- 問題：測試失敗時 vitest 直接印出錯誤的 `message`、`stack`、`cause`，不經過輸出函式；#28 規格 AC2 原本要求「錯誤訊息保留原本的內容」。
- 處理：測試函式最外層統一清理，#28 AC2 改文字（規格計畫 3）。

### #10 「英數字元」的範圍

- 問題：中文算英數字元時，`路徑/help?x=1` 不會被清。
- 處理：限定 ASCII（規格 AC3、AC6）。

### #11 `new URL()` 改寫路徑

- 問題：`../../v1/a?t=x` → `../v1/a`、`./a/../b` → `./b`、`//evil.com/a` → `/a`。
- 處理：開頭連續的 `./`、`../` 整段保留；其餘正規化列為已接受的風險（規格 AC4）。

### #13 非網址種類的導覽網址

- 問題：`about:blank`、`data:…` 的輸出沒定義，`data:` 可能把整段內容印出。
- 處理：只印 scheme（規格 AC4、計畫 1 的 `toSafeNavigationUrl`）。

## 開發者決策

| # | 問題 | 選項 | 開發者的決定 | 理由 |
|---|---|---|---|---|
| 1 | 網址從哪裡開始算 | A 任何非英數字元之後／B 只規定先清理再轉 JSON／C 接受風險 | A | 不比第 1 版退步，涵蓋最廣 |
| 5 | 往上丟的錯誤要不要清理 | A 不清理，寫進不做／B 也清理並改 #28 AC2 | B | 開發者選定 |
| 10 | 英數字元的範圍 | 限定 ASCII／含 Unicode 字母 | 限定 ASCII | 安全優先 |
| 11 | `new URL()` 改寫路徑 | A 只保留 1 個前綴／B 保留開頭連續前綴／C 保留原文路徑 | B | 改動小，常見的多層相對路徑保持正確，仍用 `new URL()` 拆 pathname |
| 12 | 錯誤清理的範圍 | 外層統一清理所有丟出的錯誤／只清 AC2 列的兩種 | 外層統一清理 | 一個地方涵蓋全部，符合開發者最初提的「全域錯誤處理」 |
| 13 | 非網址種類的導覽網址 | 只印 scheme／印 `[url]` | 只印 scheme | 足以判斷導覽去向，不印內容 |

## 尚未處理

無。

## 查證紀錄（第 2 輪）

| 規格中的事實 | 結果 | 依據（檔案:行號） |
|---|---|---|
| 診斷與重試標記印進 CI log（#28、PR #45） | 正確 | `docs/specs/issue-28-e2e-clerk-signin-flaky.md:5、31-33`；`frontend/tests/e2e/dashboard.e2e.ts:107、109` |
| PR #49 第 1 版只處理 `scheme://` 與 `/` 開頭 | 正確 | `frontend/tests/e2e/support/signInWithRetry.ts:25、27` |
| 實作審查第 1 輪找到括號、`./`、`host:port/` 會漏 | 正確 | `docs/reviews/implementation/issue-46-sanitize-relative-url-query.md` 第 1 輪 #3 |
| `clerkState` 錯誤直接 `console.error` | 正確 | `frontend/tests/e2e/dashboard.e2e.ts:48-58`、`:61-63` |
| 往上丟的錯誤 | 正確 | `frontend/tests/e2e/support/signInWithRetry.ts:61`；`frontend/tests/e2e/dashboard.e2e.ts:128` |
| 重試標記在通過時也印，#28 AC3 用它統計 | 正確 | `docs/specs/issue-28-e2e-clerk-signin-flaky.md:31`；`frontend/tests/e2e/support/signInWithRetry.ts:63-65` |
| `@nuxt/test-utils` 以 `stdio: "inherit"` 啟動 server | 正確 | `frontend/node_modules/@nuxt/test-utils/dist/shared/test-utils.B8qEdk9k.mjs:86、125` |
| CI 跑建置後的 Nuxt，沒設 `NUXT_TEST_DEV` | 正確（`?v=` 很少出現是推論） | `test-utils.B8qEdk9k.mjs:18、120-125`；`.github/workflows/deploy.yml:58-82` |
| 要改的 `console.*` 共 5 處 | 正確 | `frontend/tests/e2e/dashboard.e2e.ts:42、61、65、107、109` |
| Clerk 的登入錯誤是 `new Error`，沒有 `cause` | 正確 | `frontend/node_modules/@clerk/testing/dist/playwright/index.mjs:1` |
| vitest 會印 `cause` 與可列舉屬性 | 正確 | `frontend/node_modules/vitest/dist/chunks/index.De2FqGmR.js:244、355` |
| 測試伺服器 host 固定是 `127.0.0.1` | 正確 | `test-utils.B8qEdk9k.mjs:78-80` |
| email、JWT、secrets 的遮蔽 | 正確 | `frontend/tests/e2e/support/signInWithRetry.ts:28-33` |
| #28 AC2 的原文 | 正確 | `docs/specs/issue-28-e2e-clerk-signin-flaky.md:30` |
| 首頁 API 沒帶 query，還沒有實際外洩 | 無法查證（要看 CI 實際 log） | `frontend/composables/useProductivity.ts:28` |

## 已接受的風險

- query 之後的 `:行:欄` 一起拿掉；依假設 2，CI 很少出現。
- Nuxt server 自己的 stdout／stderr 不清理。
- 安全優先造成的誤刪：`/help?。` → `/help`、`/#28` → `/`。
- 路徑依 URL 標準正規化、預設 port 被拿掉、host 轉小寫、原文已是 JSON 跳脫時反斜線被併進網址（#11、#17）。
- `decodeURI` 會還原 `%0A`、`%22`（#16）。
- query 尾端的 `` . , ; : ! ) ] } `` 會接回輸出。
- 沒寫 scheme 的 IPv6、跳脫過的 `?`（`?`、`%3F`）不處理。
- 一個片段裡用逗號連在一起的多個網址，從第一個 query 到片段結尾都拿掉。
