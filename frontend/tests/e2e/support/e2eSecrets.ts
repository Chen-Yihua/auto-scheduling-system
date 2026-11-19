// e2e 印出內容時要換成 [redacted] 的固定值；dashboard.e2e.ts 和 vitest.e2e.config.ts 的清理用 reporter 共用（#50）
const SECRET_ENV_NAMES = ['E2E_CLERK_TEST_EMAIL', 'NUXT_CLERK_SECRET_KEY', 'E2E_CLERK_TEST_PASSWORD'] as const

export function e2eSecrets(env: Record<string, string | undefined>): string[] {
  return SECRET_ENV_NAMES.map((name) => env[name] ?? '').filter((value) => value !== '')
}
