// npm run e2e:serve：用 playwright.config.ts 同一份 webServer 啟動 E2E 的三個伺服器並保持開著，Ctrl+C 時由 Playwright 關掉。
// 不另外寫一份伺服器設定：只放一個永遠不結束的測試，讓 Playwright 啟動並維持 webServer
import { defineConfig } from '@playwright/test'
import config from './playwright.config'

export default defineConfig({
  ...config,
  projects: [{ name: 'serve', testMatch: /keepAlive\.ts$/ }],
  timeout: 0,
  reporter: [['dot']],
})
