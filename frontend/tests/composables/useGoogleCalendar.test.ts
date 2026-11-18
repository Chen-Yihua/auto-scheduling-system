import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ref as vueRef, computed as vueComputed, nextTick, type Ref } from 'vue';

// ---------- 載入被測 composable ----------
// 共用狀態（包括最近一次已知的結果）存在模組裡，每個測試重新載入才不會互相影響
let useGoogleCalendar: typeof import('~/composables/useGoogleCalendar')['useGoogleCalendar']

// ---------- Clerk mock ----------
// userId 要能切換，測登出／換使用者
const clerk = vi.hoisted(() => ({ userId: null as unknown as Ref<string | null>, isLoaded: { value: true } }))
vi.mock('@clerk/vue', async () => {
  const { ref } = await import('vue')
  clerk.userId = ref<string | null>('user_a')
  return {
    useAuth: () => ({
      getToken: { value: vi.fn().mockResolvedValue('jwt-token') },
      isLoaded: clerk.isLoaded,
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
vi.stubGlobal('$fetch', (...args: unknown[]) => fetchSpy(...args))

// 測試名稱裡沒有標規格名的 AC 編號屬於 issue-104-calendar-card-states.md；
// reauth 是 google-calendar-reauth.md，issue-77 是 issue-77-error-codes.md
describe('useGoogleCalendar composable', () => {
  beforeEach(async () => {
    fetchSpy = vi.fn()
    toastSpy.add.mockClear()
    vi.resetModules()
    ;({ useGoogleCalendar } = await import('~/composables/useGoogleCalendar'))
    if (clerk.userId) clerk.userId.value = 'user_a'
    clerk.isLoaded.value = true
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
    );
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

  it('issue-77 AC20(3)、AC5：授權狀態檢查失敗而且沒有已知的結果 → 暫時無法載入，不顯示「已連接」也不變成需要連接，不跳 toast，也不會誤打行事曆 API', async () => {
    fetchSpy.mockRejectedValueOnce(new Error('網路爆炸'))

    const ctx = useGoogleCalendar()
    await ctx.fetchGoogleCalendars()

    expect(fetchSpy).toHaveBeenCalledTimes(1)
    expect(ctx.isConnected.value).toBe(false)
    expect(ctx.unavailable.value).toBe(true)
    expect(toastSpy.add).not.toHaveBeenCalled()
  })

  it('AC5、AC10：已授權但抓行事曆清單遇到暫時性錯誤、從沒載入成功過 → 帳號設定仍是「已連接」，卡片暫時無法載入，不跳 toast', async () => {
    fetchSpy.mockResolvedValueOnce({ connected: true })
    fetchSpy.mockRejectedValueOnce(new Error('boom'))

    const ctx = useGoogleCalendar()
    await ctx.fetchGoogleCalendars()

    expect(ctx.isConnected.value).toBe(true)
    expect(ctx.unavailable.value).toBe(true)
    expect(ctx.calendarIds.value).toEqual([])
    expect(toastSpy.add).not.toHaveBeenCalled()
  })

  it('已授權但實際呼叫仍拿到 NOT_LINKED（狀態剛好變化）時，isConnected 為 false 但不跳錯誤 toast', async () => {
    fetchSpy.mockResolvedValueOnce({ connected: true })
    fetchSpy.mockRejectedValueOnce({ response: { status: 400 }, data: { error_code: 'NOT_LINKED' } })

    const ctx = useGoogleCalendar()
    await ctx.fetchGoogleCalendars()

    expect(ctx.isConnected.value).toBe(false)
    expect(toastSpy.add).not.toHaveBeenCalled()
  })

  it('AC2、AC9：授權失效（REAUTH_REQUIRED）時，首頁和帳號設定同時抓取也不跳任何 toast，卡片顯示需要連接', async () => {
    respondByUrl({
      '/oauth/status': async () => ({ connected: true }),
      '/oauth/calendars': async () => { throw { response: { status: 401 }, data: { error_code: 'REAUTH_REQUIRED' } } },
    })

    const ctx = useGoogleCalendar()
    await Promise.all([ctx.fetchGoogleCalendars(), ctx.fetchGoogleCalendars()])

    expect(toastSpy.add).not.toHaveBeenCalled()
    expect(ctx.isConnected.value).toBe(false)
    expect(ctx.unavailable.value).toBe(false)
    expect(ctx.awaitingFirstResult.value).toBe(false)
  })

  it('reauth AC4、AC10：前一次還沒結束時再呼叫，共用同一個請求：/oauth/status、/oauth/calendars 各只打一次，失敗時不跳 toast', async () => {
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
    expect(toastSpy.add).not.toHaveBeenCalled()
  })

  it('reauth AC4：前一次結束後再呼叫，會重新發請求（例如重新連接後要抓新資料）', async () => {
    respondByUrl({
      '/oauth/status': async () => ({ connected: true }),
      '/oauth/calendars': async () => ({ items: [] }),
    })

    const ctx = useGoogleCalendar()
    await ctx.fetchGoogleCalendars()
    await ctx.fetchGoogleCalendars()

    expect(callsTo('/oauth/calendars')).toBe(2)
  })

  it('reauth AC6：授權失效後重新連接、再抓取成功，isConnected 變回 true，卡片恢復顯示行事曆', async () => {
    fetchSpy.mockResolvedValueOnce({ connected: true })
    fetchSpy.mockRejectedValueOnce({ response: { status: 401 }, data: { error_code: 'REAUTH_REQUIRED' } })

    const ctx = useGoogleCalendar()
    await ctx.fetchGoogleCalendars()
    expect(ctx.isConnected.value).toBe(false)

    fetchSpy.mockResolvedValueOnce({ connected: true })
    fetchSpy.mockResolvedValueOnce({ items: [{ id: 'cal1', summary: '主行事曆', primary: true }] })
    await ctx.fetchGoogleCalendars();

    expect(ctx.isConnected.value).toBe(true)
    expect(ctx.primaryCalendarId.value).toBe('cal1')
  })

  it('reauth AC6：重新連接前發出的請求還沒回來就重新連接成功，要重新抓取；舊請求晚回來的 401 不能蓋掉新結果', async () => {
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
    expect(toastSpy.add).not.toHaveBeenCalled()
  })

  const loadedOnce = async (ctx: ReturnType<typeof useGoogleCalendar>) => {
    fetchSpy.mockResolvedValueOnce({ connected: true })
    fetchSpy.mockResolvedValueOnce({ items: [{ id: 'cal1', summary: '主行事曆', primary: true }] })
    await ctx.fetchGoogleCalendars()
  }

  it.each([
    ['Google 403 限流', { response: { status: 400 }, data: { error_code: 'UPSTREAM_RATE_LIMITED', detail: 'Google 請求太頻繁，請稍後再試' } }],
    ['伺服器限流', { response: { status: 429 }, data: { error_code: 'RATE_LIMITED', detail: '請求太頻繁，請稍後再試' } }],
    ['Google 其他 4xx', { response: { status: 400 }, data: { error_code: 'UPSTREAM_ERROR', detail: '取得行事曆列表失敗' } }],
    ['Google 5xx', { response: { status: 502 }, data: { error_code: 'UPSTREAM_ERROR', detail: 'Google 暫時無法處理請求' } }],
    ['伺服器錯誤', { response: { status: 500 } }],
  ])('issue-77 AC1(1)、AC10：曾載入成功後遇到%s → 保留清單照常嵌入、帳號設定維持已連接、不跳 toast', async (_, error) => {
    const ctx = useGoogleCalendar()
    await loadedOnce(ctx)

    fetchSpy.mockResolvedValueOnce({ connected: true })
    fetchSpy.mockRejectedValueOnce(error)
    await ctx.fetchGoogleCalendars()

    expect(ctx.calendarIds.value).toEqual(['cal1'])
    expect(ctx.isConnected.value).toBe(true)
    expect(ctx.unavailable.value).toBe(false)
    expect(toastSpy.add).not.toHaveBeenCalled()
  })

  it('AC2：權限不足或換新 token 後仍 401（REAUTH_REQUIRED）→ 沒連上、不是暫時無法載入、有結果', async () => {
    fetchSpy.mockResolvedValueOnce({ connected: true })
    fetchSpy.mockRejectedValueOnce({ response: { status: 400 }, data: { error_code: 'REAUTH_REQUIRED', detail: 'Google 授權的權限不足' } })

    const ctx = useGoogleCalendar()
    await ctx.fetchGoogleCalendars()

    expect(ctx.isConnected.value).toBe(false)
    expect(ctx.unavailable.value).toBe(false)
    expect(ctx.awaitingFirstResult.value).toBe(false)
  })

  it('issue-77 AC20(1)：曾載入成功後授權狀態檢查失敗 → 照常嵌入、帳號設定維持已連接', async () => {
    const ctx = useGoogleCalendar()
    await loadedOnce(ctx)

    fetchSpy.mockRejectedValueOnce(new Error('網路爆炸'))
    await ctx.fetchGoogleCalendars()

    expect(ctx.calendarIds.value).toEqual(['cal1'])
    expect(ctx.isConnected.value).toBe(true)
    expect(ctx.unavailable.value).toBe(false)
  })

  it('AC2、issue-77 AC20(2)：最近一次是授權已失效，之後授權狀態檢查失敗 → 維持需要連接的畫面', async () => {
    fetchSpy.mockResolvedValueOnce({ connected: true })
    fetchSpy.mockRejectedValueOnce({ response: { status: 401 }, data: { error_code: 'REAUTH_REQUIRED' } })
    const ctx = useGoogleCalendar()
    await ctx.fetchGoogleCalendars()

    fetchSpy.mockRejectedValueOnce(new Error('網路爆炸'))
    await ctx.fetchGoogleCalendars()

    expect(ctx.isConnected.value).toBe(false)
    expect(ctx.unavailable.value).toBe(false)
  })

  it('issue-77 AC20(2)：最近一次是尚未連接，之後授權狀態檢查失敗 → 維持需要連接的畫面', async () => {
    fetchSpy.mockResolvedValueOnce({ connected: false })
    const ctx = useGoogleCalendar()
    await ctx.fetchGoogleCalendars()

    fetchSpy.mockRejectedValueOnce(new Error('網路爆炸'))
    await ctx.fetchGoogleCalendars()

    expect(ctx.isConnected.value).toBe(false)
    expect(ctx.unavailable.value).toBe(false)
  })

  it('issue-77 AC20：登出再以另一個使用者登入後授權狀態檢查失敗 → 不顯示前一個使用者的行事曆，視為沒有已知的結果', async () => {
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

  describe('第一次查詢還沒有結果（awaitingFirstResult）', () => {
    it.each([
      ['已連接', () => { fetchSpy.mockResolvedValueOnce({ connected: true }); fetchSpy.mockResolvedValueOnce({ items: [] }) }],
      ['未連接', () => { fetchSpy.mockResolvedValueOnce({ connected: false }) }],
      ['授權失效', () => { fetchSpy.mockResolvedValueOnce({ connected: true }); fetchSpy.mockRejectedValueOnce({ response: { status: 401 }, data: { error_code: 'REAUTH_REQUIRED' } }) }],
      ['授權狀態檢查失敗（暫時無法載入）', () => { fetchSpy.mockRejectedValueOnce(new Error('網路爆炸')) }],
      ['抓清單遇到暫時性錯誤（暫時無法載入）', () => { fetchSpy.mockResolvedValueOnce({ connected: true }); fetchSpy.mockRejectedValueOnce({ response: { status: 502 } }) }],
    ])('AC7：第一次查詢前是還沒有結果，查詢後（%s）變成有結果', async (_, arrange) => {
      const ctx = useGoogleCalendar()
      expect(ctx.awaitingFirstResult.value).toBe(true)

      arrange()
      await ctx.fetchGoogleCalendars()

      expect(ctx.awaitingFirstResult.value).toBe(false)
    })

    it('AC7：之後重新查詢時不回到還沒有結果，畫面維持最近一次已知的結果', async () => {
      const ctx = useGoogleCalendar()
      await loadedOnce(ctx)

      let resolveStatus!: (value: unknown) => void
      fetchSpy.mockReturnValueOnce(new Promise((resolve) => { resolveStatus = resolve }))
      const refetch = ctx.fetchGoogleCalendars()
      await vi.waitFor(() => expect(callsTo('/oauth/status')).toBe(2))

      expect(ctx.awaitingFirstResult.value).toBe(false)
      expect(ctx.isConnected.value).toBe(true)

      fetchSpy.mockResolvedValueOnce({ items: [] })
      resolveStatus({ connected: true })
      await refetch
      expect(ctx.awaitingFirstResult.value).toBe(false)
    })

    it('AC7：Clerk 還沒載入完就呼叫時，維持還沒有結果', async () => {
      clerk.isLoaded.value = false
      const ctx = useGoogleCalendar()
      await ctx.fetchGoogleCalendars()

      expect(fetchSpy).not.toHaveBeenCalled()
      expect(ctx.awaitingFirstResult.value).toBe(true)
    })

    it('AC7：結果不是最新而被丟掉時，維持還沒有結果', async () => {
      let resolveStale!: (value: unknown) => void
      fetchSpy.mockReturnValueOnce(new Promise((resolve) => { resolveStale = resolve }))

      const ctx = useGoogleCalendar()
      const stale = ctx.fetchGoogleCalendars()
      await vi.waitFor(() => expect(callsTo('/oauth/status')).toBe(1))

      const connectedCount = stateStore.get('googleCalendarConnectedCount') as Ref<number>
      connectedCount.value++
      await nextTick()
      resolveStale({ connected: false })
      await stale

      expect(ctx.awaitingFirstResult.value).toBe(true)
    })

    it('AC8：前一個使用者的查詢結束後換成另一個使用者，回到還沒有結果、行事曆清單清空', async () => {
      const ctx = useGoogleCalendar()
      await loadedOnce(ctx)
      expect(ctx.awaitingFirstResult.value).toBe(false)

      clerk.userId.value = 'user_b'
      await nextTick()

      expect(ctx.awaitingFirstResult.value).toBe(true)
      expect(ctx.calendarIds.value).toEqual([])
      expect(ctx.isConnected.value).toBe(false)
    })

    it.each([
      ['未連接', () => { fetchSpy.mockResolvedValueOnce({ connected: false }) }],
      ['授權失效', () => { fetchSpy.mockResolvedValueOnce({ connected: true }); fetchSpy.mockRejectedValueOnce({ response: { status: 401 }, data: { error_code: 'REAUTH_REQUIRED' } }) }],
    ])('AC15：已有結果（%s）後連接成功，回到還沒有結果；重新查詢成功後變成有結果、已連接', async (_, arrange) => {
      const ctx = useGoogleCalendar()
      arrange()
      await ctx.fetchGoogleCalendars()
      expect(ctx.awaitingFirstResult.value).toBe(false)

      const connectedCount = stateStore.get('googleCalendarConnectedCount') as Ref<number>
      connectedCount.value++
      await nextTick()
      expect(ctx.awaitingFirstResult.value).toBe(true)

      await loadedOnce(ctx)
      expect(ctx.awaitingFirstResult.value).toBe(false)
      expect(ctx.isConnected.value).toBe(true)
    })

    it('AC15：連接成功後重新查詢時授權狀態檢查失敗，也變成有結果，維持最近一次已知的結果', async () => {
      fetchSpy.mockResolvedValueOnce({ connected: false })
      const ctx = useGoogleCalendar()
      await ctx.fetchGoogleCalendars()

      const connectedCount = stateStore.get('googleCalendarConnectedCount') as Ref<number>
      connectedCount.value++
      await nextTick()
      expect(ctx.awaitingFirstResult.value).toBe(true)

      fetchSpy.mockRejectedValueOnce(new Error('網路爆炸'))
      await ctx.fetchGoogleCalendars()

      expect(ctx.awaitingFirstResult.value).toBe(false)
      expect(ctx.isConnected.value).toBe(false)
      expect(ctx.unavailable.value).toBe(false)
    })
  })

  describe('issue-42：進入排程精靈前確認連接狀態，依這一次查詢的結果判斷', () => {
    it('AC26：沒連接 → not_linked', async () => {
      fetchSpy.mockResolvedValueOnce({ connected: false })
      expect(await useGoogleCalendar().fetchGoogleCalendars()).toBe('not_linked')
    })

    it('AC26：授權已失效（抓行事曆清單回 REAUTH_REQUIRED）→ reauth', async () => {
      fetchSpy.mockResolvedValueOnce({ connected: true })
      fetchSpy.mockRejectedValueOnce({ response: { status: 409 }, data: { error_code: 'REAUTH_REQUIRED' } })
      expect(await useGoogleCalendar().fetchGoogleCalendars()).toBe('reauth')
    })

    it('已連接 → connected', async () => {
      fetchSpy.mockResolvedValueOnce({ connected: true })
      fetchSpy.mockResolvedValueOnce({ items: [] })
      expect(await useGoogleCalendar().fetchGoogleCalendars()).toBe('connected')
    })

    it('AC28：上一次是沒連接、這一次狀態查詢失敗 → unknown，不沿用上一次的結果', async () => {
      fetchSpy.mockResolvedValueOnce({ connected: false })
      const ctx = useGoogleCalendar()
      await ctx.fetchGoogleCalendars()

      fetchSpy.mockRejectedValueOnce(new Error('網路爆炸'))
      expect(await ctx.fetchGoogleCalendars()).toBe('unknown')
    })

    it('AC28：抓行事曆清單遇到暫時性錯誤 → unknown', async () => {
      fetchSpy.mockResolvedValueOnce({ connected: true })
      fetchSpy.mockRejectedValueOnce({ response: { status: 503 }, data: { error_code: 'UPSTREAM_RATE_LIMITED' } })
      expect(await useGoogleCalendar().fetchGoogleCalendars()).toBe('unknown')
    })
  })
})
