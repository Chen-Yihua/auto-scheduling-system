import { describe, it, expect } from 'vitest'
import { getFriendlyErrorTitle } from '~/utils/errorMessages'

describe('getFriendlyErrorTitle', () => {
  it('後端自訂的 RATE_LIMITED 錯誤碼，回傳限流訊息', () => {
    const error = { data: { error_code: 'RATE_LIMITED', detail: '請求太頻繁，請稍後再試' } }
    expect(getFriendlyErrorTitle(error, 'XXX 抓取失敗')).toBe('請求太頻繁，請稍後再試')
  })

  it('狀態碼是 429（例如 Cloud Run 容量爆掉），也回傳限流訊息', () => {
    const error = { response: { status: 429 } }
    expect(getFriendlyErrorTitle(error, 'XXX 抓取失敗')).toBe('請求太頻繁，請稍後再試')
  })

  it('status 直接掛在 error 上（不同 fetch 實作的錯誤形狀）也認得出來', () => {
    const error = { status: 429 }
    expect(getFriendlyErrorTitle(error, 'XXX 抓取失敗')).toBe('請求太頻繁，請稍後再試')
  })

  it('其他錯誤（例如 401、500、網路錯誤）維持原本的 fallback 標題', () => {
    expect(getFriendlyErrorTitle({ response: { status: 401 } }, 'XXX 抓取失敗')).toBe('XXX 抓取失敗')
    expect(getFriendlyErrorTitle({ response: { status: 500 } }, 'XXX 抓取失敗')).toBe('XXX 抓取失敗')
    expect(getFriendlyErrorTitle(new Error('network error'), 'XXX 抓取失敗')).toBe('XXX 抓取失敗')
    expect(getFriendlyErrorTitle(undefined, 'XXX 抓取失敗')).toBe('XXX 抓取失敗')
  })
})
