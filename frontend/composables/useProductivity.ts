import { onScopeDispose, ref } from 'vue'
import { useAuth } from '@clerk/vue'
import type { ProductivitySummary } from '@/types/analytics'
import { getFriendlyErrorTitle } from '@/utils/errorMessages'

const AUTO_REFRESH_MS = 60 * 60 * 1000

export function useProductivity() {
  const toast = useToast()
  const config = useRuntimeConfig()
  const { getToken } = useAuth()
  const BASE_URL = config.public.apiBaseUrl

  const loading = ref(false)
  const summary = ref<ProductivitySummary | null>(null)
  const error = ref(false)

  const fetchSummary = async () => {
    loading.value = true
    error.value = false
    try {
      const token = await getToken.value()
      if (!token) throw new Error('找不到 JWT')

      summary.value = await $fetch<ProductivitySummary>(`${BASE_URL}/analytics/productivity`, {
        method: 'GET',
        // 週趨勢依使用者當地時間的週一切分
        query: { timezone: Intl.DateTimeFormat().resolvedOptions().timeZone },
        headers: { Authorization: `Bearer ${token}` },
      })
    } catch (err) {
      console.error(err)
      error.value = true
      toast.add({
        title: getFriendlyErrorTitle(err, '工作效率統計載入失敗'),
        color: 'error',
        icon: 'i-lucide-x',
      })
    } finally {
      loading.value = false
    }
  }

  let refreshTimer: ReturnType<typeof setInterval> | null = null

  const stopAutoRefresh = () => {
    if (refreshTimer === null) return
    clearInterval(refreshTimer)
    refreshTimer = null
  }

  // 載入失敗也不另外重試，等下一次自動更新
  const startAutoRefresh = () => {
    if (refreshTimer !== null) return
    refreshTimer = setInterval(fetchSummary, AUTO_REFRESH_MS)
  }

  onScopeDispose(stopAutoRefresh)

  return { loading, summary, error, fetchSummary, startAutoRefresh, stopAutoRefresh }
}
