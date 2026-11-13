// 三個平台清單共用的同步狀態：上次同步時間、立即同步按鈕、授權失效提示（issue #13）
import { describe, it, expect, vi, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent, h, type Component } from 'vue'

import GithubIssuesList from '~/components/platforms/GithubIssuesList.vue'
import JiraIssuesList from '~/components/platforms/JiraIssuesList.vue'
import MoodleAssignmentsList from '~/components/platforms/MoodleAssignmentsList.vue'

// UCard 預設的 stub 不渲染 slot，改用會渲染 slot 的假元件
const UCardStub = defineComponent({
  name: 'UCard',
  setup(_, { slots }) {
    return () => h('div', [slots.header?.(), slots.default?.(), slots.footer?.()])
  },
})

const UButtonStub = defineComponent({
  name: 'UButton',
  props: ['loading', 'disabled'],
  emits: ['click'],
  setup(props, { slots, emit, attrs }) {
    return () => h('button', { ...attrs, disabled: props.disabled || props.loading, onClick: () => emit('click') }, slots.default?.())
  },
})

const uiStubs = {
  UCard: UCardStub,
  UButton: UButtonStub,
  UAlert: defineComponent({ props: ['title'], setup: (props) => () => h('div', { class: 'alert' }, props.title) }),
  USkeleton: true,
  UBadge: true,
  UAvatar: true,
  UIcon: true,
  NuxtLink: { template: '<a><slot /></a>' },
}

const LISTS = [
  { name: 'GithubIssuesList', component: GithubIssuesList, itemsProp: 'issues', label: 'GitHub' },
  { name: 'JiraIssuesList', component: JiraIssuesList, itemsProp: 'issues', label: 'Jira' },
  { name: 'MoodleAssignmentsList', component: MoodleAssignmentsList, itemsProp: 'assignments', label: 'Moodle' },
] as const

describe.each(LISTS)('$name：同步狀態', ({ component, itemsProp, label }) => {
  const render = (props: Record<string, unknown> = {}) =>
    // 三個元件的清單 prop 名稱不同，用共用的 Component 型別掛載
    mount(component as Component, { props: { [itemsProp]: [], loading: false, ...props }, global: { stubs: uiStubs } })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('AC32：一律顯示上次同步時間（不只在退回舊資料時）', () => {
    vi.useFakeTimers().setSystemTime(new Date('2026-11-14T07:00:00Z'))

    const wrapper = render({ syncedAt: '2026-11-14T04:00:00Z', isStale: false })

    expect(wrapper.find('[data-testid="synced-at"]').text()).toBe('上次同步：3 小時前')
  })

  it('AC33：沒有同步紀錄時顯示「尚未同步」', () => {
    const wrapper = render({ syncedAt: null })

    expect(wrapper.find('[data-testid="synced-at"]').text()).toBe('尚未同步')
  })

  it('AC31：有傳 onSync 才顯示立即同步按鈕，按下呼叫它；同步中按鈕停用', async () => {
    expect(render().find('[data-testid="sync-now"]').exists()).toBe(false)

    const onSync = vi.fn()
    const wrapper = render({ onSync, syncing: false })
    await wrapper.find('[data-testid="sync-now"]').trigger('click')
    expect(onSync).toHaveBeenCalledTimes(1)

    const syncing = render({ onSync, syncing: true })
    expect(syncing.find('[data-testid="sync-now"]').attributes('disabled')).toBeDefined()
  })

  it('AC39：isStale 為 false、authError 為 true 時，顯示授權失效的提示', () => {
    const wrapper = render({ isStale: false, authError: true, syncedAt: '2026-11-14T04:00:00Z' })

    expect(wrapper.find('.alert').text()).toContain(`${label} 授權可能已失效`)
  })

  it('isStale 與 authError 都是 false 時不顯示提示', () => {
    const wrapper = render({ isStale: false, authError: false, syncedAt: '2026-11-14T04:00:00Z' })

    expect(wrapper.find('.alert').exists()).toBe(false)
  })
})
