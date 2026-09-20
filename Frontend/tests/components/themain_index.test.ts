import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { ref, watch, onMounted, h, defineComponent } from 'vue'

import TheMainIndex from '~/components/TheMain/index.vue'

vi.stubGlobal('ref', ref)
vi.stubGlobal('watch', watch)
vi.stubGlobal('onMounted', onMounted)

// ---------- Clerk mock：isSignedIn 可由測試動態控制 ----------
const isSignedInRef = ref<boolean | undefined>(undefined)

vi.mock('@clerk/vue', () => ({
  useUser: () => ({ isSignedIn: isSignedInRef }),
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
    loading: ref(false),
  }),
}))

vi.stubGlobal('useJira', () => ({
  issues: ref([]),
  fetchJiraIssues: fetchJiraIssuesSpy,
  domain: ref(''),
  isStale: ref(false),
  syncedAt: ref(null),
  loading: ref(false),
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
  // LoginRequiredCard 用到 UCard 的 header slot，要用會把 slot 畫出來的假元件
  UCard: defineComponent({
    setup(_props, { slots }) {
      return () => h('div', { class: 'ucard' }, [slots.header?.(), slots.default?.()])
    },
  }),
}

// 取出三欄各自有幾張卡片（第一層子元素），拿來比對登入前後版面是否一樣
function columnSizes(wrapper: ReturnType<typeof mount>) {
  return wrapper.findAll('.grid > div').map((col) => col.element.children.length)
}

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

  it('Clerk 還在載入時，先不畫任何卡片，避免登入的人先閃一下「請先登入」', () => {
    activeWrapper = mount(TheMainIndex, { global: { stubs: uiStubs } })

    expect(activeWrapper.text()).not.toContain('登入後即可')
    expect(activeWrapper.find('.grid').exists()).toBe(false)
  })

  it('未登入（isSignedIn=false）時，不會打任何需要授權的 API，也不掛載需要登入的元件', async () => {
    isSignedInRef.value = false
    const wrapper = mount(TheMainIndex, { global: { stubs: uiStubs } })
    activeWrapper = wrapper
    await wrapper.vm.$nextTick()

    expect(fetchGithubIssuesSpy).not.toHaveBeenCalled()
    expect(fetchJiraIssuesSpy).not.toHaveBeenCalled()
    expect(fetchGoogleCalendarsSpy).not.toHaveBeenCalled()
    // TaskForm、Moodle 掛載時會自己去抓資料，訪客不該讓它們掛載
    for (const name of ['TaskForm', 'MoodleAssignments', 'GithubIssuesList', 'JiraIssuesList', 'GoogleCalendarEmbed']) {
      expect(wrapper.findComponent({ name }).exists(), name).toBe(false)
    }
  })

  it('未登入時，需要登入的區塊各放一張提示卡，順序跟登入後一樣；不需登入的 News／Leetcode 照常顯示', async () => {
    isSignedInRef.value = false
    const wrapper = mount(TheMainIndex, { global: { stubs: uiStubs } })
    activeWrapper = wrapper
    await wrapper.vm.$nextTick()

    const titles = wrapper.findAll('.ucard span').map((el) => el.text())
    expect(titles).toEqual(['任務列表', 'Moodle 作業', 'GitHub 參與項目', 'Jira 指派任務', 'Google 行事曆'])
    expect(wrapper.text()).toContain('登入後即可查看與新增你的任務')
    expect(wrapper.text()).toContain('登入後即可查看 Google 行事曆')
    expect(wrapper.findComponent({ name: 'News' }).exists()).toBe(true)
    expect(wrapper.findComponent({ name: 'Leetcode' }).exists()).toBe(true)
  })

  it('登入前後三欄版面一樣：每一欄的卡片數量相同，News／Leetcode 都在右欄', async () => {
    isSignedInRef.value = false
    const guest = mount(TheMainIndex, { global: { stubs: uiStubs } })
    await guest.vm.$nextTick()
    const guestSizes = columnSizes(guest)
    guest.unmount()

    isSignedInRef.value = true
    const signedIn = mount(TheMainIndex, { global: { stubs: uiStubs } })
    activeWrapper = signedIn
    await signedIn.vm.$nextTick()

    expect(guestSizes).toEqual([4, 1, 2])
    expect(columnSizes(signedIn)).toEqual(guestSizes)
    const rightColumn = signedIn.findAll('.grid > div')[2]!
    expect(rightColumn.findComponent({ name: 'News' }).exists()).toBe(true)
    expect(rightColumn.findComponent({ name: 'Leetcode' }).exists()).toBe(true)
  })

  it('已登入（isSignedIn=true）時，才會打需要授權的 API', async () => {
    isSignedInRef.value = true
    const wrapper = mount(TheMainIndex, { global: { stubs: uiStubs } })
    activeWrapper = wrapper
    await wrapper.vm.$nextTick()

    expect(fetchGithubIssuesSpy).toHaveBeenCalledTimes(1)
    expect(fetchJiraIssuesSpy).toHaveBeenCalledTimes(1)
    expect(fetchGoogleCalendarsSpy).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).not.toContain('登入後即可')
    expect(wrapper.findComponent({ name: 'TaskForm' }).exists()).toBe(true)
  })
})
