// E2E 要起 Nuxt server 和瀏覽器，需要 Node 環境，不能用主設定的 jsdom
import { defineConfig } from 'vitest/config'

export default defineConfig({
  test: {
    globals: true,
    environment: 'node',
    include: ['tests/e2e/**/*.e2e.ts'],
    testTimeout: 120_000,
    hookTimeout: 120_000,
  },
})
