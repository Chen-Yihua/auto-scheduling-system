// tests/utils/useScheduleWizard.test.ts
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ref as vueRef, reactive as vueReactive, computed as vueComputed } from 'vue'

import { useScheduleWizard } from '~/composables/useScheduleWizard'
import type { SchedulableTask } from '~/types/schedulableTask'

vi.mock('@clerk/vue', () => ({
  useAuth: () => ({
    getToken: { value: vi.fn().mockResolvedValue('jwt-token') },
  }),
}))

vi.stubGlobal('ref', vueRef)
vi.stubGlobal('reactive', vueReactive)
vi.stubGlobal('computed', vueComputed)

const toastSpy = { add: vi.fn() }
vi.stubGlobal('useToast', () => toastSpy)
vi.stubGlobal('useRuntimeConfig', () => ({
  public: { apiBaseUrl: 'http://api' },
}))

let fetchSpy = vi.fn()
vi.stubGlobal('$fetch', (...args: unknown[]) => fetchSpy(...args))

function fakeTask(overrides: Partial<SchedulableTask> = {}): SchedulableTask {
  return {
    id: 'manual:t1',
    source: 'manual',
    title: '任務',
    status: 'To Do',
    priority: 'Medium',
    due_date: null,
    duration: null,
    sort_order: null,
    calendar_event_id: null,
    url: null,
    ...overrides,
  }
}

describe('useScheduleWizard composable', () => {
  beforeEach(() => {
    fetchSpy = vi.fn().mockResolvedValue({})
    toastSpy.add.mockClear()
  })

  it('initWizard 依 priority 把任務分到三欄，濾掉 Done 的任務', () => {
    const ctx = useScheduleWizard()
    ctx.initWizard([
      fakeTask({ id: 'done', status: 'Done', priority: 'High' }),
      fakeTask({ id: 'low', priority: 'Low' }),
      fakeTask({ id: 'high', priority: 'High' }),
      fakeTask({ id: 'medium', priority: 'Medium' }),
    ])

    expect(ctx.step.value).toBe(1)
    expect(ctx.columns.Low.map((t) => t.id)).toEqual(['low'])
    expect(ctx.columns.Medium.map((t) => t.id)).toEqual(['medium'])
    expect(ctx.columns.High.map((t) => t.id)).toEqual(['high'])
  })

  it('initWizard 把還沒有 priority 的任務（例如剛同步、還沒推斷過的外部平台項目）當成 Medium，不會三欄都對不到而憑空消失', () => {
    const ctx = useScheduleWizard()
    ctx.initWizard([
      fakeTask({ id: 'no-priority', priority: null, source: 'github' }),
    ])

    expect(ctx.columns.Low).toEqual([])
    expect(ctx.columns.High).toEqual([])
    expect(ctx.columns.Medium.map((t) => t.id)).toEqual(['no-priority'])
    expect(ctx.columns.Medium[0]!.priority).toBe('Medium')
  })

  it('initWizard 每次都把 preferences 重置成預設值（不工作時段每次精靈重新選，不留上一輪的設定）', () => {
    const ctx = useScheduleWizard()
    ctx.initWizard([fakeTask({ id: 'a', priority: 'Low' })])
    ctx.preferences.value.buffer_minutes = 30
    ctx.addBlockedRecurringRule()

    ctx.initWizard([fakeTask({ id: 'b', priority: 'Low' })])

    expect(ctx.preferences.value).toEqual({
      blocked_recurring: [], blocked_exceptions: [], buffer_minutes: 0, daily_max_minutes: null,
    })
  })

  it('addBlockedRecurringRule／removeBlockedRecurringRule 增刪每週固定規律', () => {
    const ctx = useScheduleWizard()
    ctx.initWizard([])

    ctx.addBlockedRecurringRule()
    expect(ctx.preferences.value.blocked_recurring).toEqual([
      { days_of_week: [], all_day: false, start_time: null, end_time: null },
    ])

    ctx.removeBlockedRecurringRule(0)
    expect(ctx.preferences.value.blocked_recurring).toEqual([])
  })

  it('addBlockedException／removeBlockedException 增刪這次額外的例外時段', () => {
    const ctx = useScheduleWizard()
    ctx.initWizard([])

    ctx.addBlockedException()
    expect(ctx.preferences.value.blocked_exceptions).toEqual([{ start: '', end: '' }])

    ctx.removeBlockedException(0)
    expect(ctx.preferences.value.blocked_exceptions).toEqual([])
  })

  it('sanitizedPreferences 濾掉還沒填完的規律／例外時段（曾經送到後端會 500／422）', () => {
    const ctx = useScheduleWizard()
    ctx.initWizard([])

    // 加了規律列，勾了星期但還沒填時間；加了整天規律但沒勾任何星期；
    // 加了例外時段但還沒選日期——這三種都是「還沒填完」，不該送出
    ctx.addBlockedRecurringRule()
    ctx.preferences.value.blocked_recurring[0]!.days_of_week = [5]
    ctx.addBlockedRecurringRule()
    ctx.preferences.value.blocked_recurring[1]!.all_day = true
    ctx.addBlockedException()

    expect(ctx.sanitizedPreferences.value.blocked_recurring).toEqual([])
    expect(ctx.sanitizedPreferences.value.blocked_exceptions).toEqual([])

    // 補完之後才會被送出
    ctx.preferences.value.blocked_recurring[0]!.start_time = '22:00'
    ctx.preferences.value.blocked_recurring[0]!.end_time = '08:00'
    ctx.preferences.value.blocked_recurring[1]!.days_of_week = [5, 6]
    ctx.preferences.value.blocked_exceptions[0]!.start = '2026-10-01T09:00:00.000Z'
    ctx.preferences.value.blocked_exceptions[0]!.end = '2026-10-01T10:00:00.000Z'

    expect(ctx.sanitizedPreferences.value.blocked_recurring).toHaveLength(2)
    expect(ctx.sanitizedPreferences.value.blocked_exceptions).toHaveLength(1)
  })

  it('initWizard 可以混著手動任務跟外部平台項目（依組合 id 的來源前綴無感處理）', () => {
    const ctx = useScheduleWizard()
    ctx.initWizard([
      fakeTask({ id: 'manual:t1', source: 'manual', priority: 'High' }),
      fakeTask({ id: 'github:42', source: 'github', priority: 'High', sort_order: 0 }),
      fakeTask({ id: 'jira:100', source: 'jira', priority: 'Medium' }),
    ])

    expect(ctx.columns.High.map((t) => t.id)).toEqual(['github:42', 'manual:t1'])
    expect(ctx.columns.Medium.map((t) => t.id)).toEqual(['jira:100'])
  })

  it('initWizard 濾掉已經確認排程、鎖定的任務（有 calendar_event_id）', () => {
    const ctx = useScheduleWizard()
    ctx.initWizard([
      fakeTask({ id: 'locked', priority: 'High', calendar_event_id: 'event-1' }),
      fakeTask({ id: 'pending', priority: 'High' }),
    ])

    expect(ctx.columns.High.map((t) => t.id)).toEqual(['pending'])
  })

  it('initWizard 時，同一欄內有 sort_order 的任務依它排序，蓋過 due_date', () => {
    const ctx = useScheduleWizard()
    ctx.initWizard([
      fakeTask({ id: 'no-order', priority: 'High', due_date: '2026-01-01T00:00:00Z' }),
      fakeTask({ id: 'order-0', priority: 'High', sort_order: 0, due_date: '2026-12-01T00:00:00Z' }),
    ])

    // order-0 排最前面，即使它的 due_date 比較晚
    expect(ctx.columns.High.map((t) => t.id)).toEqual(['order-0', 'no-order'])
  })

  it('hasTasks 反映三欄加總是否有任何任務', () => {
    const ctx = useScheduleWizard()
    ctx.initWizard([])
    expect(ctx.hasTasks.value).toBe(false)

    ctx.initWizard([fakeTask({ id: 'a', priority: 'Low' })])
    expect(ctx.hasTasks.value).toBe(true)
  })

  it('moveTask 同欄內搬動順序', () => {
    const ctx = useScheduleWizard()
    ctx.initWizard([
      fakeTask({ id: 'a', priority: 'High', sort_order: 0 }),
      fakeTask({ id: 'b', priority: 'High', sort_order: 1 }),
      fakeTask({ id: 'c', priority: 'High', sort_order: 2 }),
    ])

    ctx.moveTask('High', 2, 'High', 0) // 把 c 搬到最前面

    expect(ctx.columns.High.map((t) => t.id)).toEqual(['c', 'a', 'b'])
  })

  it('moveTask 跨欄搬動時，任務的 priority 會跟著改成目標欄', () => {
    const ctx = useScheduleWizard()
    ctx.initWizard([
      fakeTask({ id: 'a', priority: 'Low' }),
      fakeTask({ id: 'b', priority: 'High' }),
    ])

    ctx.moveTask('Low', 0, 'High', 1) // 把 a 從 Low 欄拖到 High 欄的最後面

    expect(ctx.columns.Low).toEqual([])
    expect(ctx.columns.High.map((t) => t.id)).toEqual(['b', 'a'])
    expect(ctx.columns.High.find((t) => t.id === 'a')?.priority).toBe('High')
  })

  it('confirmOrder 成功：呼叫 PUT /schedule/reorder，三欄攤平成 items 並帶上各自的 priority，並進到 step 2', async () => {
    const ctx = useScheduleWizard()
    ctx.initWizard([
      fakeTask({ id: 'low1', priority: 'Low', sort_order: 0 }),
      fakeTask({ id: 'high1', priority: 'High', sort_order: 0 }),
    ])

    await ctx.confirmOrder()

    expect(fetchSpy).toHaveBeenCalledWith(
      'http://api/schedule/reorder',
      expect.objectContaining({
        method: 'PUT',
        body: {
          items: [
            { task_id: 'low1', priority: 'Low' },
            { task_id: 'high1', priority: 'High' },
          ],
        },
        headers: { Authorization: 'Bearer jwt-token' },
      }),
    )
    expect(ctx.step.value).toBe(2)
  })

  it('confirmOrder 失敗：跳出錯誤 toast，留在 step 1', async () => {
    fetchSpy.mockRejectedValueOnce(new Error('boom'))
    const ctx = useScheduleWizard()
    ctx.initWizard([fakeTask({ id: 'a', priority: 'Low' })])

    await ctx.confirmOrder()

    expect(ctx.step.value).toBe(1)
    expect(toastSpy.add).toHaveBeenCalledWith(
      expect.objectContaining({ title: '儲存排序失敗', color: 'error' }),
    )
  })

  it('updateDueDate／updateDuration 只改動指定的任務（跨欄找得到）', () => {
    const ctx = useScheduleWizard()
    ctx.initWizard([
      fakeTask({ id: 'a', priority: 'Low' }),
      fakeTask({ id: 'b', priority: 'High' }),
    ])

    ctx.updateDueDate('a', '2026-10-01T00:00:00.000Z')
    ctx.updateDuration('a', 90)

    const taskA = ctx.columns.Low.find((t) => t.id === 'a')!
    const taskB = ctx.columns.High.find((t) => t.id === 'b')!
    expect(taskA.due_date).toBe('2026-10-01T00:00:00.000Z')
    expect(taskA.duration).toBe(90)
    expect(taskB.due_date).toBeNull()
    expect(taskB.duration).toBeNull()
  })

  it('finish 成功：把每筆任務的 due_date/duration 存回去（task_id 放 body）、呼叫 onDone', async () => {
    const ctx = useScheduleWizard()
    ctx.initWizard([fakeTask({ id: 'a', priority: 'Low', due_date: '2026-10-01T00:00:00.000Z', duration: 30 })])
    ctx.step.value = 2

    const onDone = vi.fn()
    await ctx.finish(onDone)

    expect(fetchSpy).toHaveBeenCalledWith(
      'http://api/schedule/tasks/fields',
      expect.objectContaining({
        method: 'PUT',
        body: { task_id: 'a', due_date: '2026-10-01T00:00:00.000Z', duration: 30 },
        headers: { Authorization: 'Bearer jwt-token' },
      }),
    )
    expect(onDone).toHaveBeenCalledTimes(1)
  })

  it('finish 不會送出沒有值的 due_date/duration，但仍然帶著 task_id', async () => {
    const ctx = useScheduleWizard()
    ctx.initWizard([fakeTask({ id: 'a', priority: 'Low', due_date: null })])
    ctx.step.value = 2

    await ctx.finish(vi.fn())

    expect(fetchSpy).toHaveBeenCalledWith(
      'http://api/schedule/tasks/fields',
      expect.objectContaining({ body: { task_id: 'a' } }),
    )
  })

  it('finish 失敗：跳出錯誤 toast，不呼叫 onDone', async () => {
    fetchSpy.mockRejectedValueOnce(new Error('boom'))
    const ctx = useScheduleWizard()
    ctx.initWizard([fakeTask({ id: 'a', priority: 'Low' })])
    ctx.step.value = 2

    const onDone = vi.fn()
    await ctx.finish(onDone)

    expect(onDone).not.toHaveBeenCalled()
    expect(toastSpy.add).toHaveBeenCalledWith(
      expect.objectContaining({ title: '更新任務失敗', color: 'error' }),
    )
  })
})
