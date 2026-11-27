// E2E 設定，用 npm run test:e2e 執行；內容在 tests/e2e/support/e2eConfig.ts
import { existsSync } from 'node:fs'
import { buildConfig } from './tests/e2e/support/e2eConfig'

// 不用 dotenv 套件：Node 內建就能載入，而且不覆蓋已存在的環境變數（shell 先 export 的優先）。
// @playwright/test 不像 @nuxt/test-utils 會自動載入 .env
if (existsSync('.env')) process.loadEnvFile('.env')

export default buildConfig(process.env)
