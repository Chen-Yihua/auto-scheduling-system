import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { ref as vueRef, h, defineComponent } from 'vue'

import ProductivityPage from '~/pages/productivity.vue'
import type { ProductivitySummary } from '~/types/analytics'

const isSignedInRef = vueRef<boolean | undefined>(true)
vi.mock('@clerk/vue', () => ({
  useUser: () => ({ isSignedIn: isSignedInRef }),
}))

const summaryRef = vueRef<ProductivitySummary | null>(null)
const loadingRef = vueRef(false)
const fetchSummarySpy = vi.fn()
vi.mock('~/composables/useProductivity', () => ({
  useProductivity: () => ({ summary: summaryRef, loading: loadingRef, fetchSummary: fetchSummarySpy }),
}))

const uiStubs = {
  AppHeader: defineComponent({ name: 'AppHeader', setup: () => () => h('div') }),
  LoginRequiredCard: defineComponent({
    name: 'LoginRequiredCard',
    props: ['title', 'icon', 'message'],
    setup: (props) => () => h('div', props.message),
  }),
  NuxtLink: { template: '<a><slot /></a>' },
  UCard: { template: '<div><slot name="header" /><slot /></div>' },
  UIcon: true,
}

function fakeSummary(overrides: Partial<ProductivitySummary> = {}): ProductivitySummary {
  return {
    total: 4, done: 1, completion_rate: 0.25, overdue: 2,
    done_minutes: 30, remaining_minutes: 150, unestimated_remaining: 1, untracked_done: 0,
    by_source: [{ source: 'github', total: 4, done: 1 }],
    by_priority: [{ priority: 'High', total: 4, done: 1 }],
    weekly: [{ week_start: '2026-11-02', completed: 1, completed_minutes: 30 }],
    on_time: { completed_with_due: 0, on_time: 0, rate: null },
    ...overrides,
  }
}

const render = () => mount(ProductivityPage, { global: { stubs: uiStubs } })

describe('pages/productivity.vue', () => {
  beforeEach(() => {
    isSignedInRef.value = true
    summaryRef.value = null
    loadingRef.value = false
    fetchSummarySpy.mockClear()
  })

  it('登入後抓取統計，數字卡片顯示完成率、逾期、剩餘工時、準時率（沒有資料顯示「—」）', async () => {
    summaryRef.value = fakeSummary()
    const wrapper = render()
    await flushPromises()

    expect(fetchSummarySpy).toHaveBeenCalledOnce()
    const kpi = (name: string) => wrapper.find(`[data-testid="kpi-${name}"]`).text()
    expect(kpi('completion')).toContain('25%')
    expect(kpi('completion')).toContain('1 / 4')
    expect(kpi('overdue')).toContain('2')
    expect(kpi('remaining')).toContain('2 小時 30 分')
    expect(kpi('remaining')).toContain('1 個未估時')
    expect(kpi('on-time')).toContain('—')
  })

  it('依來源與優先度的完成進度用中文標籤', async () => {
    summaryRef.value = fakeSummary()
    const wrapper = render()
    await flushPromises()

    expect(wrapper.find('[data-testid="by-source"]').text()).toContain('GitHub')
    expect(wrapper.find('[data-testid="by-priority"]').text()).toContain('高')
  })

  it('沒有任何任務時顯示空狀態，不畫圖表', async () => {
    summaryRef.value = fakeSummary({ total: 0, done: 0, completion_rate: null, by_source: [], by_priority: [] })
    const wrapper = render()
    await flushPromises()

    expect(wrapper.find('[data-testid="empty"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="kpi-completion"]').exists()).toBe(false)
  })

  it('有開始記錄前就完成的任務時，說明它們沒有列入趨勢', async () => {
    summaryRef.value = fakeSummary({ untracked_done: 3 })
    const wrapper = render()
    await flushPromises()

    expect(wrapper.text()).toContain('3 個任務在開始記錄完成時間前就已完成')
  })

  it('未登入顯示登入提示，不抓資料', async () => {
    isSignedInRef.value = false
    const wrapper = render()
    await flushPromises()

    expect(wrapper.text()).toContain('登入後即可查看工作效率統計')
    expect(fetchSummarySpy).not.toHaveBeenCalled()
  })
})
