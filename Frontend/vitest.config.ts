// vitest.config.ts
import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'
import path from 'path'

export default defineConfig({
  plugins: [vue()],
  test: {
    globals: true,
    environment: 'jsdom',
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
