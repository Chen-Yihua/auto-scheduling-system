# Auto-Scheduling Frontend

這是使用 Nuxt 3 開發的前端專案，負責處理排程系統的使用者介面（UI），結合 Tailwind CSS、Nuxt UI，登入交給 Clerk 處理，CI/CD 用 GitHub Actions（見 repo 根目錄的 `.github/workflows/deploy.yml`），測試通過才會部署到 Vercel。

## 功能

- 手動任務管理（新增/編輯/刪除，優先度跟時長沒填時由後端 AI 推斷）
- GitHub / Jira / Moodle 資料整合，含「資料是不是舊的（stale）」提示
- Google Calendar 嵌入顯示 + 可用時段/排程建議
- 帳號連結管理（GitHub/Jira/Moodle 金鑰的新增、編輯、刪除）
- 未登入時不會對需要授權的 API 發送請求，改顯示登入提示

---

## 安裝方式

```bash
# 安裝依賴套件
npm install

# 啟動開發伺服器（預設為 http://localhost:3000）
npm run dev
```

## 專案結構說明

```text
.
├── app.vue                     # 全域 App 組件（包含 Header 等 Layout）
├── assets/css/tailwind.css     # 自定義 Tailwind CSS 設定
├── components/
│   ├── TheHeader/              # 頂部導覽、帳號設定（Clerk UserButton）
│   └── TheMain/                # 主畫面，依資料來源拆成子元件
│       ├── TaskForm.vue              # 任務管理（新增/編輯/刪除）
│       ├── GithubIssuesList.vue
│       ├── JiraIssuesList.vue
│       ├── MoodleAssignments.vue
│       ├── GoogleCalendarEmbed.vue
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
│   ├── index.vue                # 首頁（登入後顯示的主畫面）
│   └── oauth/callback.vue       # Google OAuth 導回頁
├── tests/
│   ├── components/ utils/       # 元件與 composable 的單元測試（Vitest + jsdom）
│   └── e2e/                     # 真實瀏覽器 E2E 測試（Playwright，見下方「測試」）
├── public/                    # 靜態資源（favicon、robots.txt）
├── nuxt.config.ts             # Nuxt 設定檔（包含 module、plugin 設定）
├── vitest.config.ts           # 單元/元件測試設定
├── vitest.e2e.config.ts       # E2E 測試設定（獨立於上面那個，環境不同）
├── eslint.config.mjs          # ESLint 設定
├── tsconfig.json              # TypeScript 設定
└── server/tsconfig.json       # Nuxt server 模組的 TypeScript 設定
```

## 如何新增元件（Components）

### 新增共用元件（建議放在 `/components/`）

```bash
components/
└── MyComponent.vue
```

```vue
<!-- 使用方式 -->
<MyComponent />
```

### 若元件屬於某區塊（例如 Header），可放在子資料夾

```bash
components/
└── TheHeader/
    └── components/
        └── UserAvatar.vue
```

## 如何新增頁面（Pages）

Nuxt 使用 **自動路由**，只要在 `/pages` 資料夾新增 `.vue` 檔案，即可成為一個路由：

```bash
pages/
└── about.vue   → http://localhost:3000/about
```

## 如何新增 composables（自訂邏輯函式）

Nuxt 3 支援自動引入 `composables/` 內的函式，不需要手動 import，非常適合封裝可重用邏輯（類似 Vue 的 hooks 概念）。

---

### 新增一個 composable

```bash
composables/
└── useCounter.ts
```

```ts
// composables/useCounter.ts

export function useCounter() {
  const count = ref(0);
  const increment = () => count.value++;

  return {
    count,
    increment,
  };
}
```

---

### 使用方式（不需手動 import）

```vue
<script setup lang="ts">
const { count, increment } = useCounter();
</script>

<template>
  <button @click="increment">Count: {{ count }}</button>
</template>
```

---

### 命名建議

- 使用 `useXXX` 命名格式（例如 `useUser`、`useSchedule`、`useModal`）
- 每個 composable 專注在一個功能，便於重用與維護

## 測試

```bash
npm run test        # 單元/元件測試（Vitest + jsdom），CI 上跑這個
npm run test:e2e     # 真實瀏覽器 E2E 測試（Playwright），CI 上獨立一個 job 跑
npm run coverage     # 單元測試 + 覆蓋率報表
```

兩種測試環境不一樣，分開設定檔（`vitest.config.ts` / `vitest.e2e.config.ts`），不能混著跑：

- **單元/元件測試**（`tests/components/`、`tests/utils/`）：jsdom 環境，Nuxt 的 auto-import（`useAuth`、`useToast` 等）用 `vi.stubGlobal` 手動模擬，不會真的打 API 或開瀏覽器。
- **E2E 測試**（`tests/e2e/*.e2e.ts`）：用 `@nuxt/test-utils/e2e` 真的 build + 啟動一次 Nuxt app，再用 Playwright 開一個真的 headless 瀏覽器操作頁面。訪客未登入的情境不需要任何額外設定；登入後的情境需要一組真的 Clerk 測試帳密，透過環境變數提供：

  ```env
  E2E_CLERK_TEST_EMAIL=
  E2E_CLERK_TEST_PASSWORD=
  ```

  沒有設定這兩個變數時，登入後的測試會自動跳過（不會讓整個測試失敗），本機開發或是沒有這組帳密的情況下不受影響。CI 上這兩個變數存在 GitHub repo 的 Actions secrets 裡。
