// tests/utils/useSchedule.test.ts
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ref as vueRef, computed as vueComputed } from 'vue'

import { useSchedule } from '~/composables/useSchedule'
import { useGoogleCalendar } from '~/composables/useGoogleCalendar'

vi.mock('@clerk/vue', () => ({
  useAuth: () => ({
    getToken: { value: vi.fn().mockResolvedValue('jwt-token') },
    isLoaded: { value: true },
  }),
}))

vi.stubGlobal('ref', vueRef)
vi.stubGlobal('computed', vueComputed)

const toastSpy = { add: vi.fn() }
vi.stubGlobal('useToast', () => toastSpy)
vi.stubGlobal('useRuntimeConfig', () => ({
  public: { apiBaseUrl: 'http://api' },
}))

let fetchSpy = vi.fn()
vi.stubGlobal('$fetch', (...args: unknown[]) => fetchSpy(...args))

describe('useSchedule composable', () => {
  beforeEach(() => {
    fetchSpy = vi.fn()
    toastSpy.add.mockClear()
  })

  // 這個要排第一個：useSchedule 是 createSharedComposable，同一支測試檔裡
  // 後面任何一個測試呼叫過 fetchScheduleSuggestion，hasFetched 就會永久變 true，
  // 初始狀態只有在還沒有任何測試碰過它之前才驗證得到
  it('初始狀態：還沒 fetch 過，loading／hasFetched 都是 false', () => {
    const ctx = useSchedule()
    expect(ctx.loading.value).toBe(false)
    expect(ctx.hasFetched.value).toBe(false)
  })

  it('呼叫 /schedule/suggest 取得排程建議，preferences 沒帶時用預設值（都不限制，時區用瀏覽器的）', async () => {
    fetchSpy.mockResolvedValueOnce({ scheduled: [], unscheduled: [] })

    const ctx = useSchedule()
    await ctx.fetchScheduleSuggestion()

    expect(fetchSpy).toHaveBeenCalledWith(
      'http://api/schedule/suggest',
      expect.objectContaining({
        method: 'POST',
        body: {
          blocked_recurring: [], blocked_exceptions: [], buffer_minutes: 0, daily_max_minutes: null,
          timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
        },
        headers: { Authorization: 'Bearer jwt-token' },
      }),
    )
  })

  it('帶 preferences 時原封不動送出，並記住這份 preferences 供之後 confirmSchedule 重用', async () => {
    fetchSpy.mockResolvedValueOnce({ scheduled: [], unscheduled: [] })
    const preferences = {
      blocked_recurring: [{ days_of_week: [5, 6], all_day: true, start_time: null, end_time: null }],
      blocked_exceptions: [],
      buffer_minutes: 15,
      daily_max_minutes: 240,
      timezone: 'Asia/Taipei',
    }

    const ctx = useSchedule()
    await ctx.fetchScheduleSuggestion(preferences)

    expect(fetchSpy).toHaveBeenCalledWith(
      'http://api/schedule/suggest',
      expect.objectContaining({ method: 'POST', body: preferences }),
    )
    expect(ctx.lastPreferences.value).toEqual(preferences)
  })

  it('成功時把 scheduled／unscheduled 設進 state，並標記已經產生過一次', async () => {
    const scheduled = [{ task_id: 't1', title: '任務一', priority: 'High', start: 's', end: 'e' }]
    const unscheduled = [{ task_id: 't2', title: '任務二', priority: 'Low', reason: '沒有空檔' }]
    fetchSpy.mockResolvedValueOnce({ scheduled, unscheduled })

    const ctx = useSchedule()

    await ctx.fetchScheduleSuggestion()

    expect(ctx.scheduled.value).toEqual(scheduled)
    expect(ctx.unscheduled.value).toEqual(unscheduled)
    expect(ctx.loading.value).toBe(false)
    expect(ctx.hasFetched.value).toBe(true)
  })

  it('尚未連接 Google Calendar（400）→ notLinked 為 true，不跳錯誤 toast', async () => {
    fetchSpy.mockRejectedValueOnce({ response: { status: 400 } })

    const ctx = useSchedule()
    await ctx.fetchScheduleSuggestion()

    expect(ctx.notLinked.value).toBe(true)
    expect(toastSpy.add).not.toHaveBeenCalled()
  })

  it('授權失效（401）→ 跳出授權失效的 toast', async () => {
    fetchSpy.mockRejectedValueOnce({ response: { status: 401 } })

    const ctx = useSchedule()
    await ctx.fetchScheduleSuggestion()

    expect(ctx.notLinked.value).toBe(false)
    expect(toastSpy.add).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Google Calendar 授權已失效', color: 'error' }),
    )
  })

  it('其他錯誤 → 清空清單並跳出通用錯誤 toast', async () => {
    fetchSpy.mockRejectedValueOnce(new Error('boom'))

    const ctx = useSchedule()
    await ctx.fetchScheduleSuggestion()

    expect(ctx.scheduled.value).toEqual([])
    expect(ctx.unscheduled.value).toEqual([])
    expect(toastSpy.add).toHaveBeenCalledWith(
      expect.objectContaining({ title: '排程建議產生失敗', color: 'error' }),
    )
  })

  describe('confirmSchedule', () => {
    it('確認時不送任何內容（後端寫入的是它存下來的那份建議），之後用同一份 preferences 重新產生建議', async () => {
      const preferences = {
        blocked_recurring: [], blocked_exceptions: [], buffer_minutes: 30, daily_max_minutes: null,
        timezone: 'Asia/Taipei',
      }
      fetchSpy.mockResolvedValueOnce({ scheduled: [], unscheduled: [] }) // 產生建議時用掉的那一次
      const ctx = useSchedule()
      await ctx.fetchScheduleSuggestion(preferences)

      fetchSpy.mockResolvedValueOnce({ confirmed: [], failed: [] })
      fetchSpy.mockResolvedValueOnce({ scheduled: [], unscheduled: [] })
      await ctx.confirmSchedule()

      const [confirmUrl, confirmOptions] = fetchSpy.mock.calls[1]
      expect(confirmUrl).toBe('http://api/schedule/confirm')
      expect(confirmOptions).not.toHaveProperty('body')
      expect(fetchSpy).toHaveBeenNthCalledWith(
        3,
        'http://api/schedule/suggest',
        expect.objectContaining({ body: preferences }),
      )
    })

    it('排程建議已過期（409）→ 提示使用者，並自動重新產生一份建議讓他重新確認', async () => {
      fetchSpy.mockRejectedValueOnce({ response: { status: 409 } })
      fetchSpy.mockResolvedValueOnce({ scheduled: [], unscheduled: [] })

      const ctx = useSchedule()
      await ctx.confirmSchedule()

      expect(toastSpy.add).toHaveBeenCalledWith(
        expect.objectContaining({ title: '排程建議已過期', color: 'warning' }),
      )
      expect(fetchSpy).toHaveBeenNthCalledWith(2, 'http://api/schedule/suggest', expect.anything())
      expect(ctx.confirming.value).toBe(false)
    })

    it('呼叫 POST /schedule/confirm，全部成功時跳出成功 toast，並重新抓一次排程建議', async () => {
      fetchSpy.mockResolvedValueOnce({
        confirmed: [{ task_id: 't1', title: '任務一', calendar_event_id: 'event-1' }],
        failed: [],
      })
      fetchSpy.mockResolvedValueOnce({ scheduled: [], unscheduled: [] }) // confirmSchedule 之後的 fetchScheduleSuggestion

      const ctx = useSchedule()
      await ctx.confirmSchedule()

      expect(fetchSpy).toHaveBeenNthCalledWith(
        1,
        'http://api/schedule/confirm',
        expect.objectContaining({ method: 'POST', headers: { Authorization: 'Bearer jwt-token' } }),
      )
      expect(toastSpy.add).toHaveBeenCalledWith(
        expect.objectContaining({ title: '已確認 1 筆排程，寫入 Google Calendar', color: 'success' }),
      )
      expect(fetchSpy).toHaveBeenNthCalledWith(2, 'http://api/schedule/suggest', expect.anything())
      expect(ctx.confirming.value).toBe(false)
    })

    it('至少有一筆確認成功時，觸發 Google 行事曆 iframe 重新整理（曾經是真的要重刷整頁才看得到新事件）', async () => {
      fetchSpy.mockResolvedValueOnce({
        confirmed: [{ task_id: 't1', title: '任務一', calendar_event_id: 'event-1' }],
        failed: [],
      })
      fetchSpy.mockResolvedValueOnce({ scheduled: [], unscheduled: [] })

      const gcal = useGoogleCalendar()
      const before = gcal.calendarReloadToken.value
      const ctx = useSchedule()
      await ctx.confirmSchedule()

      expect(gcal.calendarReloadToken.value).toBe(before + 1)
    })

    it('全部失敗（沒有任何一筆真的寫進 Calendar）時，不觸發重新整理', async () => {
      fetchSpy.mockResolvedValueOnce({
        confirmed: [],
        failed: [{ task_id: 't1', title: '任務一', reason: '寫入 Google Calendar 失敗，請稍後再試' }],
      })
      fetchSpy.mockResolvedValueOnce({ scheduled: [], unscheduled: [] })

      const gcal = useGoogleCalendar()
      const before = gcal.calendarReloadToken.value
      const ctx = useSchedule()
      await ctx.confirmSchedule()

      expect(gcal.calendarReloadToken.value).toBe(before)
    })

    it('部分失敗時跳出警告 toast，列出失敗原因', async () => {
      fetchSpy.mockResolvedValueOnce({
        confirmed: [{ task_id: 't1', title: '任務一', calendar_event_id: 'event-1' }],
        failed: [{ task_id: 't2', title: '任務二', reason: '寫入 Google Calendar 失敗，請稍後再試' }],
      })
      fetchSpy.mockResolvedValueOnce({ scheduled: [], unscheduled: [] })

      const ctx = useSchedule()
      await ctx.confirmSchedule()

      expect(toastSpy.add).toHaveBeenCalledWith(
        expect.objectContaining({
          title: '1 筆已確認，1 筆寫入失敗',
          description: expect.stringContaining('任務二'),
          color: 'warning',
        }),
      )
    })

    it('全部失敗時跳出錯誤 toast（不是警告）', async () => {
      fetchSpy.mockResolvedValueOnce({
        confirmed: [],
        failed: [{ task_id: 't1', title: '任務一', reason: '寫入 Google Calendar 失敗，請稍後再試' }],
      })
      fetchSpy.mockResolvedValueOnce({ scheduled: [], unscheduled: [] })

      const ctx = useSchedule()
      await ctx.confirmSchedule()

      expect(toastSpy.add).toHaveBeenCalledWith(
        expect.objectContaining({ title: '0 筆已確認，1 筆寫入失敗', color: 'error' }),
      )
    })

    it('請求本身失敗（例如 500）→ 跳出「確認排程失敗」的 toast，不會噴例外', async () => {
      fetchSpy.mockRejectedValueOnce(new Error('boom'))

      const ctx = useSchedule()
      await ctx.confirmSchedule()

      expect(toastSpy.add).toHaveBeenCalledWith(
        expect.objectContaining({ title: '確認排程失敗', color: 'error' }),
      )
      expect(ctx.confirming.value).toBe(false)
    })
  })
})
