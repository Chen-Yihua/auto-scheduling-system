import { defineConfig } from '@playwright/test'

export default defineConfig({
  timeout: 60000,   // 1 分鐘
  use: {
    baseURL: 'http://localhost:3000',  // Nuxt server 跑的位置
    browserName: 'chromium',           // 先用 chromium
    headless: true,                    // CICD 用 headless 模式
    actionTimeout: 30000, // 每個 action 最多 30 秒
    navigationTimeout: 30000, // page.goto 最多 30 秒
    storageState: 'storageState.json',
  },
  testDir: './tests/e2e',              // e2e 測試檔位置
})