# E2E 改用 @playwright/test，並由測試自己啟動前端、後端與 MongoDB

- 狀態：已核准
- 等級：高風險（改的是「token、cookie 不出現在公開的 CI log」這項保證：拿掉 issue-50 的清理用 reporter（把測試結果印到終端機的元件），改成一般做法）
- 規格審查：有（高風險一定做；審查時規格還沒拆開，任務與排程流程拆到 `e2e-user-flows`（之後的 PR））
- PR：（開 PR 後填）

## 簡短說明
前端 E2E 測試改用 `@playwright/test` 執行，測試自己啟動前端、後端與 MongoDB，不連 Cloud Run，開著 `npm run dev` 也能跑。CI log 的機密處理改成一般做法：機密放在 GitHub secrets 由 GitHub 自動遮掉，測試只印清理過的登入診斷，CI 不上傳 trace（可以一步步重播測試的紀錄檔）與報告。任務管理與排程的使用者流程在下一份規格 `e2e-user-flows`（之後的 PR），要等這份合併後才做。

## 背景
E2E 現在只驗證到「訪客畫面」與「登入成功」；前端打的後端是 CI secret `NUXT_PUBLIC_API_BASE_URL` 指向的 Cloud Run，Cloud Run 關掉計費後就停機了，要打 API 的流程都跑不起來。開發者想補上任務管理與排程的 E2E，先要有一套測試自己啟動、不依賴 Cloud Run 的環境。

### 現在的 E2E
- `npm run test:e2e` 是 `vitest run -c vitest.e2e.config.ts`；`@nuxt/test-utils/e2e` 的 `setup({ browser: true })` 會 build 一次 Nuxt 並啟動，再用 `playwright-core` 開 headless Chromium（`frontend/tests/e2e/dashboard.e2e.ts:20-23`）。
- build 的位置是 `.nuxt/test/<亂數>`，結束時刪掉，不碰 `.output`（`frontend/node_modules/@nuxt/test-utils/dist/shared/test-utils.CT3RJOY3.mjs:83-89`、`:101-104`）。即使如此，開著 `npm run dev` 時跑 E2E，dev server 仍然會壞掉，錯誤像 `Package import specifier "#internal/nuxt/paths" is not defined`（`frontend/README.md:47`）。原因還沒確認；可能的原因有：build 資料夾在 `.nuxt` 底下、結束時被刪；dev 與 build 共用 vite 的快取 `node_modules/.cache/vite`（`@nuxt/vite-builder/dist/shared/vite-builder.BNZmexy5.mjs:622`、`:941`）；共用 `node_modules/.cache/nuxt`（例如 `@nuxt/fonts/dist/module.mjs:241`）。
- CI 的 `frontend-e2e-test` job 釘在 `ubuntu-24.04`，因為 Playwright 1.52 不支援 26.04（`.github/workflows/deploy.yml:84`）。
- 本機的 Clerk 金鑰與 `E2E_CLERK_TEST_EMAIL` 能讀到，是因為 `@nuxt/test-utils` 載入 Nuxt 設定時把 `frontend/.env` 放進 `process.env`；`@playwright/test` 不會自動載入 `.env`。
- fork 出去的 PR 拿不到 secrets。`.github/workflows/deploy.yml:77-79` 的註解說登入後的測試自動跳過、job 照樣通過；但沒有 Clerk 公開金鑰時，`@clerk/nuxt` 的伺服器 middleware 對每個頁面請求丟出 `Publishable key is missing`（`@clerk/nuxt/dist/module.js` 的 `addServerHandler`、`@clerk/backend/dist/chunk-LFAHZTE6.mjs:2962`、`:3012-3013`、`@clerk/shared/dist/chunk-G3VP5PJE.mjs:21-31`），所以訪客測試其實也會失敗（推論：沒有在 CI 驗證）。

### 現在的機密處理
- `frontend/tests/e2e/support/sanitizingReporter.ts` 是 vitest 的 reporter，原地清理 vitest 交給其他 reporter 的錯誤與 `console` 輸出，約 200 行、21 條規則（規格 `docs/specs/issue-50-sanitize-vitest-output.md`）。
- 登入用 `@clerk/testing/playwright` 的 `clerk.signIn`（email 模式，由 Clerk 發一次性的 sign-in ticket），遇到 `Execution context was destroyed` 由 `signInWithRetry` 重試（規格 `docs/specs/issue-28-e2e-clerk-signin-flaky.md`）。登入診斷由 `createDiagnosticLogger` 印出，網址只留 host 與 path、email 與 JWT 遮掉、cookie 只印名稱；測試函式丟出的錯誤由 `withSanitizedErrors` 清理（`frontend/tests/e2e/support/signInWithRetry.ts`，規格 `docs/specs/issue-46-sanitize-relative-url-query.md`）。
- GitHub Actions 會把 `${{ secrets.XXX }}` 的原字串在 log 裡自動換成 `***`；編碼過的值（例如 URL 編碼的 email）與執行時才產生的值（登入後的 session cookie、JWT）不會被遮。

### 為什麼改成一般做法
- Playwright 官方文件沒有清理 CI log 的建議，只提醒存登入狀態的檔案不要 commit、trace 與報告裡有請求內容。一般專案的做法是：機密放 GitHub secrets、測試不主動印出 token、公開的 repo 不上傳 trace 與報告。
- 會造成實際傷害的機密（Clerk 私密金鑰、測試帳號 email 與密碼）都是 GitHub secrets，會被自動遮掉。
- 執行時才產生的值屬於 Clerk **開發環境**的**測試帳號**：JWT 的有效期由 Clerk 後台設定（預設 60 秒）；長效的 cookie、testing token、dev browser token 外流時，別人最多能以這個測試帳號登入開發環境的 Clerk。正式環境用的是另一個 Clerk 正式環境（`pk_live_`，開發者確認），不接受開發環境簽發的 token，所以碰不到正式環境與任何真實資料。
- 實際的後果：別人可以改掉測試帳號的 email、登出所有 session 或刪掉帳號，讓 `frontend-e2e-test`（`main` 的必要檢查）的登入一直失敗。處理方式：開發者在 Clerk 後台撤銷這個帳號的 session、重設或重建測試帳號，必要時更新 `E2E_CLERK_TEST_EMAIL`。
- 會印出這些值的路徑（都不是 repo 的程式印的）：Clerk 請求失敗時 `@clerk/testing` 用 `console.warn` 印出請求網址（帶 testing token）與部分回應內容（`@clerk/testing/dist/chunk-6QEJXXZK.mjs:1`）；Playwright 錯誤訊息附的 call log（請求紀錄）列出請求網址與標頭，例如 `authorization: Bearer <JWT>`（`playwright-core/lib/server/fetch.js:432-436`、`client/connection.js:147`）。
- 把 issue-50 的 reporter 改寫成 Playwright 的介面，要再寫一套規則與整合測試，維護成本和這個風險不成比例。

### 接上本機後端時會碰到的事實
- 後端 `main.py` 一開始就呼叫 `load_dotenv()`，從 `main.py` 所在的資料夾往上找 `.env`，不覆蓋已經存在的環境變數（空字串也算存在）（`backend/main.py:1-2`）。沒有給 `MONGO_URI`、`MONGO_DB` 時，預設連 `mongodb://localhost:27017` 的 `auto_scheduling_db`，通常就是開發用的資料庫（`backend/core/database.py:7-8`）。
- 沒設定 `REDIS_URL`（或是空字串）時，快取與 rate limit 用記憶體（`backend/core/cache.py:11-29`、`backend/core/rate_limit.py:27-31`）。
- 後端啟動時執行 `ensure_indexes()` 建立索引，其中有唯一索引（`backend/main.py:38-46`、`backend/core/database.py:48-64`）。
- 後端啟動時會建立 Gemini client（`backend/main.py:42`）；沒有 `GEMINI_API_KEY` 時 `genai.Client` 丟出 `ValueError: No API key was provided`，後端啟動失敗。
- 後端必填的 `CLERK_ISSUER`、`CLERK_JWKS_URL`（`backend/core/security.py:22-25`）可以從 Clerk 公開金鑰推出：公開金鑰 `pk_test_<base64>` 解開是 Clerk 專案的網域（`frontend/tests/e2e/dashboard.e2e.ts:44` 用同樣的方式），issuer 是 `https://<網域>`，JWKS 是 `https://<網域>/.well-known/jwks.json`。
- 前端打後端的網址是 runtime config `public.apiBaseUrl`，讀 `NUXT_PUBLIC_API_BASE_URL`（`frontend/nuxt.config.ts:16`）。後端的 CORS 預設只放行 `http://localhost:3000`，可以用 `CORS_ALLOWED_ORIGINS` 改（`backend/main.py:57-59`）。
- 使用者的 `users` 文件由前端標題列的 `ensureUserRecord` 建立：先 `GET /users/me`，沒有就 `POST /users/`，已存在時回 409（`frontend/composables/useUserSync.ts:68-83`、`backend/routers/user.py:59-64`）。
- Playwright：webServer（設定裡、測試開始前自動啟動的伺服器）先啟動，`globalSetup` 之後才執行（`playwright/lib/runner/tasks.js:99-108`）；每個 worker（另外開的執行行程）都會重新載入一次設定檔（`worker/workerMain.js:163`）；預設的 `testMatch` 只收集 `*.spec.*`、`*.test.*`（`common/config.js:155`）；收集到 0 個測試會失敗（`runner/tasks.js:253-261`）；`list` reporter 對跳過的測試只印標題（`reporters/list.js:157-159`）。
- `frontend/playwright/.auth/user.json` 是開發者給 Playwright MCP 用的個人登入狀態（`.gitignore:25-29`）。主 vitest 設定用 `exclude: ['tests/e2e/**']` 排除 E2E（`frontend/vitest.config.ts:14`）。

## 需求

### Playwright 測試框架
1. 前端 E2E 測試改用 `@playwright/test` 執行，`npm run test:e2e` 改跑 `playwright test`，測試檔只從 `frontend/tests/e2e/` 收集。
2. 現有兩個 E2E 測試（訪客畫面、登入成功）改寫成 `@playwright/test`，驗證的畫面內容不變。
3. 登入、登入重試與登入後診斷，在 setup project（標成其他測試的前置步驟的測試，Playwright 官方建議的登入做法）執行一次，把登入狀態存起來（`storageState`，存下 cookie 與 local storage 的檔案）給登入後的測試用；登入後的測試自己不再登入。
4. 登入繼續用 `@clerk/testing/playwright` 與 `signInWithRetry`，重試與登入診斷（包括診斷內容的清理）照 issue-28 與 issue-46 AC1、AC3～AC7，不變；拿掉包住每個測試函式的 `withSanitizedErrors`（issue-46 AC2）。
5. 本機執行時，Playwright 設定載入 `frontend/.env`（不覆蓋已經存在的環境變數），Clerk 金鑰與 `E2E_CLERK_TEST_EMAIL` 從那裡讀到。
6. 照順序判斷要跳過哪些測試，符合一條就停止：
   1. 沒有 Clerk 公開金鑰或私密金鑰：不啟動任何伺服器，其他測試都不收集，只執行一個標示跳過、標題是「沒有 Clerk 金鑰，跳過 E2E」的測試，結束碼 0。
   2. 沒有 `E2E_CLERK_TEST_EMAIL`：setup project 與登入後的測試標示跳過，訪客測試照常執行。

### 測試自己啟動的環境
7. 本機與 CI 的 E2E 都由 Playwright 自己 build 前端、啟動前端與後端，不連開發者的 dev server 與後端，也不連 Cloud Run。
8. 開發者開著 `npm run dev` 時也能跑 E2E，跑完 dev server 照常運作（包括改檔案後畫面更新）。
9. E2E 啟動的所有伺服器用和開發環境不同的 port，開著 dev server、開發用後端與 MongoDB 時不衝突。
10. E2E 的後端與 setup project 都只連獨立的資料庫 `auto_scheduling_e2e`，不碰開發用的資料庫。
11. E2E 的後端不連 Redis，快取與 rate limit 用記憶體，不碰開發用的 Redis。
12. MongoDB 在後端之前啟動：CI 用 GitHub Actions 的 service container（job 旁邊另外開的容器），本機由 Playwright 啟動，開發者不用自己先開 MongoDB。
13. 每次執行 E2E，setup project 清空 `auto_scheduling_e2e` 的所有文件，保留後端建立的索引。
14. E2E 的後端不呼叫真的 Gemini：`GEMINI_API_KEY` 設成固定的假值，讓後端能啟動。
15. setup project 建立測試使用者的 `users` 文件，跟一般使用者登入後的狀態一樣。

### 機密處理（一般做法）
16. 機密（Clerk 私密金鑰、測試帳號 email 與密碼）只從 GitHub secrets 或本機的 `frontend/.env` 讀取；它們的原字串由 GitHub 在 CI log 自動遮掉。
17. `frontend/tests/e2e/` 的程式自己印出的內容，只有經過 `createDiagnosticLogger` 清理的登入診斷：不包含 token、cookie 的值，網址只留 host 與 path（issue-28、issue-46）。
18. CI 用 Playwright 內建的 reporter：`list` 與 `github`（在 PR 頁面顯示失敗的附註）；拿掉 issue-50 的清理用 reporter。
19. CI 不印 E2E 啟動的伺服器與子行程的輸出；本機照常印。
20. CI 不產生、也不上傳 trace、截圖、影片與 HTML 報告。
21. 本機在測試失敗時保留 trace，成功時不保留；HTML 報告不自動開啟伺服器等待。
22. 存登入狀態的檔案不 commit 進 repo，也不覆蓋開發者 Playwright MCP 的登入檔。

### CI 與文件
23. CI 的 `frontend-e2e-test` 在 job 裡啟動 MongoDB 與 E2E 的後端，不再使用 secret `NUXT_PUBLIC_API_BASE_URL`，不新增 GitHub secret。
24. `frontend-e2e-test` 在前端或後端有改動時執行；只改文件時照舊 skipped。
25. 文件與舊規格同步（項目見實作計畫「完成前檢查」）。

## 不做
- 不處理：連開發者開著的 dev server 跑 E2E。dev server 打的是開發用後端與資料庫，測試資料會寫進開發資料。
- 不處理：遮掉不是 repo 的程式主動印出的、執行時才產生的值：`@clerk/testing` 的警告、Playwright 錯誤訊息與 call log 裡的 testing token、dev browser token、session JWT、cookie。這些屬於開發環境的測試帳號，影響範圍與外流後的處理方式見背景「為什麼改成一般做法」。
- 不處理：沒有 Clerk 金鑰時（fork 出去的 PR）跑任何 E2E。前端沒有公開金鑰時每個頁面都報錯，給假金鑰的行為沒有驗證過。
- 不處理：任務管理與排程的使用者流程、假的 Google 日曆。在 `e2e-user-flows`（之後的 PR）。

## 假設
1. Playwright 升級到目前最新的穩定版，CI 的 `runs-on` 改回 `ubuntu-latest`；最新版還不支援 `ubuntu-latest` 時，維持釘住並更新註解寫明原因。
2. 本機的 MongoDB 用 `mongodb-memory-server`（測試用、會自己下載 MongoDB 執行檔的 npm 套件）當成第一個 webServer 啟動，開發者不用裝 Docker。

## 驗收條件

| # | 需求 | 條件 |
|---|---|---|
| AC1 | 1 | 在 `frontend` 執行 `npm run test:e2e`，由 Playwright 執行 `frontend/tests/e2e/` 底下的測試；`npm run test` 不會執行這些測試檔 |
| AC2 | 2 | 訪客未登入時打開 `/`，畫面顯示「登入後即可查看今天的任務」與「登入後即可查看 Google 行事曆」，標題列沒有 `aria-label="新增任務"` 的按鈕 |
| AC3 | 2、3 | 登入後的測試用 setup project 存下的登入狀態打開 `/`，畫面出現「今日」，不再出現「登入後即可查看」；這個測試自己不呼叫 `clerk.signIn` |
| AC4 | 3、4 | setup project 登入時遇到 `Execution context was destroyed`，照 issue-28 AC1～AC5 重試並印出診斷（網址照 issue-46 清理）；登入後等待逾時時印出登入後診斷 |
| AC5 | 5 | 本機只在 `frontend/.env` 設定 Clerk 金鑰與 `E2E_CLERK_TEST_EMAIL`（shell 沒有 export）時執行 `npm run test:e2e`，登入後的測試有執行，不是跳過 |
| AC6 | 6 | 沒有設定 Clerk 公開金鑰或私密金鑰時執行 `npm run test:e2e`：沒有啟動任何伺服器，只有一個標示跳過、標題是「沒有 Clerk 金鑰，跳過 E2E」的測試，結束碼 0 |
| AC7 | 6 | 有 Clerk 金鑰、沒有 `E2E_CLERK_TEST_EMAIL` 時：setup project 與登入後的測試標示跳過，訪客測試執行並通過，結束碼 0 |
| AC8 | 7、9、12 | 開發者的 `npm run dev`（port 3000）、開發用後端（port 8000）與 MongoDB（port 27017）開著時執行 `npm run test:e2e`：E2E 的伺服器都用其他 port 啟動，測試通過；這些都沒開時執行，測試也通過 |
| AC9 | 8 | 開著 `npm run dev` 執行 `npm run test:e2e`：`frontend/.nuxt`、`frontend/.output` 沒有被改寫；結束後 dev server 照常回應頁面；接著改一個頁面檔，瀏覽器看得到修改 |
| AC10 | 10 | 不變條件（資料）：執行 E2E 後，開發用資料庫每個 collection 的文件數都沒有變 |
| AC11 | 10 | 不變條件（資料）：setup project 清空資料庫前，確認連到的資料庫名稱是 `auto_scheduling_e2e`；不是時 setup project 失敗，不刪任何文件 |
| AC12 | 11 | 開發者的 `backend/.env` 有設定 `REDIS_URL` 時執行 E2E，E2E 的後端啟動 log 有「REDIS_URL 未設定」，沒有連到 Redis |
| AC13 | 13 | setup project 清空後，`auto_scheduling_e2e` 沒有任何文件，後端建立的索引都在 |
| AC14 | 15 | setup project 結束後，用測試使用者的 token 呼叫 `GET /users/me` 回 200；`POST /users/` 回 201 或 409 都算建立成功 |
| AC15 | 17 | 不變條件（安全）：`frontend/tests/e2e/` 裡只有 `createDiagnosticLogger` 內部呼叫 `console.*`；登入診斷照 issue-28 AC5、issue-46 AC1、AC3～AC7 清理 |
| AC16 | 19 | 不變條件（安全）：`GITHUB_ACTIONS=true` 時，E2E 啟動的伺服器與子行程的 stdout、stderr 都不印到 CI log |
| AC17 | 20 | 不變條件（安全）：`GITHUB_ACTIONS=true` 時，trace、截圖、影片都關閉；`frontend-e2e-test` 沒有上傳任何 artifact（可以下載的附檔） |
| AC18 | 21 | 本機測試失敗時，`test-results/` 留下這個測試的 trace；測試成功時沒有 trace；測試失敗後 `npm run test:e2e` 直接結束，不開伺服器等待 |
| AC19 | 24 | 只改後端的 PR，`frontend-e2e-test` 會執行；只改文件的 PR，`frontend-e2e-test` 顯示 skipped |

## 實作計畫

### 1. 先找出 dev server 壞掉的原因（需求 8）
- 在開發者沒有開 dev server 的時候（先用 `ps` 確認沒有 `nuxt dev`），自己起一個臨時 dev server，跑現在的 `npm run test:e2e`，重現 `#internal/nuxt/paths` 錯誤；停掉時只砍自己起的 PID。
- 依原因決定隔離方式，例如：build 資料夾放在 `.nuxt` 外面（`.nuxt-e2e`、`.output-e2e`）、E2E build 時另外指定 vite 的 `cacheDir`（例如 `node_modules/.cache/vite-e2e`）、其他共用的快取資料夾。原因與做法寫進 PR 描述。

### 2. 前端：Playwright 設定
- `frontend/package.json`：加 `@playwright/test`，`playwright` 升級到最新穩定版；`test:e2e` 改成 `playwright test`。刪除 `vitest.e2e.config.ts`、`tests/e2e/support/sanitizingReporter.ts`、`tests/e2e-support/sanitizingReporter*.test.ts` 與它們用的 fixtures。`signInWithRetry.ts`、`e2eSecrets.ts` 與 `signInWithRetry.test.ts` 保留，但刪掉 `withSanitizedErrors`、`sanitizeError` 與它們的測試（issue-46 AC2）；issue-50 AC16（`e2eSecrets` 的清單）的測試從 `sanitizingReporter.test.ts` 移到 `signInWithRetry.test.ts`，`e2eSecrets.ts` 的註解改成現在的使用者。
- `frontend/nuxt.config.ts`：有 E2E 專用的環境變數（例如 `NUXT_E2E=1`）時，套用第 1 步決定的隔離方式；`.gitignore` 加上這些資料夾與 `frontend/.auth-e2e/`。
- `frontend/playwright.config.ts`：
  - 開頭用 Node 的 `process.loadEnvFile` 載入 `frontend/.env`（檔案存在時，不覆蓋已經存在的變數）。
  - 沒有 Clerk 公開金鑰或私密金鑰時（需求 6 第 1 條）：`webServer` 是空的，只收集一個測試檔，裡面只有一個標題是「沒有 Clerk 金鑰，跳過 E2E」、呼叫 `test.skip()` 的測試（Playwright 收集到 0 個測試會失敗）。
  - `testDir: 'tests/e2e'`。
  - projects，每個用 `testMatch` 指定收集的檔案：`setup`（`/auth\.setup\.ts/`）、`guest`（`*.guest.spec.ts`，不依賴 setup）、`signed-in`（`*.signed-in.spec.ts`，依賴 `setup`，使用 `storageState: '.auth-e2e/storageState.json'`）。
  - `webServer` 依序啟動：1. MongoDB（本機用 `mongodb-memory-server` 的小腳本；CI 用 service container，這一項跳過）；2. 後端（例如 port 8001）；3. 前端：`NUXT_E2E=1` build 後啟動 build 出來的 server（例如 port 3100），`NUXT_PUBLIC_API_BASE_URL` 指向 E2E 後端。不設 `reuseExistingServer`，避免接到開發者的伺服器。
  - 每次執行產生的值（`SECRET_ENCRYPTION_KEY`、port）在主行程產生後放進 `process.env`；worker 會重新載入設定檔，載入時沿用 `process.env` 已有的值，不重新產生。
  - `GITHUB_ACTIONS=true` 時：`reporter: [['list'], ['github']]`；每個 `webServer` 的 `stdout`、`stderr` 設成 `ignore`；`trace`、`screenshot`、`video` 設成 `off`。
  - 本機：`reporter: [['list'], ['html', { open: 'never' }]]`；`trace: 'retain-on-failure'`。
- 後端的環境變數由 webServer 明確給。後端照常載入 `backend/.env`，但 python-dotenv 不覆蓋已經存在的變數，所以 E2E 給的值優先；會造成共用的變數一定要明確給（空字串也算），至少：`MONGO_URI`、`MONGO_DB=auto_scheduling_e2e`、`REDIS_URL=`、`CLERK_ISSUER`、`CLERK_JWKS_URL`（由公開金鑰推出）、`GEMINI_API_KEY`（固定假值）、`SECRET_ENCRYPTION_KEY`、`GOOGLE_CLIENT_ID`、`GOOGLE_CLIENT_SECRET`、`GOOGLE_REDIRECT_URI`（假值）、`CORS_ALLOWED_ORIGINS`（E2E 前端的網址）、`DISCORD_MR_WEBHOOK_URL=`、`DISCORD_MAIN_WEBHOOK_URL=`、`GITHUB_BOT_TOKEN=`。

### 3. setup project（`tests/e2e/auth.setup.ts`）
- 清空 `auto_scheduling_e2e`：先確認連到的資料庫名稱是 `auto_scheduling_e2e`，不是就丟出錯誤、不刪任何文件（AC11）；再刪除每個 collection 的所有文件，保留索引（需求 13）。
- 沒有 `E2E_CLERK_TEST_EMAIL` 時，登入相關的步驟標示跳過。
- 用 `clerk.signIn` 與 `signInWithRetry` 登入，診斷照現在的方式；存 `storageState`。
- 用登入後的 token 呼叫 `POST /users/`，201 或 409 都視為已建立（標題列的 `ensureUserRecord` 可能已經建好）。

### 4. E2E 測試
- `frontend/tests/e2e/dashboard.guest.spec.ts`：訪客測試；`frontend/tests/e2e/dashboard.signed-in.spec.ts`：登入後首頁。
- 測試函式照 Playwright 官方範例的寫法，不另外包一層；`signInWithRetry.ts` 改用 `@playwright/test` 的 `Page` 型別，重試與診斷的行為不變。

### 5. CI
- `deploy.yml` 的 `frontend-e2e-test`：加 MongoDB service container、Python 與後端依賴安裝；移除 `NUXT_PUBLIC_API_BASE_URL`；`npx playwright install --with-deps chromium`；執行條件改成前端或後端有改動時。

### 6. 完成前檢查
不是使用者看得到的行為，但交付前要逐項確認，實作審查也照這份清單檢查：
1. `frontend/package.json` 的 `test:e2e` 是 `playwright test`，`playwright.config.ts` 的 `testDir` 是 `tests/e2e`。
2. `GITHUB_ACTIONS=true` 時 `reporter` 是 `list` 與 `github`；`sanitizingReporter.ts`、`vitest.e2e.config.ts` 已刪除。
3. 登入狀態存在 `frontend/.auth-e2e/storageState.json`，這個路徑在 `.gitignore` 裡；`frontend/playwright/.auth/user.json` 不被讀寫。
4. `deploy.yml` 的 `frontend-e2e-test`：Clerk 私密金鑰、`E2E_CLERK_TEST_EMAIL`、`E2E_CLERK_TEST_PASSWORD` 用 `${{ secrets.* }}` 帶入；沒有 `NUXT_PUBLIC_API_BASE_URL`；用到的 secret 只有 `NUXT_PUBLIC_CLERK_PUBLISHABLE_KEY`、`NUXT_CLERK_SECRET_KEY`、`E2E_CLERK_TEST_EMAIL`、`E2E_CLERK_TEST_PASSWORD`；第 77-79 行的註解改成新的跳過行為。
5. `frontend/README.md`「測試」寫出本機執行 E2E 的步驟，不再要求跑 E2E 前先停 `npm run dev`；`npm run build` 的警告保留。
6. 根目錄 `README.md` 的技術棧與測試說明（第 49、65 行）寫 `@playwright/test`，不再提 `@nuxt/test-utils`。
7. `CLAUDE.md`「共用的開發環境」不再說 dev server 開著時不能跑 `npm run test:e2e`。
8. 舊規格的狀態：`docs/specs/issue-50-sanitize-vitest-output.md` 是「部分被 [e2e-playwright](e2e-playwright.md) 取代（AC1～AC15、AC17～AC21）」；`docs/specs/issue-46-sanitize-relative-url-query.md` 是「部分被 [e2e-playwright](e2e-playwright.md) 取代（AC2）」；`docs/specs/ci-path-filter.md` 是「部分被 [e2e-playwright](e2e-playwright.md) 取代（AC2）」。
9. `docs/architecture.md`、`docs/api.md` 不用改：沒有新增服務、collection 或 endpoint。

### 考慮過、沒選的做法
- 保留 vitest，只加流程：沒有 trace、`webServer`、`storageState`，dev server 壞掉的問題也還在。
- 把 issue-50 的清理用 reporter 改寫成 Playwright 的介面：要另外處理 Playwright 繞過 reporter 的輸出路徑（`globalSetup`、自動補上的 `dot` reporter、reporter 自己的例外）並寫整合測試，維護成本和風險不成比例（背景「為什麼改成一般做法」）。
- 保留 `withSanitizedErrors` 包住每個測試、setup、hook：只擋得住 Playwright 錯誤訊息裡的 JWT，擋不住 `@clerk/testing` 的警告；Playwright 從測試函式的參數決定提供哪些 fixture，要改寫包裝方式，每個測試都要記得包，容易漏。
- 登入與準備資料放在 `globalSetup`：Playwright 官方建議用 setup project；而且 `globalSetup` 在 webServer 之後才執行，輸出也不經過 reporter。
- 沒有 Clerk 金鑰時給前端假的 `pk_live_` 金鑰讓訪客測試照跑：瀏覽器端載入 Clerk 會失敗，首頁可能什麼都不顯示，沒有驗證過。

## 測試對應

| AC | 測試或驗證步驟 | 預期結果 |
|---|---|---|
| AC1 | CI log 的 `npm run test:e2e` 步驟；執行 `npm run test` | 是 Playwright 的輸出；`npm run test` 的結果沒有 E2E 測試檔 |
| AC2 | `dashboard.guest.spec.ts` | 通過 |
| AC3 | `dashboard.signed-in.spec.ts`（CI 有 secret 時執行）；讀程式碼 | 通過；測試裡沒有 `clerk.signIn` |
| AC4 | `frontend/tests/e2e-support/signInWithRetry.test.ts` | 通過，重試與診斷的斷言不變 |
| AC5 | 手動：只在 `frontend/.env` 設定，執行 `npm run test:e2e` | 登入後的測試有執行。PR 描述附上結果 |
| AC6 | 手動：`NUXT_PUBLIC_CLERK_PUBLISHABLE_KEY= NUXT_CLERK_SECRET_KEY= npm run test:e2e` | 沒有 build、沒有啟動伺服器；只有一個 skipped、標題是「沒有 Clerk 金鑰，跳過 E2E」；結束碼 0。PR 描述附上結果 |
| AC7 | 手動：`E2E_CLERK_TEST_EMAIL= npm run test:e2e` | 訪客測試通過，其他 skipped，結束碼 0。PR 描述附上結果 |
| AC8、AC9 | 手動，開著 `npm run dev`、開發用後端與 MongoDB，照順序做：1. 記下 `.nuxt`、`.output` 的修改時間。2. 執行 `npm run test:e2e`。3. 確認修改時間沒變。4. 打開 `http://localhost:3000`。5. 改一個頁面檔的文字。接著關掉 MongoDB 與開發用後端，再執行一次 `npm run test:e2e` | 第 2 步測試通過；第 3 步修改時間沒變；第 4 步頁面正常；第 5 步瀏覽器看得到修改；最後一次也通過。PR 描述附上結果 |
| AC10 | 手動：執行前後各查一次開發用資料庫每個 collection 的文件數 | 每個都相同 |
| AC11 | 清空函式的 unit 測試：傳入名稱不是 `auto_scheduling_e2e` 的資料庫 | 丟出錯誤，沒有呼叫刪除 |
| AC12 | 手動：`backend/.env` 有 `REDIS_URL` 時執行 E2E，看本機印出的後端 log | 有「REDIS_URL 未設定」 |
| AC13 | `auth.setup.ts` 清空後斷言每個 collection 沒有文件、索引清單和清空前相同 | 通過 |
| AC14 | `auth.setup.ts` 結束前呼叫 `GET /users/me` | 200 |
| AC15 | PR 描述附上 `grep -rn "console\." frontend/tests/e2e/` 的結果；`signInWithRetry.test.ts` | 只出現在 `createDiagnosticLogger` 裡；測試通過 |
| AC16、AC17 | unit 測試：讀 `playwright.config.ts` 匯出的設定，分別在 `GITHUB_ACTIONS` 為 `'true'` 與未設定時；讀 `deploy.yml` | CI：每個 `webServer` 的 `stdout`、`stderr` 是 `ignore`，`trace`、`screenshot`、`video` 是 `off`；`deploy.yml` 沒有 `upload-artifact` |
| AC18 | 手動：本機讓一個測試失敗、一個成功 | 只有失敗的測試在 `test-results/` 有 `trace.zip`；指令直接結束 |
| AC19 | 讀 `deploy.yml` 的 `if` 條件；這個 PR 的 CI 結果 | 前端或後端有改動時執行 |

## 修改紀錄
| 日期 | 修改 | 原因 | 確認者 |
|---|---|---|---|

## 請你決定
無
