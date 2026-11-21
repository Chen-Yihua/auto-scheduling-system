import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { mount, enableAutoUnmount } from '@vue/test-utils';
import { ref as vueRef, reactive as vueReactive, computed as vueComputed, h, defineComponent } from 'vue'

import SchedulePage from '~/pages/schedule.vue'
import type { SchedulableTask } from '~/types/schedulableTask'
import type { RemovedCalendarEvent } from '~/types/schedule'

const isSignedInRef = vueRef<boolean | undefined>(true)
vi.mock('@clerk/vue', () => ({
  useUser: () => ({ isSignedIn: isSignedInRef }),
}))

const toastSpy = { add: vi.fn() }
vi.stubGlobal('useToast', () => toastSpy)


const schedulableTasksRef = vueRef<SchedulableTask[]>([])
const loadFailedRef = vueRef(false)
const fetchSchedulableTasksSpy = vi.fn()
vi.mock('~/composables/useSchedulableTasks', () => ({
  useSchedulableTasks: () => ({ tasks: schedulableTasksRef, loadFailed: loadFailedRef, fetchSchedulableTasks: fetchSchedulableTasksSpy }),
}));

const fetchGoogleCalendarsSpy = vi.fn()
vi.mock('~/composables/useGoogleCalendar', () => ({
  useGoogleCalendar: () => ({ fetchGoogleCalendars: fetchGoogleCalendarsSpy }),
}))

const REAUTH_TOAST = { title: 'Google Calendar 授權已失效' }
const goToGoogleAuthSpy = vi.fn()
vi.mock('~/composables/useGoogleCalendarAuth', () => ({
  useGoogleCalendarAuth: () => ({ reauthToast: () => REAUTH_TOAST, goToGoogleAuth: goToGoogleAuthSpy }),
}))

const removedItemsRef = vueRef<RemovedCalendarEvent[]>([])
const fetchRemovedEventsSpy = vi.fn()
const resolveRemovedEventsSpy = vi.fn()
vi.mock('~/composables/useRemovedCalendarEvents', () => ({
  useRemovedCalendarEvents: () => ({
    items: removedItemsRef,
    fetchRemovedEvents: fetchRemovedEventsSpy,
    resolveRemovedEvents: resolveRemovedEventsSpy,
  }),
}))

const fetchScheduleSuggestionSpy = vi.fn()
vi.mock('~/composables/useSchedule', () => ({
  useSchedule: () => ({ fetchScheduleSuggestion: fetchScheduleSuggestionSpy }),
}))

const stepRef = vueRef<1 | 2 | 3>(1)
const savingRef = vueRef(false)
const columnsRef = vueReactive<Record<'Low' | 'Medium' | 'High', SchedulableTask[]>>({ Low: [], Medium: [], High: [] })
const preferencesRef = vueRef({
  blocked_recurring: [] as { days_of_week: number[]; all_day: boolean; start_time: string | null; end_time: string | null }[],
  blocked_exceptions: [] as { start: string; end: string }[],
  buffer_minutes: 0,
  daily_max_minutes: null as number | null,
})
const initWizardSpy = vi.fn()
const addNewTasksSpy = vi.fn()
const moveTaskSpy = vi.fn()
const confirmOrderSpy = vi.fn()
const backToStep1Spy = vi.fn()
const updateDueDateSpy = vi.fn()
const updateDurationSpy = vi.fn()
const finishSpy = vi.fn()
const addBlockedRecurringRuleSpy = vi.fn()
const removeBlockedRecurringRuleSpy = vi.fn()
const addBlockedExceptionSpy = vi.fn()
const removeBlockedExceptionSpy = vi.fn()

vi.mock('~/composables/useScheduleWizard', () => ({
  PRIORITIES: ['Low', 'Medium', 'High'],
  useScheduleWizard: () => ({
    step: stepRef,
    saving: savingRef,
    columns: columnsRef,
    preferences: preferencesRef,
    sanitizedPreferences: vueComputed(() => preferencesRef.value),
    hasTasks: vueComputed(() => (['Low', 'Medium', 'High'] as const).some((p) => columnsRef[p].length > 0)),
    initWizard: initWizardSpy,
    addNewTasks: addNewTasksSpy,
    moveTask: moveTaskSpy,
    confirmOrder: confirmOrderSpy,
    backToStep1: backToStep1Spy,
    updateDueDate: updateDueDateSpy,
    updateDuration: updateDurationSpy,
    finish: finishSpy,
    addBlockedRecurringRule: addBlockedRecurringRuleSpy,
    removeBlockedRecurringRule: removeBlockedRecurringRuleSpy,
    addBlockedException: addBlockedExceptionSpy,
    removeBlockedException: removeBlockedExceptionSpy,
  }),
}))

// 第 3 步的排程建議：只留「重新產生」通知精靈
const ScheduleSuggestionStub = defineComponent({
  name: 'ScheduleSuggestion',
  emits: ['regenerate'],
  setup: (_p, { emit }) => () => h('button', { 'data-testid': 'suggestion', onClick: () => emit('regenerate') }, '重新產生'),
})
const AppHeaderStub = defineComponent({ name: 'AppHeader', setup: () => () => h('div') })
const LoginRequiredCardStub = defineComponent({
  name: 'LoginRequiredCard',
  props: ['title', 'icon', 'message'],
  setup: (props) => () => h('div', props.message),
})
const UButtonStub = defineComponent({
  name: 'UButton',
  setup(_props, { slots, attrs }) {
    return () => h('button', attrs, slots.default?.())
  },
})

const uiStubs = {
  AppHeader: AppHeaderStub,
  ScheduleSuggestion: ScheduleSuggestionStub,
  LoginRequiredCard: LoginRequiredCardStub,
  UIcon: true,
  UBadge: { template: '<span><slot /></span>' },
  UButton: UButtonStub,
  USkeleton: true,
}

function fakeTask(overrides: Partial<SchedulableTask> = {}): SchedulableTask {
  return {
    id: 'manual:t1', source: 'manual', title: '任務', status: 'To Do',
    priority: 'Medium', due_date: null, duration: null, sort_order: null,
    calendar_event_id: null, url: null,
    ...overrides,
  }
}

let confirmSpy = vi.fn((_message?: string) => true)

// 掛載後要等連接狀態與已刪除事件的查詢回來，精靈才顯示
async function render() {
  const wrapper = mount(SchedulePage, { global: { stubs: uiStubs } })
  await flushMicrotasks()
  return wrapper
}

// 沒卸載的頁面會繼續 watch 共用的 isSignedIn，下一個測試改它時又初始化一次
enableAutoUnmount(afterEach)

describe('pages/schedule.vue', () => {
  beforeEach(() => {
    isSignedInRef.value = true
    stepRef.value = 1
    savingRef.value = false
    columnsRef.Low = []
    columnsRef.Medium = []
    columnsRef.High = []
    preferencesRef.value = { blocked_recurring: [], blocked_exceptions: [], buffer_minutes: 0, daily_max_minutes: null }
    schedulableTasksRef.value = []
    addNewTasksSpy.mockClear()
    fetchScheduleSuggestionSpy.mockReset()
    toastSpy.add.mockClear()
    // mockReset：其他測試設的 mockImplementation 會在掛載時改掉 schedulableTasksRef
    loadFailedRef.value = false
    fetchSchedulableTasksSpy.mockReset()
    fetchScheduleSuggestionSpy.mockClear()
    initWizardSpy.mockClear()
    moveTaskSpy.mockClear()
    confirmOrderSpy.mockClear()
    backToStep1Spy.mockClear()
    updateDueDateSpy.mockClear()
    updateDurationSpy.mockClear()
    finishSpy.mockClear()
    addBlockedRecurringRuleSpy.mockClear()
    removeBlockedRecurringRuleSpy.mockClear()
    addBlockedExceptionSpy.mockClear()
    removeBlockedExceptionSpy.mockClear()
    fetchGoogleCalendarsSpy.mockReset()
    fetchGoogleCalendarsSpy.mockResolvedValue('connected')
    goToGoogleAuthSpy.mockClear()
    removedItemsRef.value = []
    fetchRemovedEventsSpy.mockReset()
    fetchRemovedEventsSpy.mockResolvedValue('ok')
    resolveRemovedEventsSpy.mockReset()
    confirmSpy = vi.fn(() => true)
    window.confirm = confirmSpy
  })

  it('AC40：未登入時顯示「排程精靈」登入提示，不會抓任務', async () => {
    isSignedInRef.value = false
    const wrapper = await render()

    expect(wrapper.text()).toContain('登入後即可使用排程精靈')
    expect(fetchSchedulableTasksSpy).not.toHaveBeenCalled()
  })

  it('掛載時抓統一任務清單並初始化精靈', async () => {
    const tasks = [fakeTask()]
    fetchSchedulableTasksSpy.mockImplementation(() => { schedulableTasksRef.value = tasks })

    await render()

    expect(fetchSchedulableTasksSpy).toHaveBeenCalledTimes(1)
    expect(initWizardSpy).toHaveBeenCalledWith(tasks)
  })

  it('step 1：三欄渲染各自的任務', async () => {
    columnsRef.Low = [fakeTask({ id: 'low1', title: '低優先任務' })]
    columnsRef.High = [fakeTask({ id: 'high1', title: '高優先任務' })]

    const wrapper = await render()

    expect(wrapper.text()).toContain('低優先任務')
    expect(wrapper.text()).toContain('高優先任務')
  })

  it('step 1：外部平台項目（例如 GitHub）會顯示對應的來源圖示', async () => {
    columnsRef.High = [fakeTask({ id: 'github:42', source: 'github', title: 'GitHub Issue' })]

    const wrapper = await render()

    expect(wrapper.html()).toContain('mdi:github')
  })

  it('AC1：重新整理時 Clerk 還沒載入完（isSignedIn 是 undefined），等它變成 true 才抓任務並初始化精靈，只做一次', async () => {
    isSignedInRef.value = undefined
    const tasks = [fakeTask()]
    fetchSchedulableTasksSpy.mockImplementation(() => { schedulableTasksRef.value = tasks })

    const wrapper = await render()
    expect(fetchSchedulableTasksSpy).not.toHaveBeenCalled()
    expect(wrapper.findAll('[data-testid="wizard-empty"]')).toHaveLength(0)

    isSignedInRef.value = true
    await flushMicrotasks()
    isSignedInRef.value = false
    isSignedInRef.value = true
    await flushMicrotasks()

    expect(fetchSchedulableTasksSpy).toHaveBeenCalledTimes(1)
    expect(initWizardSpy).toHaveBeenCalledWith(tasks)
  })

  describe('第 1 步沒有可排程的任務', () => {
    it('AC2、AC4、schedule-index AC36：不顯示三欄，改顯示說明（寫明已逾期的任務可以在今日卡片重新排程），沒有「回首頁」按鈕', async () => {
      schedulableTasksRef.value = [fakeTask({ id: 'a', calendar_event_id: 'e' })]

      const wrapper = await render()

      expect(wrapper.text()).not.toContain('拖任務到這裡')
      expect(wrapper.text()).toContain('今日卡片')
      expect(wrapper.text()).toContain('重新排程')
      expect(wrapper.findAll('button').find((b) => b.text() === '回首頁')).toBeUndefined()
    })

    it('AC3：5 個已排進日曆、2 個已完成的任務 → 說明寫出「5」個已排進 Google 日曆、「2」個已完成', async () => {
      schedulableTasksRef.value = [
        ...Array.from({ length: 5 }, (_, i) => fakeTask({ id: `s${i}`, calendar_event_id: `e${i}` })),
        ...Array.from({ length: 2 }, (_, i) => fakeTask({ id: `d${i}`, status: 'Done' })),
        // 主任務不算
        fakeTask({ id: 'parent', is_parent: true, calendar_event_id: 'ep' }),
      ]
      fetchSchedulableTasksSpy.mockImplementation(() => {})

      const text = (await render()).get('[data-testid="wizard-empty"]').text()

      expect(text).toContain('已排進 Google 日曆的任務：5 個')
      expect(text).toContain('已完成的任務：2 個')
    })

    it('AC5：沒有任何非主任務的任務 → 只顯示「目前沒有任務」，不列數字', async () => {
      schedulableTasksRef.value = [fakeTask({ id: 'parent', is_parent: true })]

      const text = (await render()).get('[data-testid="wizard-empty"]').text()

      expect(text).toContain('目前沒有任務')
      expect(text).not.toMatch(/\d/)
      expect(text).not.toContain('今日卡片')
    })
  })

  it('AC5a、AC36：進入精靈時任務清單載入失敗 → 顯示「暫時無法載入任務」，沒有「回首頁」按鈕，不顯示 AC2–AC5 的說明', async () => {
    schedulableTasksRef.value = []
    fetchSchedulableTasksSpy.mockImplementation(() => { loadFailedRef.value = true })

    const wrapper = await render()

    const text = wrapper.get('[data-testid="wizard-empty"]').text()
    expect(text).toContain('暫時無法載入任務')
    expect(text).not.toContain('目前沒有任務')
    expect(text).not.toContain('今日卡片')
    expect(wrapper.findAll('button').find((b) => b.text() === '回首頁')).toBeUndefined()
  })

  it('AC6：有可排程的任務時照常顯示三欄', async () => {
    columnsRef.Low = [fakeTask({ id: 'low1', title: '低優先任務' })]

    const wrapper = await render()

    expect(wrapper.findAll('[data-testid="wizard-empty"]')).toHaveLength(0)
    expect(wrapper.text()).toContain('低優先任務')
  })

  it('step 1：拖曳一列到另一欄 → 呼叫 moveTask(fromColumn, fromIndex, toColumn, toIndex)', async () => {
    columnsRef.Low = [fakeTask({ id: 'low1' })]
    columnsRef.High = [fakeTask({ id: 'high1' })]

    const wrapper = await render()
    const rows = wrapper.findAll('.cursor-move')
    await rows[0]!.trigger('dragstart') // low1，Low 欄 index 0
    await rows[1]!.trigger('drop') // 丟到 high1 那一列，High 欄 index 0

    expect(moveTaskSpy).toHaveBeenCalledWith('Low', 0, 'High', 0)
  })

  it('step 1：按「下一步」呼叫 confirmOrder；AC35：沒有「取消」按鈕', async () => {
    columnsRef.Low = [fakeTask({ id: 'low1' })]
    const wrapper = await render()

    await wrapper.findAll('button').find((b) => b.text() === '下一步')!.trigger('click')
    expect(confirmOrderSpy).toHaveBeenCalledTimes(1)

    expect(wrapper.findAll('button').find((b) => b.text() === '取消')).toBeUndefined()
  });

  it('step 2：顯示可編輯欄位，改動會呼叫 updateDueDate／updateDuration', async () => {
    stepRef.value = 2
    columnsRef.Medium = [fakeTask({ id: 'a', title: '任務 A', due_date: '2026-10-01T09:00:00Z', duration: 30 })]
    const wrapper = await render();

    expect(wrapper.text()).toContain('任務 A')

    // 前兩個 number input 是偏好設定，第三個才是任務時長
    const durationInput = wrapper.findAll('input[type="number"]')[2]
    await durationInput!.setValue('60')
    expect(updateDurationSpy).toHaveBeenCalledWith('a', 60)

    const dateInput = wrapper.find('input[type="datetime-local"]')
    await dateInput.setValue('2026-10-05T10:00')
    expect(updateDueDateSpy).toHaveBeenCalledWith('a', new Date('2026-10-05T10:00').toISOString())
  })

  it('step 2、AC31：按「上一步」呼叫 backToStep1；按「確認並產生排程建議」完成後抓排程建議，同一頁進到第 3 步', async () => {
    stepRef.value = 2
    columnsRef.Medium = [fakeTask({ id: 'a' })]
    finishSpy.mockImplementation(async (onDone: () => Promise<void>) => {
      await onDone()
    })
    const wrapper = await render()

    await wrapper.findAll('button').find((b) => b.text() === '上一步')!.trigger('click')
    expect(backToStep1Spy).toHaveBeenCalledTimes(1)

    await wrapper.findAll('button').find((b) => b.text() === '確認並產生排程建議')!.trigger('click')
    expect(finishSpy).toHaveBeenCalledTimes(1)
    expect(fetchScheduleSuggestionSpy).toHaveBeenCalledWith(preferencesRef.value)
    expect(stepRef.value).toBe(3)
  })

  it('AC30：已登入、已連接、沒有已刪除的事件時，直接顯示第 1 步的三欄，沒有排程建議的內容', async () => {
    columnsRef.Low = [fakeTask({ id: 'low1', title: '低優先任務' })]

    const wrapper = await render()

    expect(wrapper.text()).toContain('低優先任務')
    expect(wrapper.find('[data-testid="suggestion"]').exists()).toBe(false)
  })

  it('AC31、AC32：第 3 步顯示排程建議的內容（確認排程由它負責），沒有三欄', async () => {
    stepRef.value = 3
    columnsRef.Medium = [fakeTask({ id: 'a', title: '任務 A' })]

    const wrapper = await render()

    expect(wrapper.find('[data-testid="suggestion"]').exists()).toBe(true)
    expect(wrapper.text()).not.toContain('任務 A')
  })

  it('AC33：第 3 步按「重新產生」，重新讀任務並回到第 1 步（initWizard）', async () => {
    stepRef.value = 3
    const tasks = [fakeTask({ id: 'a' })]
    fetchSchedulableTasksSpy.mockImplementation(() => { schedulableTasksRef.value = tasks })
    const wrapper = await render()
    initWizardSpy.mockClear()
    fetchSchedulableTasksSpy.mockClear()

    await wrapper.get('[data-testid="suggestion"]').trigger('click')
    await flushMicrotasks()

    expect(fetchSchedulableTasksSpy).toHaveBeenCalledTimes(1)
    expect(initWizardSpy).toHaveBeenCalledWith(tasks)
  })

  it('AC37：共用狀態裡已有上次沒確認的建議，打開排程頁時從頭開始（initWizard 把精靈放回第 1 步），不顯示建議', async () => {
    // 真正回到第 1 步由 initWizard 負責（useScheduleWizard.test.ts）；這裡確認每次打開都呼叫它，而且不看 useSchedule 的狀態
    columnsRef.Low = [fakeTask({ id: 'low1', title: '低優先任務' })]

    const wrapper = await render()

    expect(initWizardSpy).toHaveBeenCalledTimes(1)
    expect(wrapper.find('[data-testid="suggestion"]').exists()).toBe(false)
  })

  it('AC38、AC39：任務列表多出新任務時，只有第 1 步會呼叫 addNewTasks；第 2、3 步不處理', async () => {
    columnsRef.Low = [fakeTask({ id: 'low1' })]
    await render()
    addNewTasksSpy.mockClear()
    const withNew = [fakeTask({ id: 'new', priority: 'High' })]

    schedulableTasksRef.value = withNew
    await flushMicrotasks()
    expect(addNewTasksSpy).toHaveBeenCalledWith(withNew)

    addNewTasksSpy.mockClear()
    for (const step of [2, 3] as const) {
      stepRef.value = step
      schedulableTasksRef.value = [fakeTask({ id: `new-${step}` })]
      await flushMicrotasks()
    }
    expect(addNewTasksSpy).not.toHaveBeenCalled()
  })

  describe('step 2：排程偏好設定', () => {
    beforeEach(() => {
      stepRef.value = 2
    })

    it('按「新增規律」「新增例外時段」呼叫對應的 composable 方法', async () => {
      const wrapper = await render()

      await wrapper.findAll('button').find((b) => b.text() === '新增規律')!.trigger('click')
      expect(addBlockedRecurringRuleSpy).toHaveBeenCalledTimes(1)

      await wrapper.findAll('button').find((b) => b.text() === '新增例外時段')!.trigger('click')
      expect(addBlockedExceptionSpy).toHaveBeenCalledTimes(1)
    })

    it('每週固定規律：顯示星期切換鈕跟「整天」checkbox，按「移除」呼叫 removeBlockedRecurringRule', async () => {
      preferencesRef.value.blocked_recurring = [{ days_of_week: [5], all_day: false, start_time: '22:00', end_time: '08:00' }]
      const wrapper = await render()

      expect(wrapper.findAll('input[type="time"]').length).toBe(2) // 沒勾整天才顯示起訖時間

      await wrapper.findAll('button').find((b) => b.text() === '移除')!.trigger('click')
      expect(removeBlockedRecurringRuleSpy).toHaveBeenCalledWith(0)
    })

    it('這次額外的例外時段：顯示起訖時間輸入框，按「移除」呼叫 removeBlockedException', async () => {
      preferencesRef.value.blocked_exceptions = [{ start: '2026-10-01T09:00:00.000Z', end: '2026-10-01T10:00:00.000Z' }]
      const wrapper = await render()

      expect(wrapper.findAll('input[type="datetime-local"]').length).toBe(2) // 例外時段起訖 2 個

      await wrapper.findAll('button').find((b) => b.text() === '移除')!.trigger('click')
      expect(removeBlockedExceptionSpy).toHaveBeenCalledWith(0)
    });

    it('緩衝時間跟每天上限分鐘數會綁定到 preferences', async () => {
      const wrapper = await render()

      const bufferInput = wrapper.find('input[type="number"]')
      await bufferInput.setValue(20)
      expect(preferencesRef.value.buffer_minutes).toBe(20)
    })
  })

  it('step 1：拖到某一欄的空白處 → 放到那一欄的最後面', async () => {
    columnsRef.Low = [fakeTask({ id: 'low1' })]
    columnsRef.High = [fakeTask({ id: 'high1' }), fakeTask({ id: 'high2' })]

    const wrapper = await render()
    await wrapper.findAll('.cursor-move')[0]!.trigger('dragstart') // low1
    // 三欄依 Low／Medium／High 排列，欄位容器是帶 min-h 的那層
    const columns = wrapper.findAll('[class*="min-h-"]')
    await columns[2]!.trigger('drop')

    expect(moveTaskSpy).toHaveBeenCalledWith('Low', 0, 'High', 2)
  })

  it('step 2：清空截止日或所需時長時，送出的是 null，不是空字串或 NaN', async () => {
    stepRef.value = 2
    columnsRef.Medium = [fakeTask({ id: 'a', due_date: '2026-10-01T09:00:00Z', duration: 30 })]
    const wrapper = await render()

    await wrapper.find('input[type="datetime-local"]').setValue('')
    expect(updateDueDateSpy).toHaveBeenCalledWith('a', null)

    await wrapper.findAll('input[type="number"]')[2]!.setValue('')
    expect(updateDurationSpy).toHaveBeenCalledWith('a', null)
  })

  // ---------- 階段任務 ----------

  const stage = (n: number, priority: 'Low' | 'Medium' | 'High') => fakeTask({
    id: `manual:s${n}`, title: `階段任務${n}`, priority,
    parent_id: 'manual:p1', parent_title: '期末報告', stage: n, stage_count: 2,
  })

  it('AC27：子任務標上主任務名稱和「階段 k/N」', async () => {
    columnsRef.Medium = [stage(1, 'Medium'), stage(2, 'Medium')]
    schedulableTasksRef.value = [...columnsRef.Medium]

    const wrapper = await render()

    expect(wrapper.text()).toContain('期末報告 · 階段 2/2')
  })

  it('AC27：拖到別欄會讓後面的階段優先序高於前面的階段 → 擋下並提示原因，不移動', async () => {
    columnsRef.Medium = [stage(1, 'Medium'), stage(2, 'Medium')]
    schedulableTasksRef.value = [...columnsRef.Medium]

    const wrapper = await render()
    await wrapper.findAll('.cursor-move')[1]!.trigger('dragstart') // 階段 2
    await wrapper.findAll('[class*="min-h-"]')[2]!.trigger('drop') // 丟到 High 欄

    expect(moveTaskSpy).not.toHaveBeenCalled()
    expect(toastSpy.add).toHaveBeenCalledWith(expect.objectContaining({ description: expect.stringContaining('階段 2') }))
  })

  it('AC27：同一欄內把後面的階段拖到前面的階段上面 → 擋下並提示原因', async () => {
    columnsRef.Medium = [stage(1, 'Medium'), stage(2, 'Medium')]
    schedulableTasksRef.value = [...columnsRef.Medium]

    const wrapper = await render()
    const rows = wrapper.findAll('.cursor-move')
    await rows[1]!.trigger('dragstart') // 階段 2
    await rows[0]!.trigger('drop') // 丟到階段 1 上面

    expect(moveTaskSpy).not.toHaveBeenCalled()
    expect(toastSpy.add).toHaveBeenCalledTimes(1)
  })

  it('AC27：把前面的階段拖到比後面階段更低的欄 → 擋下並提示原因，不移動', async () => {
    columnsRef.Medium = [stage(1, 'Medium'), stage(2, 'Medium')]
    schedulableTasksRef.value = [...columnsRef.Medium]

    const wrapper = await render()
    await wrapper.findAll('.cursor-move')[0]!.trigger('dragstart') // 階段 1
    await wrapper.findAll('[class*="min-h-"]')[0]!.trigger('drop') // 丟到 Low 欄

    expect(moveTaskSpy).not.toHaveBeenCalled()
    expect(toastSpy.add).toHaveBeenCalledWith(expect.objectContaining({ description: expect.stringContaining('階段 2') }))
  })

  it('AC27：不違反階段限制的拖拉照常移動（後面的階段拖到較低的欄）', async () => {
    columnsRef.Medium = [stage(1, 'Medium'), stage(2, 'Medium')]
    schedulableTasksRef.value = [...columnsRef.Medium]

    const wrapper = await render()
    await wrapper.findAll('.cursor-move')[1]!.trigger('dragstart')
    await wrapper.findAll('[class*="min-h-"]')[0]!.trigger('drop') // 丟到 Low 欄

    expect(moveTaskSpy).toHaveBeenCalledWith('Medium', 1, 'Low', 0)
    expect(toastSpy.add).not.toHaveBeenCalled()
  })
})


// ---------- issue-42：處理在 Google 日曆上被刪除的事件 ----------

const NOT_CONNECTED_TEXT = 'Google Calendar 未連接或授權已失效，請前往 帳號設定 連接。'
const STEP1_HINT = '把任務拖到對應的優先權欄位'
const RESOLVE_FAILED = '處理失敗，請重試'

function removedItem(overrides: Partial<RemovedCalendarEvent> = {}): RemovedCalendarEvent {
  return {
    id: 'manual:t1', source: 'manual', title: '任務', status: 'To Do',
    priority: 'Medium', due_date: null, duration: null, sort_order: null,
    calendar_event_id: 'ev-1', url: null, later_stages: [],
    ...overrides,
  }
}

function removedStage(n: number, overrides: Partial<RemovedCalendarEvent> = {}) {
  return removedItem({
    id: `manual:s${n}`, title: `階段任務${n}`, parent_id: 'manual:p1', parent_title: '期末報告',
    stage: n, stage_count: 2, ...overrides,
  })
}

// 每次查詢依序回傳一組結果；結果是字串時代表查詢失敗
function removedQueries(...results: (RemovedCalendarEvent[] | 'reauth' | 'error')[]) {
  for (const result of results) {
    fetchRemovedEventsSpy.mockImplementationOnce(async () => {
      if (typeof result === 'string') return result
      removedItemsRef.value = result
      return 'ok'
    })
  }
}

type Wrapper = Awaited<ReturnType<typeof render>>

const buttonByText = (wrapper: Wrapper, text: string) => wrapper.findAll('button').find((b) => b.text() === text)

const checkedStates = (wrapper: Wrapper) =>
  wrapper.findAll('input[type="checkbox"]').map((b) => (b.element as HTMLInputElement).checked)

async function clickNext(wrapper: Wrapper) {
  await buttonByText(wrapper, '下一步')!.trigger('click')
  await flushMicrotasks()
}

describe('pages/schedule.vue：issue-42 處理已刪除的事件', () => {
  beforeEach(() => {
    isSignedInRef.value = true
    stepRef.value = 1
    columnsRef.Low = []
    // 精靈有可排程的任務才顯示拖拉排序；沒有任務時顯示說明
    columnsRef.Medium = [fakeTask({ id: 'wizard-task' })]
    columnsRef.High = []
    schedulableTasksRef.value = []
    toastSpy.add.mockClear()
    fetchSchedulableTasksSpy.mockReset()
    initWizardSpy.mockClear()
    fetchGoogleCalendarsSpy.mockReset()
    fetchGoogleCalendarsSpy.mockResolvedValue('connected')
    goToGoogleAuthSpy.mockClear()
    removedItemsRef.value = []
    fetchRemovedEventsSpy.mockReset()
    fetchRemovedEventsSpy.mockResolvedValue('ok')
    resolveRemovedEventsSpy.mockReset()
    confirmSpy = vi.fn(() => true)
    window.confirm = confirmSpy
  })

  it('AC1：有事件被刪除的任務時，精靈先顯示「處理已刪除的事件」步驟並列出它，還不顯示拖拉排序', async () => {
    removedQueries([removedItem({ title: '被刪掉的任務' })])

    const wrapper = await render()

    expect(wrapper.text()).toContain('處理已刪除的事件')
    expect(wrapper.text()).toContain('被刪掉的任務')
    expect(wrapper.text()).not.toContain(STEP1_HINT)
  })

  it('AC4：沒有事件被刪除的項目時，不出現這一步，從拖拉排序開始', async () => {
    const wrapper = await render()

    expect(wrapper.text()).not.toContain('處理已刪除的事件')
    expect(wrapper.text()).toContain(STEP1_HINT)
  })

  it('AC5：每一項顯示標題與「Google 日曆上的事件已被刪除」；階段任務另外顯示主任務名稱與「階段 k/N」', async () => {
    removedQueries([removedItem({ title: '一般任務' }), removedStage(2, { id: 'manual:s2', stage_count: 3 })])

    const wrapper = await render()

    expect(wrapper.text()).toContain('一般任務')
    expect(wrapper.text().match(/Google 日曆上的事件已被刪除/g)).toHaveLength(2)
    expect(wrapper.text()).toContain('期末報告 · 階段 2/3')
  })

  it('AC6：勾選框預設全部勾選；外部項目的勾選框不能取消，並顯示「外部平台的項目會重新排程」', async () => {
    removedQueries([removedItem(), removedItem({ id: 'github:42', source: 'github', title: 'GitHub Issue' })])

    const wrapper = await render()
    const boxes = wrapper.findAll('input[type="checkbox"]')

    expect(checkedStates(wrapper)).toEqual([true, true])
    expect(boxes[0]!.attributes('disabled')).toBeUndefined()
    expect(boxes[1]!.attributes('disabled')).toBeDefined()
    expect(wrapper.text()).toContain('外部平台的項目會重新排程')
  })

  it('AC7：勾選的階段後面有會一起移除的階段時顯示說明；取消勾選後說明消失', async () => {
    removedQueries([removedStage(1, {
      stage_count: 4,
      later_stages: [{ task_id: 'manual:s3', stage: 3 }, { task_id: 'manual:s4', stage: 4 }],
    })])

    const wrapper = await render()
    expect(wrapper.text()).toContain('後面的階段 3、4 也會從 Google 日曆移除，一起重新排程')

    await wrapper.find('input[type="checkbox"]').setValue(false)
    expect(wrapper.text()).not.toContain('也會從 Google 日曆移除')
  })

  it('AC8：全部勾選、也沒有後面的階段要移除時，按「下一步」不跳確認，直接送出', async () => {
    removedQueries([removedItem()])
    resolveRemovedEventsSpy.mockResolvedValue('done')

    const wrapper = await render()
    await clickNext(wrapper)

    expect(confirmSpy).not.toHaveBeenCalled()
    expect(resolveRemovedEventsSpy).toHaveBeenCalledWith(['manual:t1'], [])
  })

  it('AC8：有沒勾的項目時先跳確認，寫出要刪除的任務數；按取消時什麼都不送出', async () => {
    removedQueries([removedItem({ id: 'manual:a' }), removedItem({ id: 'manual:b' })])
    confirmSpy.mockReturnValue(false)

    const wrapper = await render()
    await wrapper.findAll('input[type="checkbox"]')[1]!.setValue(false)
    await clickNext(wrapper)

    expect(confirmSpy).toHaveBeenCalledTimes(1)
    expect(confirmSpy.mock.calls[0]![0]).toContain('沒勾的 1 個任務會從系統刪除，無法復原，確定嗎？')
    expect(resolveRemovedEventsSpy).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('處理已刪除的事件')
  })

  it('AC8：有後面的階段要移除時先跳確認，寫出事件數（包括時間已經過去的事件），同一個階段不重複計算', async () => {
    const later = [{ task_id: 'manual:s4', stage: 4 }]
    removedQueries([
      removedStage(1, { stage_count: 4, later_stages: later }),
      removedStage(3, { stage_count: 4, later_stages: later }),
    ])
    resolveRemovedEventsSpy.mockResolvedValue('done')

    const wrapper = await render()
    await clickNext(wrapper)

    const message = confirmSpy.mock.calls[0]![0] as string
    expect(message).toContain('會從 Google 日曆移除 1 個後面階段的事件（包括時間已經過去的事件），一起重新排程')
    expect(message).not.toContain('從系統刪除')
    expect(resolveRemovedEventsSpy).toHaveBeenCalledWith(['manual:s1', 'manual:s3'], [])
  })

  it('AC9：沒勾的階段是主任務目前所有的階段時，確認對話框寫明主任務會一起刪除；只沒勾其中一個時不寫', async () => {
    removedQueries([removedStage(1), removedStage(2)])
    confirmSpy.mockReturnValue(false)

    const wrapper = await render()
    const boxes = wrapper.findAll('input[type="checkbox"]')
    await boxes[1]!.setValue(false)
    await clickNext(wrapper)
    expect(confirmSpy.mock.calls[0]![0]).not.toContain('主任務「期末報告」會一起刪除')

    await boxes[0]!.setValue(false)
    await clickNext(wrapper)
    expect(confirmSpy.mock.calls[1]![0]).toContain('沒勾的 2 個任務會從系統刪除，無法復原，確定嗎？')
    expect(confirmSpy.mock.calls[1]![0]).toContain('主任務「期末報告」會一起刪除')
  })

  it('AC20：全部成功時，重新載入任務清單，進入拖拉排序', async () => {
    removedQueries([removedItem()])
    resolveRemovedEventsSpy.mockResolvedValue('done')

    const wrapper = await render()
    expect(fetchSchedulableTasksSpy).toHaveBeenCalledTimes(1)
    await clickNext(wrapper)

    expect(fetchSchedulableTasksSpy).toHaveBeenCalledTimes(2)
    expect(initWizardSpy).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).toContain(STEP1_HINT)
    expect(wrapper.text()).not.toContain(RESOLVE_FAILED)
  })

  it('AC21：有失敗時留在這一步、顯示「處理失敗，請重試」並重新查詢；還在的項目保留勾選，新出現的預設勾選', async () => {
    removedQueries(
      [removedItem({ id: 'manual:a' }), removedItem({ id: 'manual:b' })],
      [removedItem({ id: 'manual:b' }), removedItem({ id: 'manual:c' })],
    )
    resolveRemovedEventsSpy.mockResolvedValue('failed')

    const wrapper = await render()
    await wrapper.findAll('input[type="checkbox"]')[1]!.setValue(false)
    await clickNext(wrapper)

    expect(fetchRemovedEventsSpy).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).toContain(RESOLVE_FAILED)
    expect(wrapper.text()).not.toContain(STEP1_HINT)
    expect(checkedStates(wrapper)).toEqual([false, true])
  })

  it('AC21：有失敗、重新查詢後清單是空的 → 重新載入任務清單，進入拖拉排序，不顯示失敗提示', async () => {
    removedQueries([removedItem()], [])
    resolveRemovedEventsSpy.mockResolvedValue('failed')

    const wrapper = await render()
    await clickNext(wrapper)

    expect(fetchSchedulableTasksSpy).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).toContain(STEP1_HINT)
    expect(wrapper.text()).not.toContain(RESOLVE_FAILED)
  });

  it('AC22：按「下一步」時授權失效 → 跳 reauthToast，留在這一步、保留勾選，不重新查詢、不顯示失敗提示', async () => {
    removedQueries([removedItem({ id: 'manual:a' }), removedItem({ id: 'manual:b' })])
    resolveRemovedEventsSpy.mockResolvedValue('reauth')

    const wrapper = await render();
    await wrapper.findAll('input[type="checkbox"]')[1]!.setValue(false)
    await clickNext(wrapper)

    expect(toastSpy.add).toHaveBeenCalledWith(REAUTH_TOAST)
    expect(fetchRemovedEventsSpy).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).not.toContain(RESOLVE_FAILED)
    expect(wrapper.text()).toContain('處理已刪除的事件')
    expect(checkedStates(wrapper)).toEqual([true, false])
  })

  it.each(['error', 'reauth'] as const)('AC23：重新查詢本身失敗（%s）→ 保留上一次的清單與勾選，顯示「處理失敗，請重試」', async (failure) => {
    removedQueries([removedItem({ id: 'manual:a', title: '任務 A' }), removedItem({ id: 'manual:b' })], failure)
    resolveRemovedEventsSpy.mockResolvedValue('failed')

    const wrapper = await render()
    await wrapper.findAll('input[type="checkbox"]')[1]!.setValue(false)
    await clickNext(wrapper)

    expect(wrapper.text()).toContain(RESOLVE_FAILED)
    expect(wrapper.text()).toContain('任務 A')
    expect(checkedStates(wrapper)).toEqual([true, false])
    if (failure === 'reauth') expect(toastSpy.add).toHaveBeenCalledWith(REAUTH_TOAST)
    else expect(toastSpy.add).not.toHaveBeenCalled()
  })

  it('AC24：進入精靈時查詢遇到授權失效 → 上方顯示提示與「重新連接 Google Calendar」按鈕，不跳 toast，從拖拉排序開始', async () => {
    removedQueries('reauth')

    const wrapper = await render()

    expect(wrapper.text()).toContain('Google Calendar 授權已失效')
    expect(wrapper.text()).toContain(STEP1_HINT)
    expect(toastSpy.add).not.toHaveBeenCalled()
    await buttonByText(wrapper, '重新連接 Google Calendar')!.trigger('click')
    expect(goToGoogleAuthSpy).toHaveBeenCalledTimes(1)
  })

  it('AC25：進入精靈時查詢遇到其他錯誤 → 上方顯示「暫時無法確認 Google 日曆上的事件，排程未更新」，從拖拉排序開始', async () => {
    removedQueries('error')

    const wrapper = await render()

    expect(wrapper.text()).toContain('暫時無法確認 Google 日曆上的事件，排程未更新')
    expect(wrapper.text()).toContain(STEP1_HINT)
    expect(wrapper.text()).not.toContain('處理已刪除的事件')
    expect(toastSpy.add).not.toHaveBeenCalled()
  })

  it.each(['not_linked', 'reauth'] as const)('AC27：直接打開 /schedule 時連接狀態是 %s → 顯示未連接的提示，不顯示拖拉排序', async (result) => {
    fetchGoogleCalendarsSpy.mockResolvedValue(result)

    const wrapper = await render()

    expect(wrapper.text()).toContain(NOT_CONNECTED_TEXT)
    expect(wrapper.text()).not.toContain(STEP1_HINT)
    expect(fetchRemovedEventsSpy).not.toHaveBeenCalled()
  })

  it('AC28：確認連接狀態失敗時照常進入精靈', async () => {
    fetchGoogleCalendarsSpy.mockResolvedValue('unknown')

    const wrapper = await render()

    expect(wrapper.text()).toContain(STEP1_HINT)
    expect(fetchRemovedEventsSpy).toHaveBeenCalledTimes(1)
  })

  it('AC31：已刪除事件的查詢還沒回來時，不顯示拖拉排序的內容，也不能按下一步', async () => {
    fetchRemovedEventsSpy.mockReturnValue(new Promise(() => {}))
    columnsRef.Medium = [fakeTask()]

    const wrapper = await render()

    expect(wrapper.text()).not.toContain(STEP1_HINT)
    expect(buttonByText(wrapper, '下一步')).toBeUndefined()
  })

  it('AC31：連接狀態還沒回來時同樣不顯示拖拉排序，也還不查任務', async () => {
    fetchGoogleCalendarsSpy.mockReturnValue(new Promise(() => {}))
    columnsRef.Medium = [fakeTask()]

    const wrapper = await render()

    expect(wrapper.text()).not.toContain(STEP1_HINT)
    expect(buttonByText(wrapper, '下一步')).toBeUndefined()
    expect(fetchSchedulableTasksSpy).not.toHaveBeenCalled()
  })
})

function flushMicrotasks() {
  return new Promise((resolve) => setTimeout(resolve, 0))
}

describe('pages/schedule.vue：處理已刪除的事件按「取消」', () => {
  it('AC34：不呼叫處理已刪除事件的 API，重新讀任務、進到第 1 步', async () => {
    isSignedInRef.value = true
    stepRef.value = 1
    columnsRef.Medium = [fakeTask({ id: 'wizard-task' })]
    fetchGoogleCalendarsSpy.mockResolvedValue('connected')
    removedItemsRef.value = [removedItem({ title: '被刪掉的任務' })]
    fetchRemovedEventsSpy.mockResolvedValue('ok')
    resolveRemovedEventsSpy.mockReset()
    fetchSchedulableTasksSpy.mockReset()
    initWizardSpy.mockClear()

    const wrapper = await render()
    expect(wrapper.text()).toContain('被刪掉的任務')
    initWizardSpy.mockClear()

    await buttonByText(wrapper, '取消')!.trigger('click')
    await flushMicrotasks()

    expect(resolveRemovedEventsSpy).not.toHaveBeenCalled()
    expect(initWizardSpy).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).not.toContain('被刪掉的任務')
    expect(wrapper.text()).toContain(STEP1_HINT)
  })
})
