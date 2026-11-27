// npm run e2e:serve 用：永遠不結束，讓 Playwright 維持它啟動的伺服器
import { test } from '@playwright/test'

test('保持 E2E 伺服器開著，Ctrl+C 結束', async () => {
  await new Promise(() => {})
})
