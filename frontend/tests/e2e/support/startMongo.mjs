// 本機 E2E 的 MongoDB：用 mongodb-memory-server 在指定 port 啟動，不用自己裝 MongoDB 或 Docker。CI 用 service container，不跑這支。
import { MongoMemoryServer } from 'mongodb-memory-server'

const port = Number(process.argv[2])
const server = await MongoMemoryServer.create({ instance: { port, ip: '127.0.0.1' } })

// Playwright 結束 webServer 時送 SIGTERM
for (const signal of ['SIGINT', 'SIGTERM']) {
  process.on(signal, async () => {
    await server.stop()
    process.exit(0)
  })
}
