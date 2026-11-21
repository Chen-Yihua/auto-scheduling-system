import { ref } from 'vue';
import { useAuth } from '@clerk/vue';
import { createSharedComposable } from '@vueuse/core';
import type { SchedulableTask } from '@/types/schedulableTask';
import type { RescheduleTasksResult } from '@/types/schedule';
import { describeError, getFriendlyErrorTitle, getErrorDetail, isAuthError, logApiError } from '@/utils/errorMessages';
import type { RescheduleOutcome } from '@/utils/rescheduleToasts';
import { useGoogleCalendar } from '@/composables/useGoogleCalendar';

// 共用狀態：任務列表和排程精靈要看到同一份清單
function useSchedulableTasksImpl() {
  const toast = useToast();
  const config = useRuntimeConfig();
  const { getToken } = useAuth();
  const BASE_URL = config.public.apiBaseUrl;

  const { triggerCalendarReload } = useGoogleCalendar();

  const loading = ref(true);
  // 最近一次載入失敗；今日卡片用它和「沒有任務」分開顯示
  const loadFailed = ref(false);
  const tasks = ref<SchedulableTask[]>([]);

  const fetchSchedulableTasks = async () => {
    loading.value = true;
    loadFailed.value = false;
    try {
      const token = await getToken.value();
      if (!token) throw new Error('找不到 JWT');

      tasks.value = await $fetch<SchedulableTask[]>(`${BASE_URL}/schedule/tasks`, {
        method: 'GET',
        headers: { Authorization: `Bearer ${token}` },
      });
    } catch (error) {
      loadFailed.value = true;
      logApiError('任務列表載入失敗', error);
      toast.add({
        title: getFriendlyErrorTitle(error, '任務列表載入失敗'),
        description: describeError(error),
        color: 'error',
        icon: 'i-lucide-x',
      });
    } finally {
      loading.value = false;
    }
  };

  // 樂觀更新，失敗時重新抓取以和後端同步
  const toggleDone = async (task: SchedulableTask) => {
    const nextDone = task.status !== 'Done';
    const previousStatus = task.status;
    task.status = nextDone ? 'Done' : 'To Do';
    try {
      const token = await getToken.value();
      if (!token) throw new Error('找不到 JWT');

      await $fetch(`${BASE_URL}/schedule/tasks/done`, {
        method: 'PATCH',
        body: { task_id: task.id, done: nextDone },
        headers: { Authorization: `Bearer ${token}` },
      });
    } catch (error) {
      task.status = previousStatus;
      toast.add({
        title: getFriendlyErrorTitle(error, '更新完成狀態失敗'),
        description: describeError(error),
        color: 'error',
        icon: 'i-lucide-x',
      });
    }
  };

  // 不跳通知，結果由呼叫端依情境通知。成功或失敗都重抓清單與首頁日曆：
  // 失敗時已處理成功的任務不會復原，不重抓畫面會和資料庫不一致
  const rescheduleTasks = async (ids: string[]): Promise<RescheduleOutcome> => {
    try {
      const token = await getToken.value();
      if (!token) throw new Error('找不到 JWT');

      const res = await $fetch<RescheduleTasksResult>(`${BASE_URL}/schedule/tasks/reschedule`, {
        method: 'POST',
        body: { task_ids: ids },
        headers: { Authorization: `Bearer ${token}` },
      });
      return { kind: 'success', failed: res.failed };
    } catch (error) {
      logApiError('重新排程失敗', error);
      if (isAuthError(error)) return { kind: 'reauth', failed: [] };
      return { kind: 'error', message: getErrorDetail(error), failed: [] };
    } finally {
      await fetchSchedulableTasks();
      triggerCalendarReload();
    }
  };

  // 外部平台任務的小表單用：儲存截止日期與時長。失敗時跳通知並回傳 false
  const saveTaskFields = async (taskId: string, fields: { due_date: string | null; duration: number | null }) => {
    try {
      const token = await getToken.value();
      if (!token) throw new Error('找不到 JWT');

      const body: Record<string, unknown> = { task_id: taskId };
      if (fields.due_date) body.due_date = fields.due_date;
      if (fields.duration != null) body.duration = fields.duration;
      await $fetch(`${BASE_URL}/schedule/tasks/fields`, {
        method: 'PATCH',
        body,
        headers: { Authorization: `Bearer ${token}` },
      });
      return true;
    } catch (error) {
      logApiError('儲存失敗', error);
      toast.add({
        title: getFriendlyErrorTitle(error, '儲存失敗'),
        description: describeError(error),
        color: 'error',
        icon: 'i-lucide-x',
      });
      return false;
    }
  };

  return {
    loading,
    loadFailed,
    tasks,
    fetchSchedulableTasks,
    toggleDone,
    rescheduleTasks,
    saveTaskFields,
  };
}

export const useSchedulableTasks = createSharedComposable(useSchedulableTasksImpl);
