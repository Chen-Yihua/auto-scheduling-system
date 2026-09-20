// tests/e2e/dashboard.e2e.ts
//
// 真的 E2E 測試：起一個真的 Nuxt server、用真的（headless）瀏覽器去操作，
// 跟 tests/utils|components 底下那些用 jsdom + mock 掉 composable 的測試不是同一類。
// 用 `npm run test:e2e` 單獨跑（見 vitest.e2e.config.ts），不含在預設的
// `npm run test` 裡，因為這裡會真的 build/啟動一次 Nuxt app，比一般測試慢很多。
import { fileURLToPath } from 'node:url'
import { describe, it, expect } from 'vitest'
import { setup, createPage, url } from '@nuxt/test-utils/e2e'
import { clerkSetup, clerk } from '@clerk/testing/playwright'
import type { Page } from 'playwright-core'

await setup({
  rootDir: fileURLToPath(new URL('../..', import.meta.url)),
  browser: true,
})

// 登入後的流程需要一個真的存在於 Clerk 測試環境裡的使用者——只有在維護者的 Clerk
// dashboard 建立測試使用者、並把它的 email 存成 E2E_CLERK_TEST_EMAIL 這個 secret 之後才會有值。
// 本機開發或是 fork 出去的 PR（GitHub Actions 不會把 secrets 帶給 fork 的 PR）
// 沒有這個變數時，跳過這個測試，而不是讓整個 E2E 測試都紅掉。
//
// 用 email 登入（由後端用 secret key 發一張一次性的 sign-in ticket），不走密碼：
// clerk.signIn 的 password 模式不會檢查登入有沒有真的成功，遇到「新裝置驗證」或
// 「二階段驗證」時不會報錯、只是悄悄沒登入，最後只看到 waitForSelector 逾時，
// 完全看不出原因。ticket 模式沒登入成功會直接丟出清楚的錯誤。
const hasClerkTestUser = !!process.env.E2E_CLERK_TEST_EMAIL

// 金鑰設定錯誤（沒設定、公開/私密金鑰環境不同、用了正式金鑰）時，Clerk 只會報一個很籠統的
// 「infinite redirect loop」；這裡先檢查能檢查的部分，直接指出問題出在哪個 secret。
// 「兩把都是 test、但來自不同 Clerk 專案」沒辦法在這裡看出來，那種情況 clerk.signIn 會
// 因為找不到使用者或 ticket 無效而丟出錯誤。
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

// 登入後頁面卡住時，把「能安全印出來」的狀態印到 log，下次失敗才看得出卡在哪一步。
// 只印 cookie 的名稱和網址的路徑，不印 cookie 值和網址參數（裡面會有 token），
// 避免把憑證洩漏到公開的 CI log。
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
  it('訪客未登入時，看到登入提示，不會看到任務/整合服務內容', async () => {
    const page = await createPage('/')
    await page.waitForSelector('text=登入後即可查看你的任務、行事曆與整合服務')

    const bodyText = await page.textContent('body')
    expect(bodyText).toContain('登入後即可查看你的任務、行事曆與整合服務')
    // 訪客不該看到「新增任務」按鈕（只有登入後才會顯示）
    expect(await page.getByRole('button', { name: '新增任務' }).count()).toBe(0)

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
        // 找的是真實網頁上的按鈕（角色 + 名稱）。不能用 [icon="..."] 這種屬性選擇器：
        // icon 是 Nuxt UI 元件的 prop，只會畫成圖示，不會出現在網頁的 HTML 屬性上
        // （單元測試把元件換成假元件，假元件才會把 prop 印成屬性，兩邊行為不一樣）
        await page.getByRole('button', { name: '新增任務' }).waitFor({ timeout: 30_000 })
      } catch (error) {
        await printPostSignInDiagnostics(page, redirects)
        throw error
      }

      const bodyText = await page.textContent('body')
      expect(bodyText).not.toContain('登入後即可查看你的任務、行事曆與整合服務')

      await page.close()
    },
  )
})
