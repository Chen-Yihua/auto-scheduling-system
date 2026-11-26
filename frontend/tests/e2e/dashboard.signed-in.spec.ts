// 登入後的首頁：用 auth.setup.ts 存下的登入狀態（playwright.config.ts 的 storageState），這裡不登入
import { test, expect } from '@playwright/test'

test.skip(!process.env.E2E_CLERK_TEST_EMAIL, '沒有 E2E_CLERK_TEST_EMAIL，跳過登入後的測試')

test('用 setup 存下的登入狀態，看得到主畫面、不再顯示登入提示', async ({ page }) => {
  await page.goto('/')
  // 今日卡片的標題出現、而且訪客的登入提示消失，才代表登入完成
  await expect
    .poll(async () => {
      const text = (await page.locator('body').textContent()) ?? ''
      return text.includes('今日') && !text.includes('登入後即可查看')
    })
    .toBe(true)
})
