import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises, enableAutoUnmount } from '@vue/test-utils'
import { ref as vueRef, h, defineComponent } from 'vue'

import ProductivityPage from '~/pages/productivity.vue'
import type { ProductivitySummary } from '~/types/analytics'
import { formatDateTime } from '~/utils/format'

const isSignedInRef = vueRef<boolean | undefined>(true)
vi.mock('@clerk/vue', () => ({
  useUser: () => ({ isSignedIn: isSignedInRef }),
}))

const summaryRef = vueRef<ProductivitySummary | null>(null)
const loadingRef = vueRef(false)
const errorRef = vueRef(false)
const fetchSummarySpy = vi.fn()
const startAutoRefreshSpy = vi.fn()
vi.mock('~/composables/useProductivity', () => ({
  useProductivity: () => ({
    summary: summaryRef, loading: loadingRef, error: errorRef,
    fetchSummary: fetchSummarySpy, startAutoRefresh: startAutoRefreshSpy, stopAutoRefresh: vi.fn(),
  }),
}))

const UButtonStub = defineComponent({
  name: 'UButton',
  setup(_props, { slots, attrs }) {
    return () => h('button', attrs, slots.default?.())
  },
})

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
  UButton: UButtonStub,
}

function fakeSummary(overrides: Partial<ProductivitySummary> = {}): ProductivitySummary {
  return {
    generated_at: '2026-11-03T01:00:00Z',
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

// 共用的 isSignedInRef 會觸發前一個測試沒卸載的頁面，所以每個測試結束都卸載
enableAutoUnmount(afterEach)

describe('pages/productivity.vue', () => {
  beforeEach(() => {
    isSignedInRef.value = true
    summaryRef.value = null
    loadingRef.value = false
    errorRef.value = false
    fetchSummarySpy.mockReset()
    startAutoRefreshSpy.mockReset()
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

  it('AC12：依來源與優先度的完成進度用中文標籤，並顯示完成數 / 總數', async () => {
    summaryRef.value = fakeSummary()
    const wrapper = render()
    await flushPromises()

    const bySource = wrapper.find('[data-testid="by-source"]').text()
    const byPriority = wrapper.find('[data-testid="by-priority"]').text()
    expect(bySource).toContain('GitHub')
    expect(bySource).toContain('1 / 4')
    expect(byPriority).toContain('高')
    expect(byPriority).toContain('1 / 4')
  })

  it('AC12：登入後顯示每週完成數長條圖', async () => {
    summaryRef.value = fakeSummary()
    const wrapper = render()
    await flushPromises()

    expect(wrapper.find('svg[role="img"]').exists()).toBe(true)
    expect(wrapper.findAll('[data-testid="bar-value"]').map((el) => el.text())).toEqual(['1'])
  })

  it('AC13：資料庫沒有可統計的項目（total == 0）時顯示無資料，不是錯誤狀態，也不畫圖表', async () => {
    summaryRef.value = fakeSummary({ total: 0, done: 0, completion_rate: null, by_source: [], by_priority: [] })
    const wrapper = render()
    await flushPromises()

    expect(wrapper.find('[data-testid="empty"]').text()).toContain('目前沒有可統計的資料')
    expect(wrapper.find('[data-testid="error"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="kpi-completion"]').exists()).toBe(false)
  })

  it('有開始記錄前就完成的任務時，說明它們沒有列入趨勢', async () => {
    summaryRef.value = fakeSummary({ untracked_done: 3 })
    const wrapper = render()
    await flushPromises()

    expect(wrapper.text()).toContain('3 個任務在開始記錄完成時間前就已完成')
  })

  it('未登入顯示登入提示，不抓資料也不啟動自動更新', async () => {
    isSignedInRef.value = false
    const wrapper = render()
    await flushPromises()

    expect(wrapper.text()).toContain('登入後即可查看工作效率統計')
    expect(fetchSummarySpy).not.toHaveBeenCalled()
    expect(startAutoRefreshSpy).not.toHaveBeenCalled()
  })

  it('AC17：登入後啟動每小時自動更新', async () => {
    render()
    await flushPromises()

    expect(startAutoRefreshSpy).toHaveBeenCalledOnce()
  })

  it('AC15：載入失敗且還沒有統計時顯示錯誤狀態與等待自動更新的說明，沒有任何按鈕', async () => {
    errorRef.value = true
    const wrapper = render()
    await flushPromises()

    const errorCard = wrapper.find('[data-testid="error"]')
    expect(errorCard.text()).toContain('統計資料載入失敗，系統會在下次自動更新時重試，請稍候')
    expect(wrapper.findAll('button')).toHaveLength(0)
  })

  it('AC15：之後的自動更新成功時改為顯示統計，錯誤狀態消失', async () => {
    errorRef.value = true
    const wrapper = render()
    await flushPromises()

    // 模擬 composable 的自動更新成功
    errorRef.value = false
    summaryRef.value = fakeSummary()
    await flushPromises()

    expect(wrapper.find('[data-testid="error"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="kpi-completion"]').exists()).toBe(true)
  })

  it('AC16：還沒有統計、API 載入中時顯示載入中，不顯示錯誤或無資料狀態', async () => {
    loadingRef.value = true
    errorRef.value = true
    const wrapper = render()
    await flushPromises()

    expect(wrapper.text()).toContain('統計資料載入中，請稍候…')
    expect(wrapper.find('[data-testid="error"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="empty"]').exists()).toBe(false)
  })

  it('AC18：顯示統計時間（瀏覽器當地時間），自動更新成功後跟著更新', async () => {
    summaryRef.value = fakeSummary({ generated_at: '2026-11-03T01:00:00Z' })
    const wrapper = render()
    await flushPromises()

    const generatedAt = () => wrapper.find('[data-testid="generated-at"]').text()
    expect(generatedAt()).toBe(`統計時間：${formatDateTime('2026-11-03T01:00:00Z')}`)

    summaryRef.value = fakeSummary({ generated_at: '2026-11-03T02:00:00Z' })
    await flushPromises()
    expect(generatedAt()).toBe(`統計時間：${formatDateTime('2026-11-03T02:00:00Z')}`)
  })

  it('AC17：已有統計資料時自動更新失敗，仍顯示原本的統計而不是錯誤狀態', async () => {
    summaryRef.value = fakeSummary()
    errorRef.value = true
    const wrapper = render()
    await flushPromises()

    expect(wrapper.find('[data-testid="error"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="kpi-completion"]').exists()).toBe(true)
  })
})
