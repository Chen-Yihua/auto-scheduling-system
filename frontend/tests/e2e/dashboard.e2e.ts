// 啟動 Nuxt server 並用 headless 瀏覽器操作，用 npm run test:e2e 執行
import { fileURLToPath } from 'node:url'
import { describe, it, expect } from 'vitest'
import { setup, createPage, url } from '@nuxt/test-utils/e2e'
import { clerkSetup, clerk } from '@clerk/testing/playwright'
import type { Page } from 'playwright-core'

await setup({
  rootDir: fileURLToPath(new URL('../..', import.meta.url)),
  browser: true,
})

// 需要 Clerk 測試環境的使用者（E2E_CLERK_TEST_EMAIL）；沒設定時（本機、fork 的 PR）跳過。
// 用 sign-in ticket 而不是密碼：密碼模式遇到額外驗證時會悄悄失敗，ticket 模式會直接報錯。
const hasClerkTestUser = !!process.env.E2E_CLERK_TEST_EMAIL

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
  console.info(`[e2e] 使用的 Clerk 專案：${domain}`)
}

// 除錯用；只印 cookie 名稱和網址路徑，避免 token 出現在公開的 CI log
async function printPostSignInDiagnostics(page: Page, redirects: string[]) {
  type ClerkInBrowser = { loaded?: boolean; user?: unknown; session?: unknown }
  const clerkState = await page
    .evaluate(() => {
      const clerk = (window as unknown as { Clerk?: ClerkInBrowser }).Clerk
      return {
        path: location.pathname,
        clerkLoaded: !!clerk?.loaded,
        hasUser: !!clerk?.user,
        hasSession: !!clerk?.session,
      }
    })
    .catch((error: unknown) => ({ error: String(error) }))
  const cookieNames = (await page.context().cookies()).map((cookie) => cookie.name).sort()
  const addTaskButtonCount = await page.getByRole('button', { name: '新增任務' }).count()
  console.error(
    '[e2e] 登入後診斷：' + JSON.stringify({ clerkState, addTaskButtonCount, cookieNames, redirects }, null, 2),
  )
}

describe('Dashboard（真實瀏覽器 E2E）', () => {
  it('訪客未登入時，版面跟登入後一樣，需要登入的區塊只顯示提示、新增任務按鈕不能按', async () => {
    const page = await createPage('/')
    await page.waitForSelector('text=登入後即可查看與新增你的任務')

    const bodyText = await page.textContent('body')
    expect(bodyText).toContain('登入後即可查看 Google 行事曆')
    // 訪客也看得到「新增任務」按鈕，但是 disabled
    expect(await page.locator('button[aria-label="新增任務"][disabled]').count()).toBe(1)

    await page.close()
  })

  it.skipIf(!hasClerkTestUser)(
    '用真的 Clerk 測試帳號登入後，看得到主畫面、不再顯示登入提示',
    async () => {
      const publishableKey = process.env.NUXT_PUBLIC_CLERK_PUBLISHABLE_KEY
      const secretKey = process.env.NUXT_CLERK_SECRET_KEY
      assertClerkKeysLookRight(publishableKey, secretKey)

      await clerkSetup({ publishableKey, secretKey })
      // clerk.signIn 的 email 模式固定讀 CLERK_SECRET_KEY 這個環境變數名稱
      process.env.CLERK_SECRET_KEY = secretKey

      const page = await createPage('/')
      // clerk.signIn 要求先 goto 過一個會載入 Clerk 的頁面，才能繼續
      await clerk.signIn({ page, emailAddress: process.env.E2E_CLERK_TEST_EMAIL! })

      const redirects: string[] = []
      page.on('response', (response) => {
        if (response.status() >= 300 && response.status() < 400 && redirects.length < 30) {
          const target = new URL(response.url())
          redirects.push(`${response.status()} ${target.host}${target.pathname}`)
        }
      })

      await page.goto(url('/'))
      try {
        // 用 aria-label 找：icon 是元件 prop，不會出現在 HTML 屬性上
        // 按鈕變成可按才代表登入完成
        await page.waitForSelector('button[aria-label="新增任務"]:not([disabled])', { timeout: 30_000 })
      } catch (error) {
        await printPostSignInDiagnostics(page, redirects)
        throw error
      }

      const bodyText = await page.textContent('body')
      expect(bodyText).not.toContain('登入後即可查看')

      await page.close()
    },
  )
})
