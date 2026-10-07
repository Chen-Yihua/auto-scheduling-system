import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import JiraIssuesList from '~/components/platforms/JiraIssuesList.vue'

// UCard 的預設 auto-stub（`true`）不會渲染 slot 內容，這裡改用會渲染
// header/default/footer slot 的 stub，才能斷言卡片裡實際顯示了什麼
const UCardStub = defineComponent({
  name: 'UCard',
  emits: ['click'],
  setup(_, { slots, emit }) {
    return () =>
      h('div', { class: 'u-card-stub', onClick: () => emit('click') }, [
        slots.header?.(),
        slots.default?.(),
        slots.footer?.(),
      ])
  },
})

const uiStubs = {
  USkeleton: true,
  UBadge: true,
  UAvatar: true,
  UCard: UCardStub,
  UAlert: true,
  UIcon: true,
  NuxtLink: { template: '<a><slot /></a>' },
}

const openSpy = vi.fn()
vi.stubGlobal('open', openSpy)

const baseIssue = {
  id: '1',
  key: 'ISSUE-1',
  summary: 'a',
  status: 'Open',
  type: 'Task',
  title: 'Fix the bug',
  assignee: 'Alice',
  avatar: '',
  iconUrl: '',
  updated_at: '2025-07-01T00:00:00Z',
}

describe('JiraIssuesList.vue', () => {
  it('loading 時顯示 Skeleton，不顯示任何清單內容', () => {
    const wrapper = mount(JiraIssuesList, {
      props: { issues: [], loading: true },
      global: { stubs: uiStubs },
    })

    expect(wrapper.find('u-skeleton-stub').exists()).toBe(true)
    expect(wrapper.text()).not.toContain('尚無資料')
  })

  it('notLinked 為 true 時顯示尚未綁定提示，不顯示 Skeleton 或清單', () => {
    const wrapper = mount(JiraIssuesList, {
      props: { issues: [], loading: false, notLinked: true },
      global: { stubs: uiStubs },
    })

    expect(wrapper.text()).toContain('尚未綁定 Jira 帳號')
    expect(wrapper.find('u-skeleton-stub').exists()).toBe(false)
  })

  it('已連結但沒有 issues 時顯示尚無資料', () => {
    const wrapper = mount(JiraIssuesList, {
      props: { issues: [], loading: false, notLinked: false },
      global: { stubs: uiStubs },
    })

    expect(wrapper.text()).toContain('尚無資料')
  })

  it('有 issues 時渲染卡片，點擊會用 domain 開啟對應的 Jira 網址', async () => {
    const wrapper = mount(JiraIssuesList, {
      props: { issues: [baseIssue], loading: false, domain: 'my-team.atlassian.net' },
      global: { stubs: uiStubs },
    })

    expect(wrapper.text()).toContain('ISSUE-1')
    expect(wrapper.text()).toContain('Fix the bug')

    // 整個區塊現在也包在外層的 UCard 裡（跟 Hacker News 一樣的外框），
    // 所以畫面上有兩層 .u-card-stub：index 0 是外層的區塊容器（文字內容
    // 涵蓋整個區塊，也會包含 'ISSUE-1'，不能用文字比對來分辨），
    // index 1 才是真正顯示這筆 issue 內容的那一張卡片
    const cards = wrapper.findAll('.u-card-stub')
    expect(cards.length).toBe(2)
    await cards[1].trigger('click')

    expect(openSpy).toHaveBeenCalledWith(
      'https://my-team.atlassian.net/browse/ISSUE-1',
      '_blank',
    )
  })

  it('沒有 domain 時點擊不開任何網址，不能退回寫死的網域把使用者帶到別人的 Jira', async () => {
    openSpy.mockClear()
    const wrapper = mount(JiraIssuesList, {
      props: { issues: [baseIssue], loading: false, domain: '' },
      global: { stubs: uiStubs },
    })

    await wrapper.findAll('.u-card-stub')[1].trigger('click')

    expect(openSpy).not.toHaveBeenCalled()
  })

  it('沒帶 limit 時顯示全部 issues，不顯示「查看全部」連結', () => {
    const issues = [baseIssue, { ...baseIssue, id: '2', key: 'ISSUE-2' }]
    const wrapper = mount(JiraIssuesList, {
      props: { issues, loading: false },
      global: { stubs: uiStubs },
    })

    expect(wrapper.text()).toContain('ISSUE-1')
    expect(wrapper.text()).toContain('ISSUE-2')
    expect(wrapper.text()).not.toContain('查看全部')
  })

  it('帶 limit 且 issues 超過限制時，只顯示前 limit 筆，並顯示「查看全部」連結', () => {
    const issues = [baseIssue, { ...baseIssue, id: '2', key: 'ISSUE-2' }, { ...baseIssue, id: '3', key: 'ISSUE-3' }]
    const wrapper = mount(JiraIssuesList, {
      props: { issues, loading: false, limit: 2 },
      global: { stubs: uiStubs },
    })

    expect(wrapper.text()).toContain('ISSUE-1')
    expect(wrapper.text()).toContain('ISSUE-2')
    expect(wrapper.text()).not.toContain('ISSUE-3')
    expect(wrapper.text()).toContain('查看全部（3）')
  })
})
