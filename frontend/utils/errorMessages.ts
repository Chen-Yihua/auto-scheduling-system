// 429 可能來自後端限流（帶 error_code: "RATE_LIMITED"），也可能來自 Cloud Run（沒有 error_code）

// 錯誤物件形狀不一（FetchError、Response 等），只描述會讀到的欄位
type ErrorLike = {
  response?: { status?: number }
  status?: number
  statusCode?: number
  data?: { error_code?: string }
}

function getErrorStatus(error: unknown): number | undefined {
  const err = error as ErrorLike | null | undefined
  return err?.response?.status ?? err?.status ?? err?.statusCode
}

export function getFriendlyErrorTitle(error: unknown, fallbackTitle: string): string {
  const status = getErrorStatus(error)
  const errorCode = (error as ErrorLike | null | undefined)?.data?.error_code

  if (status === 429 || errorCode === 'RATE_LIMITED') {
    return '請求太頻繁，請稍後再試'
  }
  return fallbackTitle
}

// 第三方憑證失效且沒有舊資料可退時回 401，要請使用者重新連結
export function isAuthError(error: unknown): boolean {
  return getErrorStatus(error) === 401
}

// 還沒連結帳號時回 400，這是正常狀態，不該顯示成錯誤
export function isNotLinkedError(error: unknown): boolean {
  return getErrorStatus(error) === 400
}

// 新增綁定時，該平台已經綁定過（例如另一個分頁已經綁好）會回 409
export function isAlreadyLinkedError(error: unknown): boolean {
  return getErrorStatus(error) === 409
}

// 確認排程時建議已過期或已確認過會回 409，要重新產生建議
export function isSuggestionExpiredError(error: unknown): boolean {
  return getErrorStatus(error) === 409
}
