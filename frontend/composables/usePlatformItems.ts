import { useAuth } from '@clerk/vue'
import { getFriendlyErrorTitle, isAuthError } from '@/utils/errorMessages'
import type { GitHubIssue } from '@/types/github'
import type { JiraIssue } from '@/types/jira'
import type { MoodleAssignment } from '@/types/moodle'

// 每個外部平台的差異只有 API 路徑跟錯誤訊息，流程都一樣（對應後端的 platforms/）
const PLATFORMS = {
  github: {
    label: 'GitHub',
    path: '/github/issues',
    authFailedTitle: 'GitHub 授權已失效',
    authFailedDescription: '你的 GitHub 連結帳號可能已過期或被撤銷，請至右上角頭像 → Key 分頁重新連結',
    fetchFailedDescription: '伺服器暫時連不上 GitHub 或發生錯誤，請稍後再試一次；如果一直失敗，請確認你的 GitHub token 是否仍然有效',
  },
  jira: {
    label: 'Jira',
    path: '/jira/issues',
    authFailedTitle: 'Jira 授權已失效',
    authFailedDescription: '你的 Jira 連結帳號可能已過期或被撤銷，請至右上角頭像 → Key 分頁重新連結',
    fetchFailedDescription: '伺服器暫時連不上 Jira 或發生錯誤，請稍後再試一次；如果一直失敗，請確認你的 API Key 是否仍然有效',
  },
  moodle: {
    label: 'Moodle',
    path: '/moodle/assignments',
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

// 取得使用者在某個外部平台的項目（GitHub/Jira 的 issue、Moodle 的作業），
// 連同後端用 header 回報的資料狀態：是不是舊資料、上次同步時間、要不要重新連結
export const usePlatformItems = <P extends PlatformName>(platform: P) => {
  const settings = PLATFORMS[platform]
  const toast = useToast()
  const config = useRuntimeConfig()
  const BASE_URL = config.public.apiBaseUrl
  const { getToken } = useAuth()
  const { keys, fetchKeys } = useLinkedAccount()

  const items = ref<PlatformItemTypes[P][]>([])
  const isStale = ref(false)
  const syncedAt = ref<string | null>(null)
  const authError = ref(false)
  const notLinked = ref(false)
  const loading = ref(true)
  // 這個平台的連結帳號（例如 Jira 要用它的 domain 組出 issue 連結）
  const account = computed(() => keys.value.find(k => k.platform === platform))

  const fetchItems = async () => {
    loading.value = true
    try {
      // 先查有沒有連結帳號，還沒連結就不用打第三方 API（Moodle 還要開瀏覽器爬，成本更高），
      // 省一次注定會失敗的請求，也不會讓使用者看到「抓取失敗」的錯覺。
      // 這個檢查本身如果失敗（網路／認證問題），也不跳 toast——這只是背景
      // 資料的其中一項，失敗了安靜降級成「尚未綁定」的提示就好，不用打斷使用者，
      // 重新整理或等連線恢復自然會抓到正確狀態
      try {
        await fetchKeys()
      } catch (err) {
        console.error(`${settings.label} 帳號檢查失敗`, err)
        notLinked.value = true
        return
      }

      if (!account.value?.value) {
        notLinked.value = true
        return
      }
      notLinked.value = false

      try {
        const token = await getToken.value()
        const res = await $fetch.raw<PlatformItemTypes[P][]>(`${BASE_URL}${settings.path}`, {
          headers: { Authorization: `Bearer ${token}` },
        })

        // 後端已經轉成最終顯示格式，這裡不用再轉換一次
        items.value = res._data ?? []
        isStale.value = res.headers.get('X-Data-Stale') === 'true'
        syncedAt.value = res.headers.get('X-Synced-At')
        authError.value = res.headers.get('X-Auth-Error') === 'true'
      } catch (err) {
        // 走到這裡已經排除「還沒連結帳號」的可能性，是真正的錯誤——
        // 訊息要講清楚：是授權失效要重新連結，還是暫時性問題等等重試就好
        console.error(`${settings.label} 抓取失敗`, err)
        authError.value = isAuthError(err)
        toast.add({
          title: authError.value ? settings.authFailedTitle : getFriendlyErrorTitle(err, `${settings.label} 資料暫時無法取得`),
          description: authError.value ? settings.authFailedDescription : settings.fetchFailedDescription,
          color: 'error',
          icon: 'i-lucide-x',
        })
      }
    } finally {
      loading.value = false
    }
  }

  return { items, account, fetchItems, isStale, syncedAt, authError, notLinked, loading }
}
