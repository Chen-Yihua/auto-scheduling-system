import { describe, it, expect } from 'vitest'
import { formatMinutes, formatPercent } from '~/utils/format'

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
