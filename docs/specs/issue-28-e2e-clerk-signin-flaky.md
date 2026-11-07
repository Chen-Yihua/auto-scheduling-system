# E2E 的 Clerk 登入間歇性失敗（Execution context was destroyed）

- 狀態：已核准
- issue：[#28](https://github.com/Chen-Yihua/auto-scheduling-system/issues/28)
- PR：#45

## 現象
開發者開 PR 或合併到 `main` 後，`frontend-e2e-test` 的登入測試間歇性失敗，錯誤是 `Failed to sign in with email ***: page.evaluate: Execution context was destroyed, most likely because of a navigation.`。這是 `main` ruleset 的必要檢查：PR 因此不能合併，要手動重跑；`main` 上失敗時 `deploy-frontend` 會被跳過。2026-11-02 之後至少出現 10 次（記錄在 #28 的本文與留言），PR #43 的 run 42225862928 連續 3 次失敗，程式碼和前一個通過的 commit 完全相同。

## 重現步驟
1. 在 CI 執行 `npm run test:e2e`（需要 `E2E_CLERK_TEST_EMAIL` 等 secrets）。
2. 測試「用真的 Clerk 測試帳號登入後，看得到主畫面」先 `createPage('/')`，再呼叫 `clerk.signIn({ page, emailAddress })`。
3. 部分執行中，`clerk.signIn` 內部的 `page.evaluate`（在瀏覽器裡跑 `signIn.create({ strategy: 'ticket' })` 與 `Clerk.setActive()`）執行到一半時頁面整頁導覽，測試失敗。

無法在本機穩定重現：要有 Clerk 測試環境的 secrets，而且是間歇性的。

## 預期行為／實際行為
- 預期：登入期間如果發生這種導覽，測試等頁面重新載入後再登入，不讓間歇性的導覽擋住 PR；同時留下足夠的資訊查出是誰觸發了導覽。
- 實際：一次導覽就讓測試失敗，而且沒有任何資訊能判斷導覽的來源（測試的導覽監聽在 `signIn` 之後才註冊）。

## 原因
- 失敗位置：`@clerk/testing` 2.2.33 的 `clerk.signIn`（email 模式）先等 `window.Clerk.loaded`，再用 `page.evaluate` 在瀏覽器裡執行 ticket 登入與 `setActive`（`frontend/node_modules/@clerk/testing/dist/playwright/index.mjs`）；evaluate 期間發生整頁導覽，Playwright 丟出 `Execution context was destroyed`。
- **觸發導覽的來源：待確認。** 推測是 clerk-js 或 `@clerk/nuxt` 在開發環境的 handshake／dev browser 流程在頁面載入後又導覽了一次，但目前的 log 沒有能區分的資訊（#28「尚缺的證據」1～4）。
- 測試的導覽監聽在 `signIn` 之後才註冊（`frontend/tests/e2e/dashboard.e2e.ts:87-93`），看不到登入期間的導覽。

## 驗收條件
| # | 條件 | 類型 |
|---|---|---|
| AC1 | 登入時遇到 `Execution context was destroyed` 錯誤，測試要等頁面載入完成（Clerk 重新 loaded）後先檢查登入狀態：已經登入（`window.Clerk.user` 有值）就當作登入成功，不再呼叫登入；還沒登入才重新登入，最多重試 2 次。重新載入後的等待與登入狀態檢查如果也遇到 `Execution context was destroyed`，當作同一次重試的導覽錯誤：算進重試次數、印重試標記（AC3）與診斷（AC4）；其他錯誤照 AC2。登入成功後，測試照原本的檢查繼續並通過 | 開發者可觀察 |
| AC2 | 其他登入錯誤（找不到使用者、金鑰錯誤、逾時等）不重試，照原本的錯誤讓測試失敗；重試 2 次後仍失敗時，測試失敗，錯誤訊息保留原本的內容，網址與 secrets 依 #46 規格清理 | 不變條件（重試不能掩蓋其他失敗） |
| AC3 | 每次重試都在 CI log 印出一行標記（第幾次重試、錯誤訊息），讓之後能從 log 統計這個錯誤的發生次數 | 開發者可觀察 |
| AC4 | 從開啟頁面開始記錄 main frame 的整頁導覽、瀏覽器 console 的 error 與 pageerror、clerk-js 版本（`window.Clerk.version`）；登入發生錯誤（包括會重試的）或登入後等待逾時時，把這些記錄印到 CI log | 開發者可觀察 |
| AC5 | AC3、AC4 印出的內容不包含 token、cookie 的值、測試帳號 email 與網址的 query string／hash；網址只印 host＋path | 不變條件（安全：repo 與 CI log 是公開的） |

## 不做
- 不上傳 Playwright trace 或錄影：trace 會收錄 Clerk 的 session token 與測試帳號 email，而 artifact 是公開可下載的（開發者決定）。
- 不修根本原因：要等 AC4 的診斷收集到失敗時的導覽來源，再另外決定（#28 保持開啟，這個 PR 不關閉它）。
- `deploy-frontend` 在 `vercel pull` 失敗是 #29，不在這次範圍。

## 回歸測試
| AC | 測試 | 改程式前是否失敗 |
|---|---|---|
| AC1、AC2、AC3 | 新的登入輔助函式（例如 `frontend/tests/e2e/support/signInWithRetry.ts`）的 unit 測試，放在主 vitest 設定會跑到的位置（`tests/e2e/**` 被主設定排除）；用假的 `signIn` 模擬：第 1 次丟 `Execution context was destroyed` 後成功 → 成功並印 1 行標記；連續 3 次都丟 → 失敗且錯誤訊息保留；丟其他錯誤 → 不重試直接失敗；丟 `Execution context was destroyed` 但重新載入後已經是登入狀態 → 成功、不再呼叫 `signIn`、仍印重試標記；檢查登入狀態時第 1 次丟 `Execution context was destroyed`、第 2 次回傳已登入 → 成功；重新載入後等待頁面載入時第 1 次丟 `Execution context was destroyed`、第 2 次成功且已登入 → 成功；重新載入後的等待一直遇到導覽、重試用完 → 失敗且錯誤訊息保留；重新載入後的等待或檢查遇到其他錯誤 → 不重試，照原本的錯誤失敗；其他錯誤直接失敗與重試用完時都有印診斷 | 是（函式還不存在）；「重新載入後已登入」在 2026-11-06 第 1 筆修改前會失敗；「檢查時又遇到導覽」「等待時又遇到導覽」在第 2 筆修改前會失敗 |
| AC4、AC5 | 同一組 unit 測試：記錄導覽時網址帶 query、hash、email 時，印出的內容只有 host＋path，不含 email 與 token | 是（函式還不存在） |
| AC1～AC4 整體 | CI 的 `frontend-e2e-test` 通過；無法穩定重現，所以不要求改程式前失敗。合併後從 log 的重試標記觀察發生次數 | 不適用（間歇性） |

## 修改紀錄
| 日期 | 修改 | 原因 | 確認者 |
|---|---|---|---|
| 2026-11-06 | AC1：重新載入後先檢查登入狀態，已經登入就不再呼叫登入；回歸測試表補上「重新載入後已登入」的情境 | PR #45 第一次 CI 遇到導覽錯誤後重試，重新登入被 Clerk 以 `You're already signed in.` 拒絕：導覽發生時第一次登入已經完成，照原本的 AC1 重試永遠不會成功（Specification Defect）。影響檢查：AC2（其他錯誤不重試、次數用完保留原錯誤）、AC3（重試標記照印）、AC4、AC5 不用改；「不做」不變；回歸測試表更新 AC1 那一列 | 開發者 |
| 2026-11-06 | AC1：重新載入後的等待與登入狀態檢查遇到導覽時，也當作同一次重試；回歸測試表補上這個情境，以及失敗時印診斷的斷言 | 實作審查第 1 輪 #1（Missing AC：第 1 筆修改沒定義檢查這一步失敗的行為）、#3（Test Gap）。影響檢查：AC2（其他錯誤不重試）、AC3、AC4、AC5 文字不用改，AC3、AC4 適用範圍延伸到這一步；「不做」不變 | 開發者 |
| 2026-11-07 | AC2：錯誤訊息保留原本的內容之外，網址與 secrets 依 #46 規格（`docs/specs/issue-46-sanitize-relative-url-query.md`）清理 | #46：往上丟給 vitest 的錯誤會連同 stack、cause 印進公開的 CI log，改在 e2e 測試函式最外層統一清理。影響檢查：AC2 的 4 個測試改名稱與斷言（經外層清理後 `message` 含 `[redacted]`、不含測試帳號 email）；AC1、AC3、AC4、AC5 不用改；「不做」不變 | 開發者 |
