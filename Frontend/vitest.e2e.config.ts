// vitest.e2e.config.ts
// 跟 vitest.config.ts 分開的原因：E2E 測試要用 @nuxt/test-utils/e2e 起一個真的
// Nuxt server、用 playwright-core 開一個真的瀏覽器去打它，需要 Node 環境，
// 不能套用主設定裡給單元/元件測試用的 jsdom + #imports mock。
import { defineConfig } from 'vitest/config'

export default defineConfig({
  test: {
    globals: true,
    environment: 'node',
    include: ['tests/e2e/**/*.e2e.ts'],
    // build 一次 Nuxt app + 起 server + 開瀏覽器，比一般單元測試慢很多
    testTimeout: 120_000,
    hookTimeout: 120_000,
  },
})
