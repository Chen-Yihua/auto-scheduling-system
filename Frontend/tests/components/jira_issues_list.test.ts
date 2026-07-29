// tests/components/jiraIssuesList.test.ts
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import JiraIssuesList from '~/components/TheMain/JiraIssuesList.vue'

const uiStubs = {
  USkeleton: true,
  UBadge: true,
  UAvatar: true,
  UCard: true,
}

describe('JiraIssuesList.vue', () => {
  it('connect=true 且 calendarIds 有值時會生成含 Google Calendar 的 iframe', () => {
    const wrapper = mount(JiraIssuesList, {
      props: { 
        calendarIds: 'cal1@group.calendar.google.com', 
        id: 'dummy', 
        connect: true,
        issues: [],
        loading: false, 
        },
      global: {
        stubs: uiStubs,
      }
    })

    expect(wrapper.html()).toContain('calendar.google.com')
  })

  it('未連線或 calendarIds 為空時顯示空狀態文字', () => {
    const wrapper = mount(JiraIssuesList, {
      props: { 
        calendarIds: [], 
        id: 'bar', 
        connect: false,
        issues: [],
        loading: false, 
      },
      global: {
        stubs: uiStubs,
      }
    })

    expect(wrapper.find('iframe').exists()).toBe(false)
    expect(wrapper.text()).toMatch(/尚未連接|尚無資料/)
  })
})
