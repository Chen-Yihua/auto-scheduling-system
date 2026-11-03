import { describe, it, expect } from 'vitest'
import { formatDateTime, formatMinutes, formatPercent } from '~/utils/format'

describe('formatPercent', () => {
  it('沒有資料（null）顯示「—」，和 0% 區分', () => {
    expect(formatPercent(null)).toBe('—')
    expect(formatPercent(0)).toBe('0%')
  })

  it('四捨五入到整數百分比', () => {
    expect(formatPercent(2 / 3)).toBe('67%')
    expect(formatPercent(1)).toBe('100%')
  })
})

describe('formatMinutes', () => {
  it('不到一小時只顯示分鐘，整點不顯示 0 分', () => {
    expect(formatMinutes(0)).toBe('0 分')
    expect(formatMinutes(45)).toBe('45 分')
    expect(formatMinutes(120)).toBe('2 小時')
    expect(formatMinutes(150)).toBe('2 小時 30 分')
  })
})

describe('formatDateTime', () => {
  it('AC18：UTC 時間轉成瀏覽器當地時間，格式 YYYY/MM/DD HH:mm', () => {
    // 用當地時間建立再轉成 UTC 字串，測試結果才不受執行環境的時區影響
    const local = new Date(2026, 0, 5, 9, 7, 30)
    expect(formatDateTime(local.toISOString())).toBe('2026/01/05 09:07')
  })
})
