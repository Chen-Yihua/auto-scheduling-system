// tests/utils/useGoogleCalendar.test.ts
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ref as vueRef, computed as vueComputed } from 'vue'          /** MOD */

// ---------- Clerk mock ----------
vi.mock('@clerk/vue', () => ({
  useAuth: () => ({
    getToken: { value: vi.fn().mockResolvedValue('jwt-token') },
    isLoaded: { value: true },
  }),
}))

// ---------- Nuxt auto-import 的 ref/computed ----------
vi.stubGlobal('ref', vueRef)                                         /** MOD */
vi.stubGlobal('computed', vueComputed)                               /** MOD */

// ---------- 其他 Nuxt 全域 stub ----------
const toastSpy = { add: vi.fn() }
vi.stubGlobal('useToast', () => toastSpy)
vi.stubGlobal('useRuntimeConfig', () => ({
  public: { apiBaseUrl: 'http://api' },
}))

let fetchSpy = vi.fn()
vi.stubGlobal('$fetch', (...args: any[]) => fetchSpy(...args))

// ---------- 載入被測 composable ----------
import { useGoogleCalendar } from '~/composables/useGoogleCalendar'

describe('useGoogleCalendar composable', () => {
  beforeEach(() => {
    fetchSpy = vi.fn()
    toastSpy.add.mockClear()
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

  it('授權狀態檢查本身失敗（例如網路問題）時，安靜降級成未連接，不跳任何 toast，也不會誤打行事曆 API', async () => {
    fetchSpy.mockRejectedValueOnce(new Error('網路爆炸'))

    const ctx = useGoogleCalendar()
    await ctx.fetchGoogleCalendars()

    expect(fetchSpy).toHaveBeenCalledTimes(1)
    expect(ctx.isConnected.value).toBe(false)
    expect(toastSpy.add).not.toHaveBeenCalled()
  })

  it('已授權但實際抓行事曆清單失敗時，isConnected 為 false 且 toast.add 觸發', async () => {
    fetchSpy.mockResolvedValueOnce({ connected: true })
    fetchSpy.mockRejectedValueOnce(new Error('boom'))

    const ctx = useGoogleCalendar()
    await ctx.fetchGoogleCalendars()

    expect(ctx.isConnected.value).toBe(false)
    expect(ctx.calendarIds.value).toEqual([])
    expect(toastSpy.add).toHaveBeenCalledWith(
      expect.objectContaining({
        title: 'Google Calendar 資料暫時無法取得',
        description: expect.stringContaining('稍後再試'),
        color: 'error',
      }),
    )
  })

  it('已授權但實際呼叫仍拿到 400（狀態剛好變化）時，isConnected 為 false 但不跳錯誤 toast', async () => {
    fetchSpy.mockResolvedValueOnce({ connected: true })
    fetchSpy.mockRejectedValueOnce({ response: { status: 400 } })

    const ctx = useGoogleCalendar()
    await ctx.fetchGoogleCalendars()

    expect(ctx.isConnected.value).toBe(false)
    expect(toastSpy.add).not.toHaveBeenCalled()
  })
})
