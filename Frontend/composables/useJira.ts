import { useAuth } from '@clerk/vue'
import type { JiraIssue } from '@/types/jira'
import { getFriendlyErrorTitle, isAuthError } from '@/utils/errorMessages'

export const useJira = () => {
  const toast = useToast()
  const config = useRuntimeConfig()
  const { getToken, isLoaded } = useAuth()
  const BASE_URL = config.public.apiBaseUrl
  const issues = ref<JiraIssue[]>([])
  const domain = ref<string>('')
  const isStale = ref(false)
  const syncedAt = ref<string | null>(null)
  const authError = ref(false)
  const notLinked = ref(false)
  const loading = ref(true)
  const { keys, fetchKeys } = useLinkedAccount()

  const fetchJiraIssues = async () => {
    loading.value = true
    try {
      // 先查有沒有連結 Jira 帳號，還沒連結就不用打第三方 API，
      // 省一次注定會失敗的請求，也不會讓使用者看到「抓取失敗」的錯覺。
      // 這個檢查本身如果失敗（網路／認證問題），不該被誤判成「還沒連結」，
      // 也不能讓整頁的抓取流程卡死在 loading——跟 Moodle 的 checkMoodleAccount 一樣邏輯
      try {
        await fetchKeys()
      } catch (err) {
        console.error('Jira 帳號檢查失敗', err)
        authError.value = isAuthError(err)
        toast.add({
          title: authError.value ? 'Jira 授權已失效' : getFriendlyErrorTitle(err, 'Jira 資料暫時無法取得'),
          description: authError.value
            ? '你的登入憑證可能已過期，請重新登入後再試'
            : '伺服器暫時無法確認你的連結帳號狀態，請稍後再試一次',
          color: 'error',
          icon: 'i-lucide-x',
        })
        return
      }

      const jiraAccount = keys.value.find(k => k.platform === 'jira')
      domain.value = jiraAccount?.domain?.replace(/^https?:\/\//, '') || ''

      if (!jiraAccount?.value) {
        notLinked.value = true
        return
      }
      notLinked.value = false

      try {
        if (!isLoaded.value) return

        const token = await getToken.value()
        const res = await $fetch.raw<JiraIssue[]>(`${BASE_URL}/jira/issues`, {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        })

        // 後端已經把 Jira 原始 API 的巢狀結構拉平成最終顯示格式，這裡不用再轉換一次
        issues.value = res._data ?? []
        isStale.value = res.headers.get('X-Data-Stale') === 'true'
        syncedAt.value = res.headers.get('X-Synced-At')
        authError.value = res.headers.get('X-Auth-Error') === 'true'
      } catch (err) {
        // 走到這裡已經排除「還沒連結帳號」的可能性，是真正的錯誤——
        // 訊息要講清楚：是授權失效要重新連結，還是暫時性問題等等重試就好
        console.error('Jira 抓取失敗', err)
        authError.value = isAuthError(err)
        toast.add({
          title: authError.value ? 'Jira 授權已失效' : getFriendlyErrorTitle(err, 'Jira 資料暫時無法取得'),
          description: authError.value
            ? '你的 Jira 連結帳號可能已過期或被撤銷，請至右上角頭像 → Key 分頁重新連結'
            : '伺服器暫時連不上 Jira 或發生錯誤，請稍後再試一次；如果一直失敗，請確認你的 API Key 是否仍然有效',
          color: 'error',
          icon: 'i-lucide-x',
        })
      }
    } finally {
      loading.value = false
    }
  }

  return { issues, fetchJiraIssues, domain, isStale, syncedAt, authError, notLinked, loading }
}
