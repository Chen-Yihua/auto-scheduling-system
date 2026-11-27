// 流程 a：登入後在任務管理頁新增、修改、刪除任務（e2e-user-flows AC6～AC9）。登入狀態來自 auth.setup.ts
import { test, expect, type Page } from '@playwright/test'
import { uniqueTitle } from './support/signedInApi'

test.skip(!process.env.E2E_CLERK_TEST_EMAIL, '沒有 E2E_CLERK_TEST_EMAIL，跳過登入後的測試')

const taskTitle = (page: Page, title: string) => page.getByTestId('task-title').filter({ hasText: title })
const taskRow = (page: Page, title: string) => page.locator('.task-row').filter({ hasText: title })

// 重新載入後等任務清單重新讀完，「不出現」的斷言才不會在清單還沒載入時就通過
async function reloadAndWaitForList(page: Page) {
  const loaded = page.waitForResponse((r) => r.url().endsWith('/schedule/tasks') && r.request().method() === 'GET')
  await page.reload()
  await loaded
  await expect(page.getByTestId('tasks-add')).toBeVisible()
}

test('任務管理頁新增、修改、刪除任務，清單跟著變，重新載入後仍一致', async ({ page }) => {
  const title = uniqueTitle('新增')
  const renamed = uniqueTitle('改名')

  await page.goto('/tasks')
  await page.getByTestId('tasks-add').click()

  await test.step('AC6、AC9：填名稱、優先度、時長後送出，清單出現這個任務，不靠 Gemini 推斷', async () => {
    await page.getByPlaceholder('新增代辦事項').fill(title)
    await page.getByRole('combobox').click()
    await page.getByRole('option', { name: '高' }).click()
    await page.getByPlaceholder('分鐘，例如 60').fill('30')

    const created = page.waitForResponse((r) => r.url().endsWith('/manual-tasks/') && r.request().method() === 'POST')
    await page.getByRole('button', { name: '提交' }).click()
    const body = await (await created).json()
    expect(body.inferred_fields, 'POST /manual-tasks/ 回應的 inferred_fields').toEqual([])

    await expect(taskTitle(page, title)).toBeVisible()
  })

  await test.step('AC7：改名後清單只顯示新名稱，重新載入後仍是新名稱', async () => {
    await taskRow(page, title).getByRole('button', { name: '編輯' }).click()
    await page.getByPlaceholder('編輯代辦事項').fill(renamed)
    await page.getByRole('button', { name: '儲存變更' }).click()

    await expect(taskTitle(page, renamed)).toBeVisible()
    await expect(taskTitle(page, title)).toHaveCount(0)

    await reloadAndWaitForList(page)
    await expect(taskTitle(page, renamed)).toBeVisible()
    await expect(taskTitle(page, title)).toHaveCount(0)
  })

  await test.step('AC8：刪除後清單不再出現，重新載入後仍不出現', async () => {
    await taskRow(page, renamed).getByRole('button', { name: '編輯' }).click()
    // 刪除前會跳瀏覽器的確認對話框
    page.once('dialog', (dialog) => void dialog.accept())
    await page.getByRole('button', { name: '刪除', exact: true }).click()

    await expect(taskTitle(page, renamed)).toHaveCount(0)

    await reloadAndWaitForList(page)
    await expect(taskTitle(page, renamed)).toHaveCount(0)
  })
})
