import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ref as vueRef, computed as vueComputed, nextTick, type Ref } from 'vue'

// ---------- 載入被測 composable ----------
// 共用狀態（包括最近一次已知的結果）存在模組裡，每個測試重新載入才不會互相影響
let useGoogleCalendar: typeof import('~/composables/useGoogleCalendar')['useGoogleCalendar']

// ---------- Clerk mock ----------
// userId 要能切換，測登出／換使用者
const clerk = vi.hoisted(() => ({ userId: null as unknown as Ref<string | null> }))
vi.mock('@clerk/vue', async () => {
  const { ref } = await import('vue')
  clerk.userId = ref<string | null>('user_a')
  return {
    useAuth: () => ({
      getToken: { value: vi.fn().mockResolvedValue('jwt-token') },
      isLoaded: { value: true },
      userId: clerk.userId,
    }),
  }
})

// ---------- Nuxt auto-import 的 ref/computed ----------
vi.stubGlobal('ref', vueRef)                                         /** MOD */
vi.stubGlobal('computed', vueComputed)                               /** MOD */

// ---------- 其他 Nuxt 全域 stub ----------
const toastSpy = { add: vi.fn() }
vi.stubGlobal('useToast', () => toastSpy)
vi.stubGlobal('useRuntimeConfig', () => ({
  public: { apiBaseUrl: 'http://api', frontEndUrl: 'http://front', apiGoogleClientId: 'google-client-id' },
}))

// Nuxt 的 useState：同一個 key 在所有元件之間共用同一份狀態
const stateStore = new Map<string, Ref<unknown>>()
vi.stubGlobal('useState', (key: string, init: () => unknown) => {
  if (!stateStore.has(key)) stateStore.set(key, vueRef(init()))
  return stateStore.get(key)
})

// 依網址回應，兩個元件同時呼叫時才不會因為 mockResolvedValueOnce 的順序而混在一起
function respondByUrl(handlers: Record<string, () => Promise<unknown>>) {
  fetchSpy.mockImplementation((url: string) => handlers[url.replace('http://api', '')]!())
}

const callsTo = (path: string) => fetchSpy.mock.calls.filter(([url]) => url === `http://api${path}`).length

let fetchSpy = vi.fn()
// 按下重新連接會改 window.location.href，測完要換回 jsdom 原本的
const realLocation = window.location
vi.stubGlobal('$fetch', (...args: unknown[]) => fetchSpy(...args))

describe('useGoogleCalendar composable', () => {
  beforeEach(async () => {
    fetchSpy = vi.fn()
    toastSpy.add.mockClear()
    vi.resetModules()
    ;({ useGoogleCalendar } = await import('~/composables/useGoogleCalendar'))
    if (clerk.userId) clerk.userId.value = 'user_a'
  })

  it('成功抓取 Google Calendar 資料並設定 primary', async () => {
    const items = [
      { id: 'cal1', summary: '主行事曆', primary: true },
      { id: 'cal2', summary: '側行事曆', primary: false },
    ]
    // 1st call: 授權狀態檢查；2nd call: 實際抓行事曆清單
    fetchSpy.mockResolvedValueOnce({ connected: true })
    fetchSpy.mockResolvedValueOnce({ items })

    const ctx = useGoogleCalendar()
    await ctx.fetchGoogleCalendars()

    expect(fetchSpy).toHaveBeenNthCalledWith(
      1,
      'http://api/oauth/status',
      expect.objectContaining({
        method: 'GET',
        headers: { Authorization: 'Bearer jwt-token' },
      }),
    )
    expect(fetchSpy).toHaveBeenNthCalledWith(
      2,
      'http://api/oauth/calendars',
      expect.objectContaining({
        method: 'GET',
        headers: { Authorization: 'Bearer jwt-token' },
      }),
    )
    expect(ctx.isConnected.value).toBe(true)
    expect(ctx.calendarIds.value).toEqual(['cal1', 'cal2'])
    expect(ctx.calendarNames.value).toEqual(['主行事曆', '側行事曆'])
    expect(ctx.primaryCalendarId.value).toBe('cal1')
  })

  it('尚未做過 OAuth 授權時，根本不打 /oauth/calendars，也不跳任何 toast', async () => {
    fetchSpy.mockResolvedValueOnce({ connected: false })

    const ctx = useGoogleCalendar()
    await ctx.fetchGoogleCalendars()

    expect(fetchSpy).toHaveBeenCalledTimes(1)
    expect(fetchSpy).toHaveBeenCalledWith('http://api/oauth/status', expect.anything())
    expect(ctx.isConnected.value).toBe(false)
    expect(ctx.calendarIds.value).toEqual([])
    expect(toastSpy.add).not.toHaveBeenCalled()
  })

  it('AC20(3)：授權狀態檢查失敗而且沒有已知的結果 → 暫時無法載入，不顯示「已連接」也不變成「尚未連接」，不跳 toast，也不會誤打行事曆 API', async () => {
    fetchSpy.mockRejectedValueOnce(new Error('網路爆炸'))

    const ctx = useGoogleCalendar()
    await ctx.fetchGoogleCalendars()

    expect(fetchSpy).toHaveBeenCalledTimes(1)
    expect(ctx.isConnected.value).toBe(false)
    expect(ctx.needsReconnect.value).toBe(false)
    expect(ctx.unavailable.value).toBe(true)
    expect(toastSpy.add).not.toHaveBeenCalled()
  })

  it('AC1(1)：已授權但抓行事曆清單遇到暫時性錯誤、從沒載入成功過 → 帳號設定仍是「已連接」，卡片暫時無法載入，跳 toast', async () => {
    fetchSpy.mockResolvedValueOnce({ connected: true })
    fetchSpy.mockRejectedValueOnce(new Error('boom'))

    const ctx = useGoogleCalendar()
    await ctx.fetchGoogleCalendars()

    expect(ctx.isConnected.value).toBe(true)
    expect(ctx.needsReconnect.value).toBe(false)
    expect(ctx.unavailable.value).toBe(true)
    expect(ctx.calendarIds.value).toEqual([])
    expect(toastSpy.add).toHaveBeenCalledWith(
      expect.objectContaining({
        title: 'Google Calendar 資料暫時無法取得',
        description: expect.stringContaining('稍後再試'),
        color: 'error',
      }),
    )
  })

  it('已授權但實際呼叫仍拿到 NOT_LINKED（狀態剛好變化）時，isConnected 為 false 但不跳錯誤 toast', async () => {
    fetchSpy.mockResolvedValueOnce({ connected: true })
    fetchSpy.mockRejectedValueOnce({ response: { status: 400 }, data: { error_code: 'NOT_LINKED' } })

    const ctx = useGoogleCalendar()
    await ctx.fetchGoogleCalendars()

    expect(ctx.isConnected.value).toBe(false)
    expect(toastSpy.add).not.toHaveBeenCalled()
  })

  it('AC1：授權失效（REAUTH_REQUIRED）時，首頁和帳號設定同時抓取也只跳一個「授權已失效」toast，按鈕導到 Google 授權頁', async () => {
    respondByUrl({
      '/oauth/status': async () => ({ connected: true }),
      '/oauth/calendars': async () => { throw { response: { status: 401 }, data: { error_code: 'REAUTH_REQUIRED' } } },
    })
    vi.stubGlobal('location', { href: '' })

    const ctx = useGoogleCalendar()
    await Promise.all([ctx.fetchGoogleCalendars(), ctx.fetchGoogleCalendars()])

    expect(toastSpy.add).toHaveBeenCalledTimes(1)
    const toast = toastSpy.add.mock.calls[0]![0]
    expect(toast).toMatchObject({ title: 'Google Calendar 授權已失效', color: 'error' })
    expect(toast.description).toContain('重新連接')
    expect(toast.description).not.toContain('稍後再試')
    expect(toast.actions).toHaveLength(1)
    expect(toast.actions[0].label).toBe('重新連接 Google Calendar')
    expect(ctx.needsReconnect.value).toBe(true)
    expect(ctx.isConnected.value).toBe(false)

    toast.actions[0].onClick()

    const url = new URL(window.location.href)
    expect(url.origin + url.pathname).toBe('https://accounts.google.com/o/oauth2/v2/auth')
    expect(Object.fromEntries(url.searchParams)).toEqual({
      client_id: 'google-client-id',
      redirect_uri: 'http://front/oauth/callback',
      response_type: 'code',
      scope: 'https://www.googleapis.com/auth/calendar.readonly https://www.googleapis.com/auth/calendar.events',
      access_type: 'offline',
      prompt: 'consent',
    })
    vi.stubGlobal('location', realLocation)
  })

  it('AC4：前一次還沒結束時再呼叫，共用同一個請求：/oauth/status、/oauth/calendars 各只打一次，失敗時只跳一個 toast', async () => {
    respondByUrl({
      '/oauth/status': async () => ({ connected: true }),
      '/oauth/calendars': async () => { throw { response: { status: 502 } } },
    })

    const ctx = useGoogleCalendar()
    const first = ctx.fetchGoogleCalendars()
    const second = ctx.fetchGoogleCalendars()
    await Promise.all([first, second])

    expect(callsTo('/oauth/status')).toBe(1)
    expect(callsTo('/oauth/calendars')).toBe(1)
    expect(toastSpy.add).toHaveBeenCalledTimes(1)
    // AC3：暫時性錯誤仍是「稍後再試」，沒有重新連接按鈕
    expect(toastSpy.add).toHaveBeenCalledWith(
      expect.objectContaining({ description: expect.stringContaining('稍後再試') }),
    )
    expect(toastSpy.add.mock.calls[0]![0].actions).toBeUndefined()
  })

  it('AC4：前一次結束後再呼叫，會重新發請求（例如重新連接後要抓新資料）', async () => {
    respondByUrl({
      '/oauth/status': async () => ({ connected: true }),
      '/oauth/calendars': async () => ({ items: [] }),
    })

    const ctx = useGoogleCalendar()
    await ctx.fetchGoogleCalendars()
    await ctx.fetchGoogleCalendars()

    expect(callsTo('/oauth/calendars')).toBe(2)
  })

  it('AC6：授權失效後重新連接、再抓取成功，needsReconnect 變回 false，卡片恢復顯示行事曆', async () => {
    fetchSpy.mockResolvedValueOnce({ connected: true })
    fetchSpy.mockRejectedValueOnce({ response: { status: 401 }, data: { error_code: 'REAUTH_REQUIRED' } })

    const ctx = useGoogleCalendar()
    await ctx.fetchGoogleCalendars()
    expect(ctx.needsReconnect.value).toBe(true)

    fetchSpy.mockResolvedValueOnce({ connected: true })
    fetchSpy.mockResolvedValueOnce({ items: [{ id: 'cal1', summary: '主行事曆', primary: true }] })
    await ctx.fetchGoogleCalendars()

    expect(ctx.needsReconnect.value).toBe(false)
    expect(ctx.isConnected.value).toBe(true)
    expect(ctx.primaryCalendarId.value).toBe('cal1')
  })

  it('AC6：重新連接前發出的請求還沒回來就重新連接成功，要重新抓取；舊請求晚回來的 401 不能蓋掉新結果', async () => {
    let rejectStale!: (reason: unknown) => void
    fetchSpy.mockResolvedValueOnce({ connected: true })
    fetchSpy.mockReturnValueOnce(new Promise((_, reject) => { rejectStale = reject }))

    const ctx = useGoogleCalendar()
    const stale = ctx.fetchGoogleCalendars()
    await vi.waitFor(() => expect(callsTo('/oauth/calendars')).toBe(1))

    const connectedCount = stateStore.get('googleCalendarConnectedCount') as Ref<number>
    connectedCount.value++
    fetchSpy.mockResolvedValueOnce({ connected: true })
    fetchSpy.mockResolvedValueOnce({ items: [{ id: 'cal1', summary: '主行事曆', primary: true }] })
    await ctx.fetchGoogleCalendars()

    rejectStale({ response: { status: 401 }, data: { error_code: 'REAUTH_REQUIRED' } })
    await stale

    expect(callsTo('/oauth/calendars')).toBe(2)
    expect(ctx.isConnected.value).toBe(true)
    expect(ctx.needsReconnect.value).toBe(false)
    expect(toastSpy.add).not.toHaveBeenCalled()
  })

  const loadedOnce = async (ctx: ReturnType<typeof useGoogleCalendar>) => {
    fetchSpy.mockResolvedValueOnce({ connected: true })
    fetchSpy.mockResolvedValueOnce({ items: [{ id: 'cal1', summary: '主行事曆', primary: true }] })
    await ctx.fetchGoogleCalendars()
  }

  it.each([
    ['Google 403 限流', { response: { status: 400 }, data: { error_code: 'UPSTREAM_RATE_LIMITED', detail: 'Google 請求太頻繁，請稍後再試' } }, '請求太頻繁，請稍後再試'],
    ['Google 其他 4xx', { response: { status: 400 }, data: { error_code: 'UPSTREAM_ERROR', detail: '取得行事曆列表失敗' } }, 'Google Calendar 資料暫時無法取得'],
    ['Google 5xx', { response: { status: 502 }, data: { error_code: 'UPSTREAM_ERROR', detail: 'Google 暫時無法處理請求' } }, 'Google Calendar 資料暫時無法取得'],
  ])('AC1(1)：曾載入成功後遇到%s → 保留清單照常嵌入、帳號設定維持已連接、不顯示尚未連接', async (_, error, title) => {
    const ctx = useGoogleCalendar()
    await loadedOnce(ctx)

    fetchSpy.mockResolvedValueOnce({ connected: true })
    fetchSpy.mockRejectedValueOnce(error)
    await ctx.fetchGoogleCalendars()

    expect(ctx.calendarIds.value).toEqual(['cal1'])
    expect(ctx.isConnected.value).toBe(true)
    expect(ctx.needsReconnect.value).toBe(false)
    expect(ctx.unavailable.value).toBe(false)
    expect(toastSpy.add).toHaveBeenCalledWith(expect.objectContaining({ title, color: 'error' }))
  })

  it('AC1(2)：權限不足或換新 token 後仍 401（REAUTH_REQUIRED）→ 授權已失效、要重新連接，不顯示尚未連接', async () => {
    fetchSpy.mockResolvedValueOnce({ connected: true })
    fetchSpy.mockRejectedValueOnce({ response: { status: 400 }, data: { error_code: 'REAUTH_REQUIRED', detail: 'Google 授權的權限不足' } })

    const ctx = useGoogleCalendar()
    await ctx.fetchGoogleCalendars()

    expect(ctx.needsReconnect.value).toBe(true)
    expect(ctx.isConnected.value).toBe(false)
    expect(ctx.unavailable.value).toBe(false)
  })

  it('AC20(1)：曾載入成功後授權狀態檢查失敗 → 照常嵌入、帳號設定維持已連接', async () => {
    const ctx = useGoogleCalendar()
    await loadedOnce(ctx)

    fetchSpy.mockRejectedValueOnce(new Error('網路爆炸'))
    await ctx.fetchGoogleCalendars()

    expect(ctx.calendarIds.value).toEqual(['cal1'])
    expect(ctx.isConnected.value).toBe(true)
    expect(ctx.unavailable.value).toBe(false)
  })

  it('AC20(2)：最近一次是授權已失效，之後授權狀態檢查失敗 → 維持授權已失效的畫面', async () => {
    fetchSpy.mockResolvedValueOnce({ connected: true })
    fetchSpy.mockRejectedValueOnce({ response: { status: 401 }, data: { error_code: 'REAUTH_REQUIRED' } })
    const ctx = useGoogleCalendar()
    await ctx.fetchGoogleCalendars()

    fetchSpy.mockRejectedValueOnce(new Error('網路爆炸'))
    await ctx.fetchGoogleCalendars()

    expect(ctx.needsReconnect.value).toBe(true)
    expect(ctx.unavailable.value).toBe(false)
  })

  it('AC20(2)：最近一次是尚未連接，之後授權狀態檢查失敗 → 維持尚未連接的畫面', async () => {
    fetchSpy.mockResolvedValueOnce({ connected: false })
    const ctx = useGoogleCalendar()
    await ctx.fetchGoogleCalendars()

    fetchSpy.mockRejectedValueOnce(new Error('網路爆炸'))
    await ctx.fetchGoogleCalendars()

    expect(ctx.isConnected.value).toBe(false)
    expect(ctx.needsReconnect.value).toBe(false)
    expect(ctx.unavailable.value).toBe(false)
  })

  it('AC20：登出再以另一個使用者登入後授權狀態檢查失敗 → 不顯示前一個使用者的行事曆，視為沒有已知的結果', async () => {
    const ctx = useGoogleCalendar()
    await loadedOnce(ctx)

    clerk.userId.value = null
    await nextTick()
    expect(ctx.calendarIds.value).toEqual([])
    clerk.userId.value = 'user_b'
    fetchSpy.mockRejectedValueOnce(new Error('網路爆炸'))
    await ctx.fetchGoogleCalendars()

    expect(ctx.calendarIds.value).toEqual([])
    expect(ctx.isConnected.value).toBe(false)
    expect(ctx.unavailable.value).toBe(true)
  })
})
