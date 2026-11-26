// Playwright 設定的內容：用環境變數決定要跳過、啟動哪些伺服器、CI 要關掉什麼輸出。
// 放在這裡而不是直接寫在 playwright.config.ts，單元測試才能用不同的環境變數檢查結果。
import { existsSync } from 'node:fs'
import { resolve } from 'node:path'
import { defineConfig, devices, type PlaywrightTestConfig } from '@playwright/test'
import { E2E_DB_NAME, STORAGE_STATE_PATH, e2eEndpoints } from './e2eEnv'

type Env = Record<string, string | undefined>
type WebServer = Extract<NonNullable<PlaywrightTestConfig['webServer']>, { command: string }>

export const NO_CLERK_KEYS_TITLE = '沒有 Clerk 金鑰，跳過 E2E'

// 公開金鑰 pk_test_<base64> 解開是 Clerk 專案的網域，後端的 issuer 與 JWKS 網址都從它來
export function clerkDomain(publishableKey: string): string {
  return Buffer.from(publishableKey.split('_')[2] ?? '', 'base64').toString().replace(/\$$/, '')
}

export function buildConfig(env: Env) {
  const isCI = env.GITHUB_ACTIONS === 'true'
  const publishableKey = env.NUXT_PUBLIC_CLERK_PUBLISHABLE_KEY
  const secretKey = env.NUXT_CLERK_SECRET_KEY

  // 沒有金鑰時前端每個頁面都報錯，所以不啟動伺服器，只留一個標示跳過的測試（Playwright 收集到 0 個測試會失敗）
  if (!publishableKey || !secretKey) {
    return defineConfig({
      testDir: 'tests/e2e',
      projects: [{ name: 'no-clerk-keys', testMatch: /noClerkKeys\.ts$/ }],
      reporter: isCI ? [['list'], ['github']] : [['list']],
    })
  }

  const { frontendPort, backendPort, mongoPort, frontendUrl, backendUrl, mongoUri } = e2eEndpoints(env)
  const domain = clerkDomain(publishableKey)
  // 從 frontend 資料夾執行（npm run test:e2e），repo 根目錄的 .venv 在上一層
  const venvPython = resolve(process.cwd(), '../.venv/bin/python')
  const python = env.E2E_PYTHON ?? (existsSync(venvPython) ? venvPython : 'python')

  // CI 的 log 是公開的，伺服器與子行程的輸出不印；本機照常印
  const output = isCI ? ({ stdout: 'ignore', stderr: 'ignore' } as const) : ({ stdout: 'pipe', stderr: 'pipe' } as const)

  const webServer: WebServer[] = [
    // CI 的 MongoDB 是 service container，不在這裡啟動
    ...(isCI
      ? []
      : [
          {
            command: `node tests/e2e/support/startMongo.mjs ${mongoPort}`,
            port: mongoPort,
            timeout: 180_000,
            ...output,
          },
        ]),
    {
      command: `${python} -m uvicorn main:app --host 127.0.0.1 --port ${backendPort}`,
      cwd: '../backend',
      url: `${backendUrl}/docs`,
      timeout: 120_000,
      ...output,
      // 後端照常載入 backend/.env，但不覆蓋已存在的變數（空字串也算）：下面每個共用的變數都明確給，才不會讀到開發用的值
      env: {
        MONGO_URI: mongoUri,
        MONGO_DB: E2E_DB_NAME,
        REDIS_URL: '',
        CLERK_ISSUER: `https://${domain}`,
        CLERK_JWKS_URL: `https://${domain}/.well-known/jwks.json`,
        GEMINI_API_KEY: 'e2e-fake-gemini-key',
        SECRET_ENCRYPTION_KEY: env.E2E_SECRET_ENCRYPTION_KEY ?? '',
        GOOGLE_CLIENT_ID: 'e2e-fake-google-client-id',
        GOOGLE_CLIENT_SECRET: 'e2e-fake-google-client-secret',
        GOOGLE_REDIRECT_URI: `${frontendUrl}/e2e-fake-google-redirect`,
        CORS_ALLOWED_ORIGINS: frontendUrl,
        DISCORD_MR_WEBHOOK_URL: '',
        DISCORD_MAIN_WEBHOOK_URL: '',
        GITHUB_BOT_TOKEN: '',
      },
    },
    {
      // NUXT_E2E=1 時 build 放在 .nuxt-e2e、.output-e2e，不改寫開發者 npm run dev 在用的 .nuxt（nuxt.config.ts）
      command: 'npx nuxt build && node .output-e2e/server/index.mjs',
      url: frontendUrl,
      timeout: 300_000,
      ...output,
      env: {
        NUXT_E2E: '1',
        NITRO_HOST: '127.0.0.1',
        NITRO_PORT: String(frontendPort),
        NUXT_PUBLIC_API_BASE_URL: backendUrl,
        NUXT_PUBLIC_FRONTEND_URL: frontendUrl,
      },
    },
  ]

  return defineConfig({
    testDir: 'tests/e2e',
    // 共用同一個資料庫與登入狀態，不平行
    workers: 1,
    forbidOnly: isCI,
    timeout: 60_000,
    expect: { timeout: 15_000 },
    reporter: isCI ? [['list'], ['github']] : [['list'], ['html', { open: 'never' }]],
    use: {
      baseURL: frontendUrl,
      trace: isCI ? 'off' : 'retain-on-failure',
      screenshot: 'off',
      video: 'off',
    },
    projects: [
      { name: 'setup', testMatch: /auth\.setup\.ts$/, use: { ...devices['Desktop Chrome'] } },
      { name: 'guest', testMatch: /\.guest\.spec\.ts$/, use: { ...devices['Desktop Chrome'] } },
      {
        name: 'signed-in',
        testMatch: /\.signed-in\.spec\.ts$/,
        dependencies: ['setup'],
        use: { ...devices['Desktop Chrome'], storageState: STORAGE_STATE_PATH },
      },
    ],
    webServer,
  })
}
