import { ref } from 'vue';
import { useAuth } from '@clerk/vue';
import type { RemovedCalendarEvent, ResolveRemovedEventsResult } from '@/types/schedule';
import { isAuthError, logApiError } from '@/utils/errorMessages';

export type RemovedEventsQuery = 'ok' | 'reauth' | 'error';
export type RemovedEventsResolution = 'done' | 'failed' | 'reauth';

// 排程精靈「處理已刪除的事件」步驟的資料；不共用，每次進入精靈都重新查
export function useRemovedCalendarEvents() {
  const config = useRuntimeConfig();
  const { getToken } = useAuth();
  const BASE_URL = config.public.apiBaseUrl;

  const items = ref<RemovedCalendarEvent[]>([]);

  async function authHeaders() {
    const token = await getToken.value();
    if (!token) throw new Error('找不到 JWT');
    return { Authorization: `Bearer ${token}` };
  }

  // 失敗時 items 保留上一次的清單
  async function fetchRemovedEvents(): Promise<RemovedEventsQuery> {
    try {
      items.value = await $fetch<RemovedCalendarEvent[]>(`${BASE_URL}/schedule/removed-events`, {
        method: 'GET',
        headers: await authHeaders(),
      });
      return 'ok';
    } catch (error) {
      logApiError('查詢 Google 日曆上被刪除的事件失敗', error);
      return isAuthError(error) ? 'reauth' : 'error';
    }
  }

  // 有任何一項失敗就算失敗：畫面只顯示「處理失敗，請重試」，不細分哪幾項
  async function resolveRemovedEvents(reschedule: string[], remove: string[]): Promise<RemovedEventsResolution> {
    try {
      const res = await $fetch<ResolveRemovedEventsResult>(`${BASE_URL}/schedule/removed-events/resolve`, {
        method: 'POST',
        body: { reschedule, delete: remove },
        headers: await authHeaders(),
      })
      return res.failed.length > 0 ? 'failed' : 'done'
    } catch (error) {
      logApiError('處理 Google 日曆上被刪除的事件失敗', error)
      return isAuthError(error) ? 'reauth' : 'failed'
    }
  }

  return { items, fetchRemovedEvents, resolveRemovedEvents }
}
