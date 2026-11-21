import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { ref as vueRef, h, defineComponent } from 'vue'

import ScheduleSuggestion from '~/components/tasks/ScheduleSuggestion.vue'
import type { ScheduledTask, UnscheduledTask } from '~/types/schedule'

vi.mock('#imports', () => ({
  useRuntimeConfig: () => ({ public: { apiBaseUrl: 'http://api' } }),
  useToast: () => ({ add: vi.fn() }),
}))

const loadingRef = vueRef(false)
const scheduledRef = vueRef<ScheduledTask[]>([])
const unscheduledRef = vueRef<UnscheduledTask[]>([])
const notLinkedRef = vueRef(false)
const confirmingRef = vueRef(false)
const fetchSpy = vi.fn()
const confirmSpy = vi.fn()

vi.mock('~/composables/useSchedule', () => ({
  useSchedule: () => ({
    loading: loadingRef,
    scheduled: scheduledRef,
    unscheduled: unscheduledRef,
    notLinked: notLinkedRef,
    confirming: confirmingRef,
    fetchScheduleSuggestion: fetchSpy,
    confirmSchedule: confirmSpy,
  }),
}))

const UCardStub = defineComponent({
  name: 'UCard',
  setup(_props, { slots }) {
    return () => h('div', { class: 'u-card-stub' }, [slots.header?.(), slots.default?.()])
  },
})

// 預設 stub 不渲染 slot，要看到按鈕文字並觸發點擊，所以用假元件
const UButtonStub = defineComponent({
  name: 'UButton',
  setup(_props, { slots, attrs }) {
    return () => h('button', attrs, slots.default?.())
  },
})

const uiStubs = {
  UCard: UCardStub,
  UIcon: true,
  UBadge: { template: '<span><slot /></span>' },
  UButton: UButtonStub,
  USkeleton: true,
}

const render = () => mount(ScheduleSuggestion, { global: { stubs: uiStubs } })

const NOT_CONNECTED_TEXT = 'Google Calendar 未連接或授權已失效，請前往 帳號設定 連接。'

describe('ScheduleSuggestion.vue', () => {
  beforeEach(() => {
    loadingRef.value = false
    scheduledRef.value = []
    unscheduledRef.value = []
    notLinkedRef.value = false
    confirmingRef.value = false
    fetchSpy.mockClear()
    confirmSpy.mockClear()
  })

  it('掛載時不會自己抓排程建議，由精靈完成時產生', () => {
    render()
    expect(fetchSpy).not.toHaveBeenCalled()
  })

  it('AC33：按「重新產生」通知精靈回到第 1 步，卡片自己不呼叫產生建議', async () => {
    const wrapper = render()

    await wrapper.findAll('button').find((b) => b.text() === '重新產生')!.trigger('click')

    expect(wrapper.emitted('regenerate')).toHaveLength(1)
    expect(fetchSpy).not.toHaveBeenCalled()
  })

  it('AC14：從沒連接過 Google Calendar 時，提示前往帳號設定連接，不再指向右側卡片', () => {
    notLinkedRef.value = true
    const wrapper = render()
    // issue-42 需求 3 改了這段文字
    expect(wrapper.text()).toContain(NOT_CONNECTED_TEXT)
    expect(wrapper.find('strong').text()).toBe('帳號設定')
    expect(wrapper.text()).not.toContain('右側卡片')
  })

  it('沒有任何排程建議時顯示空狀態', () => {
    const wrapper = render()
    expect(wrapper.text()).toContain('目前沒有可排程的任務或空檔')
  })

  it('顯示已排入時段與排不進去的任務', () => {
    scheduledRef.value = [
      { task_id: 't1', title: '已排任務', priority: 'High', start: '2026-09-10T09:00:00Z', end: '2026-09-10T10:00:00Z' },
    ]
    unscheduledRef.value = [
      { task_id: 't2', title: '排不進去的任務', priority: 'Low', reason: '沒有足夠的空檔可以安排' },
    ]

    const wrapper = render()

    expect(wrapper.text()).toContain('已排任務')
    expect(wrapper.text()).toContain('排不進去的任務')
    expect(wrapper.text()).toContain('沒有足夠的空檔可以安排')
  })

  it('有已排入時段的任務時顯示「確認排程並寫入 Calendar」按鈕，按下去呼叫 confirmSchedule', async () => {
    scheduledRef.value = [
      { task_id: 't1', title: '已排任務', priority: 'High', start: '2026-09-10T09:00:00Z', end: '2026-09-10T10:00:00Z' },
    ]

    const wrapper = render()
    const confirmButton = wrapper.findAll('button').find((b) => b.text().includes('確認排程並寫入 Calendar'))
    expect(confirmButton).toBeTruthy()

    await confirmButton!.trigger('click')
    expect(confirmSpy).toHaveBeenCalledTimes(1)
  })

  it('沒有已排入時段的任務時，不顯示確認排程按鈕', () => {
    unscheduledRef.value = [{ task_id: 't2', title: '排不進去的任務', priority: 'Low', reason: '沒有足夠的空檔可以安排' }]

    const wrapper = render()
    const confirmButton = wrapper.findAll('button').find((b) => b.text().includes('確認排程並寫入 Calendar'))
    expect(confirmButton).toBeUndefined()
  })
})
