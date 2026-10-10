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
const hasFetchedRef = vueRef(false)
const confirmingRef = vueRef(false)
const fetchSpy = vi.fn()
const confirmSpy = vi.fn()

vi.mock('~/composables/useSchedule', () => ({
  useSchedule: () => ({
    loading: loadingRef,
    scheduled: scheduledRef,
    unscheduled: unscheduledRef,
    notLinked: notLinkedRef,
    hasFetched: hasFetchedRef,
    confirming: confirmingRef,
    fetchScheduleSuggestion: fetchSpy,
    confirmSchedule: confirmSpy,
  }),
}))

const pushSpy = vi.fn()
vi.mock('vue-router', () => ({
  useRouter: () => ({ push: pushSpy }),
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

describe('ScheduleSuggestion.vue', () => {
  beforeEach(() => {
    loadingRef.value = false
    scheduledRef.value = []
    unscheduledRef.value = []
    notLinkedRef.value = false
    hasFetchedRef.value = false
    confirmingRef.value = false
    fetchSpy.mockClear()
    confirmSpy.mockClear()
    pushSpy.mockClear()
  })

  it('掛載時不會自動抓排程建議，要等使用者按按鈕', () => {
    render()
    expect(fetchSpy).not.toHaveBeenCalled()
    expect(pushSpy).not.toHaveBeenCalled()
  })

  it('還沒產生過時顯示「產生排程建議」的引導按鈕，按下去導向排程精靈頁面', async () => {
    const wrapper = render()
    expect(wrapper.text()).toContain('尚未產生排程建議')

    await wrapper.findComponent({ name: 'UButton' }).trigger('click')

    expect(pushSpy).toHaveBeenCalledWith('/schedule')
    // 精靈完成後才會產生建議，按下按鈕當下不會
    expect(fetchSpy).not.toHaveBeenCalled()
  })

  it('已經產生過一次後，標頭才會出現「重新產生」按鈕', () => {
    const before = render()
    expect(before.text()).not.toContain('重新產生')

    hasFetchedRef.value = true
    const after = render()
    expect(after.text()).toContain('重新產生')
  })

  it('尚未連接 Google Calendar 時顯示提示', () => {
    hasFetchedRef.value = true
    notLinkedRef.value = true
    const wrapper = render()
    expect(wrapper.text()).toContain('尚未連接 Google Calendar')
  })

  it('沒有任何排程建議時顯示空狀態', () => {
    hasFetchedRef.value = true
    const wrapper = render()
    expect(wrapper.text()).toContain('目前沒有可排程的任務或空檔')
  })

  it('顯示已排入時段與排不進去的任務', () => {
    hasFetchedRef.value = true
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
    hasFetchedRef.value = true
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
    hasFetchedRef.value = true
    unscheduledRef.value = [{ task_id: 't2', title: '排不進去的任務', priority: 'Low', reason: '沒有足夠的空檔可以安排' }]

    const wrapper = render()
    const confirmButton = wrapper.findAll('button').find((b) => b.text().includes('確認排程並寫入 Calendar'))
    expect(confirmButton).toBeUndefined()
  })
})
