import { transformJiraItem } from '@/utils/jira'
import { useAuth } from '@clerk/vue'
import type { JiraIssue, JiraAPIRawIssue } from '@/types/jira'
import { getFriendlyErrorTitle } from '@/utils/errorMessages'

export const useJira = () => {
  const toast = useToast()
  const config = useRuntimeConfig()
  const { getToken, isLoaded } = useAuth()
  const BASE_URL = config.public.apiBaseUrl
  const issues = ref<JiraIssue[]>([])
  const domain = ref<string>('')
  const isStale = ref(false)
  const syncedAt = ref<string | null>(null)
  const { keys, fetchKeys } = useLinkedAccount()

  const fetchJiraIssues = async () => {
    await fetchKeys()

    const jiraAccount = keys.value.find(k => k.platform === 'jira')
    domain.value = jiraAccount?.domain?.replace(/^https?:\/\//, '') || ''
    try {
      if (!isLoaded.value) return

      const token = await getToken.value()
      const res = await $fetch.raw<JiraAPIRawIssue[]>(`${BASE_URL}/jira/issues`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      })

      issues.value = (res._data ?? []).map(transformJiraItem)
      isStale.value = res.headers.get('X-Data-Stale') === 'true'
      syncedAt.value = res.headers.get('X-Synced-At')
    } catch (err) {
      console.error('Jira 抓取失敗', err)
      toast.add({
        title: getFriendlyErrorTitle(err, 'Jira 資料抓取失敗'),
        color: 'error',
        icon: 'i-lucide-x',
      })
    }
  }

  return { issues, fetchJiraIssues, domain, isStale, syncedAt }
}
