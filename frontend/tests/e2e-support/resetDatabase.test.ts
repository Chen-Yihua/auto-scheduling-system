// E2E 清空資料庫的函式：只能清 auto_scheduling_e2e
import { describe, it, expect, vi } from 'vitest'
import { resetDatabase, type DatabaseLike } from '../e2e/support/resetDatabase'

function fakeDatabase(databaseName: string) {
  const deleteMany = vi.fn(async () => ({}))
  const db: DatabaseLike = {
    databaseName,
    listCollections: () => ({ toArray: async () => [{ name: 'users' }, { name: 'manual_tasks' }] }),
    collection: () => ({ deleteMany, countDocuments: async () => 0, indexes: async () => [] }),
  }
  return { db, deleteMany }
}

describe('resetDatabase', () => {
  it('e2e-playwright AC11：資料庫名稱不是 auto_scheduling_e2e 時丟出錯誤，不刪任何文件', async () => {
    const { db, deleteMany } = fakeDatabase('auto_scheduling_db')

    await expect(resetDatabase(db)).rejects.toThrow('auto_scheduling_db')

    expect(deleteMany).not.toHaveBeenCalled()
  })

  it('e2e-playwright AC13：資料庫名稱是 auto_scheduling_e2e 時，每個 collection 都清空文件', async () => {
    const { db, deleteMany } = fakeDatabase('auto_scheduling_e2e')

    await resetDatabase(db)

    expect(deleteMany).toHaveBeenCalledTimes(2)
    expect(deleteMany).toHaveBeenCalledWith({})
  })
})
