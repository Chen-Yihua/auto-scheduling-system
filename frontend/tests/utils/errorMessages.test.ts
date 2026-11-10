import { describe, it, expect, vi } from 'vitest'
import {
  describeError,
  getFriendlyErrorTitle,
  isAlreadyLinkedError,
  isAuthError,
  isNotLinkedError,
  isSuggestionExpiredError,
  logApiError,
} from '~/utils/errorMessages'

const backendError = (status: number, errorCode: string, detail = '後端說明') => ({
  response: { status },
  data: { error_code: errorCode, detail },
})

describe('getFriendlyErrorTitle', () => {
  it.each(['RATE_LIMITED', 'UPSTREAM_RATE_LIMITED'])('AC12：%s 回傳限流訊息，不論狀態碼', (code) => {
    expect(getFriendlyErrorTitle(backendError(400, code), 'XXX 抓取失敗')).toBe('請求太頻繁，請稍後再試')
  })

  it('AC12：沒有 error_code 的 429（例如 Cloud Run 容量爆掉）也回傳限流訊息', () => {
    expect(getFriendlyErrorTitle({ response: { status: 429 } }, 'XXX 抓取失敗')).toBe('請求太頻繁，請稍後再試')
    expect(getFriendlyErrorTitle({ status: 429 }, 'XXX 抓取失敗')).toBe('請求太頻繁，請稍後再試')
  })

  it('其他錯誤（例如 401、500、網路錯誤）維持原本的 fallback 標題', () => {
    expect(getFriendlyErrorTitle({ response: { status: 401 } }, 'XXX 抓取失敗')).toBe('XXX 抓取失敗')
    expect(getFriendlyErrorTitle(backendError(429, 'INTERNAL_ERROR'), 'XXX 抓取失敗')).toBe('XXX 抓取失敗')
    expect(getFriendlyErrorTitle(new Error('network error'), 'XXX 抓取失敗')).toBe('XXX 抓取失敗')
    expect(getFriendlyErrorTitle(undefined, 'XXX 抓取失敗')).toBe('XXX 抓取失敗')
  })
})

describe('依 error_code 判斷原因，不看狀態碼', () => {
  it('AC12：REAUTH_REQUIRED 才要重新連結；沒有 error_code 的 401 不算', () => {
    expect(isAuthError(backendError(401, 'REAUTH_REQUIRED'))).toBe(true)
    expect(isAuthError(backendError(500, 'REAUTH_REQUIRED'))).toBe(true)
    expect(isAuthError(backendError(401, 'UPSTREAM_RATE_LIMITED'))).toBe(false)
    expect(isAuthError({ response: { status: 401 } })).toBe(false)
  })

  it('AC1、AC12：NOT_LINKED 才是尚未連結；Google 限流的 400 不算（#59）', () => {
    expect(isNotLinkedError(backendError(400, 'NOT_LINKED'))).toBe(true)
    expect(isNotLinkedError(backendError(400, 'UPSTREAM_RATE_LIMITED'))).toBe(false)
    expect(isNotLinkedError({ response: { status: 400 } })).toBe(false)
  })

  it('AC12：ALREADY_EXISTS 是已綁定，SUGGESTION_EXPIRED 是建議過期，兩者都是 409 也分得開', () => {
    expect(isAlreadyLinkedError(backendError(409, 'ALREADY_EXISTS'))).toBe(true)
    expect(isAlreadyLinkedError(backendError(409, 'SUGGESTION_EXPIRED'))).toBe(false)
    expect(isSuggestionExpiredError(backendError(409, 'SUGGESTION_EXPIRED'))).toBe(true)
    expect(isSuggestionExpiredError(backendError(409, 'ALREADY_EXISTS'))).toBe(false)
    expect(isAlreadyLinkedError({ response: { status: 409 } })).toBe(false)
  })
})

describe('describeError', () => {
  it('AC12：其他 error_code → 原本的說明後面附加後端的 detail（不取代）', () => {
    expect(describeError(backendError(502, 'UPSTREAM_ERROR', 'Google 暫時無法處理請求'), '請稍後再試一次'))
      .toBe('請稍後再試一次\nGoogle 暫時無法處理請求')
    expect(describeError(backendError(401, 'INVALID_CREDENTIALS', 'GitHub token 無效'))).toBe('GitHub token 無效')
  })

  it('AC12：沒有 error_code（Cloud Run、網路錯誤）或限流 → 只用原本的說明', () => {
    expect(describeError({ response: { status: 500 }, data: { detail: '不是本後端的' } }, '原本的說明')).toBe('原本的說明')
    expect(describeError(new Error('network'), '原本的說明')).toBe('原本的說明')
    expect(describeError(backendError(400, 'UPSTREAM_RATE_LIMITED'), '原本的說明')).toBe('原本的說明')
  })

  it('422 的 detail 是陣列，不附加', () => {
    const error = { response: { status: 422 }, data: { error_code: 'VALIDATION_ERROR', detail: [{ msg: 'Field required' }] } }
    expect(describeError(error, '原本的說明')).toBe('原本的說明')
  })
})

describe('logApiError', () => {
  it('AC17：只記 status 與 error_code，不印出錯誤物件（裡面有 request body 與 Authorization header）', () => {
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {})
    const error = Object.assign(new Error('boom'), {
      response: { status: 401 },
      data: { error_code: 'INVALID_CREDENTIALS', detail: 'x' },
      options: { body: { apiKey: 'ghp_secret' }, headers: { Authorization: 'Bearer jwt-secret' } },
    })

    logApiError('儲存失敗', error)

    expect(spy).toHaveBeenCalledWith('儲存失敗', { status: 401, error_code: 'INVALID_CREDENTIALS' })
    expect(JSON.stringify(spy.mock.calls)).not.toContain('ghp_secret')
    expect(JSON.stringify(spy.mock.calls)).not.toContain('jwt-secret')
    spy.mockRestore()
  })
})
