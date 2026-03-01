# Auto-Scheduling Frontend

Frontend application for the Auto-Scheduling System, built with **Nuxt 3 + TypeScript**.  
This application provides the user interface for task scheduling, account linking, and third-party integrations.

The frontend communicates with a FastAPI backend and supports OAuth-based integrations (GitHub, Jira, Moodle, Google Calendar).

---

## Tech Stack

- Nuxt 3
- Vue 3 (Composition API)
- TypeScript
- Tailwind CSS
- Vitest (Unit Testing)
- Playwright (E2E Testing)

---

## Installation
```bash
npm install
npm run dev
```

---

## Project Structure

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
