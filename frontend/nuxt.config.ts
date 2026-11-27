// E2E（playwright.config.ts 設 NUXT_E2E=1）的 build 放在獨立的資料夾與 vite 快取：
// 開著 npm run dev 時，E2E 才不會改寫 dev server 在用的 .nuxt、.output 與 node_modules/.cache/vite
const e2eIsolation =
  process.env.NUXT_E2E === '1'
    ? {
        buildDir: '.nuxt-e2e',
        nitro: { output: { dir: '.output-e2e' } },
        vite: { cacheDir: 'node_modules/.cache/vite-e2e' },
      }
    : {};

// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({
  ...e2eIsolation,
  compatibilityDate: '2024-11-01',
  devtools: { enabled: true },
  css: ['~/assets/css/tailwind.css'],
  modules: [
    '@nuxt/eslint',
    '@nuxt/test-utils',
    '@nuxt/ui',
    '@nuxt/icon',
    '@clerk/nuxt',
    '@nuxt/test-utils/module',
  ],
  runtimeConfig: {
    public: {
      apiBaseUrl: process.env.NUXT_PUBLIC_API_BASE_URL || 'http://localhost:8000',
      apiGoogleClientId: process.env.GOOGLE_CLIENT_ID,
      frontEndUrl: process.env.NUXT_PUBLIC_FRONTEND_URL || 'http://localhost:3000',
    },
    private: {
      apiGoogleSecret: process.env.GOOGLE_CLIENT_SECRET,
    },
  },
  // 全站固定白底，不提供深色模式
  ui: { colorMode: false },
  // Clerk 的登入視窗、帳號設定視窗用主色
  clerk: { appearance: { variables: { colorPrimary: '#56717f' } } },
  icon: {
    customCollections: [{
      prefix: 'custom',
      dir: './assets/icons'
    }]
  }
});
