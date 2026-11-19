// E2E 要起 Nuxt server 和瀏覽器，需要 Node 環境，不能用主設定的 jsdom
import { defineConfig } from 'vitest/config';
import SanitizingReporter from './tests/e2e/support/sanitizingReporter';
import { e2eSecrets } from './tests/e2e/support/e2eSecrets';

export default defineConfig({
  test: {
    globals: true,
    environment: 'node',
    include: ['tests/e2e/**/*.e2e.ts'],
    testTimeout: 120_000,
    hookTimeout: 120_000,
    // 清理用的 reporter 要排第一個：它原地改掉要印的內容，排在後面的 reporter 才印出清理過的版本。
    // 列出 reporters 後 vitest 不會在 CI 自動加 github-actions，所以自己加。
    reporters: [
      new SanitizingReporter({ secrets: e2eSecrets(process.env) }),
      'default',
      ...(process.env.GITHUB_ACTIONS === 'true' ? ['github-actions' as const] : []),
    ],
    // diff 只印改動附近的行時，cookie 的 name、"data": [ 這些開頭行可能不在畫面上，清理規則就認不出後面的值
    diff: { expand: true },
  },
});
