// 統一判斷「這次失敗是不是被限流／系統過載」，讓使用者看到有意義的訊息，
// 而不是每次失敗都顯示同一句看不出原因的「XXX 抓取失敗」。
//
// 429 狀態碼涵蓋兩種情況：
// 1. 後端自己的限流（rate_limit.py）——回應會帶 { error_code: "RATE_LIMITED" }
// 2. Cloud Run 流量爆掉、instance 數量到頂——Google 基礎設施直接擋下來的 429，
//    不會有我們自訂的 error_code，只能靠狀態碼判斷
export function getFriendlyErrorTitle(error: unknown, fallbackTitle: string): string {
  const err = error as any
  const status = err?.response?.status ?? err?.status ?? err?.statusCode
  const errorCode = err?.data?.error_code

  if (status === 429 || errorCode === 'RATE_LIMITED') {
    return '請求太頻繁，請稍後再試'
  }
  return fallbackTitle
}
