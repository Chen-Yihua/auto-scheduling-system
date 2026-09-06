import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { ref, watch, onMounted } from 'vue'

vi.stubGlobal('ref', ref)
vi.stubGlobal('watch', watch)
vi.stubGlobal('onMounted', onMounted)

// ---------- Clerk mock：isSignedIn 可由測試動態控制 ----------
const isSignedInRef = ref<boolean | undefined>(undefined)

vi.mock('@clerk/vue', () => ({
  useUser: () => ({ isSignedIn: isSignedInRef }),
  SignedIn: {
    setup(_props: unknown, { slots }: any) {
      return () => (isSignedInRef.value ? slots.default?.() : null)
    },
  },
  SignedOut: {
    setup(_props: unknown, { slots }: any) {
      return () => (!isSignedInRef.value ? slots.default?.() : null)
    },
  },
}))

// ---------- 需要授權的 composables：用 spy 追蹤有沒有被呼叫 ----------
const fetchGithubIssuesSpy = vi.fn()
const fetchJiraIssuesSpy = vi.fn()
const fetchGoogleCalendarsSpy = vi.fn()

vi.mock('@/composables/useGithub', () => ({
  useGithub: () => ({
    issues: ref([]),
    fetchGithubIssues: fetchGithubIssuesSpy,
    isStale: ref(false),
    syncedAt: ref(null),
  }),
}))

vi.stubGlobal('useJira', () => ({
  issues: ref([]),
  fetchJiraIssues: fetchJiraIssuesSpy,
  domain: ref(''),
  isStale: ref(false),
  syncedAt: ref(null),
}))

vi.stubGlobal('useGoogleCalendar', () => ({
  calendarIds: ref([]),
  primaryCalendarId: ref(''),
  fetchGoogleCalendars: fetchGoogleCalendarsSpy,
  isConnected: ref(false),
}))

// ---------- 子元件全部 shallow stub，只測這個頁面本身的邏輯 ----------
const uiStubs = {
  TaskForm: true,
  Leetcode: true,
  News: true,
  MoodleAssignments: true,
  GithubIssuesList: true,
  JiraIssuesList: true,
  GoogleCalendarEmbed: true,
  UIcon: true,
}

import TheMainIndex from '~/components/TheMain/index.vue'

describe('TheMain/index.vue', () => {
  let activeWrapper: ReturnType<typeof mount> | null = null

  beforeEach(() => {
    isSignedInRef.value = undefined
    fetchGithubIssuesSpy.mockClear()
    fetchJiraIssuesSpy.mockClear()
    fetchGoogleCalendarsSpy.mockClear()
  })

  afterEach(() => {
    // isSignedInRef 是共用的 module-level ref，前一個測試留下的元件如果沒
    // unmount，watch(isSignedIn, ...) 還是活的，下個測試改值時會被重複觸發
    activeWrapper?.unmount()
    activeWrapper = null
  })

  it('Clerk 還在載入（isSignedIn undefined）時，不會打任何需要授權的 API', () => {
    activeWrapper = mount(TheMainIndex, { global: { stubs: uiStubs } })

    expect(fetchGithubIssuesSpy).not.toHaveBeenCalled()
    expect(fetchJiraIssuesSpy).not.toHaveBeenCalled()
    expect(fetchGoogleCalendarsSpy).not.toHaveBeenCalled()
  })

  it('未登入（isSignedIn=false）時，不會打任何需要授權的 API，也不顯示需要登入的區塊', async () => {
    isSignedInRef.value = false
    const wrapper = mount(TheMainIndex, { global: { stubs: uiStubs } })
    activeWrapper = wrapper
    await wrapper.vm.$nextTick()

    expect(fetchGithubIssuesSpy).not.toHaveBeenCalled()
    expect(fetchJiraIssuesSpy).not.toHaveBeenCalled()
    expect(fetchGoogleCalendarsSpy).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('登入後即可查看')
    expect(wrapper.findComponent({ name: 'GithubIssuesList' }).exists()).toBe(false)
  })

  it('已登入（isSignedIn=true）時，才會打需要授權的 API', async () => {
    isSignedInRef.value = true
    const wrapper = mount(TheMainIndex, { global: { stubs: uiStubs } })
    activeWrapper = wrapper
    await wrapper.vm.$nextTick()

    expect(fetchGithubIssuesSpy).toHaveBeenCalledTimes(1)
    expect(fetchJiraIssuesSpy).toHaveBeenCalledTimes(1)
    expect(fetchGoogleCalendarsSpy).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).not.toContain('登入後即可查看')
  })
})
