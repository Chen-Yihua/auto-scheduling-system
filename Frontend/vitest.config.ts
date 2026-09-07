// vitest.config.ts
import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'
import path from 'path'

export default defineConfig({
  plugins: [vue()],
  test: {
    globals: true,
    environment: 'jsdom',
    // E2E 測試需要真的 Node 環境去起一個真的 Nuxt server、開一個真的瀏覽器，
    // 跟這裡 jsdom + #imports mock 的單元/元件測試環境衝突，獨立用
    // vitest.e2e.config.ts + `npm run test:e2e` 跑，不歸這個預設指令管。
    exclude: ['**/node_modules/**', 'tests/e2e/**'],
    coverage: {
      reporter: ['text', 'lcov', 'html'], // CLI 印出 + 產出 lcov.info + HTML 報表
      reportsDirectory: './coverage',     // 可省略，預設就是 coverage/
      exclude: ['**/node_modules/**', '**/.nuxt/**', '**/tests/**'],
    },
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './'),
      '~': path.resolve(__dirname, './'),
      '#imports': path.resolve(__dirname, 'tests/__mocks__/imports.mock.ts'),
    },
  },
})
