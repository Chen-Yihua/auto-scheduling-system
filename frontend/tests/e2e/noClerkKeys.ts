// 沒有 Clerk 金鑰時唯一會執行的測試（見 support/e2eConfig.ts）：Playwright 收集到 0 個測試會失敗，所以放一個標示跳過的
import { test } from '@playwright/test'
import { NO_CLERK_KEYS_TITLE } from './support/e2eConfig'

test(NO_CLERK_KEYS_TITLE, () => {
  test.skip(true, '沒有 NUXT_PUBLIC_CLERK_PUBLISHABLE_KEY 或 NUXT_CLERK_SECRET_KEY')
})
