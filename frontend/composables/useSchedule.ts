import { useAuth } from '@clerk/vue'
import { createSharedComposable } from '@vueuse/core'
import type { ScheduleSuggestion, ScheduledTask, UnscheduledTask, ScheduleConfirmResult, SchedulePreferences } from '@/types/schedule'
import { defaultSchedulePreferences } from '@/types/schedule'
import { getFriendlyErrorTitle, isAuthError, isNotLinkedError, isSuggestionExpiredError } from '@/utils/errorMessages'
import { useGoogleCalendar } from '@/composables/useGoogleCalendar'

// 共用狀態：從精靈頁導回首頁時 ScheduleSuggestion 會重新掛載，結果不能消失
function useScheduleImpl() {
  const toast = useToast()
  const config = useRuntimeConfig()
  const { getToken } = useAuth()
  const { triggerCalendarReload } = useGoogleCalendar()

  const BASE_URL = config.public.apiBaseUrl

  // 排程建議由使用者觸發，不會自動抓取，所以預設 false
  const loading = ref(false)
  const scheduled = ref<ScheduledTask[]>([])
  const unscheduled = ref<UnscheduledTask[]>([])
  // 還沒連接 Google Calendar 是正常狀態，顯示提示而不是錯誤
  const notLinked = ref(false)
  const hasFetched = ref(false)
  const confirming = ref(false)

  // preferences 不存資料庫，記下來供確認後或過期時重新產生使用
  const lastPreferences = ref<SchedulePreferences>(defaultSchedulePreferences())

  const fetchScheduleSuggestion = async (preferences?: SchedulePreferences) => {
    if (preferences) lastPreferences.value = preferences
    loading.value = true
    notLinked.value = false
    try {
      const token = await getToken.value()
      if (!token) throw new Error('找不到 JWT')

      const res = await $fetch<ScheduleSuggestion>(`${BASE_URL}/schedule/suggest`, {
        method: 'POST',
        body: lastPreferences.value,
        headers: { Authorization: `Bearer ${token}` },
      })

      scheduled.value = res.scheduled
      unscheduled.value = res.unscheduled
    } catch (error) {
      scheduled.value = []
      unscheduled.value = []

      if (isNotLinkedError(error)) {
        notLinked.value = true
        return
      }

      const authFailed = isAuthError(error)
      toast.add({
        title: authFailed ? 'Google Calendar 授權已失效' : getFriendlyErrorTitle(error, '排程建議產生失敗'),
        description: authFailed
          ? '你的 Google 授權可能已過期或被撤銷，請重新點擊「連接 Google Calendar」'
          : '伺服器暫時發生錯誤，請稍後再試一次',
        color: 'error',
        icon: 'i-lucide-x',
      })
    } finally {
      loading.value = false
      hasFetched.value = true
    }
  }

  // 後端寫入它存的快照，所以不用送內容。結束後重新產生建議以反映最新狀態；
  // 建議過期（409）時直接重新產生，讓使用者看過再確認
  const confirmSchedule = async () => {
    confirming.value = true
    try {
      const token = await getToken.value()
      if (!token) throw new Error('找不到 JWT')

      const res = await $fetch<ScheduleConfirmResult>(`${BASE_URL}/schedule/confirm`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      })

      if (res.failed.length > 0) {
        toast.add({
          title: `${res.confirmed.length} 筆已確認，${res.failed.length} 筆寫入失敗`,
          description: res.failed.map((f) => `${f.title}：${f.reason}`).join('\n'),
          color: res.confirmed.length > 0 ? 'warning' : 'error',
          icon: 'i-lucide-alert-triangle',
        })
      } else if (res.confirmed.length > 0) {
        toast.add({
          title: `已確認 ${res.confirmed.length} 筆排程，寫入 Google Calendar`,
          description: '之後如果要調整時間，請直接到 Google Calendar 修改',
          color: 'success',
          icon: 'i-lucide-calendar-check',
        })
      }

      // 有寫入才需要重新整理嵌入的行事曆
      if (res.confirmed.length > 0) {
        triggerCalendarReload()
      }

      await fetchScheduleSuggestion()
    } catch (error) {
      if (isSuggestionExpiredError(error)) {
        toast.add({
          title: '排程建議已過期',
          description: '已重新產生排程建議，請確認後再按一次確認排程',
          color: 'warning',
          icon: 'i-lucide-refresh-cw',
        })
        await fetchScheduleSuggestion()
        return
      }
      toast.add({
        title: getFriendlyErrorTitle(error, '確認排程失敗'),
        description: '伺服器暫時發生錯誤，請稍後再試一次',
        color: 'error',
        icon: 'i-lucide-x',
      })
    } finally {
      confirming.value = false
    }
  }

  return {
    loading,
    scheduled,
    unscheduled,
    notLinked,
    hasFetched,
    confirming,
    lastPreferences,
    fetchScheduleSuggestion,
    confirmSchedule,
  }
}

export const useSchedule = createSharedComposable(useScheduleImpl)
