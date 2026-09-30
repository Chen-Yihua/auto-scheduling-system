import { ref } from 'vue'
import { useAuth } from '@clerk/vue'
import { createSharedComposable } from '@vueuse/core'
import type { SchedulableTask } from '@/types/schedulableTask'
import { getFriendlyErrorTitle } from '@/utils/errorMessages'

// createSharedComposable：任務列表卡片（TaskForm.vue）跟排程精靈頁面
// （pages/schedule.vue）都要看到同一份「手動任務 + GitHub/Jira/Moodle」統一清單，
// 標記完成或排序精靈存檔後，兩邊都該反映最新狀態，不用各自重抓一次
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

  // 使用者手動標記完成／取消完成。手動任務跟外部平台項目都走同一支端點
  // （見 crud/schedulable_items.py 的 set_done），這裡樂觀更新本地狀態，
  // 失敗再重新整理一次真正的資料，不留下跟後端不同步的假象
  const toggleDone = async (task: SchedulableTask) => {
    const nextDone = task.status !== 'Done'
    const previousStatus = task.status
    task.status = nextDone ? 'Done' : 'To Do'
    try {
      const token = await getToken.value()
      if (!token) throw new Error('找不到 JWT')

      await $fetch(`${BASE_URL}/schedule/tasks/done`, {
        method: 'PUT',
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
