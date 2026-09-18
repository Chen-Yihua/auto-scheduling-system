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
  const { keys, fetchKeys } = useLinkedAccount()

  const fetchJiraIssues = async () => {
    await fetchKeys()

    const jiraAccount = keys.value.find(k => k.platform === 'jira')
    domain.value = jiraAccount?.domain?.replace(/^https?:\/\//, '') || ''
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
      console.error('Jira 抓取失敗', err)
      // 後端在 token 失效、且完全沒有快取可退時會回 401；有快取的話後端會正常回 200
      // 加 X-Auth-Error header，不會走到這個 catch
      authError.value = isAuthError(err)
      toast.add({
        title: authError.value
          ? 'Jira 授權已失效，請重新連結帳號'
          : getFriendlyErrorTitle(err, 'Jira 資料抓取失敗'),
        color: 'error',
        icon: 'i-lucide-x',
      })
    }
  }

  return { issues, fetchJiraIssues, domain, isStale, syncedAt, authError }
}
