// E2E 登入輔助函式的 unit 測試；tests/e2e/** 不在主 vitest 設定裡，所以放這裡
import { describe, it, expect, vi } from 'vitest'
import {
  signInWithRetry,
  createSignInDiagnostics,
  createDiagnosticLogger,
  sanitizeError,
  sanitizeForLog,
  toSafeNavigationUrl,
  withSanitizedErrors,
} from '../e2e/support/signInWithRetry'

const EMAIL = 'e2e-user@example.com'
const NAVIGATION_ERROR = new Error(
  `Failed to sign in with email ${EMAIL}: page.evaluate: Execution context was destroyed, most likely because of a navigation.`,
)

function setup(
  signIn: () => Promise<void>,
  isSignedIn: () => Promise<boolean> = vi.fn(async () => false),
  waitForReady: () => Promise<void> = vi.fn(async () => {}),
) {
  const lines: string[] = []
  const onError = vi.fn(async () => {})
  const run = () =>
    signInWithRetry({
      signIn,
      waitForReady,
      isSignedIn,
      onError,
      log: (line) => lines.push(line),
      secrets: [EMAIL],
    })
  return { lines, waitForReady, isSignedIn, onError, run }
}

function expectOriginalMessageWithEmailRedacted(error: unknown, originalError: Error) {
  expect(error).toBeInstanceOf(Error)
  expect((error as Error).message).toBe(originalError.message.split(EMAIL).join('[redacted]'))
  expect((error as Error).message).toContain('[redacted]')
  expect((error as Error).message).not.toContain(EMAIL)
  // #50 AC14：比對 stack，signInWithRetry 改丟訊息相同的新錯誤時才抓得到
  expect((error as Error).stack).toBe(sanitizeForLog(originalError.stack!, [EMAIL]))
}

describe('signInWithRetry', () => {
  it('AC1、AC3：第 1 次登入遇到 Execution context was destroyed，等頁面重新載入後重試成功，並印 1 行重試標記', async () => {
    const signIn = vi.fn().mockRejectedValueOnce(NAVIGATION_ERROR).mockResolvedValueOnce(undefined)
    const { lines, waitForReady, isSignedIn, run } = setup(signIn)

    await run()

    expect(signIn).toHaveBeenCalledTimes(2)
    expect(waitForReady).toHaveBeenCalledTimes(1)
    expect(isSignedIn).toHaveBeenCalledTimes(1)
    const markers = lines.filter((line) => line.startsWith('[e2e][signin-retry]'))
    expect(markers).toHaveLength(1)
    expect(markers[0]).toContain('1/2')
    expect(markers[0]).toContain('Execution context was destroyed')
  })

  it('AC1、AC3：遇到導覽後重新載入時已經是登入狀態（第一次登入其實已完成）→ 成功、不再呼叫 signIn，仍印重試標記', async () => {
    const signIn = vi.fn().mockRejectedValueOnce(NAVIGATION_ERROR)
    const isSignedIn = vi.fn(async () => true)
    const waitForReady = vi.fn(async () => {})
    const { lines, run } = setup(signIn, isSignedIn, waitForReady)

    await run()

    expect(signIn).toHaveBeenCalledTimes(1)
    expect(waitForReady).toHaveBeenCalledTimes(1)
    expect(isSignedIn).toHaveBeenCalledTimes(1)
    // 要等頁面載入完才檢查，否則讀到的是導覽前的 Clerk 狀態
    expect(waitForReady.mock.invocationCallOrder[0]).toBeLessThan(isSignedIn.mock.invocationCallOrder[0]!)
    expect(lines.filter((line) => line.startsWith('[e2e][signin-retry]'))).toHaveLength(1)
  })

  it('AC1、AC3、AC4：重新載入後檢查登入狀態時又遇到導覽 → 算進重試次數、印標記與診斷，再檢查一次已登入就成功', async () => {
    const signIn = vi.fn().mockRejectedValueOnce(NAVIGATION_ERROR)
    const isSignedIn = vi.fn().mockRejectedValueOnce(NAVIGATION_ERROR).mockResolvedValueOnce(true)
    const { lines, waitForReady, onError, run } = setup(signIn, isSignedIn)

    await run()

    expect(signIn).toHaveBeenCalledTimes(1)
    expect(waitForReady).toHaveBeenCalledTimes(2)
    expect(isSignedIn).toHaveBeenCalledTimes(2)
    expect(onError).toHaveBeenCalledTimes(2)
    const markers = lines.filter((line) => line.startsWith('[e2e][signin-retry]'))
    expect(markers).toHaveLength(2)
    expect(markers[1]).toContain('2/2')
  })

  it('AC1、AC3、AC4：重新載入後等待頁面載入時又遇到導覽 → 算進重試次數、印標記與診斷，再等一次後已登入就成功', async () => {
    const signIn = vi.fn().mockRejectedValueOnce(NAVIGATION_ERROR)
    const waitForReady = vi.fn().mockRejectedValueOnce(NAVIGATION_ERROR).mockResolvedValueOnce(undefined)
    const isSignedIn = vi.fn(async () => true)
    const { lines, onError, run } = setup(signIn, isSignedIn, waitForReady)

    await run()

    expect(signIn).toHaveBeenCalledTimes(1)
    expect(waitForReady).toHaveBeenCalledTimes(2)
    // 等待失敗的那一輪不檢查登入狀態
    expect(isSignedIn).toHaveBeenCalledTimes(1)
    expect(onError).toHaveBeenCalledTimes(2)
    const markers = lines.filter((line) => line.startsWith('[e2e][signin-retry]'))
    expect(markers).toHaveLength(2)
    expect(markers[1]).toContain('2/2')
  })

  it('AC2：連續 3 次都遇到導覽（重試 2 次仍失敗）→ 測試失敗，錯誤訊息保留原本的內容，經外層清理後 email 遮成 [redacted]', async () => {
    const navigationError = new Error(NAVIGATION_ERROR.message)
    const signIn = vi.fn().mockRejectedValue(navigationError)
    const { lines, onError, run } = setup(signIn)

    const error = await withSanitizedErrors([EMAIL], run)().catch((error: unknown) => error)

    expectOriginalMessageWithEmailRedacted(error, navigationError)

    expect(signIn).toHaveBeenCalledTimes(3)
    expect(onError).toHaveBeenCalledTimes(3)
    expect(lines.filter((line) => line.startsWith('[e2e][signin-retry]'))).toHaveLength(2)
  })

  it('AC1、AC2：重新載入後的等待一直遇到導覽，重試 2 次用完 → 測試失敗，錯誤訊息保留原本的內容，經外層清理後 email 遮成 [redacted]', async () => {
    const navigationError = new Error(NAVIGATION_ERROR.message)
    const signIn = vi.fn().mockRejectedValueOnce(new Error(NAVIGATION_ERROR.message))
    const waitForReady = vi.fn().mockRejectedValue(navigationError)
    const isSignedIn = vi.fn(async () => true)
    const { lines, onError, run } = setup(signIn, isSignedIn, waitForReady)

    const error = await withSanitizedErrors([EMAIL], run)().catch((error: unknown) => error)

    expectOriginalMessageWithEmailRedacted(error, navigationError)

    expect(signIn).toHaveBeenCalledTimes(1)
    expect(waitForReady).toHaveBeenCalledTimes(2)
    expect(isSignedIn).not.toHaveBeenCalled()
    expect(onError).toHaveBeenCalledTimes(3)
    expect(lines.filter((line) => line.startsWith('[e2e][signin-retry]'))).toHaveLength(2)
  })

  it('AC2：重新載入後的等待或登入狀態檢查遇到其他錯誤 → 不重試，照原本的錯誤失敗，經外層清理後 email 遮成 [redacted]', async () => {
    for (const failingStep of ['waitForReady', 'isSignedIn'] as const) {
      const otherMessage = `Timeout 30000ms exceeded while signing in ${EMAIL}.`
      const otherError = new Error(otherMessage)
      const signIn = vi.fn().mockRejectedValueOnce(NAVIGATION_ERROR)
      const waitForReady =
        failingStep === 'waitForReady' ? vi.fn().mockRejectedValue(otherError) : vi.fn(async () => {})
      const isSignedIn = failingStep === 'isSignedIn' ? vi.fn().mockRejectedValue(otherError) : vi.fn(async () => true)
      const { lines, onError, run } = setup(signIn, isSignedIn, waitForReady)

      const error = await withSanitizedErrors([EMAIL], run)().catch((error: unknown) => error)

      expectOriginalMessageWithEmailRedacted(error, otherError)

      expect(signIn, failingStep).toHaveBeenCalledTimes(1)
      expect(waitForReady, failingStep).toHaveBeenCalledTimes(1)
      expect(onError, failingStep).toHaveBeenCalledTimes(2)
      expect(
        lines.filter((line) => line.startsWith('[e2e][signin-retry]')),
        failingStep,
      ).toHaveLength(1)
    }
  })

  it('AC2：其他登入錯誤（例如找不到使用者）不重試，照原本的錯誤失敗，經外層清理後 email 遮成 [redacted]', async () => {
    const otherMessage = `Failed to sign in with email ${EMAIL}: No user found with email: ${EMAIL}`
    const otherError = new Error(otherMessage)
    const signIn = vi.fn().mockRejectedValue(otherError)
    const { lines, waitForReady, onError, run } = setup(signIn)

    const error = await withSanitizedErrors([EMAIL], run)().catch((error: unknown) => error)

    expectOriginalMessageWithEmailRedacted(error, otherError)

    expect(signIn).toHaveBeenCalledTimes(1)
    expect(onError).toHaveBeenCalledTimes(1)
    expect(waitForReady).not.toHaveBeenCalled()
    expect(lines.filter((line) => line.startsWith('[e2e][signin-retry]'))).toHaveLength(0)
  })

  it('AC4：每次登入錯誤（包括會重試的）都呼叫 onError 印診斷', async () => {
    const signIn = vi.fn().mockRejectedValueOnce(NAVIGATION_ERROR).mockResolvedValueOnce(undefined)
    const { onError, run } = setup(signIn)

    await run()

    expect(onError).toHaveBeenCalledTimes(1)
  })

  it('AC5：重試標記不含測試帳號 email', async () => {
    const signIn = vi.fn().mockRejectedValueOnce(NAVIGATION_ERROR).mockResolvedValueOnce(undefined)
    const { lines, run } = setup(signIn)

    await run()

    expect(lines.join('\n')).not.toContain(EMAIL)
  })
})

describe('createSignInDiagnostics', () => {
  it('AC4、AC5：記錄導覽、console error、pageerror 與 clerk-js 版本；網址只留 host＋path，不含 email、token、query、hash', () => {
    const token = 'eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJ1c2VyIn0.c2lnbmF0dXJl'
    const diagnostics = createSignInDiagnostics({ secrets: [EMAIL] })

    diagnostics.recordNavigation(
      `https://example.clerk.accounts.dev/v1/client/handshake?redirect_url=${encodeURIComponent(EMAIL)}&__clerk_db_jwt=${token}#frag`,
    )
    diagnostics.recordNavigation(`http://127.0.0.1:3000/?__clerk_handshake=${token}`)
    diagnostics.recordConsoleError(`Failed to load https://api.example.com/me?email=${EMAIL} (token ${token})`)
    diagnostics.recordPageError(`Error: user ${EMAIL} rejected`)
    diagnostics.setClerkVersion('5.99.0')

    const output = diagnostics.format('登入失敗')

    expect(output).toContain('example.clerk.accounts.dev/v1/client/handshake')
    expect(output).toContain('127.0.0.1:3000/')
    expect(output).toContain('api.example.com/me')
    expect(output).toContain('5.99.0')
    expect(output).toContain('rejected')
    expect(output).not.toContain(EMAIL)
    expect(output).not.toContain(encodeURIComponent(EMAIL))
    expect(output).not.toContain(token)
    expect(output).not.toContain('?')
    expect(output).not.toContain('#frag')
    expect(output).not.toContain('https://')
  })
})

describe('sanitizeForLog', () => {
  it('AC5：不是 secrets 清單裡的 email 也遮掉（console 訊息可能帶其他帳號）', () => {
    expect(sanitizeForLog('hello other@example.org', [])).not.toContain('other@example.org')
  })
})

// 以下對應規格 docs/specs/issue-46-sanitize-relative-url-query.md
describe('sanitizeForLog：網址只留 host＋path 或 path（#46）', () => {
  it.each([
    ['空白', 'a /v1/a?t=x b', 'a /v1/a b'],
    ['"', '"/v1/a?t=x"', '"/v1/a"'],
    ["'", "'/v1/a?t=x'", "'/v1/a'"],
    ['`', '`/v1/a?t=x`', '`/v1/a`'],
    ['< >', '</v1/a?t=x>', '</v1/a>'],
    ['字面 \\n', '/v1/a?t=x\\n/v1/b?t=y', '/v1/a\\n/v1/b'],
    ['字面 \\t', '/v1/a?t=x\\tok', '/v1/a\\tok'],
  ])('#46 AC3 分隔（%s）：%s → %s', (_label, input, expected) => {
    expect(sanitizeForLog(input, [])).toBe(expected)
  })

  it.each([
    ['=', 'next=/v1/a?t=x', 'next=/v1/a'],
    [':', 'url:/v1/a?t=x', 'url:/v1/a'],
    ['(', '(/v1/a?t=x', '(/v1/a'],
    ['[', '[/v1/a?t=x', '[/v1/a'],
    ['{', '{/v1/a?t=x', '{/v1/a'],
    [',', 'a,/v1/a?t=x', 'a,/v1/a'],
    ['中文', '網址/v1/a?t=x', '網址/v1/a'],
    ['_ 不是起點', 'foo_/v1/a?t=x', 'foo_/v1/a?t=x'],
  ])('#46 AC3 起點（%s）：%s → %s', (_label, input, expected) => {
    expect(sanitizeForLog(input, [])).toBe(expected)
  })

  it.each([
    ['/cb?t=x.', '/cb.'],
    ['/cb?t=x,', '/cb,'],
    ['/cb?t=x;', '/cb;'],
    ['/cb?t=x:', '/cb:'],
    ['/cb?t=x!', '/cb!'],
    ['/cb?t=x)', '/cb)'],
    ['/cb?t=x]', '/cb]'],
    ['/cb?t=x}', '/cb}'],
    ['/cb?t=x?', '/cb'],
    ['/cb?t=x#', '/cb'],
    ['/cb?t=x。', '/cb'],
  ])('#46 AC3 結尾：%s → %s', (input, expected) => {
    expect(sanitizeForLog(input, [])).toBe(expected)
  })

  it.each([
    ['[GET] "/v1/client?__clerk_db_jwt=dvb_xxx#h": 404', '[GET] "/v1/client": 404'],
    ['/wiki/Foo_(bar)?token=x', '/wiki/Foo_(bar)'],
  ])('#46 AC3：%s → %s', (input, expected) => {
    expect(sanitizeForLog(input, [])).toBe(expected)
  })

  it.each([
    ['./v1/a?token=x', './v1/a'],
    ['../../v1/a?token=x', '../../v1/a'],
    ['localhost:3000/v1/a?token=x', 'localhost:3000/v1/a'],
    ['127.0.0.1:3000/v1/a?token=x', '127.0.0.1:3000/v1/a'],
    ['api.example.com/v1/a?token=x', 'api.example.com/v1/a'],
    ['url=https://h/a?token=x', 'url=h/a'],
    ['https://h/a', 'h/a'],
    ['redirect=/cb?code=abc', 'redirect=/cb'],
    ['/任務?x=1', '/任務'],
    ['{url:/v1/a?t=x}', '{url:/v1/a}'],
    ['(https://h/a.js?v=1:2:3)', '(h/a.js)'],
    ['/cb?code=abc.', '/cb.'],
  ])('#46 AC4：%s → %s', (input, expected) => {
    expect(sanitizeForLog(input, [])).toBe(expected)
  })

  it.each([
    ['about:blank', 'about:'],
    ['data:text/html,<p>x</p>', 'data:'],
    ['http://127.0.0.1:3000/?__clerk_handshake=x#y', '127.0.0.1:3000/'],
  ])('#46 AC4 導覽與轉址：toSafeNavigationUrl(%s) → %s', (input, expected) => {
    expect(toSafeNavigationUrl(input)).toBe(expected)
  })

  it.each([
    ['and/or? ok', 'and/or? ok'],
    ['1/2?對嗎', '1/2?對嗎'],
    ['見 #28', '見 #28'],
    ['為什麼失敗?', '為什麼失敗?'],
    ['是 /help? 嗎', '是 /help? 嗎'],
    ['at /_nuxt/app.js:19:22', 'at /_nuxt/app.js:19:22'],
    ['(http://127.0.0.1:3000/_nuxt/a.js:1:2)', '(127.0.0.1:3000/_nuxt/a.js:1:2)'],
  ])('#46 AC5：%s → %s', (input, expected) => {
    expect(sanitizeForLog(input, [])).toBe(expected)
  })

  it.each([
    ['/help?。', '/help'],
    ['/#28', '/'],
    ['路徑/help?x=1', '路徑/help'],
  ])('#46 AC6：%s → %s', (input, expected) => {
    expect(sanitizeForLog(input, [])).toBe(expected)
  })
})

describe('createDiagnosticLogger（#46）', () => {
  it('#46 AC1：info／warn／error 寫出前都先清理網址、email、JWT', () => {
    const token = 'eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJ1c2VyIn0.c2lnbmF0dXJl'
    const write = { info: vi.fn(), warn: vi.fn(), error: vi.fn() }
    const logger = createDiagnosticLogger({ secrets: [EMAIL], write })
    const input = `GET https://h/a?t=1 /v1/b?t=2 ${EMAIL} other@example.org ${token}`
    const expected = 'GET h/a /v1/b [redacted] [email] [token]'

    logger.info(input)
    logger.warn(input)
    logger.error(input)

    expect(write.info).toHaveBeenCalledWith(expected)
    expect(write.warn).toHaveBeenCalledWith(expected)
    expect(write.error).toHaveBeenCalledWith(expected)
  })
})

describe('withSanitizedErrors（#46）', () => {
  it('#46 AC2、#50 AC11：包住的函式丟出帶 query 與 email 的錯誤時，reject 出來的是清理過的新錯誤，類型不變', async () => {
    const error = new TypeError(`GET https://h/a?t=1 ${EMAIL}`)

    const rejected = await withSanitizedErrors([EMAIL], async () => {
      throw error
    })().catch((reason: unknown) => reason)

    expect(rejected).not.toBe(error)
    expect(rejected).toBeInstanceOf(TypeError)
    const { name, message, stack } = rejected as TypeError
    expect(name).toBe('TypeError')
    expect(message).toBe('GET h/a [redacted]')
    expect(stack).not.toContain('t=1')
    expect(stack).not.toContain(EMAIL)
  })
})

describe('sanitizeError（#46）', () => {
  it('#46 AC2、#50 AC11：清理 message、stack 與兩層 cause，回傳原型相同的新錯誤', () => {
    const inner = new Error(`inner /v1/c?t=3 ${EMAIL}`)
    const middle = new Error('middle https://h/b?t=2', { cause: inner })
    const error = new TypeError(`outer /v1/a?t=1 ${EMAIL}`, { cause: middle })
    error.stack = `TypeError: outer /v1/a?t=1 ${EMAIL}\n    at f (http://127.0.0.1:3000/_nuxt/a.js?v=9:1:2)`

    const result = sanitizeError(error, [EMAIL])

    expect(result).not.toBe(error)
    expect(result).toBeInstanceOf(TypeError)
    expect(result.name).toBe('TypeError')
    expect(result.message).toBe('outer /v1/a [redacted]')
    expect(result.stack).toBe('TypeError: outer /v1/a [redacted]\n    at f (127.0.0.1:3000/_nuxt/a.js)')
    const resultMiddle = result.cause as Error
    expect(resultMiddle).not.toBe(middle)
    expect(resultMiddle.message).toBe('middle h/b')
    expect((resultMiddle.cause as Error).message).toBe('inner /v1/c [redacted]')
  })

  it('#46 AC2：cause 是字串時也清理', () => {
    const error = new Error('outer', { cause: `GET /v1/a?t=1 ${EMAIL}` })

    const result = sanitizeError(error, [EMAIL])

    const cause = result.cause instanceof Error ? result.cause.message : String(result.cause)
    expect(cause).toBe('GET /v1/a [redacted]')
  })

  it('#46 AC2：不是 Error 的值轉成字串清理後包成 Error', () => {
    const result = sanitizeError(`failed /v1/a?t=1 ${EMAIL}`, [EMAIL])

    expect(result).toBeInstanceOf(Error)
    expect(result.message).toBe('failed /v1/a [redacted]')
  })

  it('#50 AC1：AssertionError 的 actual、expected 字串經過清理', () => {
    const error = assertionError(`https://h/cb?code=abc ${EMAIL}`, `https://h/cb?code=xyz ${EMAIL}`)

    const result = sanitizeError(error, [EMAIL]) as ErrorWithProperties

    expect(result.actual).toBe('h/cb [redacted]')
    expect(result.expected).toBe('h/cb [redacted]')
  })

  it('#50 AC1：cause 是 AssertionError 時，cause 的 actual、expected 也經過清理', () => {
    const cause = assertionError(`/cb?code=abc ${EMAIL}`, `/cb?code=xyz ${EMAIL}`)
    const error = new Error('outer', { cause })

    const result = sanitizeError(error, [EMAIL])

    const resultCause = result.cause as ErrorWithProperties
    expect(resultCause.actual).toBe('/cb [redacted]')
    expect(resultCause.expected).toBe('/cb [redacted]')
  })

  it('#50 AC1：message 唯讀而且不可重新定義時，清理結果的 message 仍經過清理', () => {
    const error = new Error('failed')
    Object.defineProperty(error, 'message', { value: `/cb?code=abc ${EMAIL}`, writable: false, configurable: false })

    const result = sanitizeError(error, [EMAIL])

    expect(result.message).toBe('/cb [redacted]')
  })

  it('#50 AC2：可列舉、不可列舉的字串屬性與自有 getter 都經過清理，enumerable 不變', () => {
    const error = makeAc2Error()

    const result = sanitizeError(error, [EMAIL]) as ErrorWithProperties

    expect(result.detail).toBe('/v1/a [token]')
    expect(result.hidden).toBe('/v1/b [token]')
    expect(result.computed).toBe('/v1/c')
    expect(Object.getOwnPropertyDescriptor(result, 'detail')?.enumerable).toBe(true)
    expect(Object.getOwnPropertyDescriptor(result, 'hidden')?.enumerable).toBe(false)
  })

  it('#50 AC2：不可重新定義的 getter 加上不存值的 setter，清理結果的值仍經過清理', () => {
    const error = new Error('failed') as ErrorWithProperties
    Object.defineProperty(error, 'detail', { get: () => '/v1/a?t=1', set: () => {}, enumerable: true, configurable: false })

    const result = sanitizeError(error, [EMAIL]) as ErrorWithProperties

    expect(result.detail).toBe('/v1/a')
  })

  it('#50 AC3：actual 是物件、陣列時換成每一層都清理過的複製品；Map 變成空物件', () => {
    const error = assertionError({ url: '/cb?code=abc', nested: [{ note: EMAIL }] }, {})
    const mapError = assertionError(new Map([['k', EMAIL]]), {})

    const result = sanitizeError(error, [EMAIL]) as ErrorWithProperties
    const mapResult = sanitizeError(mapError, [EMAIL]) as ErrorWithProperties

    expect(result.actual).toEqual({ url: '/cb', nested: [{ note: '[redacted]' }] })
    expect(mapResult.actual).toEqual({})
    expect(mapResult.actual).not.toBeInstanceOf(Map)
  })

  it('#50 AC3：AggregateError.errors 裡的 Error 也經過清理', () => {
    const error = new AggregateError([new Error(`/v1/a?t=1 ${JWT}`)])

    const result = sanitizeError(error, [EMAIL]) as AggregateError

    const inner = result.errors[0] as Error
    expect(inner.message).not.toContain('t=1')
    expect(inner.message).not.toContain(JWT)
  })

  it('#50 AC4：原本的 actual 物件與錯誤都不變；清理結果的 errors[0] 是另一個已清理的物件', () => {
    const actual = { url: '/cb?code=abc', nested: [{ note: EMAIL }] }
    const error = assertionError(actual, {})
    const originalMessage = error.message
    const inner = new Error(`/v1/a?t=1 ${JWT}`)
    const aggregate = new AggregateError([inner], `outer /v1/b?t=2`)

    const result = sanitizeError(error, [EMAIL]) as ErrorWithProperties
    const aggregateResult = sanitizeError(aggregate, [EMAIL]) as AggregateError

    expect(actual).toEqual({ url: '/cb?code=abc', nested: [{ note: EMAIL }] })
    expect(error.actual).toBe(actual)
    expect(error.message).toBe(originalMessage)
    expect(result.actual).not.toBe(actual)
    expect(aggregate.message).toBe('outer /v1/b?t=2')
    expect(aggregate.errors[0]).toBe(inner)
    expect(inner.message).toBe(`/v1/a?t=1 ${JWT}`)
    expect(aggregateResult.errors[0]).not.toBe(inner)
    expect((aggregateResult.errors[0] as Error).message).toBe('/v1/a [token]')
  })

  it('#50 AC5：actual 有循環參照時清理會結束，複製品的 self 指向複製品', () => {
    const actual: Record<string, unknown> = { url: '/cb?code=abc' }
    actual.self = actual
    const error = withProperties(new Error('failed'), { actual })

    const result = sanitizeError(error, [EMAIL]) as ErrorWithProperties

    const copy = result.actual as Record<string, unknown>
    expect(copy).not.toBe(actual)
    expect(copy.url).toBe('/cb')
    expect(copy.self).toBe(copy)
  })

  it('#50 AC5：錯誤的 cause 指回自己時清理會結束，清理結果的 cause 指向清理結果', () => {
    const error = new Error('failed /v1/a?t=1')
    error.cause = error

    const result = sanitizeError(error, [EMAIL])

    expect(result).not.toBe(error)
    expect(result.message).toBe('failed /v1/a')
    expect(result.cause).toBe(result)
  })

  it('#50 AC6：名稱看起來是機密的屬性，不論值的類型都換成 [redacted]', () => {
    const error = withProperties(new Error('failed'), {
      actual: {
        headers: { Authorization: 'Bearer opaque123' },
        apiKey: 'k',
        items: [{ password: 1 }],
        sessionId: 's',
        Cookie: 'c=1',
        clientSecret: 'cs',
        x_api_key: 'ak',
      },
      expected: { session: { id: 'abc' } },
      token: 12345,
    })

    const result = sanitizeError(error, [EMAIL]) as ErrorWithProperties

    expect(result.actual).toEqual({
      headers: { Authorization: '[redacted]' },
      apiKey: '[redacted]',
      items: [{ password: '[redacted]' }],
      sessionId: '[redacted]',
      Cookie: '[redacted]',
      clientSecret: '[redacted]',
      x_api_key: '[redacted]',
    })
    expect(result.expected).toEqual({ session: '[redacted]' })
    expect(result.token).toBe('[redacted]')
  })

  it('#50 AC7：{ name, value } 的 name 看起來是機密時，value 不論類型都換成 [redacted]', () => {
    const error = withProperties(new Error('failed'), {
      actual: [
        { name: '__clerk_db_jwt', value: 'dvb_abc' },
        { name: 'Authorization', value: 'Bearer opaque123' },
        { name: 'Set-Cookie', value: 'c=1' },
        { name: 'client_secret', value: 'cs' },
        { name: 'x_api_key', value: 'ak' },
        { name: 'session', value: { id: 'abc' } },
        { name: 'theme', value: 'dark' },
      ],
    })

    const result = sanitizeError(error, [EMAIL]) as ErrorWithProperties

    expect(result.actual).toEqual([
      { name: '__clerk_db_jwt', value: '[redacted]' },
      { name: 'Authorization', value: '[redacted]' },
      { name: 'Set-Cookie', value: '[redacted]' },
      { name: 'client_secret', value: '[redacted]' },
      { name: 'x_api_key', value: '[redacted]' },
      { name: 'session', value: '[redacted]' },
      { name: 'theme', value: 'dark' },
    ])
  })

  it('#50 AC8：讀屬性出錯時值換成 [unserializable]，其他屬性照常清理，丟出的是清理過的錯誤', async () => {
    const error = makeAc8Error()

    const rejected = (await withSanitizedErrors([EMAIL], async () => {
      throw error
    })().catch((reason: unknown) => reason)) as ErrorWithProperties

    // 不用 not.toBe：兩者不同時 vitest 會逐一比對屬性，讀到原本錯誤會丟出錯誤的 getter
    expect(rejected === error).toBe(false)
    expect(rejected.message).toBe('failed /v1/a')
    expect(rejected.broken).toBe('[unserializable]')
    expect(rejected.actual).toEqual({ broken: '[unserializable]', url: '/cb' })
    expect(rejected.detail).toBe('[redacted]')
  })

  it('#50 AC8：cause 的 getter 丟出錯誤時，丟出的是清理過的錯誤', async () => {
    const error = withProperties(new Error(`failed /v1/a?t=1`), { detail: EMAIL })
    Object.defineProperty(error, 'cause', {
      get: () => {
        throw new Error('getter failed')
      },
      configurable: true,
    })

    const rejected = (await withSanitizedErrors([EMAIL], async () => {
      throw error
    })().catch((reason: unknown) => reason)) as ErrorWithProperties

    // 不用 not.toBe：兩者不同時 vitest 會逐一比對屬性，讀到原本錯誤會丟出錯誤的 getter
    expect(rejected === error).toBe(false)
    expect(rejected.message).toBe('failed /v1/a')
    expect((rejected.cause as Error).message).toBe('[unserializable]')
    expect(rejected.detail).toBe('[redacted]')
  })

  it('#50 AC9：清理結果的 actual、expected、message、stack 仍可寫入', () => {
    for (const error of [makeAc2Error(), makeAc8Error()]) {
      // 只有 getter 的 expected：清理結果要是一般屬性，vitest 之後才寫得進去
      Object.defineProperty(error, 'expected', { get: () => '/v1/e?t=1', configurable: true })
      const result = sanitizeError(error, [EMAIL]) as ErrorWithProperties

      result.actual = 'new actual'
      result.expected = 'new expected'
      result.message = 'new message'
      result.stack = 'new stack'

      expect(result.actual).toBe('new actual')
      expect(result.expected).toBe('new expected')
      expect(result.message).toBe('new message')
      expect(result.stack).toBe('new stack')
    }
  })

  it('#50 AC11：丟出的錯誤是攔截定義屬性卻不寫入的 Proxy 時，清理結果的 message 仍經過清理', () => {
    const error = new Proxy(new Error(`/cb?code=abc ${EMAIL}`), { defineProperty: () => true })

    const result = sanitizeError(error, [EMAIL])

    expect(result).not.toBe(error)
    expect(result).toBeInstanceOf(Error)
    expect(result.message).toBe('/cb [redacted]')
  })

  it('#50 AC15 例子（1）：錯誤用 Object.create(另一個錯誤) 建立時，原型上的 message、stack、actual 也經過清理', () => {
    const inner = withProperties(new Error(`/cb?code=abc ${EMAIL}`), { actual: `/x?token=1 ${EMAIL}` })
    const error = Object.create(inner) as Error

    const result = sanitizeError(error, [EMAIL]) as ErrorWithProperties

    expect(result).toBeInstanceOf(Error)
    expect(result.message).toBe('/cb [redacted]')
    expect(result.actual).toBe('/x [redacted]')
    expect(result.stack).not.toContain('code=abc')
    expect(result.stack).not.toContain(EMAIL)
  })

  it('#50 AC15 例子（2）：三層原型時，每一層的屬性都經過清理，同名時離原本的錯誤越近的優先', () => {
    const inner = new Error(`/i?q=1 ${EMAIL}`)
    const middle = withProperties(Object.create(inner) as Error, { actual: `/m?q=1 ${EMAIL}`, message: '/m?q=2' })
    const error = withProperties(Object.create(middle) as Error, { message: '/e?q=1' })

    const result = sanitizeError(error, [EMAIL]) as ErrorWithProperties

    expect(result.message).toBe('/e')
    expect(result.actual).toBe('/m [redacted]')
    expect(result.stack?.split('\n')[0]).toBe('Error: /i [redacted]')
  })

  it('#50 AC13：值是二進位資料時整個換成 [binary]，不保留內容', () => {
    const error = withProperties(new Error('failed'), {
      actual: Buffer.from('/cb?code=SECRET'),
      expected: new Uint8Array([1, 2]),
      response: { body: Buffer.from(EMAIL) },
    })

    const result = sanitizeError(error, [EMAIL]) as ErrorWithProperties

    expect(result.actual).toBe('[binary]')
    expect(result.expected).toBe('[binary]')
    expect(result.response).toEqual({ body: '[binary]' })
  })

  it('#50 AC12 例子（1）：丟出的值是已撤銷的 Proxy 時，丟出固定文字加上出錯原因的新錯誤', async () => {
    const { proxy, revoke } = Proxy.revocable(new Error(`/cb?code=abc ${EMAIL}`), {})
    revoke()

    const rejected = await withSanitizedErrors([EMAIL], async () => {
      throw proxy
    })().catch((reason: unknown) => reason)

    expect(rejected).toBeInstanceOf(Error)
    const { message } = rejected as Error
    expect(message.startsWith('[e2e] 錯誤清理失敗：')).toBe(true)
    expect(message).toContain('revoked')
  })

  it('#50 AC12 例子（2）：出錯原因是帶 query 與 email 的字串時，丟出的訊息是固定文字加上清理過的出錯原因', async () => {
    const thrown = {
      toString() {
        throw `/cb?code=abc ${EMAIL}`
      },
    }

    const rejected = await withSanitizedErrors([EMAIL], async () => {
      throw thrown
    })().catch((error: unknown) => error)

    expect(rejected).toBeInstanceOf(Error)
    expect((rejected as Error).message).toBe('[e2e] 錯誤清理失敗：/cb [redacted]')
  })

  it('#50 AC12 例子（3）：出錯原因轉成文字時又出錯，丟出的訊息只有固定文字加 [unserializable]', async () => {
    const reason = {
      toString() {
        throw `/cb?code=abc ${EMAIL}`
      },
    }
    const thrown = {
      toString() {
        throw reason
      },
    }

    const rejected = await withSanitizedErrors([EMAIL], async () => {
      throw thrown
    })().catch((error: unknown) => error)

    expect(rejected).toBeInstanceOf(Error)
    expect((rejected as Error).message).toBe('[e2e] 錯誤清理失敗：[unserializable]')
  })
})

const JWT = 'eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1In0.c2ln'

type ErrorWithProperties = Error & Record<string, unknown>

function withProperties(error: Error, properties: Record<string, unknown>): ErrorWithProperties {
  return Object.assign(error, properties)
}

function assertionError(actual: unknown, expected: unknown): ErrorWithProperties {
  try {
    expect(actual).toBe(expected)
  } catch (error) {
    return error as ErrorWithProperties
  }
  throw new Error('expect 應該要失敗')
}

function makeAc2Error(): ErrorWithProperties {
  const error = withProperties(new Error('failed'), { detail: `/v1/a?t=1 ${JWT}` })
  Object.defineProperty(error, 'hidden', { value: `/v1/b?t=2 ${JWT}`, enumerable: false, writable: true, configurable: true })
  Object.defineProperty(error, 'computed', { get: () => '/v1/c?t=3', enumerable: true, configurable: true })
  return error
}

function makeAc8Error(): ErrorWithProperties {
  const throwing = () => {
    throw new Error('getter failed')
  }
  const actual = { url: '/cb?code=abc' }
  Object.defineProperty(actual, 'broken', { get: throwing, enumerable: true, configurable: true })
  const error = withProperties(new Error(`failed /v1/a?t=1`), { actual, detail: EMAIL })
  Object.defineProperty(error, 'broken', { get: throwing, enumerable: true, configurable: true })
  return error
}
