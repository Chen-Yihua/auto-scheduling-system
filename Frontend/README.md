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
- 後端要先跑起來，才看得到任務、GitHub / Jira / Moodle 等資料（見 [`../Backend/README.md`](../Backend/README.md)）

## 環境變數

複製 `.env.example` 成 `Frontend/.env`，把值填齊：

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

> ⚠️ **開著 `npm run dev` 的時候，不要跑 `npm run build` 或 `npm run test:e2e`**：它們都會改寫 `.nuxt` 資料夾，開發伺服器會因此壞掉（錯誤訊息像 `Package import specifier "#internal/nuxt/paths" is not defined`）。壞掉時停掉開發伺服器，刪掉 `.nuxt` 和 `.output`，重新 `npm run dev` 即可。

## 測試

```bash
npm run test        # 單元/元件測試（Vitest + jsdom），CI 上跑這個
npm run test:e2e    # 真實瀏覽器 E2E 測試（Playwright），CI 上獨立一個 job 跑
npm run coverage    # 單元測試 + 覆蓋率報表
```

兩種測試環境不一樣，分開設定檔（`vitest.config.ts` / `vitest.e2e.config.ts`），不能混著跑：

- **單元/元件測試**（`tests/components/`、`tests/utils/`、`tests/api/`）：jsdom 環境，Nuxt 的 auto-import（`useAuth`、`useToast` 等）用 `tests/__mocks__/` 和 `vi.stubGlobal` 手動模擬，不會真的打 API 或開瀏覽器。
- **E2E 測試**（`tests/e2e/*.e2e.ts`）：用 `@nuxt/test-utils/e2e` 真的 build + 啟動一次 Nuxt app，再用 Playwright 開一個真的 headless 瀏覽器操作頁面。
  - **需要先安裝瀏覽器**：`npx playwright install chromium chromium-headless-shell`
  - **需要 Clerk 金鑰**（放在 `.env`，見上面「環境變數」），而且要用開發用（`pk_test_` / `sk_test_`）的一對，不能用正式環境的。
  - **在 WSL1 跑不起來**（測試工具用來確認伺服器啟動的埠號偵測，跟 WSL1 不相容）；Linux、macOS、WSL2 可以。
  - 訪客未登入的情境不需要額外設定。登入後的情境需要一個真的 Clerk 測試使用者，用環境變數提供它的 **email**（不需要密碼，測試會請 Clerk 發一次性的登入 ticket）：

    ```env
    E2E_CLERK_TEST_EMAIL=
    ```

    這個使用者必須存在於上面那組 Clerk 金鑰所屬的專案裡。沒有設定時，登入後的測試會自動跳過（不會讓整個測試失敗）。CI 上這個變數和 Clerk 金鑰都存在 GitHub repo 的 Actions secrets 裡。

## 專案結構說明

```text
.
├── app.vue                     # 全域 App 組件（只有 <UApp><NuxtPage /></UApp>；頁面版面在 pages/index.vue）
├── assets/css/tailwind.css     # 自定義 Tailwind CSS 設定
├── components/
│   ├── TheHeader/              # 頂部列：歡迎訊息、深淺色切換、新增任務按鈕、登入按鈕、帳號設定（AccountSettings）
│   └── TheMain/                # 主畫面，依資料來源拆成子元件
│       ├── index.vue                 # 主畫面的版面配置（三欄）
│       ├── TaskForm.vue              # 任務管理（新增/編輯/刪除）
│       ├── GithubIssuesList.vue
│       ├── JiraIssuesList.vue
│       ├── MoodleAssignments.vue
│       ├── GoogleCalendarEmbed.vue
│       ├── News.vue                  # Hacker News 熱門文章（直接呼叫公開 API）
│       ├── Leetcode.vue              # LeetCode 每日一題（走 server/api/leetcode）
│       └── StaleDataBanner.vue       # 共用的「這是舊資料」提示
├── composables/                 # 每個資料來源的「前端 CRUD 層」，封裝抓資料/錯誤處理
│   ├── useGithub.ts / useJira.ts / useMoodleAssignments.ts
│   ├── useGoogleCalendar.ts
│   ├── useLinkedAccount.ts
│   └── useTaskForm.ts
├── utils/
│   ├── errorMessages.ts        # 統一判斷要顯示什麼錯誤 toast（含限流訊息）
│   └── time.ts                 # 相對時間格式化
├── types/                      # 跟後端 schema 對齊的 TypeScript type（手動維護，非自動生成）
├── pages/
│   └── index.vue                # 首頁（Header + 主畫面）；/oauth/callback 也用這個頁面，處理 Google 授權導回
├── server/
│   ├── api/leetcode.get.ts     # Nuxt server route：取得 LeetCode 每日一題
│   └── tsconfig.json           # Nuxt server 模組的 TypeScript 設定
├── tests/
│   ├── components/ utils/ api/  # 元件、composable、server route 的單元測試（Vitest + jsdom）
│   ├── __mocks__/               # 模擬 Nuxt 的 auto-import
│   └── e2e/                     # 真實瀏覽器 E2E 測試（Playwright，見上方「測試」）
├── public/                    # 靜態資源（favicon、robots.txt）
├── nuxt.config.ts             # Nuxt 設定檔（包含 module、runtimeConfig 設定）
├── vitest.config.ts           # 單元/元件測試設定
├── vitest.e2e.config.ts       # E2E 測試設定（獨立於上面那個，環境不同）
├── eslint.config.mjs          # ESLint 設定
└── tsconfig.json              # TypeScript 設定
```

## 開發慣例

Nuxt 3 會自動引入 `components/` 與 `composables/` 裡的東西，不需要手動 import。

- **元件**：放 `components/`；屬於某個區塊的放子資料夾（例如 `TheHeader/components/`）。
- **頁面**：在 `pages/` 新增 `.vue` 就會成為路由（`pages/about.vue` → `/about`）。
- **composable**：放 `composables/`，用 `useXxx` 命名，每個專注一件事。本專案每個資料來源各有一個，負責抓資料和錯誤處理，元件只負責畫畫面。

更多用法見 [Nuxt 官方文件](https://nuxt.com/docs)。
