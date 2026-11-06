// E2E 登入輔助函式的 unit 測試；tests/e2e/** 不在主 vitest 設定裡，所以放這裡
import { describe, it, expect, vi } from 'vitest'
import { signInWithRetry, createSignInDiagnostics, sanitizeForLog } from '../e2e/support/signInWithRetry'

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

describe('signInWithRetry', () => {
  it('AC1、AC3：第 1 次登入遇到 Execution context was destroyed，等頁面重新載入後重試成功，並印 1 行重試標記', async () => {
    const signIn = vi.fn().mockRejectedValueOnce(NAVIGATION_ERROR).mockResolvedValueOnce(undefined)
    const { lines, waitForReady, run } = setup(signIn)

    await run()

    expect(signIn).toHaveBeenCalledTimes(2)
    expect(waitForReady).toHaveBeenCalledTimes(1)
    const markers = lines.filter((line) => line.startsWith('[e2e][signin-retry]'))
    expect(markers).toHaveLength(1)
    expect(markers[0]).toContain('1/2')
    expect(markers[0]).toContain('Execution context was destroyed')
  })

  it('AC1、AC3：遇到導覽後重新載入時已經是登入狀態（第一次登入其實已完成）→ 成功、不再呼叫 signIn，仍印重試標記', async () => {
    const signIn = vi.fn().mockRejectedValueOnce(NAVIGATION_ERROR)
    const { lines, waitForReady, run } = setup(
      signIn,
      vi.fn(async () => true),
    )

    await run()

    expect(signIn).toHaveBeenCalledTimes(1)
    expect(waitForReady).toHaveBeenCalledTimes(1)
    expect(lines.filter((line) => line.startsWith('[e2e][signin-retry]'))).toHaveLength(1)
  })

  it('AC1、AC3、AC4：重新載入後檢查登入狀態時又遇到導覽 → 算進重試次數、印標記與診斷，再檢查一次已登入就成功', async () => {
    const signIn = vi.fn().mockRejectedValueOnce(NAVIGATION_ERROR)
    const isSignedIn = vi.fn().mockRejectedValueOnce(NAVIGATION_ERROR).mockResolvedValueOnce(true)
    const { lines, onError, run } = setup(signIn, isSignedIn)

    await run()

    expect(signIn).toHaveBeenCalledTimes(1)
    expect(isSignedIn).toHaveBeenCalledTimes(2)
    expect(onError).toHaveBeenCalledTimes(2)
    const markers = lines.filter((line) => line.startsWith('[e2e][signin-retry]'))
    expect(markers).toHaveLength(2)
    expect(markers[1]).toContain('2/2')
  })

  it('AC1、AC3、AC4：重新載入後等待頁面載入時又遇到導覽 → 算進重試次數、印標記與診斷，再等一次後已登入就成功', async () => {
    const signIn = vi.fn().mockRejectedValueOnce(NAVIGATION_ERROR)
    const waitForReady = vi.fn().mockRejectedValueOnce(NAVIGATION_ERROR).mockResolvedValueOnce(undefined)
    const { lines, onError, run } = setup(
      signIn,
      vi.fn(async () => true),
      waitForReady,
    )

    await run()

    expect(signIn).toHaveBeenCalledTimes(1)
    expect(onError).toHaveBeenCalledTimes(2)
    const markers = lines.filter((line) => line.startsWith('[e2e][signin-retry]'))
    expect(markers).toHaveLength(2)
    expect(markers[1]).toContain('2/2')
  })

  it('AC2：連續 3 次都遇到導覽（重試 2 次仍失敗）→ 測試失敗，錯誤訊息保留原本的內容', async () => {
    const signIn = vi.fn().mockRejectedValue(NAVIGATION_ERROR)
    const { lines, onError, run } = setup(signIn)

    await expect(run()).rejects.toThrow(NAVIGATION_ERROR.message)

    expect(signIn).toHaveBeenCalledTimes(3)
    expect(onError).toHaveBeenCalledTimes(3)
    expect(lines.filter((line) => line.startsWith('[e2e][signin-retry]'))).toHaveLength(2)
  })

  it('AC2：其他登入錯誤（例如找不到使用者）不重試，照原本的錯誤失敗', async () => {
    const otherError = new Error(`Failed to sign in with email ${EMAIL}: No user found with email: ${EMAIL}`)
    const signIn = vi.fn().mockRejectedValue(otherError)
    const { lines, waitForReady, onError, run } = setup(signIn)

    await expect(run()).rejects.toBe(otherError)

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
