import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ref as vueRef, computed as vueComputed, type Ref } from 'vue'

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
  public: { apiBaseUrl: 'http://api', frontEndUrl: 'http://front', apiGoogleClientId: 'google-client-id' },
}))

// Nuxt 的 useState：同一個 key 在所有元件之間共用同一份狀態
const stateStore = new Map<string, Ref<unknown>>()
vi.stubGlobal('useState', (key: string, init: () => unknown) => {
  if (!stateStore.has(key)) stateStore.set(key, vueRef(init()))
  return stateStore.get(key)
})

let fetchSpy = vi.fn()
// 按下重新連接會改 window.location.href，測完要換回 jsdom 原本的
const realLocation = window.location
vi.stubGlobal('$fetch', (...args: unknown[]) => fetchSpy(...args))

describe('useSchedule composable', () => {
  beforeEach(() => {
    fetchSpy = vi.fn()
    toastSpy.add.mockClear()
  })

  // 要排第一個：狀態是共用的，其他測試執行後 hasFetched 就不再是初始值
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

  it('尚未連接 Google Calendar（NOT_LINKED）→ notLinked 為 true，不跳錯誤 toast', async () => {
    fetchSpy.mockRejectedValueOnce({ response: { status: 400 }, data: { error_code: 'NOT_LINKED' } })

    const ctx = useSchedule()
    await ctx.fetchScheduleSuggestion()

    expect(ctx.notLinked.value).toBe(true)
    expect(toastSpy.add).not.toHaveBeenCalled()
  })

  it('授權失效（REAUTH_REQUIRED）→ 跳出授權失效的 toast', async () => {
    fetchSpy.mockRejectedValueOnce({ response: { status: 401 }, data: { error_code: 'REAUTH_REQUIRED' } })

    const ctx = useSchedule()
    await ctx.fetchScheduleSuggestion()

    expect(ctx.notLinked.value).toBe(false)
    expect(toastSpy.add).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Google Calendar 授權已失效', color: 'error' }),
    )
  })

  it('AC5：產生建議時授權失效（REAUTH_REQUIRED）→ toast 和首頁一樣有「重新連接 Google Calendar」按鈕，按下導到 Google 授權頁', async () => {
    fetchSpy.mockRejectedValueOnce({ response: { status: 401 }, data: { error_code: 'REAUTH_REQUIRED' } })
    vi.stubGlobal('location', { href: '' })

    const ctx = useSchedule()
    await ctx.fetchScheduleSuggestion()

    const toast = toastSpy.add.mock.calls[0]![0]
    expect(toast.description).toContain('重新連接')
    expect(toast.actions).toHaveLength(1)
    expect(toast.actions[0].label).toBe('重新連接 Google Calendar')

    toast.actions[0].onClick()
    expect(window.location.href).toContain('https://accounts.google.com/o/oauth2/v2/auth?')
    expect(window.location.href).toContain('client_id=google-client-id')
    vi.stubGlobal('location', realLocation)
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

    it('排程建議已過期（SUGGESTION_EXPIRED）→ 提示使用者，並自動重新產生一份建議讓他重新確認', async () => {
      fetchSpy.mockRejectedValueOnce({ response: { status: 409 }, data: { error_code: 'SUGGESTION_EXPIRED' } })
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

    it('AC7：failed 裡有一筆 REAUTH_REQUIRED → 除了列出失敗項目的 toast，另外提示重新連接 Google Calendar', async () => {
      fetchSpy.mockResolvedValueOnce({
        confirmed: [{ task_id: 't1', title: '任務一', calendar_event_id: 'event-1' }],
        failed: [
          { task_id: 't2', title: '任務二', reason: 'Google 授權已失效，請重新連接 Google Calendar', error_code: 'REAUTH_REQUIRED' },
          { task_id: 't3', title: '任務三', reason: '前一個階段寫入失敗', error_code: null },
        ],
      })
      fetchSpy.mockResolvedValueOnce({ scheduled: [], unscheduled: [] })

      const ctx = useSchedule()
      await ctx.confirmSchedule()

      const toasts = toastSpy.add.mock.calls.map((call) => call[0])
      expect(toasts).toContainEqual(expect.objectContaining({
        title: '1 筆已確認，2 筆寫入失敗',
        description: expect.stringContaining('任務二'),
      }))
      const reauth = toasts.find((t) => t.title === 'Google Calendar 授權已失效')
      expect(reauth?.actions[0].label).toBe('重新連接 Google Calendar')
    })

    it('AC7：failed 沒有 REAUTH_REQUIRED（其他原因或 null）→ 不顯示重新連接的提示', async () => {
      fetchSpy.mockResolvedValueOnce({
        confirmed: [],
        failed: [
          { task_id: 't1', title: '任務一', reason: 'Google 請求太頻繁，請稍後再試', error_code: 'UPSTREAM_RATE_LIMITED' },
          { task_id: 't2', title: '任務二', reason: '任務已經完成', error_code: null },
        ],
      })
      fetchSpy.mockResolvedValueOnce({ scheduled: [], unscheduled: [] })

      const ctx = useSchedule()
      await ctx.confirmSchedule()

      const toasts = toastSpy.add.mock.calls.map((call) => call[0])
      expect(toasts.some((t) => t.title === 'Google Calendar 授權已失效')).toBe(false)
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

  describe('依 error_code 判斷（#77）', () => {
    it('AC1、AC12：產生建議時收到 Google 限流（UPSTREAM_RATE_LIMITED，狀態碼 400）→ 不顯示尚未連接，顯示請求太頻繁', async () => {
      fetchSpy.mockRejectedValueOnce({ response: { status: 400 }, data: { error_code: 'UPSTREAM_RATE_LIMITED', detail: 'Google 請求太頻繁，請稍後再試' } })

      const ctx = useSchedule()
      await ctx.fetchScheduleSuggestion()

      expect(ctx.notLinked.value).toBe(false)
      expect(toastSpy.add).toHaveBeenCalledWith(expect.objectContaining({ title: '請求太頻繁，請稍後再試' }))
    })

    it('AC1：產生建議時收到其他 Google 4xx（UPSTREAM_ERROR，狀態碼 400）→ 不顯示尚未連接，顯示錯誤並附加 detail', async () => {
      fetchSpy.mockRejectedValueOnce({ response: { status: 400 }, data: { error_code: 'UPSTREAM_ERROR', detail: '取得行事曆列表失敗' } })

      const ctx = useSchedule()
      await ctx.fetchScheduleSuggestion()

      expect(ctx.notLinked.value).toBe(false)
      const toast = toastSpy.add.mock.calls[0]![0]
      expect(toast.title).toBe('排程建議產生失敗')
      expect(toast.description).toBe('伺服器暫時發生錯誤，請稍後再試一次\n取得行事曆列表失敗')
    })

    it('AC12：沒有 error_code 的 400（例如不是本後端回的）→ 一般錯誤，不顯示尚未連接', async () => {
      fetchSpy.mockRejectedValueOnce({ response: { status: 400 } })

      const ctx = useSchedule()
      await ctx.fetchScheduleSuggestion()

      expect(ctx.notLinked.value).toBe(false)
      expect(toastSpy.add).toHaveBeenCalledWith(expect.objectContaining({ title: '排程建議產生失敗', description: '伺服器暫時發生錯誤，請稍後再試一次' }))
    })

    it('AC12：確認排程時收到 NOT_LINKED → 這個畫面沒有尚未連接狀態，當成一般錯誤顯示並附加 detail', async () => {
      fetchSpy.mockRejectedValueOnce({ response: { status: 400 }, data: { error_code: 'NOT_LINKED', detail: '尚未連接 Google Calendar' } })

      const ctx = useSchedule()
      await ctx.confirmSchedule()

      const toast = toastSpy.add.mock.calls[0]![0]
      expect(toast).toMatchObject({ title: '確認排程失敗', color: 'error' })
      expect(toast.description).toContain('尚未連接 Google Calendar')
    })
  })
})
