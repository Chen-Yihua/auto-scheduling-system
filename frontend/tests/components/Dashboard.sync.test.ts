// 儀表板的立即同步接上真的 usePlatformItems：一個平台失敗時，其他平台照常更新，只對失敗的平台跳錯誤訊息（issue #13）
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises, enableAutoUnmount } from '@vue/test-utils'
import { ref, computed, watch, onMounted, h, defineComponent, type Ref } from 'vue'

import Dashboard from '~/components/dashboard/Dashboard.vue'

vi.stubGlobal('ref', ref)
vi.stubGlobal('computed', computed)
vi.stubGlobal('watch', watch)
vi.stubGlobal('onMounted', onMounted)

const stateStore = new Map<string, Ref<unknown>>()
vi.stubGlobal('useState', (key: string, init: () => unknown) => {
  if (!stateStore.has(key)) stateStore.set(key, ref(init()))
  return stateStore.get(key)
})
vi.stubGlobal('useRuntimeConfig', () => ({ public: { apiBaseUrl: 'http://api' } }))

const isSignedInRef = ref<boolean | undefined>(true)
vi.mock('@clerk/vue', async () => {
  const { ref } = await import('vue')
  return {
    useUser: () => ({ isSignedIn: isSignedInRef }),
    useAuth: () => ({ getToken: { value: async () => 'jwt-token' }, userId: ref('user_a') }),
  }
})

const toastSpy = { add: vi.fn() }
vi.stubGlobal('useToast', () => toastSpy)
const linkedKeys = ref([
  { platform: 'github', value: 'KEY****' },
  { platform: 'jira', value: 'KEY****', domain: 'team.atlassian.net' },
  { platform: 'moodle', value: 'PW****' },
])
vi.stubGlobal('useLinkedAccount', () => ({ keys: linkedKeys, fetchKeys: vi.fn().mockResolvedValue(undefined) }))
vi.stubGlobal('useGoogleCalendar', () => ({
  needsReconnect: ref(false),
  unavailable: ref(false),
  calendarIds: ref([]),
  primaryCalendarId: ref(''),
  fetchGoogleCalendars: vi.fn(),
  isConnected: ref(false),
  calendarReloadToken: ref(0),
}))

const fetchRaw = vi.fn()
vi.stubGlobal('$fetch', Object.assign(vi.fn(), { raw: (...args: unknown[]) => fetchRaw(...args) }))
const ok = (data: unknown[]) => ({ _data: data, headers: new Headers({ 'X-Synced-At': '2026-11-14T05:00:00Z' }) })

const uiStubs = {
  TaskForm: true,
  ScheduleSuggestion: true,
  Leetcode: true,
  News: true,
  MoodleAssignmentsList: true,
  GithubIssuesList: true,
  JiraIssuesList: true,
  GoogleCalendarEmbed: true,
  UIcon: true,
  UButton: defineComponent({
    name: 'UButton',
    emits: ['click'],
    setup(_props, { slots, emit, attrs }) {
      return () => h('button', { ...attrs, onClick: () => emit('click') }, slots.default?.())
    },
  }),
}

enableAutoUnmount(afterEach)

describe('dashboard/Dashboard.vue 立即同步', () => {
  beforeEach(() => {
    toastSpy.add.mockClear()
    fetchRaw.mockReset()
    stateStore.clear()
    linkedKeys.value = [
      { platform: 'github', value: 'KEY****' },
      { platform: 'jira', value: 'KEY****', domain: 'team.atlassian.net' },
      { platform: 'moodle', value: 'PW****' },
    ]
  })

  it('AC34、AC35：三個平台各呼叫自己的 POST；Jira 失敗時 GitHub、Moodle 仍更新，只跳一個 Jira 的錯誤訊息', async () => {
    // 進頁面時的三個 GET
    fetchRaw.mockResolvedValue(ok([]))
    const wrapper = mount(Dashboard, { global: { stubs: uiStubs } })
    await flushPromises()

    fetchRaw.mockReset()
    fetchRaw.mockImplementation(async (url: string) => {
      if (url === 'http://api/jira/sync') throw { response: { status: 502 }, data: { error_code: 'UPSTREAM_ERROR', detail: '說明' } }
      return ok([{ id: url }])
    })
    await wrapper.find('[data-testid="dashboard-sync-now"]').trigger('click')
    await flushPromises()

    const posted = fetchRaw.mock.calls.map(([url, options]) => [url, options.method])
    expect(posted).toEqual(expect.arrayContaining([
      ['http://api/github/sync', 'POST'],
      ['http://api/jira/sync', 'POST'],
      ['http://api/moodle/sync', 'POST'],
    ]))
    expect(posted).toHaveLength(3)
    expect(wrapper.findComponent({ name: 'GithubIssuesList' }).props('issues')).toEqual([{ id: 'http://api/github/sync' }])
    expect(wrapper.findComponent({ name: 'MoodleAssignmentsList' }).props('assignments')).toEqual([{ id: 'http://api/moodle/sync' }])
    expect(toastSpy.add).toHaveBeenCalledTimes(1)
    expect(toastSpy.add.mock.calls[0]![0].title).toContain('Jira')
  })

  it('AC35：進儀表板時 GitHub 尚未綁定，之後按立即同步成功 → GitHub 卡片不再顯示尚未綁定，清單已更新', async () => {
    linkedKeys.value = [
      { platform: 'github', value: '' },
      { platform: 'jira', value: 'KEY****', domain: 'team.atlassian.net' },
      { platform: 'moodle', value: 'PW****' },
    ]
    fetchRaw.mockResolvedValue(ok([]))
    const wrapper = mount(Dashboard, { global: { stubs: uiStubs } })
    await flushPromises()
    expect(wrapper.findComponent({ name: 'GithubIssuesList' }).props('notLinked')).toBe(true)

    fetchRaw.mockReset()
    fetchRaw.mockImplementation(async (url: string) => ok([{ id: url }]))
    await wrapper.find('[data-testid="dashboard-sync-now"]').trigger('click')
    await flushPromises()

    const github = wrapper.findComponent({ name: 'GithubIssuesList' })
    expect(github.props('notLinked')).toBe(false)
    expect(github.props('issues')).toEqual([{ id: 'http://api/github/sync' }])
  })
})
