// 規格：docs/specs/issue-42-removed-calendar-events.md
import { describe, it, expect, vi, beforeEach } from 'vitest'

import { useRemovedCalendarEvents } from '~/composables/useRemovedCalendarEvents'
import type { RemovedCalendarEvent } from '~/types/schedule'

vi.mock('@clerk/vue', () => ({
  useAuth: () => ({
    getToken: { value: vi.fn().mockResolvedValue('jwt-token') },
  }),
}))

vi.stubGlobal('useRuntimeConfig', () => ({
  public: { apiBaseUrl: 'http://api' },
}))

let fetchSpy = vi.fn()
vi.stubGlobal('$fetch', (...args: unknown[]) => fetchSpy(...args))

const reauthError = { response: { status: 409 }, data: { error_code: 'REAUTH_REQUIRED' } }
const upstreamError = { response: { status: 502 }, data: { error_code: 'UPSTREAM_ERROR' } }

function removed(overrides: Partial<RemovedCalendarEvent> = {}): RemovedCalendarEvent {
  return {
    id: 'manual:t1', source: 'manual', title: '任務', status: 'To Do',
    calendar_event_id: 'ev-1', later_stages: [],
    ...overrides,
  }
}

describe('useRemovedCalendarEvents composable', () => {
  beforeEach(() => {
    fetchSpy = vi.fn()
  })

  it('AC1：查詢 GET /schedule/removed-events，結果存進 items', async () => {
    const items = [removed()]
    fetchSpy.mockResolvedValueOnce(items)

    const ctx = useRemovedCalendarEvents()
    expect(await ctx.fetchRemovedEvents()).toBe('ok')

    expect(fetchSpy).toHaveBeenCalledWith('http://api/schedule/removed-events', expect.objectContaining({ method: 'GET' }))
    expect(ctx.items.value).toEqual(items)
  })

  it('AC24、AC25：查詢遇到授權失效回 reauth，其他錯誤回 error；items 保留上一次的清單', async () => {
    const ctx = useRemovedCalendarEvents()
    fetchSpy.mockResolvedValueOnce([removed()])
    await ctx.fetchRemovedEvents()

    fetchSpy.mockRejectedValueOnce(reauthError)
    expect(await ctx.fetchRemovedEvents()).toBe('reauth')
    fetchSpy.mockRejectedValueOnce(upstreamError)
    expect(await ctx.fetchRemovedEvents()).toBe('error')

    expect(ctx.items.value).toEqual([removed()])
  })

  it('AC20：送出 POST /schedule/removed-events/resolve，全部成功回 done', async () => {
    fetchSpy.mockResolvedValueOnce({ succeeded: ['manual:a', 'manual:b'], failed: [] })

    const ctx = useRemovedCalendarEvents()
    expect(await ctx.resolveRemovedEvents(['manual:a'], ['manual:b'])).toBe('done')

    expect(fetchSpy).toHaveBeenCalledWith(
      'http://api/schedule/removed-events/resolve',
      expect.objectContaining({ method: 'POST', body: { reschedule: ['manual:a'], delete: ['manual:b'] } }),
    )
  })

  it('AC21、AC22：有任何一項失敗或後端回錯誤是 failed；授權失效是 reauth', async () => {
    const ctx = useRemovedCalendarEvents()

    fetchSpy.mockResolvedValueOnce({ succeeded: [], failed: [{ task_id: 'manual:a', reason: 'x', error_code: null }] })
    expect(await ctx.resolveRemovedEvents(['manual:a'], [])).toBe('failed')

    fetchSpy.mockRejectedValueOnce(upstreamError)
    expect(await ctx.resolveRemovedEvents(['manual:a'], [])).toBe('failed')

    fetchSpy.mockRejectedValueOnce(reauthError)
    expect(await ctx.resolveRemovedEvents(['manual:a'], [])).toBe('reauth')
  })
})
