import { useAuth } from '@clerk/vue'
import { createSharedComposable } from '@vueuse/core'
import type { ScheduleSuggestion, ScheduledTask, UnscheduledTask, ScheduleConfirmResult, SchedulePreferences } from '@/types/schedule'
import { defaultSchedulePreferences } from '@/types/schedule'
import { getFriendlyErrorTitle, isAuthError, isNotLinkedError, isSuggestionExpiredError } from '@/utils/errorMessages'
import { useGoogleCalendar } from '@/composables/useGoogleCalendar'

// createSharedComposable：排程精靈現在是獨立頁面（pages/schedule.vue），完成後
// 導回 / 首頁時，ScheduleSuggestion.vue 會是全新掛載的元件實例——如果這裡不是
// 共用狀態，結果會憑空消失，使用者導回來還是看到「尚未產生排程建議」。
function useScheduleImpl() {
  const toast = useToast()
  const config = useRuntimeConfig()
  const { getToken } = useAuth()
  const { triggerCalendarReload } = useGoogleCalendar()

  const BASE_URL = config.public.apiBaseUrl

  // 這張卡片不像其他卡片一樣進頁面就自動抓資料——排程建議是使用者主動觸發
  // 的動作，loading 預設 false，直到使用者按下「產生排程建議」才開始抓
  const loading = ref(false)
  const scheduled = ref<ScheduledTask[]>([])
  const unscheduled = ref<UnscheduledTask[]>([])
  // 還沒連接 Google Calendar 是正常狀態（跟 useGoogleCalendar 的 isConnected 同一個
  // 前提條件），不是排程建議本身出錯，畫面上要顯示「請先連接」而不是紅色錯誤提示
  const notLinked = ref(false)
  // 還沒成功產生過一次結果之前，畫面要顯示「產生排程建議」而不是「重新產生」，
  // 不能讓使用者以為系統已經自動排過一次了
  const hasFetched = ref(false)
  const confirming = ref(false)

  // 排程精靈填的「不工作時段」「做事風格」不存資料庫，每次都要重新帶給後端
  // （見 types/schedule.ts 的 SchedulePreferences）。這裡記住「產生這份建議時
  // 用的是哪一份 preferences」，確認排程後、或建議過期要重新產生時，用同一份
  // 再抓一次——那些地方在 ScheduleSuggestion.vue，跟填 preferences 的精靈頁
  // 不是同一個元件，沒有這份記憶就只能退回預設值
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

  // 使用者按下「確認排程並寫入 Calendar」時呼叫。後端寫入的是產生建議時存下來的
  // 那一份（使用者畫面上看到的），所以這裡不用送任何內容，只送「確認」這個動作。
  // 成功的任務會被鎖定、之後不會再出現在排程建議或拖拉排序精靈裡——所以無論
  // 成功幾筆，結束後都要重新抓一次排程建議，畫面才會反映最新狀態。
  // 建議放太久（超過 30 分鐘）後端會回 409，這時直接幫使用者重新產生一份，
  // 讓他看過新的建議再確認，而不是只丟一個錯誤訊息。
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

      // 真的有寫進 Google Calendar 才需要重新整理嵌入的行事曆 iframe，
      // 全部失敗（res.confirmed 空）的話行事曆內容沒有變，不用刷
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
