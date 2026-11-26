// E2E 用的位址與資料庫名稱：playwright.config.ts 啟動伺服器、auth.setup.ts 連資料庫都讀這裡，兩邊才會一致。
// port 和開發環境（3000、8000、27017）不同，開著 dev server、開發用後端與 MongoDB 時不衝突。
export const E2E_DB_NAME = 'auto_scheduling_e2e'

export const STORAGE_STATE_PATH = '.auth-e2e/storageState.json'

type Env = Record<string, string | undefined>

function port(env: Env, name: string, fallback: number): number {
  const value = Number(env[name])
  return Number.isInteger(value) && value > 0 ? value : fallback
}

export function e2eEndpoints(env: Env) {
  const frontendPort = port(env, 'E2E_FRONTEND_PORT', 3100)
  const backendPort = port(env, 'E2E_BACKEND_PORT', 8001)
  const mongoPort = port(env, 'E2E_MONGO_PORT', 27018)
  return {
    frontendPort,
    backendPort,
    mongoPort,
    // 用 127.0.0.1 不用 localhost：localhost 可能解析成 IPv6，伺服器只聽 IPv4 時連不上
    frontendUrl: `http://127.0.0.1:${frontendPort}`,
    backendUrl: `http://127.0.0.1:${backendPort}`,
    mongoUri: `mongodb://127.0.0.1:${mongoPort}`,
  }
}
