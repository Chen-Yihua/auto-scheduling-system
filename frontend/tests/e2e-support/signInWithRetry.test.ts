// E2E 登入輔助函式的 unit 測試；tests/e2e/** 不在主 vitest 設定裡，所以放這裡
import { describe, it, expect, vi } from 'vitest'
import {
  signInWithRetry,
  createSignInDiagnostics,
  createDiagnosticLogger,
  sanitizeError,
  sanitizeForLog,
  toSafeNavigationUrl,
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

// e2e 測試函式最外層會用 sanitizeError 清理往上丟的錯誤
async function rejectionAfterOuterCleanup(run: () => Promise<void>): Promise<unknown> {
  return run().then(
    () => {
      throw new Error('預期登入失敗')
    },
    (error: unknown) => sanitizeError(error, [EMAIL]),
  )
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

    const error = await rejectionAfterOuterCleanup(run)

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

    const error = await rejectionAfterOuterCleanup(run)

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

      const error = await rejectionAfterOuterCleanup(run)

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

    const error = await rejectionAfterOuterCleanup(run)

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

  it('#46 AC2：不是 Error 的值轉成字串清理後包成 Error', () => {
    const result = sanitizeError(`failed /v1/a?t=1 ${EMAIL}`, [EMAIL])

    expect(result).toBeInstanceOf(Error)
    expect(result.message).toBe('failed /v1/a [redacted]')
  })
})
