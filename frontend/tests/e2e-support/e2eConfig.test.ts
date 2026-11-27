// Playwright 設定在 CI 與本機、有無 Clerk 金鑰時的差異
import { spawnSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, it, expect } from 'vitest'
import { buildConfig, NO_CLERK_KEYS_TITLE } from '../e2e/support/e2eConfig'

// pk_test_ 後面是 base64 的 "example.clerk.accounts.dev$"
const KEYS = { NUXT_PUBLIC_CLERK_PUBLISHABLE_KEY: 'pk_test_ZXhhbXBsZS5jbGVyay5hY2NvdW50cy5kZXYk', NUXT_CLERK_SECRET_KEY: 'sk_test_x' }

describe('buildConfig：CI 與本機', () => {
  it('e2e-playwright AC16：GITHUB_ACTIONS=true 時，每個 webServer 的 stdout、stderr 都是 ignore', () => {
    const config = buildConfig({ ...KEYS, GITHUB_ACTIONS: 'true' })

    const servers = config.webServer as { stdout?: string; stderr?: string }[]
    expect(servers.length).toBeGreaterThan(0)
    for (const server of servers) {
      expect(server.stdout).toBe('ignore')
      expect(server.stderr).toBe('ignore')
    }
  })

  it('e2e-playwright AC17：GITHUB_ACTIONS=true 時，trace、截圖、影片都是 off', () => {
    const { use } = buildConfig({ ...KEYS, GITHUB_ACTIONS: 'true' })

    expect([use?.trace, use?.screenshot, use?.video]).toEqual(['off', 'off', 'off'])
  })

  it('e2e-playwright AC17：CI 的 workflow 沒有上傳任何 artifact', () => {
    const workflow = readFileSync(resolve(process.cwd(), '../.github/workflows/deploy.yml'), 'utf-8')

    expect(workflow).not.toContain('upload-artifact')
  })

  it('e2e-playwright 完成前檢查 2：GITHUB_ACTIONS=true 時 reporter 只有 list 與 github', () => {
    expect(buildConfig({ ...KEYS, GITHUB_ACTIONS: 'true' }).reporter).toEqual([['list'], ['github']])
  })

  it('e2e-playwright AC8：CI 不啟動 MongoDB（deploy.yml 的步驟啟動），本機啟動且排在後端之前', () => {
    const commands = (env: Record<string, string>) =>
      (buildConfig({ ...KEYS, ...env }).webServer as { command: string }[]).map((server) => server.command)

    expect(commands({ GITHUB_ACTIONS: 'true' }).some((command) => command.includes('startMongo'))).toBe(false)
    const local = commands({})
    expect(local[0]).toContain('startMongo')
    expect(local[1]).toContain('uvicorn')
  })

  it('e2e-local-run AC1：本機失敗時留下截圖、錄影、trace，通過的不留', () => {
    const { use } = buildConfig(KEYS)

    expect([use?.trace, use?.screenshot, use?.video]).toEqual(['retain-on-failure', 'only-on-failure', 'retain-on-failure'])
  })

  it('e2e-local-run AC3：本機三個伺服器的指令都用 > 覆寫導到 e2e-logs/<名稱>.log，不是 >>', () => {
    const servers = buildConfig(KEYS).webServer as { command: string }[]
    const find = (text: string) => servers.find((server) => server.command.includes(text))!

    for (const [text, name] of [['startMongo', 'mongo'], ['uvicorn', 'backend'], ['nuxt build', 'frontend']] as const) {
      const command = find(text).command
      expect(command).toMatch(new RegExp(`[^>]> '[^']*e2e-logs/${name}\\.log' 2>&1`))
      expect(command).not.toContain('>>')
    }
  })

  it('e2e-local-run AC3、AC4：本機 stdout 是 ignore、stderr 是 pipe（指令失敗時才有內容）；CI 的指令不導向任何檔案', () => {
    for (const server of buildConfig(KEYS).webServer as { stdout?: string; stderr?: string }[]) {
      expect([server.stdout, server.stderr]).toEqual(['ignore', 'pipe'])
    }
    for (const server of buildConfig({ ...KEYS, GITHUB_ACTIONS: 'true' }).webServer as { command: string }[]) {
      expect(server.command).not.toContain('e2e-logs')
    }
  })

  it('e2e-local-run AC5：指令以非 0 結束時，stderr 印出 log 內容並保留原本的結束碼；成功時什麼都不印', () => {
    const backend = (env: Record<string, string>) =>
      (buildConfig({ ...KEYS, ...env }).webServer as { command: string; cwd?: string }[]).find((server) => server.command.includes('uvicorn'))!
    const run = (command: string) => spawnSync('sh', ['-c', command], { encoding: 'utf-8' })

    const failed = run(backend({ E2E_PYTHON: '/nonexistent-python' }).command)
    expect(failed.status).toBe(127)
    expect(failed.stderr).toContain('/nonexistent-python')

    const ok = run(backend({ E2E_PYTHON: 'true' }).command)
    expect([ok.status, ok.stdout, ok.stderr]).toEqual([0, '', ''])
  })

  it('e2e-local-run AC9：收到 SIGTERM 時，指令等內部的程式結束後才結束', () => {
    const { command } = (buildConfig(KEYS).webServer as { command: string }[]).find((server) => server.command.includes('startMongo'))!
    // 用會慢慢收尾的程式取代 startMongo：收到 SIGTERM 後等 1 秒才結束
    const slow = command.replace(/node tests\/e2e\/support\/startMongo\.mjs \d+/, `sh -c "trap 'sleep 1; exit 0' TERM; sleep 30 & wait"`)
    const started = Date.now()
    const result = spawnSync('sh', ['-c', `${slow} & p=$!; sleep 1; kill -TERM $p; wait $p`], { encoding: 'utf-8' })

    expect(result.status).toBe(0)
    expect(Date.now() - started).toBeGreaterThanOrEqual(1900)
  })

  it('e2e-local-run AC13：本機沿用已開著的伺服器，CI 不沿用', () => {
    const reuse = (env: Record<string, string>) =>
      (buildConfig({ ...KEYS, ...env }).webServer as { reuseExistingServer?: boolean }[]).map((server) => server.reuseExistingServer)

    expect(reuse({})).toEqual([true, true, true])
    expect(reuse({ GITHUB_ACTIONS: 'true' })).toEqual([false, false])
  })

  it('e2e-local-run AC14：frontend-e2e-test 不用 service container，改用 docker run --log-driver none 啟動 MongoDB', () => {
    const workflow = readFileSync(resolve(process.cwd(), '../.github/workflows/deploy.yml'), 'utf-8')
    const job = workflow.slice(workflow.indexOf('  frontend-e2e-test:'), workflow.indexOf('  deploy-backend:'))

    expect(job).not.toMatch(/^\s+services:/m)
    expect(job).toContain('docker run -d --log-driver none -p 27018:27017 mongo:7')
  })

  it('e2e-playwright AC18：本機 trace 只在失敗時保留，HTML 報告不開伺服器等待', () => {
    const config = buildConfig(KEYS)

    expect(config.use?.trace).toBe('retain-on-failure')
    expect(config.reporter).toContainEqual(['html', { open: 'never' }])
  })
})

describe('buildConfig：E2E 的環境', () => {
  it('e2e-playwright AC8、AC10：伺服器不用開發環境的 port，後端只連 auto_scheduling_e2e、不連 Redis', () => {
    const servers = buildConfig(KEYS).webServer as { command: string; port?: number; url?: string; env?: Record<string, string> }[]
    const backend = servers.find((server) => server.command.includes('uvicorn'))!
    const frontend = servers.find((server) => server.command.includes('nuxt build'))!

    expect(backend.url).toBe('http://127.0.0.1:8001/docs')
    expect(frontend.url).toBe('http://127.0.0.1:3100')
    expect(servers.find((server) => server.command.includes('startMongo'))?.port).toBe(27018)
    expect(backend.env).toMatchObject({
      MONGO_URI: 'mongodb://127.0.0.1:27018',
      MONGO_DB: 'auto_scheduling_e2e',
      REDIS_URL: '',
      CLERK_ISSUER: 'https://example.clerk.accounts.dev',
      CLERK_JWKS_URL: 'https://example.clerk.accounts.dev/.well-known/jwks.json',
      CORS_ALLOWED_ORIGINS: 'http://127.0.0.1:3100',
    })
    expect(frontend.env).toMatchObject({ NUXT_E2E: '1', NUXT_PUBLIC_API_BASE_URL: 'http://127.0.0.1:8001' })
  })

  it('e2e-playwright AC3：登入後的專案依賴 setup，使用存下的登入狀態；訪客專案不依賴', () => {
    const projects = buildConfig(KEYS).projects!
    const byName = Object.fromEntries(projects.map((project) => [project.name, project]))

    expect(byName['signed-in']!.dependencies).toEqual(['setup'])
    expect(byName['signed-in']!.use?.storageState).toBe('.auth-e2e/storageState.json')
    expect(byName.guest!.dependencies).toBeUndefined()
  })
})

describe('buildConfig：沒有 Clerk 金鑰', () => {
  it.each([
    ['沒有公開金鑰', { NUXT_CLERK_SECRET_KEY: 'sk_test_x' }],
    ['沒有私密金鑰', { NUXT_PUBLIC_CLERK_PUBLISHABLE_KEY: KEYS.NUXT_PUBLIC_CLERK_PUBLISHABLE_KEY }],
    ['金鑰是空字串', { NUXT_PUBLIC_CLERK_PUBLISHABLE_KEY: '', NUXT_CLERK_SECRET_KEY: '' }],
  ])('e2e-playwright AC6、e2e-local-run AC10：%s → 不啟動任何伺服器，只收集標示跳過的那個測試', (_name, env) => {
    const config = buildConfig(env)

    expect(config.webServer).toBeUndefined()
    expect(config.projects).toHaveLength(1)
    const testMatch = config.projects![0]!.testMatch as RegExp
    expect(testMatch.test('noClerkKeys.ts')).toBe(true)
    expect(testMatch.test('dashboard.guest.spec.ts')).toBe(false)
    expect(testMatch.test('auth.setup.ts')).toBe(false)
    expect(NO_CLERK_KEYS_TITLE).toBe('沒有 Clerk 金鑰，跳過 E2E')
  })
})
