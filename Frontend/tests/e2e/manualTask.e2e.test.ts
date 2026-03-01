// 元件 : components/TheMain/TaskFoem.vue -> 載入 編輯任務
// api : composables/useTaskForm.ts

import { expect, test } from '@playwright/test'

test.use({ storageState: 'storageState.json' }) // 整個 test 用 storageState.json 登入

// 開 index 頁面 -> 按編輯按鈕 -> 開 taskFoCrm modal -> 填表單 -> 送出 -> 關掉 modal -> 檢查是否有新資料
test('create task test', async ({ page }) => {
  await page.goto('http://localhost:3000') // 開 index
  await page.waitForSelector('button[data-testid="create-button"]', { timeout: 120000 }) // 等 button 出現
  await page.click('button[data-testid="create-button"]') // 按編輯按鈕
  await page.waitForSelector('[data-testid="task-form"]', { state: 'visible', timeout: 10000 }) // 等表單出現
  await page.fill('input[data-testid="task-title"]', 'test_title') // 填表單
  await page.fill('textarea[data-testid="task-description"]', 'test_des') 
  await page.click('[data-testid="priority-select"]')
  await page.getByRole('option',{name:'High'}).click()
  await expect(page.locator('[data-testid="priority-select"]')).toHaveText('High') // 確認優先級選擇
  await page.click('[data-testid="due-date-button"]')
  await page.click('[aria-label="Wednesday, June 25, 2025"]')
  await page.click('button[data-testid="submit-button"]')  // 送出
  await page.waitForSelector('[data-testid="task-form"]', { state: 'hidden'}) // 等表單關掉

  await page.reload({ waitUntil: 'networkidle' })
  await expect(page.locator('[data-testid="task-list"]').last()).toContainText('test_title') // 檢查有新資料
  await expect(page.locator('[data-testid="task-list"]').last()).toContainText('test_des') 
  await expect(page.locator('[data-testid="task-list"]').last()).toContainText('6/25') 
  await expect(page.locator('[data-testid="task-list"]').last()).toContainText('High') 
})

// 按 index 上的任務編輯按鈕 -> 打開 taskForm modal -> 更新表單內容 -> 點更新 -> 關掉 modal -> 檢查是否有更新資料
test('updata task test', async ({ page }) => {
  await page.goto('http://localhost:3000')
  await page.waitForSelector('button[data-testid="edit-button"]', { timeout: 60000 }) // 等 button 出現
  await page.locator('button[data-testid="edit-button"]').last().click()
  await page.waitForSelector('[data-testid="task-form"]', { state: 'visible', timeout: 10000 }) // 檢查表單出現
  await page.fill('input[data-testid="task-title"]', '更新任務') // 更新 title
  await page.click('button[data-testid="submit-button"]') // 提交
  await page.waitForSelector('[data-testid="task-form"]', { state: 'hidden' }) //等表單關閉
  const texts = await page.locator('[data-testid="task-list"]').allTextContents(); // 檢查有無更新
  expect(texts.join()).toContain('更新任務');
})

// 按 index 上的任務編輯按鈕 -> 打開 taskForm modal -> 按刪除 -> 關掉 modal -> 檢查 index 是否有刪除資料
test('delete task test', async ({ page }) => {
  await page.goto('http://localhost:3000')
  await page.waitForSelector('button[data-testid="edit-button"]', { timeout: 60000 }) // 等 button 出現
  await page.locator('button[data-testid="edit-button"]').last().click() // 點剛剛新增的任務的編輯按鈕
  await page.waitForSelector('[data-testid="task-form"]', { state: 'visible', timeout: 10000 }) // 檢查表單出現
  page.on('dialog', async dialog => {
    await dialog.accept(); // 自動點「確定」
  })
  await page.click('button[data-testid="delete-button"]') // 刪除
  await page.waitForSelector('[data-testid="task-form"]', { state: 'hidden' }) //等表單關閉
  const texts = await page.locator('[data-testid="task-list"]').allTextContents() // 檢查任務有無更新
  expect(texts.join()).not.toContain('更新任務')
})

// 按 index 上的任務編輯按鈕 -> 打開 taskForm modal -> 取消 -> 關掉 modal
test('cancel task test', async ({ page }) => {
  await page.goto('http://localhost:3000')
  await page.waitForSelector('button[data-testid="edit-button"]', { timeout: 60000 }) // 等 button 出現
  await page.locator('button[data-testid="edit-button"]').last().click() // 點剛剛新增的任務的編輯按鈕
  await page.waitForSelector('[data-testid="task-form"]', { state: 'visible', timeout: 10000 }) // 檢查表單出現
  await page.click('button[data-testid="cancel-button"]') // 取消
  await page.waitForSelector('[data-testid="task-form"]', { state: 'hidden' }) // 等表單關閉
})

