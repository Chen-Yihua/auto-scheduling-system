import { useAuth } from '@clerk/vue'
import { watch } from 'vue'
import { describeError, getFriendlyErrorTitle, isAuthError, isNotLinkedError, logApiError } from '@/utils/errorMessages'
import type { GitHubIssue } from '@/types/github'
import type { JiraIssue } from '@/types/jira'
import type { MoodleAssignment } from '@/types/moodle'

const PLATFORMS = {
  github: {
    label: 'GitHub',
    path: '/github/issues',
    syncPath: '/github/sync',
    authFailedTitle: 'GitHub 授權已失效',
    authFailedDescription: '你的 GitHub 連結帳號可能已過期或被撤銷，請至右上角頭像 → Key 分頁重新連結',
    fetchFailedDescription: '伺服器暫時連不上 GitHub 或發生錯誤，請稍後再試一次；如果一直失敗，請確認你的 GitHub token 是否仍然有效',
  },
  jira: {
    label: 'Jira',
    path: '/jira/issues',
    syncPath: '/jira/sync',
    authFailedTitle: 'Jira 授權已失效',
    authFailedDescription: '你的 Jira 連結帳號可能已過期或被撤銷，請至右上角頭像 → Key 分頁重新連結',
    fetchFailedDescription: '伺服器暫時連不上 Jira 或發生錯誤，請稍後再試一次；如果一直失敗，請確認你的 API Key 是否仍然有效',
  },
  moodle: {
    label: 'Moodle',
    path: '/moodle/assignments',
    syncPath: '/moodle/sync',
    authFailedTitle: 'Moodle 帳號或密碼已失效',
    authFailedDescription: '你的 Moodle 帳號或密碼可能已經變更，請至右上角頭像 → Key 分頁重新輸入',
    fetchFailedDescription: '伺服器暫時連不上 Moodle 或發生錯誤，請稍後再試一次；如果一直失敗，請確認帳號密碼是否仍然正確',
  },
} as const

interface PlatformItemTypes {
  github: GitHubIssue
  jira: JiraIssue
  moodle: MoodleAssignment
}

export type PlatformName = keyof PlatformItemTypes

// 外部平台的項目：打開頁面時讀後端資料庫（fetchItems），按「立即同步」時即時同步（syncNow）；
// 以及 header 回報的狀態（是否舊資料、同步時間、是否需重新連結）
export const usePlatformItems = <P extends PlatformName>(platform: P) => {
  const settings = PLATFORMS[platform]
  const toast = useToast()
  const config = useRuntimeConfig()
  const BASE_URL = config.public.apiBaseUrl
  const { getToken, userId } = useAuth()
  const { keys, fetchKeys } = useLinkedAccount()

  const items = ref<PlatformItemTypes[P][]>([])
  const isStale = ref(false)
  const syncedAt = ref<string | null>(null)
  const authError = ref(false)
  const notLinked = ref(false)
  // 已存的憑證無法讀取（帳號列表的 needs_reauth）：當成已連結，請使用者重新連結
  const needsReauth = ref(false)
  // 帳號檢查失敗而且還沒有已知的結果：顯示「暫時無法載入」，不顯示「尚未綁定」
  const unavailable = ref(false)
  const loading = ref(true)
  const syncing = ref(false)
  // 例如 Jira 要用 domain 組出 issue 連結
  const account = computed(() => keys.value.find(k => k.platform === platform))

  // 最近一次已知的結果只存在記憶體、只屬於 ownerUserId；帳號檢查失敗時維持它
  let hasKnownResult = false
  let ownerUserId: string | null = null

  const reset = () => {
    hasKnownResult = false
    items.value = []
    isStale.value = false
    syncedAt.value = null
    authError.value = false
    notLinked.value = false
    needsReauth.value = false
    unavailable.value = false
  }

  // 登出或換成另一個使用者時清掉，不顯示前一個使用者的清單
  const switchOwner = (current: string | null) => {
    if (current === ownerUserId) return
    ownerUserId = current
    reset()
  }
  watch(() => userId?.value ?? null, switchOwner)

  const applyResponse = (res: { _data?: PlatformItemTypes[P][]; headers: Headers }) => {
    hasKnownResult = true
    items.value = res._data ?? []
    isStale.value = res.headers.get('X-Data-Stale') === 'true'
    syncedAt.value = res.headers.get('X-Synced-At')
    authError.value = res.headers.get('X-Auth-Error') === 'true'
  }

  const handleRequestError = (err: unknown, action: string) => {
    logApiError(`${settings.label} ${action}`, err)
    if (isNotLinkedError(err)) {
      hasKnownResult = true
      notLinked.value = true
      return
    }
    authError.value = isAuthError(err)
    toast.add({
      title: authError.value ? settings.authFailedTitle : getFriendlyErrorTitle(err, `${settings.label} 資料暫時無法取得`),
      description: authError.value ? settings.authFailedDescription : describeError(err, settings.fetchFailedDescription),
      color: 'error',
      icon: 'i-lucide-x',
    })
  }

  const fetchItems = async () => {
    loading.value = true
    switchOwner(userId?.value ?? null)
    try {
      // 先確認是否已連結，避免呼叫注定失敗的 API；這個檢查失敗時不跳 toast，維持最近一次已知的結果
      try {
        await fetchKeys()
      } catch (err) {
        logApiError(`${settings.label} 帳號檢查失敗`, err)
        if (!hasKnownResult) unavailable.value = true
        return
      }
      unavailable.value = false

      if (account.value?.needsReauth) {
        hasKnownResult = true
        notLinked.value = false
        needsReauth.value = true
        items.value = []
        return
      }
      needsReauth.value = false

      if (!account.value?.value) {
        hasKnownResult = true
        notLinked.value = true
        items.value = []
        return
      }
      notLinked.value = false

      try {
        const token = await getToken.value()
        const res = await $fetch.raw<PlatformItemTypes[P][]>(`${BASE_URL}${settings.path}`, {
          headers: { Authorization: `Bearer ${token}` },
        })
        applyResponse(res)
      } catch (err) {
        handleRequestError(err, '抓取失敗')
      }
    } finally {
      loading.value = false
    }
  }

  // 立即同步：後端一律即時向平台抓資料；失敗時後端有舊資料就退回舊資料（isStale）
  const syncNow = async () => {
    syncing.value = true
    switchOwner(userId?.value ?? null)
    try {
      const token = await getToken.value()
      const res = await $fetch.raw<PlatformItemTypes[P][]>(`${BASE_URL}${settings.syncPath}`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      })
      applyResponse(res)
    } catch (err) {
      handleRequestError(err, '同步失敗')
    } finally {
      syncing.value = false
    }
  }

  return { items, account, fetchItems, syncNow, syncing, isStale, syncedAt, authError, notLinked, needsReauth, unavailable, loading }
}
