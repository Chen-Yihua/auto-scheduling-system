import { ref } from 'vue'
import { useAuth } from '@clerk/vue'
import { createSharedComposable } from '@vueuse/core'
import type { SchedulableTask } from '@/types/schedulableTask'
import { getFriendlyErrorTitle } from '@/utils/errorMessages'

// 共用狀態：任務列表和排程精靈要看到同一份清單
function useSchedulableTasksImpl() {
  const toast = useToast()
  const config = useRuntimeConfig()
  const { getToken } = useAuth()
  const BASE_URL = config.public.apiBaseUrl

  const loading = ref(true)
  const tasks = ref<SchedulableTask[]>([])

  const fetchSchedulableTasks = async () => {
    loading.value = true
    try {
      const token = await getToken.value()
      if (!token) throw new Error('找不到 JWT')

      tasks.value = await $fetch<SchedulableTask[]>(`${BASE_URL}/schedule/tasks`, {
        method: 'GET',
        headers: { Authorization: `Bearer ${token}` },
      })
    } catch (error) {
      console.error(error)
      toast.add({
        title: getFriendlyErrorTitle(error, '任務列表載入失敗'),
        color: 'error',
        icon: 'i-lucide-x',
      })
    } finally {
      loading.value = false
    }
  }

  // 樂觀更新，失敗時重新抓取以和後端同步
  const toggleDone = async (task: SchedulableTask) => {
    const nextDone = task.status !== 'Done'
    const previousStatus = task.status
    task.status = nextDone ? 'Done' : 'To Do'
    try {
      const token = await getToken.value()
      if (!token) throw new Error('找不到 JWT')

      await $fetch(`${BASE_URL}/schedule/tasks/done`, {
        method: 'PATCH',
        body: { task_id: task.id, done: nextDone },
        headers: { Authorization: `Bearer ${token}` },
      })
    } catch (error) {
      task.status = previousStatus
      toast.add({
        title: getFriendlyErrorTitle(error, '更新完成狀態失敗'),
        color: 'error',
        icon: 'i-lucide-x',
      })
    }
  }

  return {
    loading,
    tasks,
    fetchSchedulableTasks,
    toggleDone,
  }
}

export const useSchedulableTasks = createSharedComposable(useSchedulableTasksImpl)
