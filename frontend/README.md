# Auto-Scheduling Frontend

這是使用 Nuxt 3 開發的前端專案，負責處理排程系統的使用者介面（UI），結合 Tailwind CSS、Nuxt UI，登入交給 Clerk 處理，CI/CD 用 GitHub Actions（見 repo 根目錄的 `.github/workflows/deploy.yml`），測試通過才會部署到 Vercel。

## 功能

- 手動任務管理（新增/編輯/刪除，優先度跟時長沒填時由後端 AI 推斷）
- GitHub / Jira / Moodle 資料整合，含「資料是不是舊的（stale）」提示
- Google Calendar 嵌入顯示 + 可用時段/排程建議
- 帳號連結管理（GitHub/Jira/Moodle 金鑰的新增、編輯、刪除）
- Hacker News 熱門文章、LeetCode 每日一題（不需要登入）
- 未登入時不會對需要授權的 API 發送請求，改顯示登入提示

---

## 需求

- **Node.js 20**（CI 用這個版本）
- 後端要先跑起來，才看得到任務、GitHub / Jira / Moodle 等資料（見 [`../backend/README.md`](../backend/README.md)）

## 環境變數

複製 `.env.example` 成 `frontend/.env`，把值填齊：

| 變數 | 必填 | 說明 |
|---|---|---|
| `NUXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | ✅ | Clerk 的 Publishable key |
| `NUXT_CLERK_SECRET_KEY` | ✅ | Clerk 的 Secret key，要跟上面那把來自**同一個 Clerk 專案**，且跟後端用同一個專案 |
| `NUXT_PUBLIC_API_BASE_URL` | | 後端 API 網址，預設 `http://localhost:8000` |
| `NUXT_PUBLIC_FRONTEND_URL` | | 前端自己的網址（Google 授權完成後導回用），預設 `http://localhost:3000` |
| `GOOGLE_CLIENT_ID` | | Google Calendar 授權用，跟後端同一個；沒設定就無法連接 Google Calendar |

沒有設定 Clerk 的兩把金鑰，網站會無法登入。

## 安裝與啟動

```bash
# 安裝依賴套件
npm install

# 啟動開發伺服器（預設為 http://localhost:3000）
npm run dev
```

其他常用指令：`npm run lint`（ESLint）、`npm run format`（Prettier）、`npm run build`（正式建置）。

> ⚠️ **開著 `npm run dev` 的時候，不要跑 `npm run build`**：它會改寫 `.nuxt` 資料夾，開發伺服器會因此壞掉（錯誤訊息像 `Package import specifier "#internal/nuxt/paths" is not defined`）。壞掉時停掉開發伺服器，刪掉 `.nuxt` 和 `.output`，重新 `npm run dev` 即可。`npm run test:e2e` 的 build 放在 `.nuxt-e2e`、`.output-e2e`，開著 `npm run dev` 也能跑。

## 測試

```bash
npm run test        # 單元/元件測試（Vitest + jsdom），CI 上跑這個
npm run test:e2e    # 真實瀏覽器 E2E 測試（Playwright），CI 上獨立一個 job 跑
npm run coverage    # 單元測試 + 覆蓋率報表
```

兩種測試環境不一樣，分開執行（`vitest.config.ts` / `playwright.config.ts`），不能混著跑：

- **單元/元件測試**（`tests/components/`、`tests/composables/`、`tests/utils/`、`tests/pages/`、`tests/server/`、`tests/e2e-support/`）：jsdom 環境，Nuxt 的 auto-import（`useAuth`、`useToast` 等）用 `tests/__mocks__/` 和 `vi.stubGlobal` 手動模擬，不會真的打 API 或開瀏覽器。
- **E2E 測試**（`tests/e2e/`）：用 `@playwright/test` 執行。Playwright 自己 build 並啟動前端（port 3100）、後端（port 8001）、MongoDB（port 27018）與假的 Google 日曆伺服器（port 8002，讓排程不連真的 Google），再開一個真的 headless 瀏覽器操作頁面；不連開發用的後端、資料庫、Redis，也不連 Cloud Run，所以開著 `npm run dev` 也能跑。
  - **本機執行步驟**：
    1. `npm install`，再 `npx playwright install chromium` 安裝瀏覽器。
    2. 後端依賴已安裝（repo 根目錄的 `.venv`，見 [backend/README.md](../backend/README.md)）；後端用 `.venv/bin/python`，沒有 `.venv` 時用 `python`，也可以用環境變數 `E2E_PYTHON` 指定。
    3. 第一次執行時，`mongodb-memory-server` 會下載 MongoDB 執行檔，不需要自己裝 Docker 或 MongoDB。
    4. 在 `.env` 放 Clerk 金鑰（見上面「環境變數」），而且要用開發用（`pk_test_` / `sk_test_`）的一對，不能用正式環境的。
    5. `npm run test:e2e`。
  - **UI 模式**（Playwright 官方的圖形介面，開著期間可以反覆重跑測試）：`npm run test:e2e:ui`。
    1. 指令會在瀏覽器打開 UI，網址印在終端機（`http://localhost:9400`）。
    2. UI 開著期間伺服器一直開著，在 UI 裡重跑測試不重新 build、不重新啟動伺服器。
    3. `npm run test:e2e` 發現 port 3100、8001、8002、27018 已經有伺服器，也會沿用。
    4. 只會沿用 E2E 自己的伺服器，不會接到 `npm run dev` 與開發用後端；CI 不沿用。
    5. 第一次打開時，在 UI 的 Projects 設定勾選 `setup`、`guest`、`signed-in` 三個。
    6. 只勾 `signed-in` 時，`setup` 不會先跑，登入狀態可能是舊的或不存在。
    7. 改了前端或後端程式後，在執行 `npm run test:e2e:ui` 的終端機按 Ctrl+C，再重新執行。
    8. 只關瀏覽器分頁不會關伺服器；伺服器還用舊程式開著，`npm run test:e2e` 也會沿用它們。
    9. 打開 UI、重新整理 UI 分頁，或 UI 開著時在另一個終端機執行 `npm run test:e2e`，都會清空 `test-results/`，要先看完上一次失敗的紀錄。
  - **伺服器 log**：本機 MongoDB、後端、前端、假的 Google 日曆伺服器的輸出分別寫在 `e2e-logs/mongo.log`、`e2e-logs/backend.log`、`e2e-logs/frontend.log`、`e2e-logs/google.log`（每次啟動時覆寫，不進版控）。
    1. `npm run test:e2e` 平常只顯示測試進度與結果。
    2. 某個伺服器的指令以非 0 結束碼結束時（例如啟動失敗），終端機會印出它的 log；UI 模式顯示在 UI 的 Output 面板。
    3. 伺服器起不來時去看 `e2e-logs/`。啟動逾時時不會印出 log，也是看這個資料夾。
    4. 沿用已開著的伺服器時，log 是那些伺服器啟動時寫的。
  - E2E 的資料庫是 `auto_scheduling_e2e`，setup 執行時清空；沒有 `E2E_CLERK_TEST_EMAIL` 時整個 setup 跳過，資料庫不清空；後端的 `REDIS_URL` 一律不設定，用記憶體；setup 會在測試使用者底下放一筆假的 Google 日曆連線資料，後端的 `GOOGLE_API_BASE_URL` 指向假的 Google 伺服器。
  - **在 WSL1 沒有驗證過**；Linux、macOS、WSL2 可以。
  - 沒有 Clerk 金鑰時，不啟動任何伺服器，整個 E2E 只有一個標示跳過的測試，結束碼 0。
  - 訪客未登入的情境只需要 Clerk 金鑰。登入後的情境需要一個真的 Clerk 測試使用者，用環境變數提供它的 **email**（不需要密碼，測試會請 Clerk 發一次性的登入 ticket）：

    ```env
    E2E_CLERK_TEST_EMAIL=
    ```

    這個使用者必須存在於上面那組 Clerk 金鑰所屬的專案裡。沒有設定時，登入與登入後的測試會自動跳過（不會讓整個測試失敗）。CI 上這個變數和 Clerk 金鑰都存在 GitHub repo 的 Actions secrets 裡。
  - 登入狀態存在 `.auth-e2e/storageState.json`（不進版控）。
  - 本機測試失敗時，`test-results/<測試名稱>/` 會留下截圖（`.png`）、錄影（`.webm`）與 `trace.zip`，通過的測試不留。
    1. UI 模式一律錄 trace。
    2. trace 裡有瀏覽器的 Console、Network 請求與每一步的畫面。
    3. 用 `npx playwright show-trace test-results/<測試名稱>/trace.zip` 打開 trace。
  - CI 不產生 trace、截圖、影片與報告，也不印伺服器的輸出（MongoDB 用 `docker run --log-driver none` 啟動）：repo 與 CI log 都是公開的。
  - 機密只放在 GitHub secrets 與 `.env`。`tests/e2e/` 的程式自己印出的內容只有 `createDiagnosticLogger` 清理過的登入診斷。

## 專案結構說明

```text
.
├── app.vue                     # 全域 App 組件（只有 <UApp><NuxtPage /></UApp>；頁面版面在 pages/index.vue）
├── app.config.ts               # Nuxt UI 的語意色（primary、error 等）對應到哪一組色階
├── assets/css/tailwind.css     # 全站配色：色階定義、白底與框線顏色（固定淺色，沒有深色模式）
├── components/                 # 依功能分組；跨頁面共用的直接放這層（LoginRequiredCard：未登入時的提示卡片；NoticeBox：尚未連結等提醒；CardTitle：卡片標題；PriorityBadge、SourceBadge、TaskStatus：任務的優先級、來源、完成狀態標籤）
│   ├── header/                 # 頂部列（AppHeader）：首頁、任務管理、排程、分析 4 個連結，歡迎訊息、帳號設定（AccountSettings）
│   ├── dashboard/              # 首頁專用：版面配置（Dashboard）、今日卡片、Google 行事曆、Hacker News、LeetCode 每日一題
│   ├── tasks/                  # 任務列表與立即同步（TaskForm）、新增/編輯/刪除視窗（TaskEditModal，掛在首頁 Dashboard 與任務管理頁）、排程建議（ScheduleSuggestion，排程精靈的第 3 步）
│   └── platforms/              # GithubIssuesList / JiraIssuesList / MoodleAssignmentsList，以及共用的 StaleDataBanner（「這是舊資料」提示）
├── composables/                 # 每個資料來源的「前端 CRUD 層」，封裝抓資料/錯誤處理
│   ├── usePlatformItems.ts     # GitHub/Jira/Moodle 共用（對應後端 platforms/）
│   ├── useGoogleCalendar.ts / useGoogleCalendarAuth.ts / useGoogleOAuthCallback.ts
│   ├── useSchedule.ts / useScheduleWizard.ts / useSchedulableTasks.ts
│   ├── useLinkedAccount.ts / useUserSync.ts
│   └── useTaskForm.ts
├── utils/
│   ├── errorMessages.ts        # 統一判斷要顯示什麼錯誤 toast（含限流訊息）
│   └── time.ts                 # 相對時間格式化
├── types/                      # 跟後端 schema 對齊的 TypeScript type（手動維護，非自動生成）
├── pages/
│   ├── index.vue                # 首頁（Header + 主畫面）；/oauth/callback 也用這個頁面，處理 Google 授權導回
│   └── tasks / schedule / productivity / github / jira / moodle.vue  # 各功能的完整頁面；schedule.vue 是 3 步的排程精靈
├── server/
│   ├── api/leetcode.get.ts     # Nuxt server route：取得 LeetCode 每日一題
│   └── tsconfig.json           # Nuxt server 模組的 TypeScript 設定
├── tests/
│   ├── components/ composables/ utils/ pages/ server/  # 單元測試（Vitest + jsdom），資料夾對應原始碼、檔名跟被測的檔案同名
│   ├── __mocks__/               # 模擬 Nuxt 的 auto-import
│   └── e2e/                     # 真實瀏覽器 E2E 測試（Playwright，見上方「測試」）
├── public/                    # 靜態資源（favicon、robots.txt）
├── nuxt.config.ts             # Nuxt 設定檔（包含 module、runtimeConfig 設定）
├── vitest.config.ts           # 單元/元件測試設定
├── playwright.config.ts       # E2E 測試設定（Playwright，伺服器、專案、reporter）
├── eslint.config.mjs          # ESLint 設定
└── tsconfig.json              # TypeScript 設定
```

## 開發慣例

Nuxt 3 會自動引入 `composables/` 跟 `utils/` 裡的東西；元件本專案一律明確 import（`~/components/<分組>/<元件>.vue`），看程式碼就知道元件從哪來。

- **元件**：放進 `components/` 底下對應功能的子資料夾；跨頁面共用的直接放 `components/` 這層。
- **頁面**：在 `pages/` 新增 `.vue` 就會成為路由（`pages/about.vue` → `/about`）。
- **composable**：放 `composables/`，用 `useXxx` 命名，每個專注一件事。本專案每個資料來源各有一個，負責抓資料和錯誤處理，元件只負責畫畫面。

更多用法見 [Nuxt 官方文件](https://nuxt.com/docs)。
