import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ref as vueRef } from 'vue';

import { useSchedulableTasks } from '~/composables/useSchedulableTasks';
import type { SchedulableTask } from '~/types/schedulableTask';

vi.mock('@clerk/vue', () => ({
  useAuth: () => ({
    getToken: { value: vi.fn().mockResolvedValue('jwt-token') },
  }),
}));

vi.stubGlobal('ref', vueRef);

const triggerCalendarReloadSpy = vi.fn();
vi.mock('@/composables/useGoogleCalendar', () => ({
  useGoogleCalendar: () => ({ triggerCalendarReload: triggerCalendarReloadSpy }),
}));

const toastSpy = { add: vi.fn() };
vi.stubGlobal('useToast', () => toastSpy);
vi.stubGlobal('useRuntimeConfig', () => ({
  public: { apiBaseUrl: 'http://api' },
}));

let fetchSpy = vi.fn();
vi.stubGlobal('$fetch', (...args: unknown[]) => fetchSpy(...args));

function fakeTask(overrides: Partial<SchedulableTask> = {}): SchedulableTask {
  return {
    id: 'manual:t1', source: 'manual', title: '任務', status: 'To Do',
    priority: 'Medium', duration: 30, due_date: null, sort_order: null,
    calendar_event_id: null, url: null,
    ...overrides,
  }
}

describe('useSchedulableTasks composable', () => {
  beforeEach(() => {
    fetchSpy = vi.fn()
    toastSpy.add.mockClear()
    triggerCalendarReloadSpy.mockClear()
  })

  it('AC23b：fetchSchedulableTasks 失敗時 loadFailed 是 true，下一次成功後回到 false', async () => {
    const ctx = useSchedulableTasks()
    fetchSpy.mockRejectedValueOnce(new Error('boom'))
    await ctx.fetchSchedulableTasks()
    expect(ctx.loadFailed.value).toBe(true)

    fetchSpy.mockResolvedValueOnce([])
    await ctx.fetchSchedulableTasks()
    expect(ctx.loadFailed.value).toBe(false)
  })

  it('AC50：rescheduleTasks 呼叫 POST /schedule/tasks/reschedule，完成後重新抓清單並重新載入首頁日曆，不跳通知', async () => {
    fetchSpy
      .mockResolvedValueOnce({ succeeded: ['manual:a'], failed: [{ task_id: 'manual:b', reason: '原因', error_code: null }] })
      .mockResolvedValueOnce([fakeTask()])
    const ctx = useSchedulableTasks()

    const outcome = await ctx.rescheduleTasks(['manual:a', 'manual:b'])

    expect(fetchSpy).toHaveBeenNthCalledWith(
      1,
      'http://api/schedule/tasks/reschedule',
      expect.objectContaining({ method: 'POST', body: { task_ids: ['manual:a', 'manual:b'] } }),
    )
    expect(fetchSpy).toHaveBeenNthCalledWith(2, 'http://api/schedule/tasks', expect.objectContaining({ method: 'GET' }))
    expect(triggerCalendarReloadSpy).toHaveBeenCalledTimes(1)
    expect(outcome).toEqual({ kind: 'success', failed: [{ task_id: 'manual:b', reason: '原因', error_code: null }] })
    expect(toastSpy.add).not.toHaveBeenCalled()
  })

  it('AC50a：rescheduleTasks API 回錯誤時，仍重新抓清單並重新載入首頁日曆，回傳錯誤訊息', async () => {
    fetchSpy
      .mockRejectedValueOnce({ data: { error_code: 'UPSTREAM_ERROR', detail: 'Google 暫時無法處理請求' }, status: 502 })
      .mockResolvedValueOnce([])
    const ctx = useSchedulableTasks()

    const outcome = await ctx.rescheduleTasks(['manual:a'])

    expect(fetchSpy).toHaveBeenCalledTimes(2)
    expect(triggerCalendarReloadSpy).toHaveBeenCalledTimes(1)
    expect(outcome).toEqual({ kind: 'error', message: 'Google 暫時無法處理請求', failed: [] })
    expect(toastSpy.add).not.toHaveBeenCalled()
  })

  it('AC46：rescheduleTasks 遇到授權失效（REAUTH_REQUIRED）時，回傳的種類是 reauth', async () => {
    fetchSpy
      .mockRejectedValueOnce({ data: { error_code: 'REAUTH_REQUIRED', detail: '請重新連接' }, status: 409 })
      .mockResolvedValueOnce([])
    const ctx = useSchedulableTasks()

    const outcome = await ctx.rescheduleTasks(['manual:a'])

    expect(outcome.kind).toBe('reauth')
  })

  it('saveTaskFields 呼叫 PATCH /schedule/tasks/fields；失敗時跳通知並回傳 false', async () => {
    const ctx = useSchedulableTasks()
    fetchSpy.mockResolvedValueOnce(undefined)
    expect(await ctx.saveTaskFields('github:1', { due_date: '2026-11-30T00:00:00Z', duration: 45 })).toBe(true)
    expect(fetchSpy).toHaveBeenCalledWith(
      'http://api/schedule/tasks/fields',
      expect.objectContaining({ method: 'PATCH', body: { task_id: 'github:1', due_date: '2026-11-30T00:00:00Z', duration: 45 } }),
    )

    fetchSpy.mockRejectedValueOnce(new Error('boom'))
    expect(await ctx.saveTaskFields('github:1', { due_date: null, duration: 45 })).toBe(false)
    expect(toastSpy.add).toHaveBeenCalledWith(expect.objectContaining({ title: '儲存失敗', color: 'error' }))
  })

  it('fetchSchedulableTasks 呼叫 GET /schedule/tasks 並存進 state', async () => {
    const tasks = [fakeTask()]
    fetchSpy.mockResolvedValueOnce(tasks)

    const ctx = useSchedulableTasks()
    await ctx.fetchSchedulableTasks()

    expect(fetchSpy).toHaveBeenCalledWith(
      'http://api/schedule/tasks',
      expect.objectContaining({ method: 'GET', headers: { Authorization: 'Bearer jwt-token' } }),
    )
    expect(ctx.tasks.value).toEqual(tasks)
    expect(ctx.loading.value).toBe(false)
  })

  it('fetchSchedulableTasks 失敗時跳出錯誤 toast', async () => {
    fetchSpy.mockRejectedValueOnce(new Error('boom'))

    const ctx = useSchedulableTasks()
    await ctx.fetchSchedulableTasks()

    expect(toastSpy.add).toHaveBeenCalledWith(
      expect.objectContaining({ title: '任務列表載入失敗', color: 'error' }),
    )
  })

  it('toggleDone 成功：樂觀更新狀態，並呼叫 PATCH /schedule/tasks/done', async () => {
    fetchSpy.mockResolvedValueOnce(undefined)
    const ctx = useSchedulableTasks()
    const task = fakeTask({ id: 'github:42', status: 'To Do' })

    await ctx.toggleDone(task)

    expect(task.status).toBe('Done')
    expect(fetchSpy).toHaveBeenCalledWith(
      'http://api/schedule/tasks/done',
      expect.objectContaining({
        method: 'PATCH',
        body: { task_id: 'github:42', done: true },
        headers: { Authorization: 'Bearer jwt-token' },
      }),
    )
  })

  it('toggleDone 對已完成的任務會取消完成（done: false）', async () => {
    fetchSpy.mockResolvedValueOnce(undefined)
    const ctx = useSchedulableTasks()
    const task = fakeTask({ id: 'github:42', status: 'Done' })

    await ctx.toggleDone(task)

    expect(task.status).toBe('To Do')
    expect(fetchSpy).toHaveBeenCalledWith(
      'http://api/schedule/tasks/done',
      expect.objectContaining({ body: { task_id: 'github:42', done: false } }),
    )
  })

  it('toggleDone 失敗時復原本地狀態並跳出錯誤 toast', async () => {
    fetchSpy.mockRejectedValueOnce(new Error('boom'))
    const ctx = useSchedulableTasks()
    const task = fakeTask({ id: 'github:42', status: 'To Do' })

    await ctx.toggleDone(task)

    expect(task.status).toBe('To Do') // 失敗要復原，不能停在樂觀更新的錯誤狀態
    expect(toastSpy.add).toHaveBeenCalledWith(
      expect.objectContaining({ title: '更新完成狀態失敗', color: 'error' }),
    )
  })

  it('toggleDone 對已完成的任務會取消完成（done: false）', async () => {
    fetchSpy.mockResolvedValueOnce(undefined)
    const ctx = useSchedulableTasks()
    const task = fakeTask({ status: 'Done' })

    await ctx.toggleDone(task)

    expect(fetchSpy.mock.calls[0][1].body).toEqual({ task_id: task.id, done: false })
    expect(task.status).toBe('To Do')
  })
})
