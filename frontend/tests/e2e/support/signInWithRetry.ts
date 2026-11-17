// E2E 登入的重試與診斷：登入期間的整頁導覽會讓 clerk.signIn 失敗（#28），重試並記錄導覽來源。
// 印出的內容與往上丟的錯誤會進公開的 CI log：一律經過 createDiagnosticLogger 輸出、sanitizeError 清理（#46）。
import type { Page } from 'playwright-core'

const NAVIGATION_ERROR = 'Execution context was destroyed'
export const RETRY_MARKER = '[e2e][signin-retry]'
const MAX_ENTRIES = 30

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error)
}

const SEPARATOR = /(\s|["'`<>]|\\[nt])/
const NOT_START_AFTER = /[A-Za-z0-9.~_-]/
const SCHEME = /^[A-Za-z][A-Za-z0-9+.-]*:\/\//
const DOT_PREFIX = /^(?:\.\.?\/)+/
const HOST = /^(?:localhost|[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+)(?::\d+)?\//
const TRAILING = /[.,;:!)\]}]+$/
const RELATIVE_BASE = 'http://relative.invalid'

type CandidateKind = 'scheme' | 'dot' | 'slash' | 'host'

function candidateKind(text: string): CandidateKind | null {
  if (SCHEME.test(text)) return 'scheme'
  if (DOT_PREFIX.test(text)) return 'dot'
  if (text.startsWith('/')) return 'slash'
  if (HOST.test(text)) return 'host'
  return null
}

// 網址只留 host＋path 或 path：query／hash 裡有 handshake token、redirect_url 等
export function toSafeUrl(candidate: string): string {
  const kind = candidateKind(candidate)
  try {
    if (kind === 'scheme') {
      const parsed = new URL(candidate)
      return parsed.host + decodeURI(parsed.pathname)
    }
    if (kind === 'host') {
      // 不加 http:// 的話，localhost:3000/a 的 localhost: 會被當成 scheme
      const parsed = new URL(`http://${candidate}`)
      if (!parsed.search && !parsed.hash) return candidate
      return parsed.host + decodeURI(parsed.pathname)
    }
    if (kind === 'slash' || kind === 'dot') {
      // new URL 會把開頭的 ./、../ 展開成絕對路徑，所以先拿掉、輸出時再接回
      const prefix = kind === 'dot' ? DOT_PREFIX.exec(candidate)![0] : ''
      const parsed = new URL(kind === 'dot' ? `/${candidate.slice(prefix.length)}` : candidate, RELATIVE_BASE)
      // ? 後面沒有內容的保留，`是 /help? 嗎` 這種句子才不會少問號
      if (!parsed.search && !parsed.hash) return candidate
      const path = decodeURI(parsed.pathname)
      return kind === 'dot' ? prefix + path.slice(1) : path
    }
  } catch {
    return '[url]'
  }
  return '[url]'
}

// 導覽與轉址記錄：about:blank、data: 這類不是網址候選的只印 scheme
export function toSafeNavigationUrl(url: string): string {
  if (candidateKind(url)) return toSafeUrl(url)
  return /^[A-Za-z][A-Za-z0-9+.-]*:/.exec(url)?.[0] ?? '[url]'
}

// 從片段裡第一個網址候選到片段結尾都當成網址，偏向多刪不漏刪
function sanitizeUrlsInPart(part: string): string {
  for (let i = 0; i < part.length; i++) {
    if (i > 0 && NOT_START_AFTER.test(part[i - 1]!)) continue
    const rest = part.slice(i)
    if (!candidateKind(rest)) continue
    const trailing = TRAILING.exec(rest)?.[0] ?? ''
    return part.slice(0, i) + toSafeUrl(rest.slice(0, rest.length - trailing.length)) + trailing
  }
  return part
}

export function sanitizeForLog(text: string, secrets: string[]): string {
  let result = text
    .split(SEPARATOR)
    .map((part, index) => (index % 2 === 1 ? part : sanitizeUrlsInPart(part)))
    .join('')
  for (const secret of secrets.filter(Boolean)) {
    result = result.split(secret).join('[redacted]').split(encodeURIComponent(secret)).join('[redacted]')
  }
  return result
    .replace(/[\w.+-]+(@|%40)[\w-]+(\.[\w-]+)+/g, '[email]')
    .replace(/eyJ[\w-]+\.[\w-]+\.[\w-]*/g, '[token]')
}

const SENSITIVE_NAME = /authorization|cookie|password|token|secret|apikey|api_key|jwt|session/i
const REDACTED = '[redacted]'
const UNSERIALIZABLE = '[unserializable]'
const HANDLED_ERROR_KEYS = new Set(['message', 'stack', 'cause'])

function isSensitiveName(name: string): boolean {
  return SENSITIVE_NAME.test(name)
}

// getter 可能丟出錯誤；不接住的話，沒清理完的錯誤會被這個新錯誤取代往上丟
function readProperty(target: object, key: string): unknown {
  try {
    return (target as Record<string, unknown>)[key]
  } catch {
    return UNSERIALIZABLE
  }
}

// 不用賦值：key 是 __proto__ 時會改到複製品的原型
function defineValue(target: object, key: string, value: unknown, enumerable = true) {
  Object.defineProperty(target, key, { value, writable: true, configurable: true, enumerable })
}

// seen 記錄「原本的物件 → 清理結果」，循環參照時複製品保留同樣的參照關係
function sanitizeValue(value: unknown, secrets: string[], seen: Map<object, unknown>): unknown {
  if (typeof value === 'string') return sanitizeForLog(value, secrets)
  if (value === null || typeof value !== 'object') return value
  if (seen.has(value)) return seen.get(value)
  // Error 和 cause 一樣直接清理，不複製：AggregateError.errors 裡仍是同一個錯誤
  if (value instanceof Error) return sanitizeError(value, secrets, seen)
  if (Array.isArray(value)) {
    const copy: unknown[] = []
    seen.set(value, copy)
    for (let i = 0; i < value.length; i++) copy.push(sanitizeValue(readProperty(value, String(i)), secrets, seen))
    return copy
  }
  let keys: string[]
  try {
    keys = Object.getOwnPropertyNames(value)
  } catch {
    return UNSERIALIZABLE
  }
  const copy = {}
  seen.set(value, copy)
  const name = readProperty(value, 'name')
  // Playwright 的 header、cookie 是 { name, value }：機密在 value，名稱在 name
  const redactValue = typeof name === 'string' && isSensitiveName(name)
  for (const key of keys) {
    const redact = isSensitiveName(key) || (key === 'value' && redactValue)
    defineValue(copy, key, redact ? REDACTED : sanitizeValue(readProperty(value, key), secrets, seen))
  }
  return copy
}

// vitest 會把往上丟的錯誤連同 stack、cause、actual／expected 的 diff 與其他自有屬性（含不可列舉的）印進 CI log
export function sanitizeError(error: unknown, secrets: string[], seen = new Map<object, unknown>()): Error {
  if (!(error instanceof Error)) return new Error(sanitizeForLog(String(error), secrets))
  if (seen.has(error)) return error
  seen.set(error, error)
  error.message = sanitizeValue(readProperty(error, 'message'), secrets, seen) as string
  const stack = readProperty(error, 'stack')
  if (stack) error.stack = sanitizeValue(stack, secrets, seen) as string
  const cause = readProperty(error, 'cause')
  if (cause !== undefined) replaceProperty(error, 'cause', sanitizeError(cause, secrets, seen))
  for (const key of Object.getOwnPropertyNames(error)) {
    if (HANDLED_ERROR_KEYS.has(key)) continue
    replaceProperty(error, key, isSensitiveName(key) ? REDACTED : sanitizeValue(readProperty(error, key), secrets, seen))
  }
  return error
}

// 換成一般的可寫屬性：getter 才換得掉，vitest 之後也寫得進 actual、expected
function replaceProperty(error: Error, key: string, value: unknown) {
  const descriptor = Object.getOwnPropertyDescriptor(error, key)
  if (descriptor?.configurable) defineValue(error, key, value, descriptor.enumerable)
  else (error as unknown as Record<string, unknown>)[key] = value
}

// e2e 的測試函式都要包這層：測試函式丟出的錯誤會連同 stack、cause 印進公開的 CI log
export function withSanitizedErrors(secrets: string[], test: () => Promise<void>) {
  return async () => {
    try {
      await test()
    } catch (error) {
      throw sanitizeError(error, secrets)
    }
  }
}

type LogWriter = Pick<Console, 'info' | 'warn' | 'error'>

export function createDiagnosticLogger(options: { secrets: string[]; write?: LogWriter }) {
  const write = options.write ?? console
  const clean = (text: string) => sanitizeForLog(text, options.secrets)
  return {
    info: (text: string) => write.info(clean(text)),
    warn: (text: string) => write.warn(clean(text)),
    error: (text: string) => write.error(clean(text)),
  }
}

export type DiagnosticLogger = ReturnType<typeof createDiagnosticLogger>

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
  let retries = 0
  let afterNavigation = false
  for (;;) {
    try {
      if (afterNavigation) {
        await options.waitForReady()
        // 導覽可能發生在 setActive 之後：這時已經登入，再登入會被 Clerk 以 already signed in 拒絕
        if (await options.isSignedIn()) return
        afterNavigation = false
      }
      await options.signIn()
      return
    } catch (error) {
      await options.onError(error)
      const isNavigation = errorMessage(error).includes(NAVIGATION_ERROR)
      if (!isNavigation || retries >= maxRetries) throw error
      retries++
      options.log(
        `${RETRY_MARKER} 第 ${retries}/${maxRetries} 次重試：${sanitizeForLog(errorMessage(error), options.secrets)}`,
      )
      afterNavigation = true
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
      push(navigations, `${elapsed()} ${toSafeNavigationUrl(url)}`)
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
