import { useAuth } from '@clerk/vue'

// 登入是 Clerk 管的，但後端資料庫有自己的 users 集合。
// 使用者第一次登入時後端還不認識他，這裡負責在登入後確認後端有這個使用者，沒有就建立。
//
// 提示的原則：
// - 「確認使用者存在」這一步失敗（網路、伺服器錯誤）只寫 console，不打斷使用者——
//   這是背景檢查，其他資料區塊各自失敗時自己會顯示提示。
// - 已經確定後端沒有這個使用者、卻建立失敗時，一定要讓使用者知道。

type ClerkUserLike = {
  id: string
  primaryEmailAddress?: { emailAddress?: string } | null
  fullName?: string | null
}

// 建立失敗時，依狀態碼給出對使用者有意義的說明（沒有狀態碼代表根本連不上伺服器）
function describeCreateFailure(status?: number): string {
  if (status === undefined) return '無法連線到伺服器，請確認網路後重新整理頁面'
  if (status === 429) return '請求太頻繁，請稍後再重新整理頁面'
  if (status === 401 || status === 403) return '登入狀態驗證失敗，請重新登入後再試'
  if (status === 503) return '資料庫暫時無法使用，請稍後再重新整理頁面'
  return '伺服器發生錯誤，請稍後再重新整理頁面'
}

export const useUserSync = () => {
  const toast = useToast()
  const config = useRuntimeConfig()
  const { getToken } = useAuth()
  const BASE_URL = config.public.apiBaseUrl

  // 已經確認過（或建立成功）的使用者 id：Clerk 的 user 物件在同一次瀏覽中可能重新觸發，
  // 不需要每次都再打一輪後端。建立失敗的不記，下次觸發時會再試一次。
  let syncedUserId: string | null = null
  let inFlight: Promise<void> | null = null

  const notifyCreateFailed = (status?: number) => {
    toast.add({
      title: '無法建立你的使用者資料',
      description: describeCreateFailure(status),
      color: 'error',
      icon: 'i-lucide-x',
    })
  }

  const run = async (clerkUser: ClerkUserLike) => {
    let token: string | null
    try {
      token = await getToken.value()
    } catch (error) {
      console.error('取得登入憑證失敗', error)
      return
    }
    const authHeaders = { Authorization: `Bearer ${token}` }

    // 1. 確認後端有沒有這個使用者
    let meResponse: Response
    try {
      meResponse = await fetch(`${BASE_URL}/users/me`, { method: 'GET', headers: authHeaders })
    } catch (error) {
      console.error('確認使用者資料失敗', error)
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

    // 2. 後端確定沒有這個使用者：建立
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
      // 409 代表使用者已經存在（例如另一個分頁剛好先建好了），目的已達成，不算失敗
      if (createResponse.ok || createResponse.status === 409) {
        syncedUserId = clerkUser.id
        return
      }
      console.error('建立使用者失敗，狀態碼', createResponse.status)
      notifyCreateFailed(createResponse.status)
    } catch (error) {
      console.error('建立使用者失敗', error)
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
