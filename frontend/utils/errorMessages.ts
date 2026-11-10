// 後端的錯誤回應是 { detail, error_code }，畫面依 error_code 判斷（ADR 0011）；detail 只用來顯示。
// Cloud Run 自己回的回應與網路錯誤沒有 error_code：429 當成限流，其他顯示通用錯誤

// 錯誤物件形狀不一（FetchError、Response 等），只描述會讀到的欄位
type ErrorLike = {
  response?: { status?: number }
  status?: number
  statusCode?: number
  data?: { error_code?: unknown; detail?: unknown }
}

export function getErrorStatus(error: unknown): number | undefined {
  const err = error as ErrorLike | null | undefined
  return err?.response?.status ?? err?.status ?? err?.statusCode
}

export function getErrorCode(error: unknown): string | undefined {
  const code = (error as ErrorLike | null | undefined)?.data?.error_code
  return typeof code === 'string' ? code : undefined
}

const RATE_LIMITED_CODES = new Set(['RATE_LIMITED', 'UPSTREAM_RATE_LIMITED'])

export function isRateLimitedError(error: unknown): boolean {
  const code = getErrorCode(error)
  if (code) return RATE_LIMITED_CODES.has(code)
  return getErrorStatus(error) === 429
}

export function getFriendlyErrorTitle(error: unknown, fallbackTitle: string): string {
  return isRateLimitedError(error) ? '請求太頻繁，請稍後再試' : fallbackTitle
}

// 拿已存的第三方憑證抓資料時被拒、權限不足或憑證無法讀取，要請使用者重新連結
export function isAuthError(error: unknown): boolean {
  return getErrorCode(error) === 'REAUTH_REQUIRED'
}

// 還沒連結帳號；只有有「尚未連接」狀態的畫面把它當成正常狀態
export function isNotLinkedError(error: unknown): boolean {
  return getErrorCode(error) === 'NOT_LINKED'
}

// 新增綁定時該平台已經綁定過（例如另一個分頁已經綁好），或註冊時使用者已存在
export function isAlreadyLinkedError(error: unknown): boolean {
  return getErrorCode(error) === 'ALREADY_EXISTS'
}

// 確認排程時建議已過期或已確認過，要重新產生建議
export function isSuggestionExpiredError(error: unknown): boolean {
  return getErrorCode(error) === 'SUGGESTION_EXPIRED'
}

// 後端回給使用者看的說明（例如是哪一個階段違反限制）；422 的 detail 是陣列，不顯示
export function getErrorDetail(error: unknown): string | undefined {
  const detail = (error as ErrorLike | null | undefined)?.data?.detail
  return typeof detail === 'string' ? detail : undefined
}

// 畫面原本的說明後面附加後端的 detail；限流（標題已說明）與沒有 error_code 的回應只用原本的說明。
// 有專屬畫面的原因（例如 NOT_LINKED）由呼叫端先處理，沒處理的畫面就當成一般錯誤附加 detail
export function describeError(error: unknown, description?: string): string | undefined {
  const code = getErrorCode(error)
  const detail = getErrorDetail(error)
  if (!code || RATE_LIMITED_CODES.has(code) || !detail) return description
  return description ? `${description}\n${detail}` : detail
}

// 不印整個錯誤物件：裡面帶著送出的 request body（憑證）與 Authorization header
export function logApiError(message: string, error: unknown): void {
  console.error(message, { status: getErrorStatus(error), error_code: getErrorCode(error) })
}
