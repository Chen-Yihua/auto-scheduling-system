import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { $fetch as ofetch } from 'ofetch'

import { backendRetryFetchOptions, decideRetry, isBackendRequest, type RetryInput } from '~/utils/fetchRetry'

const API = 'http://localhost:8000'
const FRONT = 'http://localhost:3000/schedule'

function input(overrides: Partial<RetryInput>): RetryInput {
  return { method: 'GET', hasIdempotencyKey: false, attempt: 1, ...overrides }
}

describe('decideRetry：需求 7 的重送規則（AC9）', () => {
  it.each([
    ['沒有收到回應', {}],
    ['沒有 error_code 的 502', { status: 502 }],
    ['沒有 error_code 的 503', { status: 503 }],
    ['沒有 error_code 的 504', { status: 504 }],
    ['SERVICE_UNAVAILABLE', { status: 503, errorCode: 'SERVICE_UNAVAILABLE' }],
    ['UPSTREAM_TIMEOUT', { status: 504, errorCode: 'UPSTREAM_TIMEOUT' }],
  ])('暫時性錯誤（%s）→ 重送，第 1 次重送前等 0.5 秒', (_, overrides) => {
    expect(decideRetry(input(overrides))).toEqual({ retry: true, delayMs: 500 })
  })

  it('第 2 次重送前等 1 秒；送滿 3 次（第 1 次加 2 次重送）後不再重送', () => {
    expect(decideRetry(input({ status: 503, attempt: 2 }))).toEqual({ retry: true, delayMs: 1000 })
    expect(decideRetry(input({ status: 503, attempt: 3 }))).toEqual({ retry: false })
  })

  it.each([
    ['400 INVALID_REQUEST', { status: 400, errorCode: 'INVALID_REQUEST' }],
    ['401 UNAUTHENTICATED', { status: 401, errorCode: 'UNAUTHENTICATED' }],
    ['404 沒有 error_code', { status: 404 }],
    ['409 REAUTH_REQUIRED', { status: 409, errorCode: 'REAUTH_REQUIRED' }],
    ['422 VALIDATION_ERROR', { status: 422, errorCode: 'VALIDATION_ERROR' }],
    ['500 INTERNAL_ERROR', { status: 500, errorCode: 'INTERNAL_ERROR' }],
    ['502 UPSTREAM_ERROR', { status: 502, errorCode: 'UPSTREAM_ERROR' }],
  ])('永久性錯誤（%s）→ 不重送', (_, overrides) => {
    expect(decideRetry(input(overrides))).toEqual({ retry: false })
  })

  it.each([
    ['429 RATE_LIMITED', { status: 429, errorCode: 'RATE_LIMITED' }],
    ['503 UPSTREAM_RATE_LIMITED', { status: 503, errorCode: 'UPSTREAM_RATE_LIMITED', retryAfter: '1' }],
    ['沒有 error_code 的 429', { status: 429 }],
  ])('限流（%s）→ 不重送', (_, overrides) => {
    expect(decideRetry(input(overrides))).toEqual({ retry: false })
  })

  it.each([
    ['沒有 error_code 的 500', { status: 500 }],
    ['沒有 error_code 的 501', { status: 501 }],
  ])('其他沒列出的情況（%s）→ 不重送', (_, overrides) => {
    expect(decideRetry(input(overrides))).toEqual({ retry: false })
  })

  it.each([
    ['GET', false, true],
    ['POST', true, true],
    ['POST', false, false],
    ['PUT', true, false],
    ['PATCH', false, false],
    ['DELETE', false, false],
  ])('%s（帶 Idempotency-Key：%s）遇到暫時性錯誤 → 重送：%s', (method, hasIdempotencyKey, expected) => {
    expect(decideRetry(input({ method, hasIdempotencyKey, status: 503 })).retry).toBe(expected)
  })

  it.each([
    ['3', 1, 3000],
    ['0', 1, 500],
    ['0', 2, 1000],
    ['Wed, 21 Oct 2026 07:28:00 GMT', 1, 500],
    [null, 1, 500],
  ])('Retry-After=%s、第 %i 次失敗 → 等 %i 毫秒（取固定間隔與 Retry-After 較長的）', (retryAfter, attempt, delayMs) => {
    expect(decideRetry(input({ status: 503, errorCode: 'SERVICE_UNAVAILABLE', retryAfter, attempt }))).toEqual({ retry: true, delayMs })
  })
})

describe('isBackendRequest：只有本後端的請求套用重送規則（AC9）', () => {
  it.each([
    ['http://localhost:8000/schedule/tasks', API, true],
    ['http://localhost:8000/schedule/tasks', 'http://localhost:8000/', true],
    ['https://api.example.com/api', 'https://api.example.com/api', true],
    ['https://api.example.com/api/x', 'https://api.example.com/api', true],
    ['https://api.example.com/api/x', 'https://api.example.com/api/', true],
    ['https://api.example.com/api2/x', 'https://api.example.com/api', false],
    ['https://api.example.com.evil.com/schedule', 'https://api.example.com', false],
    ['https://api.example.com@evil.com/schedule', 'https://api.example.com', false],
    ['/api/leetcode', API, false],
    ['http://localhost:9000/schedule', API, false],
    ['https://hacker-news.firebaseio.com/v0/topstories.json', API, false],
  ])('%s（apiBaseUrl=%s）→ %s', (url, base, expected) => {
    expect(isBackendRequest(url, base, FRONT)).toBe(expected)
  })
})

describe('串接到 $fetch.create（AC9）', () => {
  type Outcome = { status: number; body?: unknown; headers?: Record<string, string> } | Error

  function mockFetch(...outcomes: Outcome[]) {
    return vi.fn(async () => {
      const outcome = outcomes.length > 1 ? outcomes.shift()! : outcomes[0]!
      if (outcome instanceof Error) throw outcome
      return new Response(outcome.body === undefined ? null : JSON.stringify(outcome.body), {
        status: outcome.status,
        headers: { 'content-type': 'application/json', ...outcome.headers },
      })
    })
  }

  function createFetch(fetch: ReturnType<typeof mockFetch>) {
    return ofetch.create(backendRetryFetchOptions(API, () => FRONT), { fetch })
  }

  // 等重送的間隔跑完，回傳結果或錯誤
  async function settle<T>(promise: Promise<T>): Promise<T | unknown> {
    const result = promise.catch((error: unknown) => error)
    await vi.runAllTimersAsync()
    return result
  }

  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('本後端沒有回應（網路中斷）→ 重送，跨重送總共最多 3 次', async () => {
    const fetch = mockFetch(new TypeError('Failed to fetch'))

    const error = await settle(createFetch(fetch)(`${API}/schedule/tasks`))

    expect(fetch).toHaveBeenCalledTimes(3)
    expect(error).toBeInstanceOf(Error)
  })

  it('本後端沒有 error_code 的 503 之後成功 → 重送一次並拿到結果', async () => {
    const fetch = mockFetch({ status: 503 }, { status: 200, body: [{ id: 'manual:t1' }] })

    const result = await settle(createFetch(fetch)(`${API}/schedule/tasks`))

    expect(fetch).toHaveBeenCalledTimes(2)
    expect(result).toEqual([{ id: 'manual:t1' }])
  })

  it('$fetch.raw 也套用同樣的規則', async () => {
    const fetch = mockFetch({ status: 504, body: { detail: 'x', error_code: 'UPSTREAM_TIMEOUT' } }, { status: 200, body: {} })

    await settle(createFetch(fetch).raw(`${API}/oauth/calendars`))

    expect(fetch).toHaveBeenCalledTimes(2)
  })

  it.each([
    ['限流 UPSTREAM_RATE_LIMITED', { status: 503, body: { detail: 'x', error_code: 'UPSTREAM_RATE_LIMITED' } }],
    ['永久性錯誤 UPSTREAM_ERROR', { status: 502, body: { detail: 'x', error_code: 'UPSTREAM_ERROR' } }],
    ['沒有 error_code 的 500', { status: 500, body: 'Internal Server Error' }],
    ['409 REAUTH_REQUIRED', { status: 409, body: { detail: 'x', error_code: 'REAUTH_REQUIRED' } }],
  ])('本後端 GET 遇到%s → 不重送（ofetch 預設會重送的狀態碼也一樣）', async (_, outcome) => {
    const fetch = mockFetch(outcome)

    await settle(createFetch(fetch)(`${API}/github/issues`))

    expect(fetch).toHaveBeenCalledTimes(1)
  })

  it('本後端不帶 Idempotency-Key 的 POST 遇到暫時性錯誤 → 不重送；帶 Idempotency-Key 才重送', async () => {
    const withoutKey = mockFetch({ status: 503 })
    await settle(createFetch(withoutKey)(`${API}/manual-tasks/`, { method: 'POST', body: {} }))

    const withKey = mockFetch({ status: 503 }, { status: 201, body: {} })
    await settle(createFetch(withKey)(`${API}/manual-tasks/`, { method: 'POST', body: {}, headers: { 'Idempotency-Key': 'k' } }))

    expect(withoutKey).toHaveBeenCalledTimes(1)
    expect(withKey).toHaveBeenCalledTimes(2)
  })

  it('本後端的回應帶 Retry-After 時，等到 Retry-After 的秒數才重送', async () => {
    const fetch = mockFetch(
      { status: 503, body: { detail: 'x', error_code: 'SERVICE_UNAVAILABLE' }, headers: { 'Retry-After': '2' } },
      { status: 200, body: {} },
    )

    const promise = createFetch(fetch)(`${API}/schedule/tasks`)
    await vi.advanceTimersByTimeAsync(1500)
    expect(fetch).toHaveBeenCalledTimes(1)
    await vi.advanceTimersByTimeAsync(600)
    await promise

    expect(fetch).toHaveBeenCalledTimes(2)
  })

  it('非本後端的 GET 遇到 503 → 照 ofetch 預設重送 1 次', async () => {
    const fetch = mockFetch({ status: 503 })

    await settle(createFetch(fetch)('https://hacker-news.firebaseio.com/v0/topstories.json'))

    expect(fetch).toHaveBeenCalledTimes(2)
  })

  it('非本後端的相對網址（前端自己的 server route）遇到 400 → 照 ofetch 預設不重送', async () => {
    const fetch = mockFetch({ status: 400 })

    await settle(createFetch(fetch)('http://localhost:3000/api/leetcode'))

    expect(fetch).toHaveBeenCalledTimes(1)
  })
})

describe('plugins/backendFetchRetry.client.ts', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.useRealTimers()
  })

  it('把瀏覽器端的 globalThis.$fetch 換成套用重送規則的版本（AC9）', async () => {
    vi.useFakeTimers()
    const fetch = vi.fn(async () => new Response(null, { status: 503 }))
    vi.stubGlobal('$fetch', ofetch.create({}, { fetch }))
    vi.stubGlobal('defineNuxtPlugin', (setup: () => void) => setup)
    vi.stubGlobal('useRuntimeConfig', () => ({ public: { apiBaseUrl: API } }))

    const { default: setup } = await import('~/plugins/backendFetchRetry.client')
    ;(setup as unknown as () => void)()
    const result = globalThis.$fetch(`${API}/schedule/tasks`).catch((error: unknown) => error)
    await vi.runAllTimersAsync()
    await result

    expect(fetch).toHaveBeenCalledTimes(3)
  })
})
