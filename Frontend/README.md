# 🧠 Auto-Scheduling Frontend

這是使用 Nuxt 3 開發的前端專案，負責處理排程系統的使用者介面（UI），結合 Tailwind CSS、Nuxt UI，並預計整合 Clerk 登入與 GitLab CI/CD。

---

## 📦 安裝方式

```bash
# 安裝依賴套件
npm install

# 啟動開發伺服器（預設為 http://localhost:3000）
npm run dev
```

## 📁 專案結構說明

```text
.
├── app.vue                     # 全域 App 組件（包含 Header 等 Layout）
├── assets/css/tailwind.css     # 自定義 Tailwind CSS 設定
├── components/                 # 可重用元件
│   └── TheHeader/              # Header 元件資料夾
│       ├── components/
│       │   └── ColorModeButton.vue   # 切換亮暗色模式按鈕
│       └── index.vue                # Header 主組件
├── pages/
│   └── index.vue              # 首頁路由
├── public/                    # 靜態資源（favicon、robots.txt）
├── nuxt.config.ts             # Nuxt 設定檔（包含 module、plugin 設定）
├── eslint.config.mjs          # ESLint 設定
├── tsconfig.json              # TypeScript 設定
└── server/tsconfig.json       # Nuxt server 模組的 TypeScript 設定
```

## 🧱 如何新增元件（Components）

### ✅ 新增共用元件（建議放在 `/components/`）

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

## 📄 如何新增頁面（Pages）

Nuxt 使用 **自動路由**，只要在 `/pages` 資料夾新增 `.vue` 檔案，即可成為一個路由：

```bash
pages/
└── about.vue   → http://localhost:3000/about
```

## 🧪 如何新增 composables（自訂邏輯函式）

Nuxt 3 支援自動引入 `composables/` 內的函式，不需要手動 import，非常適合封裝可重用邏輯（類似 Vue 的 hooks 概念）。

---

### ✅ 新增一個 composable

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

### 🧠 使用方式（不需手動 import）

```vue
<script setup lang="ts">
const { count, increment } = useCounter();
</script>

<template>
  <button @click="increment">Count: {{ count }}</button>
</template>
```

---

### 📌 命名建議

- 使用 `useXXX` 命名格式（例如 `useUser`、`useSchedule`、`useModal`）
- 每個 composable 專注在一個功能，便於重用與維護
