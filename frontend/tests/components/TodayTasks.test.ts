// 今日卡片怎麼顯示、怎麼呼叫 composable（composable 全部 mock）；分區與排序的規則由 tests/utils/todayTasks.test.ts 負責
import { describe, it, expect, vi, beforeEach, afterEach, type MockInstance } from 'vitest'
import { mount, flushPromises, enableAutoUnmount } from '@vue/test-utils'
import { ref, defineComponent, h } from 'vue'
import type { SchedulableTask } from '~/types/schedulableTask'

import TodayTasks from '~/components/dashboard/TodayTasks.vue'

enableAutoUnmount(afterEach)

const toastSpy = { add: vi.fn() }
vi.stubGlobal('useToast', () => toastSpy)

const tasksRef = ref<SchedulableTask[]>([])
const loadingRef = ref(false)
const loadFailedRef = ref(false)
const fetchSchedulableTasksSpy = vi.fn()
const rescheduleTasksSpy = vi.fn()
const saveTaskFieldsSpy = vi.fn()
vi.mock('~/composables/useSchedulableTasks', () => ({
  useSchedulableTasks: () => ({
    tasks: tasksRef,
    loading: loadingRef,
    loadFailed: loadFailedRef,
    fetchSchedulableTasks: fetchSchedulableTasksSpy,
    rescheduleTasks: rescheduleTasksSpy,
    saveTaskFields: saveTaskFieldsSpy,
  }),
}))

const allTasksRef = ref<{ id: string; title: string }[]>([])
const startEditTaskSpy = vi.fn()
const onDeleteTaskSpy = vi.fn()
vi.mock('~/composables/useTaskForm', () => ({
  useTaskForm: () => ({ all_tasks: allTasksRef, startEditTask: startEditTaskSpy, onDeleteTask: onDeleteTaskSpy }),
}))

const REAUTH_TOAST = { title: 'Google Calendar 授權已失效' }
vi.mock('~/composables/useGoogleCalendarAuth', () => ({
  useGoogleCalendarAuth: () => ({ reauthToast: () => ({ ...REAUTH_TOAST, actions: [{ label: '重新連接 Google Calendar', onClick: vi.fn() }] }) }),
}))

const stubs = {
  UCard: defineComponent({ setup: (_, { slots }) => () => h('div', [slots.header?.(), slots.default?.()]) }),
  UButton: defineComponent({
    emits: ['click'],
    setup: (_, { slots, emit, attrs }) => () => h('button', { ...attrs, onClick: () => emit('click') }, slots.default?.()),
  }),
  UBadge: defineComponent({ setup: (_, { slots, attrs }) => () => h('span', attrs, slots.default?.()) }),
  UModal: defineComponent({ setup: (_, { slots }) => () => h('div', slots.content?.()) }),
  USkeleton: true,
  UIcon: true,
}

// 固定「現在」：2026-11-21 10:00（Asia/Taipei，vitest.config.ts）；只假造 Date，不影響 promise 與 timer
const NOW = new Date('2026-11-21T10:00:00+08:00')

function task(overrides: Partial<SchedulableTask> & { id: string }): SchedulableTask {
  return {
    source: 'manual', title: overrides.id, status: 'To Do', priority: 'Medium', duration: 30,
    due_date: null, calendar_event_id: null, scheduled_start: null, scheduled_end: null, url: null,
    ...overrides,
  }
}

const OVERDUE = { due_date: '2026-11-20T00:00:00+08:00' }
const TODAY_SLOT = { scheduled_start: '2026-11-21T14:00:00+08:00', scheduled_end: '2026-11-21T15:00:00+08:00' }

const render = () => mount(TodayTasks, { global: { stubs } })
const byTestId = (wrapper: ReturnType<typeof render>, id: string) => wrapper.findAll(`[data-testid="${id}"]`)
const toasts = () => toastSpy.add.mock.calls.map((c) => c[0] as { title: string; description?: string; actions?: unknown[] })

let confirmSpy: MockInstance<typeof window.confirm>

describe('TodayTasks.vue', () => {
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ['Date'] })
    vi.setSystemTime(NOW)
    tasksRef.value = []
    allTasksRef.value = []
    loadingRef.value = false
    loadFailedRef.value = false
    toastSpy.add.mockReset()
    for (const spy of [fetchSchedulableTasksSpy, rescheduleTasksSpy, saveTaskFieldsSpy, startEditTaskSpy, onDeleteTaskSpy]) spy.mockReset()
    confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true)
  })

  afterEach(() => {
    vi.useRealTimers()
    confirmSpy.mockRestore()
  })

  it('AC14：已逾期的任務標「已逾期」，日期文字是紅色；不是已逾期的日期文字不是紅色', () => {
    tasksRef.value = [task({ id: 'late', ...OVERDUE }), task({ id: 'ok', calendar_event_id: 'e', ...TODAY_SLOT })]

    const wrapper = render()

    const rows = byTestId(wrapper, 'today-row')
    expect(rows).toHaveLength(2)
    expect(rows[0]!.find('[data-testid="today-label"]').text()).toBe('已逾期')
    expect(rows[0]!.find('[data-testid="today-date"]').classes().join(' ')).toContain('text-red')
    expect(rows[1]!.find('[data-testid="today-label"]').text()).toBe('未開始')
    expect(rows[1]!.find('[data-testid="today-date"]').classes().join(' ')).not.toContain('text-red')
  })

  it('AC23：載入完成、沒有任何要列的任務時，顯示「今天沒有排程的任務，也沒有已逾期的任務」', () => {
    const wrapper = render()

    expect(wrapper.text()).toContain('今天沒有排程的任務，也沒有已逾期的任務')
  })

  it('AC23a：載入中時顯示載入框，不顯示 AC23 的文字', () => {
    loadingRef.value = true

    const wrapper = render()

    expect(wrapper.find('[data-testid="today-loading"]').exists()).toBe(true)
    expect(wrapper.text()).not.toContain('今天沒有排程的任務')
  })

  it('AC23b：載入失敗時顯示「暫時無法載入任務」，不顯示 AC23 的文字', () => {
    loadFailedRef.value = true

    const wrapper = render()

    expect(wrapper.text()).toContain('暫時無法載入任務')
    expect(wrapper.text()).not.toContain('今天沒有排程的任務')
  })

  it('AC24：沒完成的手動任務有「修改」「刪除」；沒完成的外部平台任務只有「修改」；已完成的任務沒有按鈕', () => {
    tasksRef.value = [
      task({ id: 'manual-a', ...OVERDUE }),
      task({ id: 'gh', source: 'github', ...OVERDUE }),
      task({ id: 'done', status: 'Done', ...TODAY_SLOT }),
    ]

    const rows = byTestId(render(), 'today-row')

    const buttons = (row: (typeof rows)[number]) => row.findAll('button').map((b) => b.text())
    expect(buttons(rows[0]!)).toEqual(['修改', '刪除'])
    expect(buttons(rows[1]!)).toEqual(['修改'])
    expect(buttons(rows[2]!)).toEqual([])
  })

  it('AC25：手動任務按「修改」，用原始 id（去掉 manual: 前綴）對應的任務呼叫 startEditTask，並帶今日卡片的標記', async () => {
    tasksRef.value = [task({ id: 'manual:t1', ...OVERDUE })]
    allTasksRef.value = [{ id: 't1', title: '完整的 t1' }]

    const wrapper = render()
    await byTestId(wrapper, 'today-edit')[0]!.trigger('click')

    expect(startEditTaskSpy).toHaveBeenCalledWith({ id: 't1', title: '完整的 t1' }, { fromToday: true })
  })

  it('AC26：外部平台任務按「修改」，打開只有截止日期與時長的表單', async () => {
    tasksRef.value = [task({ id: 'github:1', source: 'github', duration: 45, ...OVERDUE })]

    const wrapper = render()
    await byTestId(wrapper, 'today-edit')[0]!.trigger('click')

    const form = wrapper.find('[data-testid="external-form"]')
    expect(form.exists()).toBe(true)
    expect(form.findAll('input').map((i) => i.attributes('data-testid'))).toEqual(['external-due', 'external-duration'])
    expect((form.find('[data-testid="external-duration"]').element as HTMLInputElement).value).toBe('45')
    expect(startEditTaskSpy).not.toHaveBeenCalled()
  })

  it('AC27：外部平台任務有 calendar_event_id 時，表單上方顯示會移除時段的說明；沒有時不顯示', async () => {
    tasksRef.value = [
      task({ id: 'github:1', source: 'github', calendar_event_id: 'e', ...OVERDUE }),
      task({ id: 'github:2', source: 'github', ...OVERDUE }),
    ]

    const wrapper = render()
    await byTestId(wrapper, 'today-edit')[0]!.trigger('click')
    expect(wrapper.find('[data-testid="reschedule-note"]').text()).toContain('任務回到排程清單')

    await wrapper.find('[data-testid="external-form"] button').trigger('click')
    await byTestId(wrapper, 'today-edit')[1]!.trigger('click')
    expect(wrapper.find('[data-testid="reschedule-note"]').exists()).toBe(false)
  })

  async function saveExternalForm(wrapper: ReturnType<typeof render>) {
    await byTestId(wrapper, 'today-edit')[0]!.trigger('click')
    await wrapper.find('[data-testid="external-duration"]').setValue('90')
    await wrapper.find('[data-testid="external-save"]').trigger('click')
    await flushPromises()
  }

  it('AC29：外部平台任務表單儲存成功 → 先呼叫儲存欄位，再呼叫重新排程；通知只有「儲存成功」', async () => {
    tasksRef.value = [task({ id: 'github:1', source: 'github', calendar_event_id: 'e', ...OVERDUE })]
    const order: string[] = []
    saveTaskFieldsSpy.mockImplementation(async () => { order.push('save'); return true })
    rescheduleTasksSpy.mockImplementation(async () => { order.push('reschedule'); return { kind: 'success', failed: [] } })

    await saveExternalForm(render())

    expect(order).toEqual(['save', 'reschedule'])
    expect(saveTaskFieldsSpy).toHaveBeenCalledWith('github:1', expect.objectContaining({ duration: 90 }))
    expect(rescheduleTasksSpy).toHaveBeenCalledWith(['github:1'])
    expect(toasts().map((t) => t.title)).toEqual(['儲存成功'])
  })

  it('外部平台任務沒有 calendar_event_id：儲存成功後不重新排程', async () => {
    tasksRef.value = [task({ id: 'github:1', source: 'github', ...OVERDUE })]
    saveTaskFieldsSpy.mockResolvedValue(true)

    await saveExternalForm(render())

    expect(rescheduleTasksSpy).not.toHaveBeenCalled()
    expect(toasts().map((t) => t.title)).toEqual(['儲存成功'])
  })

  it('AC31：外部平台任務表單儲存失敗 → 不呼叫重新排程', async () => {
    tasksRef.value = [task({ id: 'github:1', source: 'github', calendar_event_id: 'e', ...OVERDUE })]
    saveTaskFieldsSpy.mockResolvedValue(false)

    await saveExternalForm(render())

    expect(rescheduleTasksSpy).not.toHaveBeenCalled()
  })

  it('AC32b：外部平台任務表單儲存成功、重新排程回 500 → 只有一個通知，寫「已儲存，但重新排程失敗」與錯誤訊息', async () => {
    tasksRef.value = [task({ id: 'github:1', source: 'github', calendar_event_id: 'e', ...OVERDUE })]
    saveTaskFieldsSpy.mockResolvedValue(true)
    rescheduleTasksSpy.mockResolvedValue({ kind: 'error', message: '伺服器暫時發生錯誤', failed: [] })

    await saveExternalForm(render())

    expect(toasts()).toHaveLength(1)
    expect(toasts()[0]).toMatchObject({ title: '已儲存，但重新排程失敗', description: '伺服器暫時發生錯誤' })
  })

  it('AC30：外部平台任務表單儲存成功、重新排程因授權失效失敗 → 一個通知，附重新連接按鈕', async () => {
    tasksRef.value = [task({ id: 'github:1', source: 'github', calendar_event_id: 'e', ...OVERDUE })]
    saveTaskFieldsSpy.mockResolvedValue(true)
    rescheduleTasksSpy.mockResolvedValue({ kind: 'reauth', failed: [] })

    await saveExternalForm(render())

    expect(toasts()).toHaveLength(1)
    expect(toasts()[0]!.title).toBe('已儲存，但需要重新連接 Google Calendar 才能重新排程')
    expect(toasts()[0]!.actions).toHaveLength(1)
  })

  it('AC34：按手動任務的「刪除」→ 呼叫既有的刪除流程（確認與連同 Google 日曆事件一起刪除由它負責），完成後重新抓清單', async () => {
    tasksRef.value = [task({ id: 'manual:t1', ...OVERDUE })]
    allTasksRef.value = [{ id: 't1', title: '完整的 t1' }]

    const wrapper = render()
    await byTestId(wrapper, 'today-delete')[0]!.trigger('click')
    await flushPromises()

    expect(onDeleteTaskSpy).toHaveBeenCalledWith({ id: 't1', title: '完整的 t1' })
    expect(fetchSchedulableTasksSpy).toHaveBeenCalled()
  })

  it('AC35：有已逾期、已排程的任務時顯示「批次重新排程」；沒有時不顯示', () => {
    tasksRef.value = [task({ id: 'late-unscheduled', ...OVERDUE }), task({ id: 'today', calendar_event_id: 'e', ...TODAY_SLOT })]
    expect(byTestId(render(), 'today-batch-reschedule')).toHaveLength(0)

    tasksRef.value = [task({ id: 'late', calendar_event_id: 'e', ...OVERDUE })]
    expect(byTestId(render(), 'today-batch-reschedule')).toHaveLength(1)
  })

  const batchTasks = () => [
    task({ id: 'manual:o1', title: '逾期一', calendar_event_id: 'e1', ...OVERDUE }),
    task({ id: 'manual:o2', title: '逾期二', calendar_event_id: 'e2', due_date: '2026-11-19T00:00:00+08:00' }),
    task({ id: 'manual:today', calendar_event_id: 'e3', ...TODAY_SLOT }),
  ]
  const clickBatch = async (wrapper: ReturnType<typeof render>) => {
    await byTestId(wrapper, 'today-batch-reschedule')[0]!.trigger('click')
    await flushPromises()
  }

  it('AC36：按「批次重新排程」跳出確認，寫出 N；確認後只送出已逾期、已排程的 N 個任務 id（AC51b：全部成功時通知「已把 N 個任務放回排程清單」）', async () => {
    tasksRef.value = batchTasks()
    rescheduleTasksSpy.mockResolvedValue({ kind: 'success', failed: [] })

    await clickBatch(render())

    expect(confirmSpy).toHaveBeenCalledWith('會從 Google 日曆移除 2 個任務的時段，放回排程清單，確定嗎？')
    expect(rescheduleTasksSpy).toHaveBeenCalledWith(['manual:o2', 'manual:o1'])
    expect(toasts().map((t) => t.title)).toEqual(['已把 2 個任務放回排程清單'])
  })

  it('AC36b：已逾期的階段 1 後面有排在今天、還沒逾期的階段 2 → 確認訊息另外寫「另外 1 個後面階段的時段也會一起移除」', async () => {
    tasksRef.value = [
      task({ id: 'manual:s1', parent_id: 'manual:p', stage: 1, calendar_event_id: 'e1', ...OVERDUE }),
      task({ id: 'manual:s2', parent_id: 'manual:p', stage: 2, calendar_event_id: 'e2', ...TODAY_SLOT }),
    ]
    rescheduleTasksSpy.mockResolvedValue({ kind: 'success', failed: [] })

    await clickBatch(render())

    expect(confirmSpy).toHaveBeenCalledWith(
      '會從 Google 日曆移除 1 個任務的時段，放回排程清單，確定嗎？\n另外 1 個後面階段的時段也會一起移除',
    )
    expect(rescheduleTasksSpy).toHaveBeenCalledWith(['manual:s1'])
  })

  it('AC37：確認時按取消，不呼叫 API', async () => {
    tasksRef.value = batchTasks()
    confirmSpy.mockReturnValue(false)

    await clickBatch(render())

    expect(rescheduleTasksSpy).not.toHaveBeenCalled()
    expect(toastSpy.add).not.toHaveBeenCalled()
  })

  it('AC46：批次重新排程時授權失效 → 跳出既有的重新連接提示', async () => {
    tasksRef.value = batchTasks()
    rescheduleTasksSpy.mockResolvedValue({ kind: 'reauth', failed: [] })

    await clickBatch(render())

    expect(toasts()).toHaveLength(1)
    expect(toasts()[0]!.title).toBe('Google Calendar 授權已失效')
  })

  it('AC51：批次重新排程的回應有失敗清單 → 通知列出失敗的任務名稱與原因', async () => {
    tasksRef.value = batchTasks()
    rescheduleTasksSpy.mockResolvedValue({ kind: 'success', failed: [{ task_id: 'manual:o1', reason: '編號已變更', error_code: null }] })

    await clickBatch(render())

    expect(toasts()).toHaveLength(1)
    expect(toasts()[0]!.description).toContain('「逾期一」：編號已變更')
  })

  it('AC51a：批次重新排程時 API 回 500 → 只有一個通知，含「重新排程沒有全部完成」、錯誤訊息與「請再按一次」', async () => {
    tasksRef.value = batchTasks()
    rescheduleTasksSpy.mockResolvedValue({ kind: 'error', message: '伺服器暫時發生錯誤', failed: [] })

    await clickBatch(render())

    expect(toasts()).toHaveLength(1)
    expect(toasts()[0]!.title).toBe('重新排程沒有全部完成')
    expect(toasts()[0]!.description).toContain('伺服器暫時發生錯誤')
    expect(toasts()[0]!.description).toContain('已處理的任務已放回排程清單，請再按一次處理剩下的任務')
  })
})
