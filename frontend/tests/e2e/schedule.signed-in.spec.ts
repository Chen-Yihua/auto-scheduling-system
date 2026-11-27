// 流程 b：登入後在排程頁走完步驟，看到排程建議（e2e-user-flows AC3、AC5、AC10～AC12）。登入狀態來自 auth.setup.ts
import { test, expect } from '@playwright/test'
import { e2eEndpoints } from './support/e2eEnv'
import { getAuthHeaders, uniqueTitle } from './support/signedInApi'

test.skip(!process.env.E2E_CLERK_TEST_EMAIL, '沒有 E2E_CLERK_TEST_EMAIL，跳過登入後的測試')

const { backendUrl, googleUrl } = e2eEndpoints(process.env)

const PREFERENCE_READ_FAILED = '讀不到上次的排程偏好，請重新填寫'
const PREFERENCE_SAVE_FAILED = '排程偏好沒有存成功，下次要重新填'
const NOT_CONNECTED = 'Google Calendar 未連接或授權已失效'

type FakeGoogleRequest = { method: string; path: string }

test('排程頁照步驟走完，顯示任務排在什麼時間，而且沒有寫進 Google 日曆', async ({ page, request }) => {
  const title = uniqueTitle('排程')

  await page.goto('/')
  const headers = await getAuthHeaders(page)

  await test.step('AC5：先刪掉測試使用者所有任務，只建立這一個未排程任務', async () => {
    const existing = await request.get(`${backendUrl}/manual-tasks/me`, { headers })
    expect(existing.status(), 'GET /manual-tasks/me 的狀態碼').toBe(200)
    for (const task of (await existing.json()) as { id: string }[]) {
      const deleted = await request.delete(`${backendUrl}/manual-tasks/${task.id}`, { headers })
      // 刪主任務時階段一起刪，之後輪到階段會是 404
      expect([200, 404], 'DELETE /manual-tasks/<id> 的狀態碼').toContain(deleted.status())
    }
    const dueDate = new Date(Date.now() + 3 * 24 * 60 * 60 * 1000).toISOString()
    const created = await request.post(`${backendUrl}/manual-tasks/`, {
      headers,
      data: { title, description: '', status: 'To Do', priority: 'High', duration: 30, due_date: dueDate },
    })
    expect(created.status(), 'POST /manual-tasks/ 的狀態碼').toBe(201)

    const after = await request.get(`${backendUrl}/manual-tasks/me`, { headers })
    expect(((await after.json()) as { title: string }[]).map((t) => t.title)).toEqual([title])
  })

  const noPreferenceErrors = async () => {
    await expect(page.getByText(PREFERENCE_READ_FAILED)).toHaveCount(0)
    await expect(page.getByText(PREFERENCE_SAVE_FAILED)).toHaveCount(0)
  }

  // UI 模式開著時假伺服器會被沿用，記錄留著前幾次執行的請求，所以只看從這裡開始的
  const readFakeGoogleRequests = async () =>
    (await (await request.get(`${googleUrl}/__e2e/requests`)).json()) as FakeGoogleRequest[]
  const requestsBefore = (await readFakeGoogleRequests()).length

  await test.step('AC3：打開排程頁，不顯示 Google Calendar 未連接', async () => {
    await page.goto('/schedule')
    await expect(page.getByText('拖拉排序優先權')).toBeVisible()
    await expect(page.getByText(NOT_CONNECTED)).toHaveCount(0)
    await noPreferenceErrors()
  })

  await test.step('AC10、AC11：拖拉排序優先權 → 確認截止日期與時長 → 查看排程建議', async () => {
    // 第 1 步：只有這一個任務
    await expect(page.locator('[draggable="true"]')).toHaveCount(1)
    await expect(page.locator('[draggable="true"]').filter({ hasText: title })).toBeVisible()
    await page.getByRole('button', { name: '下一步' }).click()

    // 第 2 步
    await expect(page.getByRole('button', { name: '確認並產生排程建議' })).toBeVisible()
    await noPreferenceErrors()
    await page.getByRole('button', { name: '確認並產生排程建議' }).click()

    // 第 3 步
    await expect(page.getByText('已排入時段')).toBeVisible()
    // 名稱與時間在同一列：從名稱往上找最近的 justify-between 容器
    const row = page.getByText(title).locator('xpath=ancestor::div[contains(@class, "justify-between")][1]')
    await expect(row).toBeVisible()
    // 時間字串依瀏覽器語系而不同，只確認有「時:分:秒 - 時:分:秒」的範圍
    await expect(row).toHaveText(/\d{1,2}:\d{2}:\d{2}.*-.*\d{1,2}:\d{2}:\d{2}/)
    await noPreferenceErrors()
  })

  await test.step('AC12：流程 b 開始後，假的 Google 沒有收到新增事件的請求', async () => {
    const since = (await readFakeGoogleRequests()).slice(requestsBefore)
    expect(since.some((r) => r.path.endsWith('/freeBusy')), '有向假的 Google 查空檔').toBe(true)
    expect(since.filter((r) => r.method === 'POST' && r.path.endsWith('/events'))).toEqual([])
  })
})
