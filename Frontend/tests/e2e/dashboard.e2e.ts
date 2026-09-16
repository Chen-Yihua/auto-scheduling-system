// tests/e2e/dashboard.e2e.ts
//
// 真的 E2E 測試：起一個真的 Nuxt server、用真的（headless）瀏覽器去操作，
// 跟 tests/utils|components 底下那些用 jsdom + mock 掉 composable 的測試不是同一類。
// 用 `npm run test:e2e` 單獨跑（見 vitest.e2e.config.ts），不含在預設的
// `npm run test` 裡，因為這裡會真的 build/啟動一次 Nuxt app，比一般測試慢很多。
import { fileURLToPath } from 'node:url'
import { describe, it, expect, beforeAll } from 'vitest'
import { setup, createPage, url } from '@nuxt/test-utils/e2e'
import { clerkSetup, clerk } from '@clerk/testing/playwright'

await setup({
  rootDir: fileURLToPath(new URL('../..', import.meta.url)),
  browser: true,
})

// 登入後的流程需要一組真的存在於 Clerk 測試環境裡的帳號密碼——這組帳密只有
// 在維護者的 Clerk dashboard 建立測試使用者、並把 email/password 存成
// E2E_CLERK_TEST_EMAIL / E2E_CLERK_TEST_PASSWORD 這兩個 secret 之後才會有值。
// 本機開發或是 fork 出去的 PR（GitHub Actions 不會把 secrets 帶給 fork 的 PR）
// 沒有這兩個變數時，跳過這個測試，而不是讓整個 E2E 測試都紅掉。
const hasClerkTestCredentials =
  !!process.env.E2E_CLERK_TEST_EMAIL && !!process.env.E2E_CLERK_TEST_PASSWORD

describe('Dashboard（真實瀏覽器 E2E）', () => {
  it('訪客未登入時，看到登入提示，不會看到任務/整合服務內容', async () => {
    const page = await createPage('/')
    await page.waitForSelector('text=登入後即可查看你的任務、行事曆與整合服務')

    const bodyText = await page.textContent('body')
    expect(bodyText).toContain('登入後即可查看你的任務、行事曆與整合服務')
    // 訪客不該看到「編輯任務」的浮動按鈕（TaskForm 只在登入後掛載）
    expect(await page.locator('[icon="mdi-file-edit"]').count()).toBe(0)

    await page.close()
  })

  it.skipIf(!hasClerkTestCredentials)(
    '用真的 Clerk 測試帳號登入後，看得到主畫面、不再顯示登入提示',
    async () => {
      await clerkSetup({
        publishableKey: process.env.NUXT_PUBLIC_CLERK_PUBLISHABLE_KEY,
        secretKey: process.env.NUXT_CLERK_SECRET_KEY,
      })

      const page = await createPage('/')
      // clerk.signIn 要求先 goto 過一個會載入 Clerk 的頁面，才能繼續
      await clerk.signIn({
        page,
        signInParams: {
          strategy: 'password',
          identifier: process.env.E2E_CLERK_TEST_EMAIL!,
          password: process.env.E2E_CLERK_TEST_PASSWORD!,
        },
      })

      await page.goto(url('/'))
      await page.waitForSelector('[icon="mdi-file-edit"]')

      const bodyText = await page.textContent('body')
      expect(bodyText).not.toContain('登入後即可查看你的任務、行事曆與整合服務')

      await page.close()
    },
  )
})
