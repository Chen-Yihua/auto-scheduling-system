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

  // CI 的 log 是公開的，伺服器的輸出不印也不存。
  // 本機把輸出導到 e2e-logs/（每次啟動覆寫）；指令以非 0 結束時把 log 印到 stderr，
  // 所以終端機平常只有測試進度，伺服器啟動失敗或中途掛掉時才看得到原因。
  const logDir = resolve(process.cwd(), 'e2e-logs')
  const logFile = (name: string) => `'${logDir}/${name}.log'`
  // 指令放背景、用 trap 接住 SIGTERM 並等指令結束：shell 不先結束，Playwright 才會等 startMongo.mjs 清理完。
  // Playwright 對整個行程群組送 SIGTERM，指令本來就收得到；trap 裡的 kill 是給只對 shell 送訊號的情況
  const toLog = (command: string, name: string) =>
    isCI
      ? command
      : `mkdir -p '${logDir}' && { { ${command}; } > ${logFile(name)} 2>&1 & p=$!; trap 'kill -TERM $p' TERM INT; ` +
        `wait $p; c=$?; while kill -0 $p 2>/dev/null; do wait $p; c=$?; done; ` +
        `if [ $c -ne 0 ]; then cat ${logFile(name)} >&2; fi; exit $c; }`
  const output = isCI ? ({ stdout: 'ignore', stderr: 'ignore' } as const) : ({ stdout: 'ignore', stderr: 'pipe' } as const)

  const webServer: WebServer[] = [
    // CI 的 MongoDB 由 deploy.yml 的步驟用 docker run 啟動，不在這裡啟動
    ...(isCI
      ? []
      : [
          {
            command: toLog(`node tests/e2e/support/startMongo.mjs ${mongoPort}`, 'mongo'),
            port: mongoPort,
            timeout: 180_000,
            // 預設結束時送 SIGKILL，startMongo.mjs 的 SIGTERM 處理器不會執行，記憶體資料庫與暫存資料夾不會清掉
            gracefulShutdown: { signal: 'SIGTERM', timeout: 10_000 } as const,
            ...output,
          },
        ]),
    {
      command: toLog(`${python} -m uvicorn main:app --host 127.0.0.1 --port ${backendPort}`, 'backend'),
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
      command: toLog('npx nuxt build && node .output-e2e/server/index.mjs', 'frontend'),
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

  // 本機沿用已開著的 E2E 伺服器（npm run test:e2e:ui 開著時）；CI 每次都是新的環境，不沿用
  for (const server of webServer) server.reuseExistingServer = !isCI

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
      screenshot: isCI ? 'off' : 'only-on-failure',
      video: isCI ? 'off' : 'retain-on-failure',
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
