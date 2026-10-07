import { describe, it, expect, vi, afterEach } from 'vitest'
import { formatRelativeTime } from '~/utils/time'

describe('formatRelativeTime', () => {
  afterEach(() => {
    vi.useRealTimers()
  })

  it('沒有時間字串時回傳「未知時間」', () => {
    expect(formatRelativeTime(null)).toBe('未知時間')
    expect(formatRelativeTime(undefined)).toBe('未知時間')
  })

  it('不到 1 分鐘顯示「剛剛」', () => {
    const now = new Date('2026-09-03T12:00:00Z')
    vi.useFakeTimers().setSystemTime(now)
    expect(formatRelativeTime('2026-09-03T11:59:30Z')).toBe('剛剛')
  })

  it('未滿一小時顯示「X 分鐘前」', () => {
    const now = new Date('2026-09-03T12:00:00Z')
    vi.useFakeTimers().setSystemTime(now)
    expect(formatRelativeTime('2026-09-03T11:45:00Z')).toBe('15 分鐘前')
  })

  it('未滿一天顯示「X 小時前」', () => {
    const now = new Date('2026-09-03T12:00:00Z')
    vi.useFakeTimers().setSystemTime(now)
    expect(formatRelativeTime('2026-09-03T09:00:00Z')).toBe('3 小時前')
  })

  it('超過一天顯示「X 天前」', () => {
    const now = new Date('2026-09-03T12:00:00Z')
    vi.useFakeTimers().setSystemTime(now)
    expect(formatRelativeTime('2026-09-01T12:00:00Z')).toBe('2 天前')
  })
})
