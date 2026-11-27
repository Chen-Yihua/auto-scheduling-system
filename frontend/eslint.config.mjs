// @ts-check
import withNuxt from './.nuxt/eslint.config.mjs';

// E2E 的 build 與 Playwright 的輸出不是原始碼（見 .nuxtignore）
export default withNuxt({
  ignores: ['.nuxt-e2e/**', '.output-e2e/**', '.auth-e2e/**', 'test-results/**', 'e2e-logs/**', 'playwright-report/**'],
});
// Your custom configs here
