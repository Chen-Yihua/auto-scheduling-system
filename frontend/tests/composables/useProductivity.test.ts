import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ref as vueRef } from 'vue'

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

  it('失敗時 error 為 true，之後重試成功 error 回到 false', async () => {
    fetchSpy.mockRejectedValueOnce(new Error('boom'))
    const ctx = useProductivity()
    await ctx.fetchSummary()
    expect(ctx.error.value).toBe(true)

    fetchSpy.mockResolvedValueOnce({ total: 1 })
    await ctx.fetchSummary()
    expect(ctx.error.value).toBe(false)
    expect(ctx.summary.value).toEqual({ total: 1 })
  })
})
