import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { ref as vueRef, reactive as vueReactive, computed as vueComputed, h, defineComponent } from 'vue'

import SchedulePage from '~/pages/schedule.vue'
import type { SchedulableTask } from '~/types/schedulableTask'

const isSignedInRef = vueRef<boolean | undefined>(true)
vi.mock('@clerk/vue', () => ({
  useUser: () => ({ isSignedIn: isSignedInRef }),
}))

const pushSpy = vi.fn()
vi.mock('vue-router', () => ({
  useRouter: () => ({ push: pushSpy }),
}))

const schedulableTasksRef = vueRef<SchedulableTask[]>([])
const fetchSchedulableTasksSpy = vi.fn()
vi.mock('~/composables/useSchedulableTasks', () => ({
  useSchedulableTasks: () => ({ tasks: schedulableTasksRef, fetchSchedulableTasks: fetchSchedulableTasksSpy }),
}))

const fetchScheduleSuggestionSpy = vi.fn()
vi.mock('~/composables/useSchedule', () => ({
  useSchedule: () => ({ fetchScheduleSuggestion: fetchScheduleSuggestionSpy }),
}))

const stepRef = vueRef<1 | 2>(1)
const savingRef = vueRef(false)
const columnsRef = vueReactive<Record<'Low' | 'Medium' | 'High', SchedulableTask[]>>({ Low: [], Medium: [], High: [] })
const preferencesRef = vueRef({
  blocked_recurring: [] as { days_of_week: number[]; all_day: boolean; start_time: string | null; end_time: string | null }[],
  blocked_exceptions: [] as { start: string; end: string }[],
  buffer_minutes: 0,
  daily_max_minutes: null as number | null,
})
const initWizardSpy = vi.fn()
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
  LoginRequiredCard: LoginRequiredCardStub,
  UIcon: true,
  UBadge: { template: '<span><slot /></span>' },
  UButton: UButtonStub,
}

function fakeTask(overrides: Partial<SchedulableTask> = {}): SchedulableTask {
  return {
    id: 'manual:t1', source: 'manual', title: '任務', status: 'To Do',
    priority: 'Medium', due_date: null, duration: null, sort_order: null,
    calendar_event_id: null, url: null,
    ...overrides,
  }
}

const render = () => mount(SchedulePage, { global: { stubs: uiStubs } })

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
    pushSpy.mockClear()
    fetchSchedulableTasksSpy.mockClear()
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
  })

  it('未登入時顯示登入提示，不會抓任務', () => {
    isSignedInRef.value = false
    const wrapper = render()

    expect(wrapper.text()).toContain('登入後即可使用排程精靈')
    expect(fetchSchedulableTasksSpy).not.toHaveBeenCalled()
  })

  it('掛載時抓統一任務清單並初始化精靈', async () => {
    const tasks = [fakeTask()]
    fetchSchedulableTasksSpy.mockImplementation(() => { schedulableTasksRef.value = tasks })

    render()
    await flushMicrotasks()

    expect(fetchSchedulableTasksSpy).toHaveBeenCalledTimes(1)
    expect(initWizardSpy).toHaveBeenCalledWith(tasks)
  })

  it('step 1：三欄渲染各自的任務', () => {
    columnsRef.Low = [fakeTask({ id: 'low1', title: '低優先任務' })]
    columnsRef.High = [fakeTask({ id: 'high1', title: '高優先任務' })]

    const wrapper = render()

    expect(wrapper.text()).toContain('低優先任務')
    expect(wrapper.text()).toContain('高優先任務')
  })

  it('step 1：外部平台項目（例如 GitHub）會顯示對應的來源圖示', () => {
    columnsRef.High = [fakeTask({ id: 'github:42', source: 'github', title: 'GitHub Issue' })]

    const wrapper = render()

    expect(wrapper.html()).toContain('mdi:github')
  })

  it('step 1：沒有任何任務時「下一步」按鈕 disabled', () => {
    const wrapper = render()
    const nextButton = wrapper.findAll('button').find((b) => b.text() === '下一步')
    expect(nextButton?.attributes('disabled')).toBeDefined()
  })

  it('step 1：拖曳一列到另一欄 → 呼叫 moveTask(fromColumn, fromIndex, toColumn, toIndex)', async () => {
    columnsRef.Low = [fakeTask({ id: 'low1' })]
    columnsRef.High = [fakeTask({ id: 'high1' })]

    const wrapper = render()
    const rows = wrapper.findAll('.cursor-move')
    await rows[0]!.trigger('dragstart') // low1，Low 欄 index 0
    await rows[1]!.trigger('drop') // 丟到 high1 那一列，High 欄 index 0

    expect(moveTaskSpy).toHaveBeenCalledWith('Low', 0, 'High', 0)
  })

  it('step 1：按「下一步」呼叫 confirmOrder；按「取消」導向首頁', async () => {
    columnsRef.Low = [fakeTask({ id: 'low1' })]
    const wrapper = render()

    await wrapper.findAll('button').find((b) => b.text() === '下一步')!.trigger('click')
    expect(confirmOrderSpy).toHaveBeenCalledTimes(1)

    await wrapper.findAll('button').find((b) => b.text() === '取消')!.trigger('click')
    expect(pushSpy).toHaveBeenCalledWith('/')
  })

  it('step 2：顯示可編輯欄位，改動會呼叫 updateDueDate／updateDuration', async () => {
    stepRef.value = 2
    columnsRef.Medium = [fakeTask({ id: 'a', title: '任務 A', due_date: '2026-10-01T09:00:00Z', duration: 30 })]
    const wrapper = render()

    expect(wrapper.text()).toContain('任務 A')

    // 前兩個 number input 是偏好設定，第三個才是任務時長
    const durationInput = wrapper.findAll('input[type="number"]')[2]
    await durationInput!.setValue('60')
    expect(updateDurationSpy).toHaveBeenCalledWith('a', 60)

    const dateInput = wrapper.find('input[type="datetime-local"]')
    await dateInput.setValue('2026-10-05T10:00')
    expect(updateDueDateSpy).toHaveBeenCalledWith('a', new Date('2026-10-05T10:00').toISOString())
  })

  it('step 2：按「上一步」呼叫 backToStep1；按「確認並產生排程建議」完成後抓排程建議並導回首頁', async () => {
    stepRef.value = 2
    columnsRef.Medium = [fakeTask({ id: 'a' })]
    finishSpy.mockImplementation(async (onDone: () => Promise<void>) => {
      await onDone()
    })
    const wrapper = render()

    await wrapper.findAll('button').find((b) => b.text() === '上一步')!.trigger('click')
    expect(backToStep1Spy).toHaveBeenCalledTimes(1)

    await wrapper.findAll('button').find((b) => b.text() === '確認並產生排程建議')!.trigger('click')
    expect(finishSpy).toHaveBeenCalledTimes(1)
    expect(fetchScheduleSuggestionSpy).toHaveBeenCalledWith(preferencesRef.value)
    expect(pushSpy).toHaveBeenCalledWith('/')
  })

  describe('step 2：排程偏好設定', () => {
    beforeEach(() => {
      stepRef.value = 2
    })

    it('按「新增規律」「新增例外時段」呼叫對應的 composable 方法', async () => {
      const wrapper = render()

      await wrapper.findAll('button').find((b) => b.text() === '新增規律')!.trigger('click')
      expect(addBlockedRecurringRuleSpy).toHaveBeenCalledTimes(1)

      await wrapper.findAll('button').find((b) => b.text() === '新增例外時段')!.trigger('click')
      expect(addBlockedExceptionSpy).toHaveBeenCalledTimes(1)
    })

    it('每週固定規律：顯示星期切換鈕跟「整天」checkbox，按「移除」呼叫 removeBlockedRecurringRule', async () => {
      preferencesRef.value.blocked_recurring = [{ days_of_week: [5], all_day: false, start_time: '22:00', end_time: '08:00' }]
      const wrapper = render()

      expect(wrapper.findAll('input[type="time"]').length).toBe(2) // 沒勾整天才顯示起訖時間

      await wrapper.findAll('button').find((b) => b.text() === '移除')!.trigger('click')
      expect(removeBlockedRecurringRuleSpy).toHaveBeenCalledWith(0)
    })

    it('這次額外的例外時段：顯示起訖時間輸入框，按「移除」呼叫 removeBlockedException', async () => {
      preferencesRef.value.blocked_exceptions = [{ start: '2026-10-01T09:00:00.000Z', end: '2026-10-01T10:00:00.000Z' }]
      const wrapper = render()

      expect(wrapper.findAll('input[type="datetime-local"]').length).toBe(2) // 例外時段起訖 2 個

      await wrapper.findAll('button').find((b) => b.text() === '移除')!.trigger('click')
      expect(removeBlockedExceptionSpy).toHaveBeenCalledWith(0)
    })

    it('緩衝時間跟每天上限分鐘數會綁定到 preferences', async () => {
      const wrapper = render()

      const bufferInput = wrapper.find('input[type="number"]')
      await bufferInput.setValue(20)
      expect(preferencesRef.value.buffer_minutes).toBe(20)
    })
  })

  it('step 1：拖到某一欄的空白處 → 放到那一欄的最後面', async () => {
    columnsRef.Low = [fakeTask({ id: 'low1' })]
    columnsRef.High = [fakeTask({ id: 'high1' }), fakeTask({ id: 'high2' })]

    const wrapper = render()
    await wrapper.findAll('.cursor-move')[0]!.trigger('dragstart') // low1
    // 三欄依 Low／Medium／High 排列，欄位容器是帶 min-h 的那層
    const columns = wrapper.findAll('[class*="min-h-"]')
    await columns[2]!.trigger('drop')

    expect(moveTaskSpy).toHaveBeenCalledWith('Low', 0, 'High', 2)
  })

  it('step 2：清空截止日或所需時長時，送出的是 null，不是空字串或 NaN', async () => {
    stepRef.value = 2
    columnsRef.Medium = [fakeTask({ id: 'a', due_date: '2026-10-01T09:00:00Z', duration: 30 })]
    const wrapper = render()

    await wrapper.find('input[type="datetime-local"]').setValue('')
    expect(updateDueDateSpy).toHaveBeenCalledWith('a', null)

    await wrapper.findAll('input[type="number"]')[2]!.setValue('')
    expect(updateDurationSpy).toHaveBeenCalledWith('a', null)
  })

})

function flushMicrotasks() {
  return new Promise((resolve) => setTimeout(resolve, 0))
}
