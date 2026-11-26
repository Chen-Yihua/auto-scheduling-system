// setup project：清空 E2E 資料庫、登入一次、存下登入狀態給登入後的測試用，並建立測試使用者的 users 文件。
// 登入後的測試自己不登入，所以登入重試與診斷只在這裡。
import { mkdirSync } from 'node:fs'
import { dirname } from 'node:path'
import { test as setup, expect, type Page } from '@playwright/test'
import { clerkSetup, clerk } from '@clerk/testing/playwright'
import { MongoClient } from 'mongodb'
import { E2E_DB_NAME, STORAGE_STATE_PATH, e2eEndpoints } from './support/e2eEnv'
import { e2eSecrets } from './support/e2eSecrets'
import { readDatabaseState, resetDatabase } from './support/resetDatabase'
import {
  attachSignInDiagnostics,
  createDiagnosticLogger,
  createSignInDiagnostics,
  readClerkVersion,
  sanitizeForLog,
  signInWithRetry,
  toSafeNavigationUrl,
  type SignInDiagnostics,
} from './support/signInWithRetry'

// 需要 Clerk 測試環境的使用者（E2E_CLERK_TEST_EMAIL）；沒設定時（本機沒填、fork 的 PR）整個 setup 與登入後的測試跳過。
// 用 sign-in ticket 而不是密碼：密碼模式遇到額外驗證時會悄悄失敗，ticket 模式會直接報錯。
setup.skip(!process.env.E2E_CLERK_TEST_EMAIL, '沒有 E2E_CLERK_TEST_EMAIL，跳過登入')

const secrets = e2eSecrets(process.env)
const logger = createDiagnosticLogger({ secrets })
const { backendUrl, mongoUri } = e2eEndpoints(process.env)

// 金鑰設定錯誤時 Clerk 只會報 infinite redirect loop，所以先檢查並指出是哪個 secret 有問題
function assertClerkKeysLookRight(publishableKey?: string, secretKey?: string) {
  if (!publishableKey) {
    throw new Error('沒有設定 NUXT_PUBLIC_CLERK_PUBLISHABLE_KEY（檢查 GitHub secrets 的名稱和值）')
  }
  if (!secretKey) {
    throw new Error('沒有設定 NUXT_CLERK_SECRET_KEY（檢查 GitHub secrets 的名稱和值）')
  }
  const pkEnv = publishableKey.startsWith('pk_live_') ? 'live' : 'test'
  const skEnv = secretKey.startsWith('sk_live_') ? 'live' : 'test'
  if (pkEnv !== skEnv) {
    throw new Error(`Clerk 金鑰環境不一致：公開金鑰是 ${pkEnv}，私密金鑰是 ${skEnv}，請換成同一個環境的一對`)
  }
  if (pkEnv === 'live') {
    throw new Error('E2E 不能用正式環境（pk_live/sk_live）的金鑰：正式環境只能在設定過的網域運作，在 CI 的 localhost 會一直重導向')
  }
  // 公開金鑰的內容就是這個 Clerk 專案的網域（公開資訊，不是機密），印出來方便跟 dashboard 對照
  const domain = Buffer.from(publishableKey.split('_')[2] ?? '', 'base64').toString().replace(/\$$/, '')
  logger.info(`[e2e] 使用的 Clerk 專案：${domain}`)
}

// 除錯用；只印 cookie 名稱和網址路徑，避免 token 出現在公開的 CI log
async function printPostSignInDiagnostics(page: Page, redirects: string[], diagnostics: SignInDiagnostics) {
  type ClerkInBrowser = { loaded?: boolean; user?: unknown; session?: unknown }
  const clerkState = await page
    .evaluate(() => {
      const clerk = (window as unknown as { Clerk?: ClerkInBrowser }).Clerk
      return {
        path: location.pathname,
        clerkLoaded: !!clerk?.loaded,
        hasUser: !!clerk?.user,
        hasClerkSid: !!clerk?.session,
      }
    })
    .catch((error: unknown) => ({ error: sanitizeForLog(String(error), secrets) }))
  const browserStorageNames = (await page.context().cookies()).map((cookie) => cookie.name).sort()
  const todayCardCount = await page.getByText('今日', { exact: true }).count()
  logger.error(
    '[e2e] 登入後診斷：' + JSON.stringify({ clerkState, todayCardCount, browserStorageNames, redirects }, null, 2),
  )
  diagnostics.setClerkVersion(await readClerkVersion(page))
  logger.error(diagnostics.format('登入後等待逾時'))
}

setup('清空資料庫、登入並建立測試使用者', async ({ page, request }) => {
  const publishableKey = process.env.NUXT_PUBLIC_CLERK_PUBLISHABLE_KEY
  const secretKey = process.env.NUXT_CLERK_SECRET_KEY
  assertClerkKeysLookRight(publishableKey, secretKey)

  await setup.step('清空 E2E 資料庫，保留索引', async () => {
    const mongo = new MongoClient(mongoUri)
    try {
      const db = mongo.db(E2E_DB_NAME)
      const before = await readDatabaseState(db)
      await resetDatabase(db)
      const after = await readDatabaseState(db)
      for (const [name, state] of Object.entries(after)) {
        expect(state.documents, `${name} 的文件數`).toBe(0)
        expect(state.indexes, `${name} 的索引`).toEqual(before[name]?.indexes)
      }
      expect(Object.keys(after)).toEqual(Object.keys(before))
    } finally {
      await mongo.close()
    }
  })

  await clerkSetup({ publishableKey, secretKey })
  // clerk.signIn 的 email 模式固定讀 CLERK_SECRET_KEY 這個環境變數名稱
  process.env.CLERK_SECRET_KEY = secretKey

  const emailAddress = process.env.E2E_CLERK_TEST_EMAIL!
  const diagnostics = createSignInDiagnostics({ secrets })
  attachSignInDiagnostics(page, diagnostics)
  // clerk.signIn 要求先 goto 過一個會載入 Clerk 的頁面，才能繼續
  await page.goto('/')
  await clerk.loaded({ page })
  await signInWithRetry({
    signIn: () => clerk.signIn({ page, emailAddress }),
    waitForReady: async () => {
      await page.waitForLoadState('load')
      await clerk.loaded({ page })
    },
    isSignedIn: () => page.evaluate(() => !!(window as unknown as { Clerk?: { user?: unknown } }).Clerk?.user),
    onError: async (error) => {
      diagnostics.setClerkVersion(await readClerkVersion(page))
      logger.error(diagnostics.format('登入錯誤：' + (error instanceof Error ? error.message : String(error))))
    },
    log: (line) => logger.warn(line),
    secrets,
  })

  const redirects: string[] = []
  page.on('response', (response) => {
    if (response.status() >= 300 && response.status() < 400 && redirects.length < 30) {
      redirects.push(`${response.status()} ${toSafeNavigationUrl(response.url())}`)
    }
  })

  await page.goto('/')
  try {
    // 今日卡片的標題出現、而且訪客的登入提示消失，才代表登入完成
    await page.waitForFunction(
      () => document.body.textContent?.includes('今日') && !document.body.textContent.includes('登入後即可查看'),
      undefined,
      { timeout: 30_000 },
    )
  } catch (error) {
    await printPostSignInDiagnostics(page, redirects, diagnostics)
    throw error
  }

  mkdirSync(dirname(STORAGE_STATE_PATH), { recursive: true })
  await page.context().storageState({ path: STORAGE_STATE_PATH })

  await setup.step('建立測試使用者的 users 文件', async () => {
    type ClerkInBrowser = {
      user?: { id: string; fullName: string | null; primaryEmailAddress?: { emailAddress: string } | null }
      session?: { getToken(): Promise<string | null> }
    }
    const identity = await page.evaluate(async () => {
      const clerk = (window as unknown as { Clerk?: ClerkInBrowser }).Clerk
      return {
        token: await clerk?.session?.getToken(),
        clerk_id: clerk?.user?.id,
        email: clerk?.user?.primaryEmailAddress?.emailAddress,
        name: clerk?.user?.fullName,
      }
    })
    const { token, ...body } = identity
    const headers = { Authorization: `Bearer ${token}` }

    // 標題列的 ensureUserRecord 可能已經建好，所以 201 與 409 都算建立成功
    const created = await request.post(`${backendUrl}/users/`, { headers, data: body })
    expect([201, 409], 'POST /users/ 的狀態碼').toContain(created.status())
    const me = await request.get(`${backendUrl}/users/me`, { headers })
    expect(me.status(), 'GET /users/me 的狀態碼').toBe(200)
  })
})
