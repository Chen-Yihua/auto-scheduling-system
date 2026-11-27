// 訪客（未登入）看到的首頁
import { test, expect } from '@playwright/test'

test('訪客未登入時，版面跟登入後一樣，今日卡片與行事曆的位置只顯示提示、標題列沒有新增任務按鈕', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByText('登入後即可查看今天的任務')).toBeVisible()

  await expect(page.locator('body')).toContainText('登入後即可查看 Google 行事曆')
  // 新增任務只在任務管理頁，標題列沒有按鈕
  await expect(page.locator('button[aria-label="新增任務"]')).toHaveCount(0)
})
