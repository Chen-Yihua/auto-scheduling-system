import { useAuth } from '@clerk/vue'
import { logApiError } from '@/utils/errorMessages'

// 登入後確認後端有這個使用者，沒有就建立。
// 確認失敗只記 console；確定沒有使用者卻建立失敗時才提示使用者。

type ClerkUserLike = {
  id: string
  primaryEmailAddress?: { emailAddress?: string } | null
  fullName?: string | null
}

// 沒有狀態碼代表連不上伺服器；沒有 error_code（例如 Cloud Run 自己回的）時依狀態碼判斷
function describeCreateFailure(status?: number, errorCode?: string): string {
  if (status === undefined) return '無法連線到伺服器，請確認網路後重新整理頁面'
  if (errorCode) {
    if (errorCode === 'RATE_LIMITED' || errorCode === 'UPSTREAM_RATE_LIMITED') return '請求太頻繁，請稍後再重新整理頁面'
    if (errorCode === 'UNAUTHENTICATED') return '登入狀態驗證失敗，請重新登入後再試'
    if (errorCode === 'SERVICE_UNAVAILABLE') return '資料庫暫時無法使用，請稍後再重新整理頁面'
    return '伺服器發生錯誤，請稍後再重新整理頁面'
  }
  if (status === 429) return '請求太頻繁，請稍後再重新整理頁面'
  if (status === 401 || status === 403) return '登入狀態驗證失敗，請重新登入後再試'
  if (status === 503) return '資料庫暫時無法使用，請稍後再重新整理頁面'
  return '伺服器發生錯誤，請稍後再重新整理頁面'
}

async function readErrorCode(response: Response): Promise<string | undefined> {
  try {
    const body = await response.json()
    return typeof body?.error_code === 'string' ? body.error_code : undefined
  } catch {
    return undefined
  }
}

export const useUserSync = () => {
  const toast = useToast()
  const config = useRuntimeConfig()
  const { getToken } = useAuth()
  const BASE_URL = config.public.apiBaseUrl

  // Clerk 的 user 可能重複觸發，記下已確認的 id 避免重複呼叫；建立失敗的不記，下次會重試
  let syncedUserId: string | null = null
  let inFlight: Promise<void> | null = null

  const notifyCreateFailed = (status?: number, errorCode?: string) => {
    toast.add({
      title: '無法建立你的使用者資料',
      description: describeCreateFailure(status, errorCode),
      color: 'error',
      icon: 'i-lucide-x',
    })
  }

  const run = async (clerkUser: ClerkUserLike) => {
    let token: string | null
    try {
      token = await getToken.value()
    } catch (error) {
      logApiError('取得登入憑證失敗', error)
      return
    }
    const authHeaders = { Authorization: `Bearer ${token}` }

    let meResponse: Response
    try {
      meResponse = await fetch(`${BASE_URL}/users/me`, { method: 'GET', headers: authHeaders })
    } catch (error) {
      logApiError('確認使用者資料失敗', error)
      return
    }
    if (meResponse.ok) {
      syncedUserId = clerkUser.id
      return
    }
    if (meResponse.status !== 404) {
      console.error('確認使用者資料失敗，狀態碼', meResponse.status)
      return
    }

    try {
      const createResponse = await fetch(`${BASE_URL}/users/`, {
        method: 'POST',
        headers: { ...authHeaders, 'Content-Type': 'application/json' },
        body: JSON.stringify({
          clerk_id: clerkUser.id,
          email: clerkUser.primaryEmailAddress?.emailAddress,
          name: clerkUser.fullName,
        }),
      })
      if (createResponse.ok) {
        syncedUserId = clerkUser.id
        return
      }
      const errorCode = await readErrorCode(createResponse)
      // 已註冊：其他分頁已建立，不算失敗
      if (errorCode === 'ALREADY_EXISTS' || (!errorCode && createResponse.status === 409)) {
        syncedUserId = clerkUser.id
        return
      }
      console.error('建立使用者失敗', { status: createResponse.status, error_code: errorCode })
      notifyCreateFailed(createResponse.status, errorCode)
    } catch (error) {
      logApiError('建立使用者失敗', error)
      notifyCreateFailed()
    }
  }

  const ensureUserRecord = (clerkUser: ClerkUserLike): Promise<void> => {
    if (syncedUserId === clerkUser.id) return Promise.resolve()
    if (inFlight) return inFlight // 已經有一輪在跑，不要同時建立兩次
    inFlight = run(clerkUser).finally(() => {
      inFlight = null
    })
    return inFlight
  }

  return { ensureUserRecord }
}
