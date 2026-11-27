// 在測試使用者底下放一筆假的 Google 日曆連線資料：呼叫 backend/scripts/e2e_seed_google_token.py，
// 用後端自己的 save_google_calendar_token 加密寫入，不在 Node 重寫加密。
import { spawnSync } from 'node:child_process'
import { resolve } from 'node:path'
import { E2E_DB_NAME, e2eEndpoints } from './e2eEnv'
import { E2E_SECRET_ENCRYPTION_KEY, resolvePython } from './e2eConfig'

type Env = Record<string, string | undefined>

export function buildSeedCommand(env: Env, clerkId: string) {
  const isCI = env.GITHUB_ACTIONS === 'true'
  return {
    command: resolvePython(env),
    args: ['scripts/e2e_seed_google_token.py', clerkId],
    options: {
      cwd: resolve(process.cwd(), '../backend'),
      // 只給這三個：不依賴後端程式碼對 MONGO_URI、MONGO_DB 的預設值（開發用的資料庫），也不繼承 shell 的其他變數
      env: {
        PATH: env.PATH ?? '',
        MONGO_URI: e2eEndpoints(env).mongoUri,
        MONGO_DB: E2E_DB_NAME,
        SECRET_ENCRYPTION_KEY: E2E_SECRET_ENCRYPTION_KEY,
      },
      // CI 的 log 是公開的：子行程的輸出不印
      stdio: isCI ? ('ignore' as const) : ('inherit' as const),
    },
  }
}

export function seedGoogleToken(env: Env, clerkId: string): void {
  const { command, args, options } = buildSeedCommand(env, clerkId)
  const result = spawnSync(command, args, options)
  if (result.status !== 0) {
    throw new Error(`寫入假的 Google 連線資料失敗（結束碼 ${result.status}）`)
  }
}
