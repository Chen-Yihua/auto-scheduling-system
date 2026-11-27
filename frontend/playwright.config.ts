// E2E 設定，用 npm run test:e2e 執行；內容在 tests/e2e/support/e2eConfig.ts
import { randomBytes } from 'node:crypto'
import { existsSync } from 'node:fs'
import { buildConfig } from './tests/e2e/support/e2eConfig'

// 不用 dotenv 套件：Node 內建就能載入，而且不覆蓋已存在的環境變數（shell 先 export 的優先）。
// @playwright/test 不像 @nuxt/test-utils 會自動載入 .env
if (existsSync('.env')) process.loadEnvFile('.env')

// 每次執行一把新的加密金鑰（Fernet：32 bytes 的 url-safe base64）。worker 會重新載入這個檔案，沿用已有的值才會跟後端一致
process.env.E2E_SECRET_ENCRYPTION_KEY ??= randomBytes(32).toString('base64').replace(/\+/g, '-').replace(/\//g, '_')

export default buildConfig(process.env)
