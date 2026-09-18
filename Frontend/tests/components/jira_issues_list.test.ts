// tests/components/jiraIssuesList.test.ts
import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import JiraIssuesList from '~/components/TheMain/JiraIssuesList.vue'

const uiStubs = {
  USkeleton: true,
  UBadge: true,
  UAvatar: true,
  UCard: true,
  UAlert: true,
  UIcon: true,
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

    await wrapper.find('u-card-stub').trigger('click')

    expect(openSpy).toHaveBeenCalledWith(
      'https://my-team.atlassian.net/browse/ISSUE-1',
      '_blank',
    )
  })
})
