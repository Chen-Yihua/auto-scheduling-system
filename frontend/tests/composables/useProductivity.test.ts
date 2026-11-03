import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { effectScope, ref as vueRef } from 'vue'

import { useProductivity } from '~/composables/useProductivity'

vi.mock('@clerk/vue', () => ({
  useAuth: () => ({
    getToken: { value: vi.fn().mockResolvedValue('jwt-token') },
  }),
}))

vi.stubGlobal('ref', vueRef)

const toastSpy = { add: vi.fn() }
vi.stubGlobal('useToast', () => toastSpy)
vi.stubGlobal('useRuntimeConfig', () => ({
  public: { apiBaseUrl: 'http://api' },
}))

let fetchSpy = vi.fn()
vi.stubGlobal('$fetch', (...args: unknown[]) => fetchSpy(...args))

describe('useProductivity composable', () => {
  beforeEach(() => {
    fetchSpy = vi.fn()
    toastSpy.add.mockClear()
  })

  it('帶瀏覽器時區呼叫 GET /analytics/productivity，週趨勢才會依當地時間切分', async () => {
    const summary = { total: 1 }
    fetchSpy.mockResolvedValueOnce(summary)
    const timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone

    const ctx = useProductivity()
    await ctx.fetchSummary()

    expect(fetchSpy).toHaveBeenCalledWith(
      'http://api/analytics/productivity',
      expect.objectContaining({
        method: 'GET',
        query: { timezone: timeZone },
        headers: { Authorization: 'Bearer jwt-token' },
      }),
    )
    expect(ctx.summary.value).toEqual(summary)
    expect(ctx.loading.value).toBe(false)
  })

  it('失敗時跳出錯誤 toast，summary 維持 null', async () => {
    fetchSpy.mockRejectedValueOnce(new Error('boom'))

    const ctx = useProductivity()
    await ctx.fetchSummary()

    expect(toastSpy.add).toHaveBeenCalledWith(
      expect.objectContaining({ title: '工作效率統計載入失敗', color: 'error' }),
    )
    expect(ctx.summary.value).toBeNull()
    expect(ctx.loading.value).toBe(false)
  })

  it('AC14：429 失敗時 toast 標題用 getFriendlyErrorTitle 的限流訊息，不是預設文字', async () => {
    fetchSpy.mockRejectedValueOnce({ status: 429 })

    const ctx = useProductivity()
    await ctx.fetchSummary()

    expect(toastSpy.add).toHaveBeenCalledWith(
      expect.objectContaining({ title: '請求太頻繁，請稍後再試', color: 'error' }),
    )
  })

  it('AC16：呼叫 API 期間 loading 為 true，回應後回到 false', async () => {
    let resolve: (value: unknown) => void = () => {}
    fetchSpy.mockReturnValueOnce(new Promise((r) => { resolve = r }))

    const ctx = useProductivity()
    const pending = ctx.fetchSummary()
    await vi.waitFor(() => expect(fetchSpy).toHaveBeenCalled())
    expect(ctx.loading.value).toBe(true)

    resolve({ total: 1 })
    await pending
    expect(ctx.loading.value).toBe(false)
  })
})

describe('useProductivity 自動更新', () => {
  const HOUR = 60 * 60 * 1000
  let scope: ReturnType<typeof effectScope>

  // 頁面卸載時 Vue 會停掉元件的 scope，用 effectScope 模擬同樣的生命週期
  const setup = () => {
    scope = effectScope()
    const ctx = scope.run(() => useProductivity())!
    ctx.startAutoRefresh()
    return ctx
  }

  beforeEach(() => {
    vi.useFakeTimers()
    fetchSpy = vi.fn()
    toastSpy.add.mockClear()
  })

  afterEach(() => {
    scope?.stop()
    vi.useRealTimers()
  })

  it('AC17：頁面開著時每小時重新呼叫一次 API，未滿一小時不呼叫', async () => {
    fetchSpy.mockResolvedValue({ total: 1 })
    setup()

    await vi.advanceTimersByTimeAsync(HOUR - 1)
    expect(fetchSpy).not.toHaveBeenCalled()
    await vi.advanceTimersByTimeAsync(1)
    expect(fetchSpy).toHaveBeenCalledTimes(1)
    await vi.advanceTimersByTimeAsync(HOUR)
    expect(fetchSpy).toHaveBeenCalledTimes(2)
  })

  it('AC17：重複啟動自動更新不會變成每小時呼叫多次', async () => {
    fetchSpy.mockResolvedValue({ total: 1 })
    const ctx = setup()
    ctx.startAutoRefresh()

    await vi.advanceTimersByTimeAsync(HOUR)
    expect(fetchSpy).toHaveBeenCalledTimes(1)
  })

  it('AC17：已有統計時自動更新失敗，保留原本的統計並跳 toast', async () => {
    const ctx = setup()
    fetchSpy.mockResolvedValueOnce({ total: 1 })
    await ctx.fetchSummary()

    fetchSpy.mockRejectedValueOnce(new Error('boom'))
    await vi.advanceTimersByTimeAsync(HOUR)

    expect(ctx.summary.value).toEqual({ total: 1 })
    expect(toastSpy.add).toHaveBeenCalledWith(expect.objectContaining({ color: 'error' }))
  })

  it('AC17：離開頁面後停止自動更新', async () => {
    fetchSpy.mockResolvedValue({ total: 1 })
    setup()
    scope.stop()

    await vi.advanceTimersByTimeAsync(HOUR * 3)
    expect(fetchSpy).not.toHaveBeenCalled()
  })

  it('AC15：載入失敗後等下一次自動更新重試，成功時 error 回到 false 並有統計', async () => {
    const ctx = setup()
    fetchSpy.mockRejectedValueOnce(new Error('boom'))
    await ctx.fetchSummary()
    expect(ctx.error.value).toBe(true)
    expect(ctx.summary.value).toBeNull()

    fetchSpy.mockResolvedValueOnce({ total: 1 })
    await vi.advanceTimersByTimeAsync(HOUR)

    expect(ctx.error.value).toBe(false)
    expect(ctx.summary.value).toEqual({ total: 1 })
  })
})
