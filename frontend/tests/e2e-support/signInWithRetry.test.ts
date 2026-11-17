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

function expectOriginalMessageWithEmailRedacted(error: unknown, original: string) {
  expect(error).toBeInstanceOf(Error)
  expect((error as Error).message).toBe(original.split(EMAIL).join('[redacted]'))
  expect((error as Error).message).toContain('[redacted]')
  expect((error as Error).message).not.toContain(EMAIL)
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

    expect(error).toBe(navigationError)
    expectOriginalMessageWithEmailRedacted(error, NAVIGATION_ERROR.message)

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

    expect(error).toBe(navigationError)
    expectOriginalMessageWithEmailRedacted(error, NAVIGATION_ERROR.message)

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

      expect(error, failingStep).toBe(otherError)
      expectOriginalMessageWithEmailRedacted(error, otherMessage)

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

    expect(error).toBe(otherError)
    expectOriginalMessageWithEmailRedacted(error, otherMessage)

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
  it('#46 AC2：包住的函式丟出帶 query 與 email 的錯誤時，reject 出來的是清理過的同一個錯誤', async () => {
    const error = new TypeError(`GET https://h/a?t=1 ${EMAIL}`)

    const rejected = await withSanitizedErrors([EMAIL], async () => {
      throw error
    })().catch((reason: unknown) => reason)

    expect(rejected).toBe(error)
    expect(error.message).toBe('GET h/a [redacted]')
    expect(error.stack).not.toContain('t=1')
    expect(error.stack).not.toContain(EMAIL)
  })
})

describe('sanitizeError（#46）', () => {
  it('#46 AC2：清理 message、stack 與兩層 cause，回傳同一個物件、類型不變', () => {
    const inner = new Error(`inner /v1/c?t=3 ${EMAIL}`)
    const middle = new Error('middle https://h/b?t=2', { cause: inner })
    const error = new TypeError(`outer /v1/a?t=1 ${EMAIL}`, { cause: middle })
    error.stack = `TypeError: outer /v1/a?t=1 ${EMAIL}\n    at f (http://127.0.0.1:3000/_nuxt/a.js?v=9:1:2)`

    const result = sanitizeError(error, [EMAIL])

    expect(result).toBe(error)
    expect(result).toBeInstanceOf(TypeError)
    expect(result.message).toBe('outer /v1/a [redacted]')
    expect(result.stack).toBe('TypeError: outer /v1/a [redacted]\n    at f (127.0.0.1:3000/_nuxt/a.js)')
    expect(middle.message).toBe('middle h/b')
    expect(middle.cause).toBe(inner)
    expect(inner.message).toBe('inner /v1/c [redacted]')
  })

  it('#46 AC2：cause 是字串時也清理', () => {
    const error = new Error('outer', { cause: `GET /v1/a?t=1 ${EMAIL}` })

    sanitizeError(error, [EMAIL])

    const cause = error.cause instanceof Error ? error.cause.message : String(error.cause)
    expect(cause).toBe('GET /v1/a [redacted]')
  })

  it('#46 AC2：不是 Error 的值轉成字串清理後包成 Error', () => {
    const result = sanitizeError(`failed /v1/a?t=1 ${EMAIL}`, [EMAIL])

    expect(result).toBeInstanceOf(Error)
    expect(result.message).toBe('failed /v1/a [redacted]')
  })

  it('#50 AC1：AssertionError 的 actual、expected 字串經過清理', () => {
    const error = assertionError(`https://h/cb?code=abc ${EMAIL}`, `https://h/cb?code=xyz ${EMAIL}`)

    sanitizeError(error, [EMAIL])

    expect(error.actual).toBe('h/cb [redacted]')
    expect(error.expected).toBe('h/cb [redacted]')
  })

  it('#50 AC1：cause 是 AssertionError 時，cause 的 actual、expected 也經過清理', () => {
    const cause = assertionError(`/cb?code=abc ${EMAIL}`, `/cb?code=xyz ${EMAIL}`)
    const error = new Error('outer', { cause })

    sanitizeError(error, [EMAIL])

    expect(cause.actual).toBe('/cb [redacted]')
    expect(cause.expected).toBe('/cb [redacted]')
  })

  it('#50 AC2：可列舉、不可列舉的字串屬性與自有 getter 都經過清理，enumerable 不變', () => {
    const error = makeAc2Error()

    sanitizeError(error, [EMAIL])

    expect(error.detail).toBe('/v1/a [token]')
    expect(error.hidden).toBe('/v1/b [token]')
    expect(error.computed).toBe('/v1/c')
    expect(Object.getOwnPropertyDescriptor(error, 'detail')?.enumerable).toBe(true)
    expect(Object.getOwnPropertyDescriptor(error, 'hidden')?.enumerable).toBe(false)
  })

  it('#50 AC3：actual 是物件、陣列時換成每一層都清理過的複製品；Map 變成空物件', () => {
    const error = assertionError({ url: '/cb?code=abc', nested: [{ note: EMAIL }] }, {})
    const mapError = assertionError(new Map([['k', EMAIL]]), {})

    sanitizeError(error, [EMAIL])
    sanitizeError(mapError, [EMAIL])

    expect(error.actual).toEqual({ url: '/cb', nested: [{ note: '[redacted]' }] })
    expect(mapError.actual).toEqual({})
    expect(mapError.actual).not.toBeInstanceOf(Map)
  })

  it('#50 AC3：AggregateError.errors 裡的 Error 也經過清理', () => {
    const error = new AggregateError([new Error(`/v1/a?t=1 ${JWT}`)])

    sanitizeError(error, [EMAIL])

    const inner = error.errors[0] as Error
    expect(inner.message).not.toContain('t=1')
    expect(inner.message).not.toContain(JWT)
  })

  it('#50 AC4：原本的 actual 物件不變；AggregateError.errors[0] 是同一個物件、已清理', () => {
    const actual = { url: '/cb?code=abc', nested: [{ note: EMAIL }] }
    const error = assertionError(actual, {})
    const inner = new Error(`/v1/a?t=1 ${JWT}`)
    const aggregate = new AggregateError([inner])

    sanitizeError(error, [EMAIL])
    sanitizeError(aggregate, [EMAIL])

    expect(actual).toEqual({ url: '/cb?code=abc', nested: [{ note: EMAIL }] })
    expect(error.actual).not.toBe(actual)
    expect(aggregate.errors[0]).toBe(inner)
    expect(inner.message).toBe('/v1/a [token]')
  })

  it('#50 AC5：actual 有循環參照時清理會結束，複製品的 self 指向複製品', () => {
    const actual: Record<string, unknown> = { url: '/cb?code=abc' }
    actual.self = actual
    const error = withProperties(new Error('failed'), { actual })

    sanitizeError(error, [EMAIL])

    const copy = error.actual as Record<string, unknown>
    expect(copy).not.toBe(actual)
    expect(copy.url).toBe('/cb')
    expect(copy.self).toBe(copy)
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
      token: 12345,
    })

    sanitizeError(error, [EMAIL])

    expect(error.actual).toEqual({
      headers: { Authorization: '[redacted]' },
      apiKey: '[redacted]',
      items: [{ password: '[redacted]' }],
      sessionId: '[redacted]',
      Cookie: '[redacted]',
      clientSecret: '[redacted]',
      x_api_key: '[redacted]',
    })
    expect(error.token).toBe('[redacted]')
  })

  it('#50 AC7：{ name, value } 的 name 看起來是機密時，value 換成 [redacted]', () => {
    const error = withProperties(new Error('failed'), {
      actual: [
        { name: '__clerk_db_jwt', value: 'dvb_abc' },
        { name: 'Authorization', value: 'Bearer opaque123' },
        { name: 'Set-Cookie', value: 'c=1' },
        { name: 'client_secret', value: 'cs' },
        { name: 'x_api_key', value: 'ak' },
        { name: 'theme', value: 'dark' },
      ],
    })

    sanitizeError(error, [EMAIL])

    expect(error.actual).toEqual([
      { name: '__clerk_db_jwt', value: '[redacted]' },
      { name: 'Authorization', value: '[redacted]' },
      { name: 'Set-Cookie', value: '[redacted]' },
      { name: 'client_secret', value: '[redacted]' },
      { name: 'x_api_key', value: '[redacted]' },
      { name: 'theme', value: 'dark' },
    ])
  })

  it('#50 AC8：讀屬性出錯時值換成 [unserializable]，其他屬性照常清理，丟出的仍是原本的錯誤', async () => {
    const error = makeAc8Error()

    const rejected = await withSanitizedErrors([EMAIL], async () => {
      throw error
    })().catch((reason: unknown) => reason)

    expect(rejected).toBe(error)
    expect(error.broken).toBe('[unserializable]')
    expect(error.actual).toEqual({ broken: '[unserializable]', url: '/cb' })
    expect(error.detail).toBe('[redacted]')
    expect(error.message).toBe('failed /v1/a')
  })

  it('#50 AC8：cause 的 getter 丟出錯誤時，丟出的仍是原本那個清理過的錯誤', async () => {
    const error = withProperties(new Error(`failed /v1/a?t=1`), { detail: EMAIL })
    Object.defineProperty(error, 'cause', {
      get: () => {
        throw new Error('getter failed')
      },
      configurable: true,
    })

    const rejected = await withSanitizedErrors([EMAIL], async () => {
      throw error
    })().catch((reason: unknown) => reason)

    expect(rejected).toBe(error)
    expect((error.cause as Error).message).toBe('[unserializable]')
    expect(error.detail).toBe('[redacted]')
  })

  it('#50 AC9：清理後 actual、expected、message、stack 仍可寫入', () => {
    for (const error of [makeAc2Error(), makeAc8Error()]) {
      // 只有 getter 的 expected：清理時要換成一般屬性，vitest 之後才寫得進去
      Object.defineProperty(error, 'expected', { get: () => '/v1/e?t=1', configurable: true })
      sanitizeError(error, [EMAIL])

      error.actual = 'new actual'
      error.expected = 'new expected'
      error.message = 'new message'
      error.stack = 'new stack'

      expect(error.actual).toBe('new actual')
      expect(error.expected).toBe('new expected')
      expect(error.message).toBe('new message')
      expect(error.stack).toBe('new stack')
    }
  })

  it('#50 AC13：值是二進位資料時整個換成 [binary]，不保留內容', () => {
    const error = withProperties(new Error('failed'), {
      actual: Buffer.from('/cb?code=SECRET'),
      expected: new Uint8Array([1, 2]),
      response: { body: Buffer.from(EMAIL) },
    })

    sanitizeError(error, [EMAIL])

    expect(error.actual).toBe('[binary]')
    expect(error.expected).toBe('[binary]')
    expect(error.response).toEqual({ body: '[binary]' })
  })

  it('#50 AC12：清理途中寫回 message 失敗時，丟出訊息經過清理的新錯誤', async () => {
    const error = new Error('failed')
    Object.defineProperty(error, 'message', { value: `/cb?code=abc ${EMAIL}`, writable: false, configurable: false })

    const rejected = await withSanitizedErrors([EMAIL], async () => {
      throw error
    })().catch((reason: unknown) => reason)

    expect(rejected).not.toBe(error)
    expect(rejected).toBeInstanceOf(Error)
    const { message } = rejected as Error
    expect(message.startsWith('[e2e] 錯誤清理失敗：')).toBe(true)
    expect(message).not.toContain('code=abc')
    expect(message).not.toContain(EMAIL)
  })

  it('#50 AC12：message 唯讀但可重新定義時，丟出原本的錯誤，message 已清理', async () => {
    const error = new Error('failed')
    Object.defineProperty(error, 'message', { value: `/cb?code=abc ${EMAIL}`, writable: false, configurable: true })

    const rejected = await withSanitizedErrors([EMAIL], async () => {
      throw error
    })().catch((reason: unknown) => reason)

    expect(rejected).toBe(error)
    expect(error.message).toBe('/cb [redacted]')
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
