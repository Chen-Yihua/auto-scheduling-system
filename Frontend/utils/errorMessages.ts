// 統一判斷「這次失敗是不是被限流／系統過載」，讓使用者看到有意義的訊息，
// 而不是每次失敗都顯示同一句看不出原因的「XXX 抓取失敗」。
//
// 429 狀態碼涵蓋兩種情況：
// 1. 後端自己的限流（rate_limit.py）——回應會帶 { error_code: "RATE_LIMITED" }
// 2. Cloud Run 流量爆掉、instance 數量到頂——Google 基礎設施直接擋下來的 429，
//    不會有我們自訂的 error_code，只能靠狀態碼判斷

// 前端各處拿到的錯誤形狀不一（ofetch 的 FetchError、原生 Response 錯誤、測試裡手寫的物件…），
// 這裡只描述我們會讀的欄位，全部都是選填
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

// 後端在第三方憑證（GitHub token / Jira token / Moodle 帳密）失效、且完全沒有快取
// 可以退回時，會回 401——用來跟一般的暫時性抓取失敗區分，好顯示「請重新連結帳號」
// 而不是「請稍後再試」（重試也沒用）。
export function isAuthError(error: unknown): boolean {
  return getErrorStatus(error) === 401
}

// 後端在使用者「根本還沒連結」這個平台的帳號時（GitHub/Jira/Google Calendar），
// 一律回 400——用來跟真正的抓取失敗區分：這是正常、預期中的狀態（新使用者、
// 或只是還沒設定），不該用跟系統錯誤一樣的紅色警示嚇使用者，只需要溫和地
// 告訴他去哪裡連結。
export function isNotLinkedError(error: unknown): boolean {
  return getErrorStatus(error) === 400
}
