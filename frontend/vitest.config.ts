import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'
import path from 'path'

export default defineConfig({
  plugins: [vue()],
  test: {
    globals: true,
    environment: 'jsdom',
    // E2E 需要 Node 環境，用 vitest.e2e.config.ts（npm run test:e2e）另外跑
    exclude: ['**/node_modules/**', 'tests/e2e/**'],
    coverage: {
      reporter: ['text', 'lcov', 'html'],
      reportsDirectory: './coverage',
      // 只統計自己寫的程式碼，排除設定檔、types/ 和 app.vue
      include: ['components/**', 'composables/**', 'pages/**', 'utils/**', 'server/**'],
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
