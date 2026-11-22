import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ref as vueRef, reactive as vueReactive, computed as vueComputed } from 'vue'

import { useScheduleWizard } from '~/composables/useScheduleWizard'
import { defaultSchedulePreferences } from '~/types/schedule'
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
    // 共用狀態：initWizard 不再重設偏好，每個測試自己歸零
    useScheduleWizard().preferences.value = defaultSchedulePreferences()
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

  it('issue-182 AC10、AC11：initWizard 保留 preferences（精靈回到第 1 步後，第 2 步仍是畫面上填的內容，不管有沒有存成）', async () => {
    const ctx = useScheduleWizard()
    fetchSpy = vi.fn().mockResolvedValue({
      blocked_recurring: [{ days_of_week: [1], all_day: false, start_time: '09:00', end_time: '10:00' }],
      blocked_exceptions: [], buffer_minutes: 0, daily_max_minutes: null,
    })
    await ctx.loadSavedPreferences()
    ctx.preferences.value.blocked_recurring[0]!.days_of_week = [2, 3]
    ctx.addBlockedException()
    ctx.preferences.value.buffer_minutes = 30
    const edited = JSON.parse(JSON.stringify(ctx.preferences.value))

    ctx.initWizard([fakeTask({ id: 'b', priority: 'Low' })])

    expect(ctx.preferences.value).toEqual(edited)
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

    // 三種還沒填完的時段都不該送出
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

  it('issue-178 AC39：initWizard 把精靈放回第 1 步（上次停在第 3 步也一樣）', () => {
    const ctx = useScheduleWizard()
    ctx.step.value = 3

    ctx.initWizard([fakeTask({ id: 'a' })])

    expect(ctx.step.value).toBe(1)
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
        method: 'PATCH',
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

  it('initWizard 欄內排序：有 sort_order 的排前面；都沒有就照截止日，沒有截止日的排最後', () => {
    const ctx = useScheduleWizard()
    ctx.initWizard([
      fakeTask({ id: 'no-order-no-due' }),
      fakeTask({ id: 'no-order-late', due_date: '2026-12-01T00:00:00Z' }),
      fakeTask({ id: 'ordered', sort_order: 5 }),
      fakeTask({ id: 'no-order-early', due_date: '2026-10-01T00:00:00Z' }),
    ])

    expect(ctx.columns.Medium.map((t) => t.id)).toEqual([
      'ordered', 'no-order-early', 'no-order-late', 'no-order-no-due',
    ])
  })

  it('AC27：initWizard 不放主任務，只放子任務和一般任務', () => {
    const ctx = useScheduleWizard()
    ctx.initWizard([
      fakeTask({ id: 'manual:p1', priority: null, is_parent: true }),
      fakeTask({ id: 'manual:s1', priority: 'High', parent_id: 'manual:p1', stage: 1, stage_count: 1 }),
      fakeTask({ id: 'manual:plain', priority: 'Low' }),
    ])

    const ids = [...ctx.columns.Low, ...ctx.columns.Medium, ...ctx.columns.High].map((t) => t.id)
    expect(ids.sort()).toEqual(['manual:plain', 'manual:s1'])
  })
})


describe('issue-182：記住排程偏好', () => {
  const rule = (o: Record<string, unknown> = {}) => ({ days_of_week: [0], all_day: false, start_time: '12:00', end_time: '13:00', ...o })

  beforeEach(() => {
    vi.useRealTimers()
    fetchSpy = vi.fn().mockResolvedValue({})
    toastSpy.add.mockClear()
    useScheduleWizard().preferences.value = defaultSchedulePreferences()
  })

  it('AC1、AC6：loadSavedPreferences 把存的偏好帶進 preferences，時區用瀏覽器當時的', async () => {
    // 只還原這個 spy：restoreAllMocks 會把登入 mock 的回傳值也清掉
    const timeZoneSpy = vi.spyOn(Intl.DateTimeFormat.prototype, 'resolvedOptions').mockReturnValue({ timeZone: 'Asia/Tokyo' } as Intl.ResolvedDateTimeFormatOptions)
    const future = { start: '2999-01-01T09:00:00.000Z', end: '2999-01-01T10:00:00.000Z' }
    fetchSpy = vi.fn().mockResolvedValue({
      blocked_recurring: [rule()], blocked_exceptions: [future], buffer_minutes: 15, daily_max_minutes: 240,
    })
    const ctx = useScheduleWizard()

    await ctx.loadSavedPreferences()
    timeZoneSpy.mockRestore()

    expect(fetchSpy.mock.calls[0]![0]).toBe('http://api/users/me/schedule-preferences')
    expect(ctx.preferences.value).toEqual({
      blocked_recurring: [rule()], blocked_exceptions: [future], buffer_minutes: 15, daily_max_minutes: 240,
      timezone: 'Asia/Tokyo',
    })
  })

  it('AC3：沒存過偏好（後端回預設值）→ preferences 是空白預設值', async () => {
    fetchSpy = vi.fn().mockResolvedValue({ blocked_recurring: [], blocked_exceptions: [], buffer_minutes: 0, daily_max_minutes: null })
    const ctx = useScheduleWizard()

    await ctx.loadSavedPreferences()

    expect(ctx.preferences.value).toEqual({
      blocked_recurring: [], blocked_exceptions: [], buffer_minutes: 0, daily_max_minutes: null,
      timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
    })
  })

  it('AC9：帶入時拿掉結束時間已過的一次性例外，每週規律一律保留', async () => {
    vi.useFakeTimers({ toFake: ['Date'] })
    vi.setSystemTime(new Date('2030-06-01T12:00:00Z'))
    const past = { start: '2030-06-01T09:00:00.000Z', end: '2030-06-01T10:00:00.000Z' }
    const notYet = { start: '2030-06-01T13:00:00.000Z', end: '2030-06-01T14:00:00.000Z' }
    fetchSpy = vi.fn().mockResolvedValue({
      blocked_recurring: [rule()], blocked_exceptions: [past, notYet], buffer_minutes: 0, daily_max_minutes: null,
    })
    const ctx = useScheduleWizard()

    await ctx.loadSavedPreferences()

    expect(ctx.preferences.value.blocked_exceptions).toEqual([notYet])
    expect(ctx.preferences.value.blocked_recurring).toEqual([rule()])
  })

  it('AC15、AC16：讀取失敗 → preferences 是空白預設值，跳「讀不到上次的排程偏好，請重新填寫」', async () => {
    fetchSpy = vi.fn().mockRejectedValue(new Error('boom'))
    const ctx = useScheduleWizard()
    ctx.preferences.value.buffer_minutes = 99

    await ctx.loadSavedPreferences()

    expect(ctx.preferences.value.buffer_minutes).toBe(0)
    expect(ctx.preferences.value.blocked_recurring).toEqual([])
    expect(toastSpy.add).toHaveBeenCalledTimes(1)
    expect(JSON.stringify(toastSpy.add.mock.calls[0]![0])).toContain('讀不到上次的排程偏好，請重新填寫')
  })

  it('AC4、AC5：savePreferences 用 PUT 送出只有填完整的時段、不含時區的內容', async () => {
    const ctx = useScheduleWizard()
    ctx.preferences.value = {
      blocked_recurring: [rule({ days_of_week: [] }), rule()],
      blocked_exceptions: [], buffer_minutes: 15, daily_max_minutes: 240, timezone: 'Asia/Taipei',
    }

    await ctx.savePreferences()

    const [url, opts] = fetchSpy.mock.calls[0]!
    expect(url).toBe('http://api/users/me/schedule-preferences')
    expect(opts.method).toBe('PUT')
    expect(opts.body).toEqual({
      blocked_recurring: [rule()], blocked_exceptions: [], buffer_minutes: 15, daily_max_minutes: 240,
    })
  })

  it('AC13、AC14：存偏好失敗不丟例外，跳「排程偏好沒有存成功，下次要重新填」', async () => {
    fetchSpy = vi.fn().mockRejectedValue(new Error('boom'))
    const ctx = useScheduleWizard()

    await expect(ctx.savePreferences()).resolves.toBeUndefined()

    expect(toastSpy.add).toHaveBeenCalledTimes(1)
    expect(JSON.stringify(toastSpy.add.mock.calls[0]![0])).toContain('排程偏好沒有存成功，下次要重新填')
  })

  it('AC30：勾了整天的規律送出時一律是 00:00、23:59，畫面上的規律物件不變', async () => {
    const ctx = useScheduleWizard()
    ctx.preferences.value.blocked_recurring = [
      { days_of_week: [1], all_day: true, start_time: '', end_time: null },
    ]
    const expected = [{ days_of_week: [1], all_day: true, start_time: '00:00', end_time: '23:59' }]

    expect(ctx.sanitizedPreferences.value.blocked_recurring).toEqual(expected)
    await ctx.savePreferences()

    expect(fetchSpy.mock.calls[0]![1].body.blocked_recurring).toEqual(expected)
    expect(ctx.preferences.value.blocked_recurring[0]).toEqual(
      { days_of_week: [1], all_day: true, start_time: '', end_time: null },
    )
  })

  it('AC31、AC32：toggleAllDay 勾選時起訖變 00:00、23:59，取消勾選時清成 null', () => {
    const ctx = useScheduleWizard()
    const r = { days_of_week: [1], all_day: false, start_time: '09:00' as string | null, end_time: '10:00' as string | null }

    ctx.toggleAllDay(r, true)
    expect(r).toEqual({ days_of_week: [1], all_day: true, start_time: '00:00', end_time: '23:59' })

    ctx.toggleAllDay(r, false)
    expect(r).toEqual({ days_of_week: [1], all_day: false, start_time: null, end_time: null })
  })

  it('AC33：帶入的整天規律取消勾選後，起訖時間變成空白', async () => {
    fetchSpy = vi.fn().mockResolvedValue({
      blocked_recurring: [rule({ all_day: true, start_time: '00:00', end_time: '23:59' })],
      blocked_exceptions: [], buffer_minutes: 0, daily_max_minutes: null,
    })
    const ctx = useScheduleWizard()
    await ctx.loadSavedPreferences()

    ctx.toggleAllDay(ctx.preferences.value.blocked_recurring[0]!, false)

    expect(ctx.preferences.value.blocked_recurring[0]).toEqual(
      { days_of_week: [0], all_day: false, start_time: null, end_time: null },
    )
  })
})
