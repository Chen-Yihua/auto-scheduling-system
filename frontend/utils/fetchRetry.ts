// 瀏覽器端呼叫本後端時的重送規則（取代 ofetch 預設只看狀態碼的自動重送）。
// 暫時性錯誤才重送、總共最多 3 次、限流不重送；非本後端的請求不套用，維持 ofetch 的預設。
// 由 plugins/backendFetchRetry.client.ts 掛到 globalThis.$fetch
import type { FetchContext, FetchOptions } from 'ofetch'

export const MAX_ATTEMPTS = 3
const RETRY_DELAYS_MS = [500, 1000]

// 本後端暫時不能用、重送可能成功的原因；UPSTREAM_ERROR 不算：同一個 code 也涵蓋外部的 4xx，而外部的暫時性錯誤後端已經重試過
const TRANSIENT_ERROR_CODES = new Set(['SERVICE_UNAVAILABLE', 'UPSTREAM_TIMEOUT'])
// 沒有 error_code 的 502、503、504 是 Cloud Run 冷啟動或過載
const TRANSIENT_STATUSES_WITHOUT_CODE = new Set([502, 503, 504])

function normalizedBasePath(pathname: string): string {
  return pathname.endsWith('/') ? pathname : `${pathname}/`
}

// 不用 startsWith(apiBaseUrl)：https://api.example.com.evil.com 這類網址會被誤判
export function isBackendRequest(url: string, apiBaseUrl: string, currentHref: string): boolean {
  let request: URL
  let base: URL
  try {
    request = new URL(url, currentHref)
    base = new URL(apiBaseUrl)
  } catch {
    return false
  }
  if (request.origin !== base.origin) return false
  const basePath = normalizedBasePath(base.pathname)
  return request.pathname === basePath.replace(/\/$/, '') || request.pathname.startsWith(basePath)
}

export interface RetryInput {
  method: string
  hasIdempotencyKey: boolean
  // 沒有收到回應時是 undefined
  status?: number
  errorCode?: string
  retryAfter?: string | null
  // 包括剛失敗的這一次，已經送出幾次
  attempt: number
}

export type RetryDecision = { retry: false } | { retry: true; delayMs: number }

function canResend(method: string, hasIdempotencyKey: boolean): boolean {
  if (method === 'GET') return true
  // 帶 Idempotency-Key 的 POST 重送不會重複建立
  return method === 'POST' && hasIdempotencyKey
}

function isTransient(status: number | undefined, errorCode: string | undefined): boolean {
  if (status === undefined) return true
  if (errorCode) return TRANSIENT_ERROR_CODES.has(errorCode)
  return TRANSIENT_STATUSES_WITHOUT_CODE.has(status)
}

function retryAfterMs(value: string | null | undefined): number {
  const trimmed = value?.trim() ?? ''
  return /^\d+$/.test(trimmed) ? Number(trimmed) * 1000 : 0
}

export function decideRetry(input: RetryInput): RetryDecision {
  if (input.attempt >= MAX_ATTEMPTS) return { retry: false }
  if (!canResend(input.method, input.hasIdempotencyKey)) return { retry: false }
  if (!isTransient(input.status, input.errorCode)) return { retry: false }
  const baseDelay = RETRY_DELAYS_MS[input.attempt - 1] ?? 0
  return { retry: true, delayMs: Math.max(baseDelay, retryAfterMs(input.retryAfter)) }
}

// 重送時 ofetch 會把整個 options 複製一份，所以已送出的次數記在 options 上
const ATTEMPT_FIELD = 'backendRetryAttempt'
type RetryOptions = FetchOptions & { [ATTEMPT_FIELD]?: number }

function requestUrl(request: FetchContext['request']): string {
  return typeof request === 'string' ? request : request.url
}

function errorCodeOf(data: unknown): string | undefined {
  // 非 JSON 的回應 _data 是字串，當成沒有 error_code
  if (!data || typeof data !== 'object') return undefined
  const code = (data as { error_code?: unknown }).error_code
  return typeof code === 'string' ? code : undefined
}

// ofetch 的 hook 不能回傳新的回應，只能設定 retry、retryStatusCodes、retryDelay，由 ofetch 在 onError 讀
function applyRetryDecision(context: FetchContext, apiBaseUrl: string, currentHref: () => string): void {
  if (!isBackendRequest(requestUrl(context.request), apiBaseUrl, currentHref())) return
  const options = context.options as RetryOptions
  const attempt = options[ATTEMPT_FIELD] ?? 1
  const decision = decideRetry({
    method: (options.method ?? 'GET').toUpperCase(),
    hasIdempotencyKey: new Headers(options.headers).has('Idempotency-Key'),
    status: context.response?.status,
    errorCode: errorCodeOf(context.response?._data),
    retryAfter: context.response?.headers.get('Retry-After'),
    attempt,
  })
  if (!decision.retry) {
    options.retry = false
    return
  }
  options.retry = 1
  // 沒有收到回應時 ofetch 以 500 判斷要不要重送
  options.retryStatusCodes = [context.response?.status ?? 500]
  options.retryDelay = decision.delayMs
  options[ATTEMPT_FIELD] = attempt + 1
}

// 傳給 $fetch.create；不設 retry、retryStatusCodes、retryDelay 的預設值，非本後端的請求才會維持 ofetch 的預設
export function backendRetryFetchOptions(apiBaseUrl: string, currentHref: () => string): FetchOptions {
  const hook = (context: FetchContext) => applyRetryDecision(context, apiBaseUrl, currentHref)
  return { onRequestError: hook, onResponseError: hook }
}
