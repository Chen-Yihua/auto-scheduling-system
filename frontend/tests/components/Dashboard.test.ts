import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { ref, watch, onMounted, h, defineComponent, type Ref } from 'vue'

import Dashboard from '~/components/dashboard/Dashboard.vue'

vi.stubGlobal('ref', ref)
vi.stubGlobal('watch', watch)
vi.stubGlobal('onMounted', onMounted)

// Nuxt 的 useState：同一個 key 在所有元件之間共用同一份狀態
const stateStore = new Map<string, Ref<unknown>>()
vi.stubGlobal('useState', (key: string, init: () => unknown) => {
  if (!stateStore.has(key)) stateStore.set(key, ref(init()))
  return stateStore.get(key)
})

vi.stubGlobal('useRuntimeConfig', () => ({ public: { apiBaseUrl: 'http://api' } }))

// ---------- Clerk mock：isSignedIn 可由測試動態控制 ----------
const isSignedInRef = ref<boolean | undefined>(undefined)

vi.mock('@clerk/vue', () => ({
  useUser: () => ({ isSignedIn: isSignedInRef }),
}))

// ---------- 需要授權的 composables ----------
const fetchGoogleCalendarsSpy = vi.fn()

const calendarReloadTokenRef = ref(0)
const calendarUnavailableRef = ref(false)
const awaitingFirstResultRef = ref(false)
vi.stubGlobal('useGoogleCalendar', () => ({
  // 已移除的欄位：留著才驗得出 Dashboard 有沒有停止把它傳給卡片
  needsReconnect: ref(true),
  awaitingFirstResult: awaitingFirstResultRef,
  unavailable: calendarUnavailableRef,
  calendarIds: ref([]),
  primaryCalendarId: ref(''),
  fetchGoogleCalendars: fetchGoogleCalendarsSpy,
  isConnected: ref(false),
  calendarReloadToken: calendarReloadTokenRef,
}))

// ---------- 子元件全部 shallow stub，只測這個頁面本身的邏輯 ----------
const uiStubs = {
  TodayTasks: true,
  TaskForm: true,
  TaskEditModal: true,
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
  // LoginRequiredCard 用到 UCard 的 header slot，要用會把 slot 畫出來的假元件
  UCard: defineComponent({
    setup(_props, { slots }) {
      return () => h('div', { class: 'ucard' }, [slots.header?.(), slots.default?.()])
    },
  }),
}

const REMOVED_CARDS = ['TaskForm', 'ScheduleSuggestion', 'MoodleAssignmentsList', 'GithubIssuesList', 'JiraIssuesList']

describe('dashboard/Dashboard.vue', () => {
  let activeWrapper: ReturnType<typeof mount> | null = null

  beforeEach(() => {
    isSignedInRef.value = undefined
    stateStore.clear()
    fetchGoogleCalendarsSpy.mockClear()
  })

  afterEach(() => {
    // isSignedInRef 是共用的，沒 unmount 的話上一個元件的 watch 會被觸發
    activeWrapper?.unmount()
    activeWrapper = null
  })

  it('Clerk 還在載入（isSignedIn undefined）時，不會打任何需要授權的 API', () => {
    activeWrapper = mount(Dashboard, { global: { stubs: uiStubs } })

    expect(fetchGoogleCalendarsSpy).not.toHaveBeenCalled()
  })

  it('Clerk 還在載入時，先不畫任何卡片，避免登入的人先閃一下「請先登入」', () => {
    activeWrapper = mount(Dashboard, { global: { stubs: uiStubs } })

    expect(activeWrapper.text()).not.toContain('登入後即可')
    expect(activeWrapper.find('.grid').exists()).toBe(false)
  })

  it('issue-178 AC7：訪客只有今日卡片與行事曆兩張登入提示卡，News／Leetcode 照常顯示，不打需要授權的 API、不掛載需要登入的元件', async () => {
    isSignedInRef.value = false
    const wrapper = mount(Dashboard, { global: { stubs: uiStubs } })
    activeWrapper = wrapper
    await wrapper.vm.$nextTick()

    expect(fetchGoogleCalendarsSpy).not.toHaveBeenCalled()
    const titles = wrapper.findAll('.ucard span').map((el) => el.text())
    expect(titles).toEqual(['今日', 'Google 行事曆'])
    expect(wrapper.text()).toContain('登入後即可查看今天的任務')
    expect(wrapper.text()).toContain('登入後即可查看 Google 行事曆')
    expect(wrapper.findComponent({ name: 'News' }).exists()).toBe(true)
    expect(wrapper.findComponent({ name: 'Leetcode' }).exists()).toBe(true)
    for (const name of ['TodayTasks', 'GoogleCalendarEmbed', 'TaskEditModal', ...REMOVED_CARDS]) {
      expect(wrapper.findComponent({ name }).exists(), name).toBe(false)
    }
  })

  it('issue-178 AC5：已登入時只有今日卡片、Google 行事曆、Hacker News、LeetCode 4 張卡片；三欄版面維持左欄今日、中欄行事曆、右欄 News 與 Leetcode', async () => {
    isSignedInRef.value = true
    const wrapper = mount(Dashboard, { global: { stubs: uiStubs } })
    activeWrapper = wrapper
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).not.toContain('登入後即可')
    const columns = wrapper.findAll('.grid > div')
    expect(columns.map((col) => Array.from(col.element.querySelectorAll('*')).map((el) => el.tagName.toLowerCase()).filter((tag) => tag.endsWith('-stub')))).toEqual([
      ['today-tasks-stub'],
      ['google-calendar-embed-stub'],
      ['news-stub', 'leetcode-stub'],
    ])
    for (const name of REMOVED_CARDS) {
      expect(wrapper.findComponent({ name }).exists(), name).toBe(false)
    }
  })

  it('issue-178 AC8：已登入時掛載編輯視窗（今日卡片的「修改」要用），它不算一張卡片，不在三欄裡', async () => {
    isSignedInRef.value = true
    const wrapper = mount(Dashboard, { global: { stubs: uiStubs } })
    activeWrapper = wrapper
    await wrapper.vm.$nextTick()

    expect(wrapper.findComponent({ name: 'TaskEditModal' }).exists()).toBe(true)
    expect(wrapper.find('.grid').findComponent({ name: 'TaskEditModal' }).exists()).toBe(false)
  })

  it('issue-178 AC6：沒有「立即同步外部平台」按鈕', async () => {
    isSignedInRef.value = true
    const wrapper = mount(Dashboard, { global: { stubs: uiStubs } })
    activeWrapper = wrapper
    await wrapper.vm.$nextTick()

    expect(wrapper.find('[data-testid="dashboard-sync-now"]').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('立即同步外部平台')
  })

  it('已登入（isSignedIn=true）時，才會查行事曆', async () => {
    isSignedInRef.value = true
    const wrapper = mount(Dashboard, { global: { stubs: uiStubs } })
    activeWrapper = wrapper
    await wrapper.vm.$nextTick()

    expect(fetchGoogleCalendarsSpy).toHaveBeenCalledTimes(1)
  })

  it('Google 授權在背景進行時，只有行事曆卡片收到「連接中」，其他卡片照常掛載', async () => {
    isSignedInRef.value = true
    const wrapper = mount(Dashboard, { global: { stubs: uiStubs } })
    activeWrapper = wrapper
    await wrapper.vm.$nextTick()

    const calendar = wrapper.findComponent({ name: 'GoogleCalendarEmbed' })
    expect(calendar.props('connecting')).toBe(false)
    expect(calendar.props('reloadToken')).toBe(calendarReloadTokenRef.value)

    stateStore.get('googleCalendarConnecting')!.value = true
    await wrapper.vm.$nextTick()

    expect(calendar.props('connecting')).toBe(true)
    for (const name of ['TodayTasks', 'News', 'Leetcode']) {
      expect(wrapper.findComponent({ name }).exists(), name).toBe(true)
    }
  })

  it('AC2：沒連上時，行事曆卡片收到 connect=false，不再收到 needsReconnect', async () => {
    isSignedInRef.value = true
    const wrapper = mount(Dashboard, { global: { stubs: uiStubs } })
    activeWrapper = wrapper
    await wrapper.vm.$nextTick()

    const calendar = wrapper.findComponent({ name: 'GoogleCalendarEmbed' })
    expect(calendar.props('connect')).toBe(false)
    expect(calendar.props('needsReconnect')).toBeUndefined()
    expect(calendar.attributes('needs-reconnect')).toBeUndefined()
    expect(calendar.attributes('needsreconnect')).toBeUndefined()
  })

  it('AC7：第一次查詢還沒有結果的狀態傳給行事曆卡片', async () => {
    isSignedInRef.value = true
    awaitingFirstResultRef.value = true
    const wrapper = mount(Dashboard, { global: { stubs: uiStubs } })
    activeWrapper = wrapper
    await wrapper.vm.$nextTick()

    const calendar = wrapper.findComponent({ name: 'GoogleCalendarEmbed' })
    expect(calendar.props('loading')).toBe(true)

    awaitingFirstResultRef.value = false
    await wrapper.vm.$nextTick()
    expect(calendar.props('loading')).toBe(false)
  })

  it('Google 授權完成（連接成功次數 +1）時，重新查一次行事曆，卡片才會換成行事曆', async () => {
    isSignedInRef.value = true
    const wrapper = mount(Dashboard, { global: { stubs: uiStubs } })
    activeWrapper = wrapper
    await wrapper.vm.$nextTick()
    expect(fetchGoogleCalendarsSpy).toHaveBeenCalledTimes(1) // 進頁面時的那一次

    const connectedCount = stateStore.get('googleCalendarConnectedCount') as Ref<number>
    connectedCount.value++
    await wrapper.vm.$nextTick()

    expect(fetchGoogleCalendarsSpy).toHaveBeenCalledTimes(2)
  })

  it('AC1、AC20：行事曆暫時無法載入時，卡片收到 unavailable', async () => {
    isSignedInRef.value = true
    calendarUnavailableRef.value = true
    const wrapper = mount(Dashboard, { global: { stubs: uiStubs } })
    activeWrapper = wrapper
    await wrapper.vm.$nextTick()

    expect(wrapper.findComponent({ name: 'GoogleCalendarEmbed' }).props('unavailable')).toBe(true)
    calendarUnavailableRef.value = false
  })
})
