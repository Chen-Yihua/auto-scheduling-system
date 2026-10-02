// tests/utils/useSchedulableTasks.test.ts
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ref as vueRef } from 'vue'

import { useSchedulableTasks } from '~/composables/useSchedulableTasks'
import type { SchedulableTask } from '~/types/schedulableTask'

vi.mock('@clerk/vue', () => ({
  useAuth: () => ({
    getToken: { value: vi.fn().mockResolvedValue('jwt-token') },
  }),
}))

vi.stubGlobal('ref', vueRef)

const toastSpy = { add: vi.fn() }
vi.stubGlobal('useToast', () => toastSpy)
vi.stubGlobal('useRuntimeConfig', () => ({
  public: { apiBaseUrl: 'http://api' },
}))

let fetchSpy = vi.fn()
vi.stubGlobal('$fetch', (...args: unknown[]) => fetchSpy(...args))

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
