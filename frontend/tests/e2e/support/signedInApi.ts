// 登入後的測試直接呼叫後端 API 準備資料：用瀏覽器裡 Clerk 的 session 取得 token
import type { Page } from '@playwright/test'

export async function getAuthHeaders(page: Page): Promise<{ Authorization: string }> {
  await page.waitForFunction(() => !!(window as unknown as { Clerk?: { session?: unknown } }).Clerk?.session)
  const token = await page.evaluate(() =>
    (window as unknown as { Clerk: { session: { getToken(): Promise<string | null> } } }).Clerk.session.getToken(),
  )
  return { Authorization: `Bearer ${token}` }
}

// 名稱帶這次執行獨有的字串，在清單裡才找得到自己的任務
export function uniqueTitle(label: string): string {
  return `E2E ${label} ${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`
}
