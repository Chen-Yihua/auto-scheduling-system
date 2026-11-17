# e2e 錯誤的 actual／expected 與其他屬性沒有清理：規格審查紀錄

- 規格：[docs/specs/issue-50-sanitize-error-properties.md](../../specs/issue-50-sanitize-error-properties.md)
- PR：#126
- 等級：高風險
- 輪數：2（第 1 輪 2026-11-17 草稿；第 2 輪 2026-11-17 修改後草稿，只審改過的部分）
- 最終結果：沒有阻擋項目（第 2 輪的阻擋項目由開發者決定後修改規格）

## 摘要

- 發現：13 項（規格內容互相矛盾或沒有依據 3、規格沒寫某個情境該怎麼做 3、規格對現有系統的描述和程式不符 1、沒有錯但可以更好 6；影響小的問題 7、不影響功能只供參考 6）
- 開發者決策：7 項
- 尚未處理：0 項

## 各輪摘要

| 輪 | 日期／commit | 新發現（阻擋） | 這一輪之後改了什麼 |
|---|---|---|---|
| 1 | 2026-11-17 草稿 | #1–#8（#1–#5） | 新增「要清理的錯誤」定義；AC3、AC4 寫清楚 Error 例外；AC6 加 jwt、session；新增 AC7（name/value）、AC8（讀取出錯）、AC9（可寫）；原 AC7、AC8 改為 AC10、AC11；背景與已接受的風險修正事實 |
| 2 | 2026-11-17 修改後草稿 | #9–#13（#9、#10） | AC6 改成不論類型；已接受的風險第 2 點擴大為清理途中出錯的三種情況，實作計畫寫回方式改成依可否重新定義分開；定義文字、測試資料前提、背景與已接受的風險補充 |

## 發現與處理

| # | 輪 | 標題 | 類型 | 嚴重程度 | 阻擋合併 | 涉及安全／架構 | 根本原因 | 處理 | 決定者 | 結果 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1 | AC3 要求內層 Error 原地清理，和 AC4「原本的物件不變」衝突 | 規格內容互相矛盾或沒有依據 | 影響小的問題 | 是 | 否 | 內層 Error 的例外沒寫 | AC3 改「Error 以外的物件或陣列」，AC4 補 Error 例外 | 開發者 | 規格已修改 |
| 2 | 1 | cause 裡的錯誤，其 actual／expected 與其他屬性沒有 AC 涵蓋 | 規格沒寫某個情境該怎麼做 | 影響小的問題 | 是 | 安全 | 清理對象範圍 | 新增「要清理的錯誤」定義，AC1、AC2 改用 | 開發者 | 規格已修改 |
| 3 | 1 | { name, value } 格式的 header、cookie 不會被遮 | 規格沒寫某個情境該怎麼做 | 影響小的問題 | 是 | 安全 | 依名稱遮蔽的範圍 | 新增 AC7；AC6 加 jwt、session | 開發者 | 規格已修改 |
| 4 | 1 | 清理到一半出錯、vitest 寫不回屬性時沒有定義 | 規格沒寫某個情境該怎麼做 | 影響小的問題 | 是 | 安全 | 清理途中出錯 | 新增 AC8、AC9 | 開發者 | 規格已修改 |
| 5 | 1 | AssertionError 原型 getter（讀取時才算出值的屬性）、assertion 數量的描述和程式不符 | 規格對現有系統的描述和程式不符 | 影響小的問題 | 是 | 否 | 事實描述 | 依 chai/chai.js:160-165、dashboard.e2e.ts:80、:82、:137 修正 | 主 session | 規格已修改 |
| 6 | 1 | 背景沒寫 Serialized Error 由哪個 reporter 印 | 沒有錯，但可以更好 | 不影響功能，只供參考 | 否 | 否 | — | 背景補上 | 開發者 | 規格已修改 |
| 7 | 1 | 已接受的風險沒寫 Date／URL 變空物件、diff 看不出差異、toJSON | 沒有錯，但可以更好 | 不影響功能，只供參考 | 否 | 否 | — | 已接受的風險補三點 | 開發者 | 規格已修改 |
| 8 | 1 | AC2 測試沒測自有 getter；AC10（原 AC7）只靠 PR 描述 | 沒有錯，但可以更好 | 不影響功能，只供參考 | 否 | 否 | — | AC2 測試補 getter 例子；AC10 維持 | 開發者 | 規格已修改 |
| 9 | 2 | 實作計畫有三種情況會在清理途中丟出錯誤，和 AC8、AC9、已接受的風險不一致 | 規格內容互相矛盾或沒有依據 | 影響小的問題 | 是 | 安全 | 清理途中出錯 | 選 B：AC8 不變；寫回依可否重新定義分開；其餘列已接受的風險；AC9 註明例外 | 開發者 | 規格已修改 |
| 10 | 2 | AC6 只套用在字串與物件，卻寫不論類型 | 規格內容互相矛盾或沒有依據 | 影響小的問題 | 是 | 安全 | 依名稱遮蔽的範圍 | AC6 改成要清理的錯誤自己的屬性與複製品的屬性，不論類型 | 開發者 | 規格已修改 |
| 11 | 2 | 「要清理的錯誤」沒寫清楚是否可以接續往下找 | 沒有錯，但可以更好 | 不影響功能，只供參考 | 否 | 安全 | — | 定義改寫，意思不變 | 主 session | 規格已修改 |
| 12 | 2 | AC7 會遮掉 sessionCount 這類一般 name 的 value | 沒有錯，但可以更好 | 不影響功能，只供參考 | 否 | 否 | — | 已接受的風險第 4 點補充 | 開發者 | 規格已修改 |
| 13 | 2 | AC9 列的屬性和 vitest 實際寫入的不完全一樣；AC8 測試沒寫 getter 要可重新定義 | 沒有錯，但可以更好 | 不影響功能，只供參考 | 否 | 否 | — | AC8 測試寫明 configurable: true；AC9 維持 | 主 session | 規格已修改 |

## 問題說明

### #1 AC3 要求內層 Error 原地清理，和 AC4「原本的物件不變」衝突
內層 Error 交給 sanitizeError 會直接改原物件（`frontend/tests/e2e/support/signInWithRetry.ts:96-98`），AC4 沒排除 Error，兩條照字面無法同時成立。

### #2 cause 裡的錯誤，其 actual／expected 與其他屬性沒有 AC 涵蓋
vitest 對 cause 遞迴處理並算 diff（`frontend/node_modules/@vitest/utils/dist/error.js:100-104`、`:118-120`），印 cause 時 printProperties 用預設 true（`frontend/node_modules/vitest/dist/chunks/index.De2FqGmR.js:166`、`:245`），只清最外層的實作也能通過原本的 AC。

### #3 { name, value } 格式的 header、cookie 不會被遮
Playwright 用 { name, value } 陣列存 header、cookie（`frontend/node_modules/playwright-core/lib/client/network.js:496`、`:707-713`），依欄位名稱遮蔽抓不到；`__clerk_db_jwt` 的值是 `dvb_` 開頭，#46 的規則也抓不到。

### #4 清理到一半出錯、vitest 寫不回屬性時沒有定義
讀屬性出錯時 withSanitizedErrors 會丟出沒清理的新錯誤；vitest 會寫入 actual、expected（`frontend/node_modules/@vitest/utils/dist/error.js:100-111`），屬性不可寫時嚴格模式丟 TypeError。推論，未重現。

### #5 AssertionError 原型 getter、assertion 數量的描述和程式不符
chai 的 AssertionError 原型上有 name、ok getter（`frontend/node_modules/chai/chai.js:160-165`）；e2e 有三個 expect（`frontend/tests/e2e/dashboard.e2e.ts:80`、`:82`、`:137`）。結論不變。

### #9 實作計畫有三種情況會在清理途中丟出錯誤
不可重新定義但可寫的屬性用 defineProperty 改 configurable 會失敗；只有 getter 的 message／stack 直接賦值會失敗；已撤銷的 Proxy 判斷型別就失敗（Node 20 實測）。結果是丟出新的 TypeError，原錯誤不印，不外洩。

### #10 AC6 只套用在字串與物件，卻寫不論類型
AC6 用「AC2、AC3 清理時」界定範圍，但 AC2 只管字串、AC3 只管物件與陣列，`err.token = 12345` 照字面不在範圍內，和實作計畫不一致。

## 開發者決策

| # | 問題 | 選項 | 開發者的決定 | 理由 |
|---|---|---|---|---|
| 1 | 內層 Error 是否為「原物件不變」的例外 | 改寫 AC3、AC4／不改 | 改寫 | 只是寫清楚已確認的內容，行為不變 |
| 2 | cause 裡的錯誤是否也清 actual／expected 與其他屬性 | 擴大範圍／不擴大 | 擴大 | vitest 兩種 reporter 都會印 cause |
| 3 | { name, value } 格式 | A：name 符合字詞時遮 value；B：A＋字詞加 jwt、session；C：不處理 | B | cookie 是背景點名的風險，遮太多只少一些診斷資訊 |
| 4 | 清理到一半出錯 | A：加 AC8、AC9；B：列已接受的風險 | A | 成本低，做法和 vitest 自己的處理一致 |
| 9 | 清理途中判斷型別或寫回出錯 | A：擴大 AC8，寫不回時改丟新 Error；B：AC8 不變，寫回依可否重新定義分開，其餘列已接受的風險 | B | 查不到來源，B 已保證不外洩 |
| 10 | AC6 範圍 | 改成不論類型／不改 | 改 | 和需求 5、實作計畫一致 |
| 6–8、12 | 不阻擋的建議 | 採用／不採用 | 採用 | 補說明與測試 |

## 尚未處理

無

## 查證紀錄（第 2 輪）

| 規格中的事實（AC／假設編號） | 結果 | 依據 |
|---|---|---|
| 背景：e2e 有三個 assertion | 正確 | `frontend/tests/e2e/dashboard.e2e.ts:80`、`:82`、`:137` |
| 背景：secrets 清單只有測試帳號 email | 正確 | `frontend/tests/e2e/dashboard.e2e.ts:27` |
| 已接受的風險第 1 點：AssertionError 原型上的 name、ok 是 getter、回傳固定值 | 正確 | `frontend/node_modules/chai/chai.js:160`、`:163` |
| AC9：vitest 之後會寫入 actual、expected | 正確（也寫 stackStr、nameStr、diff，message、cause 在 try 裡，不寫 stack） | `frontend/node_modules/@vitest/utils/dist/error.js:95-120` |
| AC8：vitest 讀屬性失敗時換成 unserializable 訊息 | 正確 | `frontend/node_modules/@vitest/utils/dist/error.js:14`、`:61`、`:78` |
| AC1：#46 規格 AC3～AC7 的清理 | 正確 | `docs/specs/issue-46-sanitize-relative-url-query.md:34-38` |
| AC11：#46 規格 AC2 的行為 | 正確 | `docs/specs/issue-46-sanitize-relative-url-query.md:33` |
| 背景（第 1 輪查證）：diff 與 Serialized Error 的來源、vitest 在錯誤丟出後才讀屬性、dot reporter 仍印錯誤 | 正確 | `frontend/node_modules/@vitest/utils/dist/error.js:23-124`；`frontend/node_modules/@vitest/runner/dist/index.js:1441-1446`；`frontend/node_modules/vitest/dist/chunks/index.De2FqGmR.js:1435`、`:938-941` |

## 已接受的風險（第 2 輪）

- 原型上的 getter、`toJSON` 回傳非自有屬性時不處理。
- 清理途中判斷型別或寫回出錯（不可寫也不可重新定義、只有 getter 的 message／stack、已撤銷的 Proxy）時丟出 TypeError，原錯誤不印，不外洩。
- 複製品類別名稱變 Object；沒有自有屬性的物件變空物件；只差 query 的網址 diff 看不出差異。
- 名稱含敏感字的一般欄位與 { name, value } 的 value 也會被遮。
- setup()、hook、背景事件的錯誤與 #51 的非 Error cause 不在範圍內。

## 安全與一致性檢查（第 2 輪，改過的部分）

| 項目 | 結果 | 依據 |
|---|---|---|
| 登入與權限 | 不適用 | 只改 e2e 測試的錯誤清理 |
| 輸入驗證與注入 | 不適用 | 不處理使用者輸入 |
| 憑證、token、個資不出現在 log | 有涵蓋（#10 修改後） | AC1–AC3、AC6、AC7、AC10；「要清理的錯誤」定義 |
| 同時操作 | 不適用 | 同步處理一個錯誤物件 |
| 中途失敗後的資料狀態 | 有涵蓋（#9 依開發者決定列為已接受的風險） | AC8；已接受的風險第 2 點 |
| 和外部系統的一致性 | 不適用 | 不呼叫外部系統 |
| 既有資料 | 不適用 | 沒有儲存的資料 |
