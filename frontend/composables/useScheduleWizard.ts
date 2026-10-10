import { ref, reactive, computed } from 'vue'
import { useAuth } from '@clerk/vue'
import { createSharedComposable } from '@vueuse/core'
import type { SchedulableTask } from '@/types/schedulableTask'
import type { SchedulePreferences } from '@/types/schedule'
import { defaultSchedulePreferences } from '@/types/schedule'
import { getFriendlyErrorTitle } from '@/utils/errorMessages'

export const PRIORITIES = ['Low', 'Medium', 'High'] as const
export type PriorityKey = (typeof PRIORITIES)[number]

// 欄內順序：有 sort_order 的在前，其餘依 due_date，和後端排程規則一致
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

// 共用狀態：排程精靈頁面和其中的元件要用同一份資料
function useScheduleWizardImpl() {
  const toast = useToast()
  const config = useRuntimeConfig()
  const { getToken } = useAuth()
  const BASE_URL = config.public.apiBaseUrl

  const step = ref<1 | 2>(1)
  const saving = ref(false)
  // 依 priority 分三欄，拖到別欄即改變 priority
  const columns = reactive<Record<PriorityKey, SchedulableTask[]>>({ Low: [], Medium: [], High: [] })

  // 每次執行精靈都重新填，不存進資料庫
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

  // 濾掉還沒填完的時段，否則後端驗證會讓整個請求失敗
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

  // 只排未完成、還沒寫入行事曆的項目
  // 沒有 priority 的項目當成 Medium，否則不屬於任何一欄，會從畫面上消失
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

  function moveTask(fromColumn: PriorityKey, fromIndex: number, toColumn: PriorityKey, toIndex: number) {
    const source = columns[fromColumn]
    if (fromIndex < 0 || fromIndex >= source.length) return
    const [moved] = source.splice(fromIndex, 1) as [SchedulableTask]
    moved.priority = toColumn
    const target = columns[toColumn]
    const clampedIndex = Math.max(0, Math.min(toIndex, target.length))
    target.splice(clampedIndex, 0, moved)
  }

  // 三欄直接串接送出即可：sort_order 只在同 priority 內比較
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

  function updateDueDate(taskId: string, dueDate: string | null) {
    const task = allTasks().find((t) => t.id === taskId)
    if (task) task.due_date = dueDate
  }

  function updateDuration(taskId: string, duration: number | null) {
    const task = allTasks().find((t) => t.id === taskId)
    if (task) task.duration = duration
  }

  // task_id 放 body：Moodle 的 id 是網址，放路徑會被誤判
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
