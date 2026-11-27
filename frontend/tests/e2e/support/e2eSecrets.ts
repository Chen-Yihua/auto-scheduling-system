// e2e 的診斷輸出要換成 [redacted] 的固定值（auth.setup.ts 的 createDiagnosticLogger 與 createSignInDiagnostics 用；#50 AC16）
const SECRET_ENV_NAMES = ['E2E_CLERK_TEST_EMAIL', 'NUXT_CLERK_SECRET_KEY', 'E2E_CLERK_TEST_PASSWORD'] as const

export function e2eSecrets(env: Record<string, string | undefined>): string[] {
  return SECRET_ENV_NAMES.map((name) => env[name] ?? '').filter((value) => value !== '')
}
