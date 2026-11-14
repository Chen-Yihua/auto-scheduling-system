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

// ---------- 需要授權的 composables：每個平台各一個 spy ----------
const fetchItemsSpies = { github: vi.fn(), jira: vi.fn(), moodle: vi.fn() }
const syncNowSpies = { github: vi.fn(), jira: vi.fn(), moodle: vi.fn() }
const syncedAtByPlatform = { github: '2026-11-14T04:00:00Z', jira: '2026-11-13T04:00:00Z', moodle: null }
const fetchGoogleCalendarsSpy = vi.fn()

vi.mock('@/composables/usePlatformItems', () => ({
  usePlatformItems: (platform: 'github' | 'jira' | 'moodle') => ({
    items: ref([]),
    account: ref(undefined),
    fetchItems: fetchItemsSpies[platform],
    syncNow: syncNowSpies[platform],
    syncing: ref(false),
    isStale: ref(false),
    syncedAt: ref(syncedAtByPlatform[platform]),
    authError: ref(false),
    notLinked: ref(false),
    needsReauth: ref(false),
    unavailable: ref(false),
    loading: ref(false),
  }),
}))

const calendarReloadTokenRef = ref(0)
const needsReconnectRef = ref(false)
const calendarUnavailableRef = ref(false)
vi.stubGlobal('useGoogleCalendar', () => ({
  needsReconnect: needsReconnectRef,
  unavailable: calendarUnavailableRef,
  calendarIds: ref([]),
  primaryCalendarId: ref(''),
  fetchGoogleCalendars: fetchGoogleCalendarsSpy,
  isConnected: ref(false),
  calendarReloadToken: calendarReloadTokenRef,
}))

// ---------- 子元件全部 shallow stub，只測這個頁面本身的邏輯 ----------
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

describe('dashboard/Dashboard.vue', () => {
  let activeWrapper: ReturnType<typeof mount> | null = null

  beforeEach(() => {
    isSignedInRef.value = undefined
    stateStore.clear()
    Object.values(fetchItemsSpies).forEach(spy => spy.mockClear())
    Object.values(syncNowSpies).forEach(spy => spy.mockReset())
    fetchGoogleCalendarsSpy.mockClear()
  })

  afterEach(() => {
    // isSignedInRef 是共用的，沒 unmount 的話上一個元件的 watch 會被觸發
    activeWrapper?.unmount()
    activeWrapper = null
  })

  it('Clerk 還在載入（isSignedIn undefined）時，不會打任何需要授權的 API', () => {
    activeWrapper = mount(Dashboard, { global: { stubs: uiStubs } })

    Object.values(fetchItemsSpies).forEach(spy => expect(spy).not.toHaveBeenCalled())
    expect(fetchGoogleCalendarsSpy).not.toHaveBeenCalled()
  })

  it('Clerk 還在載入時，先不畫任何卡片，避免登入的人先閃一下「請先登入」', () => {
    activeWrapper = mount(Dashboard, { global: { stubs: uiStubs } })

    expect(activeWrapper.text()).not.toContain('登入後即可')
    expect(activeWrapper.find('.grid').exists()).toBe(false)
  })

  it('未登入（isSignedIn=false）時，不會打任何需要授權的 API，也不掛載需要登入的元件', async () => {
    isSignedInRef.value = false
    const wrapper = mount(Dashboard, { global: { stubs: uiStubs } })
    activeWrapper = wrapper
    await wrapper.vm.$nextTick()

    Object.values(fetchItemsSpies).forEach(spy => expect(spy).not.toHaveBeenCalled())
    expect(fetchGoogleCalendarsSpy).not.toHaveBeenCalled()
    // TaskForm、Moodle 掛載時會自己去抓資料，訪客不該讓它們掛載
    for (const name of ['TaskForm', 'ScheduleSuggestion', 'MoodleAssignmentsList', 'GithubIssuesList', 'JiraIssuesList', 'GoogleCalendarEmbed']) {
      expect(wrapper.findComponent({ name }).exists(), name).toBe(false)
    }
  })

  it('未登入時，需要登入的區塊各放一張提示卡，順序跟登入後一樣；不需登入的 News／Leetcode 照常顯示', async () => {
    isSignedInRef.value = false
    const wrapper = mount(Dashboard, { global: { stubs: uiStubs } })
    activeWrapper = wrapper
    await wrapper.vm.$nextTick()

    const titles = wrapper.findAll('.ucard span').map((el) => el.text())
    expect(titles).toEqual(['任務列表', '排程建議', 'Moodle 作業', 'GitHub 參與項目', 'Jira 指派任務', 'Google 行事曆'])
    expect(wrapper.text()).toContain('登入後即可查看與新增你的任務')
    expect(wrapper.text()).toContain('登入後即可查看 Google 行事曆')
    expect(wrapper.findComponent({ name: 'News' }).exists()).toBe(true)
    expect(wrapper.findComponent({ name: 'Leetcode' }).exists()).toBe(true)
  })

  it('登入前後三欄版面一樣：每一欄的卡片數量相同，News／Leetcode 都在右欄', async () => {
    isSignedInRef.value = false
    const guest = mount(Dashboard, { global: { stubs: uiStubs } })
    await guest.vm.$nextTick()
    const guestSizes = columnSizes(guest)
    guest.unmount()

    isSignedInRef.value = true
    const signedIn = mount(Dashboard, { global: { stubs: uiStubs } })
    activeWrapper = signedIn
    await signedIn.vm.$nextTick()

    expect(guestSizes).toEqual([5, 1, 2])
    expect(columnSizes(signedIn)).toEqual(guestSizes)
    const rightColumn = signedIn.findAll('.grid > div')[2]!
    expect(rightColumn.findComponent({ name: 'News' }).exists()).toBe(true)
    expect(rightColumn.findComponent({ name: 'Leetcode' }).exists()).toBe(true)
  })

  it('已登入（isSignedIn=true）時，才會打需要授權的 API', async () => {
    isSignedInRef.value = true
    const wrapper = mount(Dashboard, { global: { stubs: uiStubs } })
    activeWrapper = wrapper
    await wrapper.vm.$nextTick()

    Object.values(fetchItemsSpies).forEach(spy => expect(spy).toHaveBeenCalledTimes(1))
    expect(fetchGoogleCalendarsSpy).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).not.toContain('登入後即可')
    expect(wrapper.findComponent({ name: 'TaskForm' }).exists()).toBe(true)
    expect(wrapper.findComponent({ name: 'ScheduleSuggestion' }).exists()).toBe(true)
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
    for (const name of ['TaskForm', 'ScheduleSuggestion', 'MoodleAssignmentsList', 'GithubIssuesList', 'JiraIssuesList', 'News', 'Leetcode']) {
      expect(wrapper.findComponent({ name }).exists(), name).toBe(true)
    }
  })

  it('AC1：Google 授權失效時，行事曆卡片收到 needsReconnect，改顯示「授權已失效」', async () => {
    isSignedInRef.value = true
    needsReconnectRef.value = false
    const wrapper = mount(Dashboard, { global: { stubs: uiStubs } })
    activeWrapper = wrapper
    await wrapper.vm.$nextTick()

    const calendar = wrapper.findComponent({ name: 'GoogleCalendarEmbed' })
    expect(calendar.props('needsReconnect')).toBe(false)

    needsReconnectRef.value = true
    await wrapper.vm.$nextTick()

    expect(calendar.props('needsReconnect')).toBe(true)
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

  describe('外部平台定時同步（issue #13）', () => {
    it('AC30：打開儀表板只讀資料（fetchItems），不呼叫立即同步', async () => {
      isSignedInRef.value = true
      const wrapper = mount(Dashboard, { global: { stubs: uiStubs } })
      activeWrapper = wrapper
      await wrapper.vm.$nextTick()

      Object.values(fetchItemsSpies).forEach(spy => expect(spy).toHaveBeenCalledTimes(1))
      Object.values(syncNowSpies).forEach(spy => expect(spy).not.toHaveBeenCalled())
    })

    it('AC34、AC35：按「立即同步」同時呼叫三個平台的同步；其中一個失敗不影響其他平台', async () => {
      isSignedInRef.value = true
      syncNowSpies.jira.mockRejectedValueOnce(new Error('Jira 掛了'))
      const wrapper = mount(Dashboard, { global: { stubs: uiStubs } })
      activeWrapper = wrapper
      await wrapper.vm.$nextTick()

      await wrapper.find('[data-testid="dashboard-sync-now"]').trigger('click')

      Object.values(syncNowSpies).forEach(spy => expect(spy).toHaveBeenCalledTimes(1))
    })

    it('AC36：三個平台的卡片各自收到自己的上次同步時間；卡片上不放立即同步按鈕', async () => {
      isSignedInRef.value = true
      const wrapper = mount(Dashboard, { global: { stubs: uiStubs } })
      activeWrapper = wrapper
      await wrapper.vm.$nextTick()

      const cards = {
        github: wrapper.findComponent({ name: 'GithubIssuesList' }),
        jira: wrapper.findComponent({ name: 'JiraIssuesList' }),
        moodle: wrapper.findComponent({ name: 'MoodleAssignmentsList' }),
      }
      for (const [platform, card] of Object.entries(cards)) {
        expect(card.props('syncedAt'), platform).toBe(syncedAtByPlatform[platform as keyof typeof syncedAtByPlatform])
        expect(card.props('onSync'), platform).toBeUndefined()
      }
    })
  })
})
