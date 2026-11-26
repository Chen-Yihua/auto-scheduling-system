// 清空 E2E 資料庫的文件、保留索引；名稱不是 auto_scheduling_e2e 時一律不動，避免誤刪開發用的資料。
import { E2E_DB_NAME } from './e2eEnv'

export interface DatabaseLike {
  databaseName: string
  listCollections(): { toArray(): Promise<{ name: string }[]> }
  collection(name: string): {
    deleteMany(filter: Record<string, never>): Promise<unknown>
    countDocuments(): Promise<number>
    indexes(): Promise<{ name?: string }[]>
  }
}

export async function resetDatabase(db: DatabaseLike): Promise<void> {
  if (db.databaseName !== E2E_DB_NAME) {
    throw new Error(`不清空資料庫：連到的是 ${db.databaseName}，E2E 只能清空 ${E2E_DB_NAME}`)
  }
  for (const { name } of await db.listCollections().toArray()) {
    await db.collection(name).deleteMany({})
  }
}

// 每個 collection 的文件數與索引名稱，給清空前後比對
export async function readDatabaseState(db: DatabaseLike) {
  const state: Record<string, { documents: number; indexes: string[] }> = {}
  for (const { name } of await db.listCollections().toArray()) {
    const collection = db.collection(name)
    const indexes = (await collection.indexes()).map((index) => index.name ?? '').sort()
    state[name] = { documents: await collection.countDocuments(), indexes }
  }
  return state
}
