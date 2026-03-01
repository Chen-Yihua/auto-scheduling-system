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
    fetchSpy.mockResolvedValueOnce({ items })

    const ctx = useGoogleCalendar()
    await ctx.fetchGoogleCalendars()

    expect(fetchSpy).toHaveBeenCalledWith(
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

  it('API 失敗時 isConnected 為 false 且 toast.add 觸發', async () => {
    fetchSpy.mockRejectedValueOnce(new Error('boom'))

    const ctx = useGoogleCalendar()
    await ctx.fetchGoogleCalendars()

    expect(ctx.isConnected.value).toBe(false)
    expect(ctx.calendarIds.value).toEqual([])
    expect(toastSpy.add).toHaveBeenCalledWith(
      expect.objectContaining({
        title: 'Google Calendar 抓取失敗',
        color: 'error',
      }),
    )
  })
})
