// E2E 登入的重試與診斷：登入期間的整頁導覽會讓 clerk.signIn 失敗（#28），重試並記錄導覽來源。
// 印出的內容會進公開的 CI log，一律經過 sanitizeForLog。
import type { Page } from 'playwright-core'

const NAVIGATION_ERROR = 'Execution context was destroyed'
export const RETRY_MARKER = '[e2e][signin-retry]'
const MAX_ENTRIES = 30

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error)
}

// 網址只留 host＋path：query／hash 裡有 handshake token、redirect_url 等
function sanitizeUrl(raw: string): string {
  try {
    const parsed = new URL(raw)
    return `${parsed.host}${parsed.pathname}`
  } catch {
    return '[url]'
  }
}

export function sanitizeForLog(text: string, secrets: string[]): string {
  let result = text.replace(/\b[a-z][a-z0-9+.-]*:\/\/[^\s"'<>`)\]]+/gi, sanitizeUrl)
  for (const secret of secrets.filter(Boolean)) {
    result = result.split(secret).join('[redacted]').split(encodeURIComponent(secret)).join('[redacted]')
  }
  return result
    .replace(/[\w.+-]+(@|%40)[\w-]+(\.[\w-]+)+/g, '[email]')
    .replace(/eyJ[\w-]+\.[\w-]+\.[\w-]*/g, '[token]')
}

export async function signInWithRetry(options: {
  signIn: () => Promise<void>
  waitForReady: () => Promise<void>
  isSignedIn: () => Promise<boolean>
  onError: (error: unknown) => Promise<void>
  log: (line: string) => void
  secrets: string[]
  maxRetries?: number
}): Promise<void> {
  const maxRetries = options.maxRetries ?? 2
  for (let attempt = 0; ; attempt++) {
    try {
      await options.signIn()
      return
    } catch (error) {
      await options.onError(error)
      const isNavigation = errorMessage(error).includes(NAVIGATION_ERROR)
      if (!isNavigation || attempt >= maxRetries) throw error
      options.log(
        `${RETRY_MARKER} 第 ${attempt + 1}/${maxRetries} 次重試：${sanitizeForLog(errorMessage(error), options.secrets)}`,
      )
      await options.waitForReady()
      // 導覽可能發生在 setActive 之後：這時已經登入，再登入會被 Clerk 以 already signed in 拒絕
      if (await options.isSignedIn()) return
    }
  }
}

export function createSignInDiagnostics(options: { secrets: string[] }) {
  const clean = (text: string) => sanitizeForLog(text, options.secrets)
  const startedAt = Date.now()
  const elapsed = () => `+${Date.now() - startedAt}ms`
  const navigations: string[] = []
  const consoleErrors: string[] = []
  const pageErrors: string[] = []
  let clerkVersion: string | null = null

  const push = (list: string[], entry: string) => {
    if (list.length < MAX_ENTRIES) list.push(entry)
  }

  return {
    recordNavigation(url: string) {
      push(navigations, `${elapsed()} ${sanitizeUrl(url)}`)
    },
    recordConsoleError(text: string) {
      push(consoleErrors, `${elapsed()} ${clean(text)}`)
    },
    recordPageError(text: string) {
      push(pageErrors, `${elapsed()} ${clean(text)}`)
    },
    setClerkVersion(version: string | null) {
      clerkVersion = version === null ? null : clean(version)
    },
    format(reason: string): string {
      return (
        `[e2e] 登入診斷（${clean(reason)}）：` +
        JSON.stringify({ clerkVersion, navigations, consoleErrors, pageErrors }, null, 2)
      )
    },
  }
}

export type SignInDiagnostics = ReturnType<typeof createSignInDiagnostics>

// 要在 goto 之前呼叫，才記得到開啟頁面時與登入期間的導覽
export function attachSignInDiagnostics(page: Page, diagnostics: SignInDiagnostics) {
  page.on('framenavigated', (frame) => {
    if (frame === page.mainFrame()) diagnostics.recordNavigation(frame.url())
  })
  page.on('console', (message) => {
    if (message.type() === 'error') diagnostics.recordConsoleError(message.text())
  })
  page.on('pageerror', (error) => diagnostics.recordPageError(String(error)))
}

export async function readClerkVersion(page: Page): Promise<string | null> {
  return page
    .evaluate(() => (window as unknown as { Clerk?: { version?: string } }).Clerk?.version ?? null)
    .catch(() => null)
}
