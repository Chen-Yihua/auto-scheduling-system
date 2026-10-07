import { ref, reactive, computed } from 'vue'
import { useAuth } from '@clerk/vue'
import { createSharedComposable } from '@vueuse/core'
import type { SchedulableTask } from '@/types/schedulableTask'
import type { SchedulePreferences } from '@/types/schedule'
import { defaultSchedulePreferences } from '@/types/schedule'
import { getFriendlyErrorTitle } from '@/utils/errorMessages'

export const PRIORITIES = ['Low', 'Medium', 'High'] as const
export type PriorityKey = (typeof PRIORITIES)[number]

// 欄內初始順序：sort_order 有值的先排，沒有的退回 due_date，跟後端
// crud/schedule.py 的退路規則一致，只是現在只需要在「同一個 priority 欄」內比較
function defaultOrderWithinColumn(a: SchedulableTask, b: SchedulableTask): number {
  const aOrder = a.sort_order ?? null
  const bOrder = b.sort_order ?? null
  if (aOrder !== null && bOrder !== null) return aOrder - bOrder
  if (aOrder !== null) return -1
  if (bOrder !== null) return 1

  const aDue = a.due_date ? new Date(a.due_date).getTime() : Number.POSITIVE_INFINITY
  const bDue = b.due_date ? new Date(b.due_date).getTime() : Number.POSITIVE_INFINITY
  return aDue - bDue
}

// createSharedComposable：排程精靈是獨立頁面（pages/schedule.vue），
// 頁面元件跟裡面用到這個 composable 的地方要共用同一份狀態
function useScheduleWizardImpl() {
  const toast = useToast()
  const config = useRuntimeConfig()
  const { getToken } = useAuth()
  const BASE_URL = config.public.apiBaseUrl

  const step = ref<1 | 2>(1)
  const saving = ref(false)
  // 三欄：低/中/高，拖到別欄＝當場把那筆項目改成那一欄的 priority。
  // 項目可能來自手動任務，也可能是 GitHub/Jira/Moodle（見 SchedulableTask 的
  // id：組合 id，例如 "manual:abc123"／"github:42"）
  const columns = reactive<Record<PriorityKey, SchedulableTask[]>>({ Low: [], Medium: [], High: [] })

  // 不工作時段／做事風格：使用者每次跑精靈都重新填，不存資料庫（見
  // types/schedule.ts 的 SchedulePreferences），initWizard 時重置成預設值
  const preferences = ref<SchedulePreferences>(defaultSchedulePreferences())

  function addBlockedRecurringRule() {
    preferences.value.blocked_recurring.push({ days_of_week: [], all_day: false, start_time: null, end_time: null })
  }

  function removeBlockedRecurringRule(index: number) {
    preferences.value.blocked_recurring.splice(index, 1)
  }

  function addBlockedException() {
    preferences.value.blocked_exceptions.push({ start: '', end: '' })
  }

  function removeBlockedException(index: number) {
    preferences.value.blocked_exceptions.splice(index, 1)
  }

  // 使用者可能加了一列規律／例外時段但還沒填完（例如剛勾了星期、還沒選時間，
  // 或加了例外時段還沒選日期）就按下一步——這種還沒填完的不該送給後端：
  // 後端的 BlockedException 是必填的 datetime，空字串會被 Pydantic 直接
  // 擋掉變成整個請求失敗，而不是「忽略這一條」。送出前先濾掉不完整的項目，
  // 讓使用者可以先加好幾列慢慢填，而不是每列都要填完才能繼續
  const sanitizedPreferences = computed<SchedulePreferences>(() => ({
    ...preferences.value,
    blocked_recurring: preferences.value.blocked_recurring.filter((rule) =>
      rule.days_of_week.length > 0 && (rule.all_day || (!!rule.start_time && !!rule.end_time))),
    blocked_exceptions: preferences.value.blocked_exceptions.filter((e) => !!e.start && !!e.end),
  }))

  const hasTasks = computed(() => PRIORITIES.some((p) => columns[p].length > 0))

  function allTasks(): SchedulableTask[] {
    return PRIORITIES.flatMap((p) => columns[p])
  }

  // 用使用者目前的統一任務清單（手動任務 + 外部平台項目）初始化精靈。只看
  // 未完成、還沒確認排程的項目——Done 的不需要排程，已經有 calendar_event_id
  // 的代表已經鎖定寫進 Google Calendar 了，不該再讓使用者在這裡重新排序或改動它。
  //
  // 還沒有 priority 的任務（例如剛同步進來、還沒被 LLM 推斷過的外部平台項目）
  // 一律當成 Medium：三欄只有 Low/Medium/High，priority 是 null 的任務如果直接
  // 拿去跟這三個字串比對，會三欄都對不到、整筆憑空消失在精靈畫面上
  // （使用者看到的就是「任務不見了」）——所以這裡要先補一個預設值，再分欄。
  function initWizard(currentTasks: SchedulableTask[]) {
    const pending = currentTasks.filter((t) => t.status !== 'Done' && !t.calendar_event_id)
    const withDefaultPriority = pending.map((t) => ({ ...t, priority: t.priority ?? 'Medium' }))
    for (const p of PRIORITIES) {
      columns[p] = withDefaultPriority
        .filter((t) => t.priority === p)
        .sort(defaultOrderWithinColumn)
    }
    step.value = 1
    preferences.value = defaultSchedulePreferences()
  }

  // 拖拉：同欄內搬動順序，或跨欄搬動（連帶把 priority 改成目標欄）
  function moveTask(fromColumn: PriorityKey, fromIndex: number, toColumn: PriorityKey, toIndex: number) {
    const source = columns[fromColumn]
    if (fromIndex < 0 || fromIndex >= source.length) return
    // 上一行已經確認 fromIndex 在範圍內，splice 一定拿得到一筆
    const [moved] = source.splice(fromIndex, 1) as [SchedulableTask]
    moved.priority = toColumn
    const target = columns[toColumn]
    const clampedIndex = Math.max(0, Math.min(toIndex, target.length))
    target.splice(clampedIndex, 0, moved)
  }

  // Step 1 → Step 2：把三欄拖拉完的結果存回後端（PUT /schedule/reorder，
  // 跨手動任務／外部平台項目統一處理，見 crud/schedulable_items.py）。
  // 三欄攤平串在一起送出即可——sort_order 只在同一個 priority 內比較
  // （見後端 crud/schedule.py 的 sort_key），跨欄串接的順序不影響排程結果
  async function confirmOrder() {
    saving.value = true
    try {
      const token = await getToken.value()
      if (!token) throw new Error('找不到 JWT')

      const items = PRIORITIES.flatMap((p) => columns[p].map((t) => ({ task_id: t.id, priority: p })))
      await $fetch(`${BASE_URL}/schedule/reorder`, {
        method: 'PUT',
        body: { items },
        headers: { Authorization: `Bearer ${token}` },
      })
      step.value = 2
    } catch (err) {
      toast.add({
        title: getFriendlyErrorTitle(err, '儲存排序失敗'),
        description: '伺服器暫時發生錯誤，請稍後再試一次',
        color: 'error',
        icon: 'i-lucide-x',
      })
    } finally {
      saving.value = false
    }
  }

  function backToStep1() {
    step.value = 1
  }

  // Step 2：使用者在這裡只能改 due_date／duration（優先權、標題、描述都鎖定不能改）
  function updateDueDate(taskId: string, dueDate: string | null) {
    const task = allTasks().find((t) => t.id === taskId)
    if (task) task.due_date = dueDate
  }

  function updateDuration(taskId: string, duration: number | null) {
    const task = allTasks().find((t) => t.id === taskId)
    if (task) task.duration = duration
  }

  // 完成：把每筆項目目前的 due_date／duration 存回去（PATCH /schedule/tasks/fields，
  // task_id 放 body——Moodle 的組合 id 是完整網址，放 URL 路徑會被誤判成路徑
  // 分隔或查詢字串），再交給呼叫端（排程建議頁）產生正式的排程建議
  async function finish(onDone: () => void | Promise<void>) {
    saving.value = true
    try {
      const token = await getToken.value()
      if (!token) throw new Error('找不到 JWT')

      await Promise.all(
        allTasks().map((task) => {
          const body: Record<string, unknown> = { task_id: task.id }
          if (task.due_date) body.due_date = task.due_date
          if (task.duration != null) body.duration = task.duration
          return $fetch(`${BASE_URL}/schedule/tasks/fields`, {
            method: 'PATCH',
            body,
            headers: { Authorization: `Bearer ${token}` },
          })
        }),
      )

      await onDone()
    } catch (err) {
      toast.add({
        title: getFriendlyErrorTitle(err, '更新任務失敗'),
        description: '伺服器暫時發生錯誤，請稍後再試一次',
        color: 'error',
        icon: 'i-lucide-x',
      })
    } finally {
      saving.value = false
    }
  }

  return {
    step,
    saving,
    columns,
    hasTasks,
    preferences,
    sanitizedPreferences,
    initWizard,
    moveTask,
    confirmOrder,
    backToStep1,
    updateDueDate,
    updateDuration,
    finish,
    addBlockedRecurringRule,
    removeBlockedRecurringRule,
    addBlockedException,
    removeBlockedException,
  }
}

export const useScheduleWizard = createSharedComposable(useScheduleWizardImpl)
