import { useAuth } from '@clerk/vue';
import { createSharedComposable } from '@vueuse/core';
import type { CalendarListEntry } from '@/types/google';
import { getFriendlyErrorTitle, isAuthError, isNotLinkedError } from '@/utils/errorMessages';
import { useGoogleCalendarAuth } from '@/composables/useGoogleCalendarAuth';

// 共用狀態：確認排程後要讓 GoogleCalendarEmbed 重新整理 iframe
const useGoogleCalendarImpl = () => {
  const toast = useToast();
  const config = useRuntimeConfig();
  const { getToken, isLoaded } = useAuth();
  const { connectedCount, reauthToast } = useGoogleCalendarAuth();

  const BASE_URL = config.public.apiBaseUrl;

  const isConnected = ref(false);
  // 後端回 401：token 不能用，要重新連接，卡片不能顯示成「尚未連接」
  const needsReconnect = ref(false);
  const calendars = ref<CalendarListEntry[]>([]);
  const primaryCalendarId = ref('');
  const calendarIds = computed(() => calendars.value.map((c) => c.id));
  const calendarNames = computed(() => calendars.value.map((c) => c.summary));

  // 遞增後當作 iframe 的 key，強制重新載入嵌入的行事曆
  const calendarReloadToken = ref(0);
  const triggerCalendarReload = () => {
    calendarReloadToken.value++;
  };

  // 只有發出時的連接次數還是最新的，結果才寫回狀態：重新連接前發出的請求比較晚回來時，不能蓋掉新的結果
  const loadCalendars = async (isCurrent: () => boolean) => {
    try {
      if (!isLoaded.value) return;

      const token = await getToken.value();
      if (!token) throw new Error('找不到 JWT');

      // 先確認是否已授權，避免呼叫注定失敗的 API；這個檢查失敗時不跳 toast，顯示成未連接
      let status: { connected: boolean };
      try {
        status = await $fetch<{ connected: boolean }>(`${BASE_URL}/oauth/status`, {
          method: 'GET',
          headers: { Authorization: `Bearer ${token}` },
        });
      } catch (err) {
        console.error('Google Calendar 授權狀態檢查失敗', err);
        if (!isCurrent()) return;
        isConnected.value = false;
        calendars.value = [];
        return;
      }

      if (!isCurrent()) return;
      if (!status.connected) {
        isConnected.value = false;
        needsReconnect.value = false;
        calendars.value = [];
        return;
      }

      const res = await $fetch<{ items: CalendarListEntry[] }>(`${BASE_URL}/oauth/calendars`, {
        method: 'GET',
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (!isCurrent()) return;
      calendars.value = res.items || [];
      isConnected.value = true;
      needsReconnect.value = false;

      const primary = calendars.value.find((item) => item.primary);
      primaryCalendarId.value = primary?.id || '';
    } catch (error) {
      if (!isCurrent()) return;
      isConnected.value = false;
      calendars.value = [];

      // 檢查後到呼叫前授權可能剛好被移除
      if (isNotLinkedError(error)) return;

      if (isAuthError(error)) {
        needsReconnect.value = true;
        toast.add(reauthToast());
        return;
      }
      toast.add({
        title: getFriendlyErrorTitle(error, 'Google Calendar 資料暫時無法取得'),
        description: '伺服器暫時連不上 Google 或發生錯誤，請稍後再試一次',
        color: 'error',
        icon: 'i-lucide-x',
      });
    }
  };

  // 首頁和帳號設定掛載時都會呼叫；同時進行的呼叫共用一個請求，失敗時才不會跳兩個 toast。
  // 重新連接後（連接次數變了）要重新發請求，不能沿用連接前的
  let inFlight: { count: number; promise: Promise<void> } | null = null;
  const fetchGoogleCalendars = (): Promise<void> => {
    const count = connectedCount.value;
    if (inFlight?.count === count) return inFlight.promise;

    const current = {
      count,
      promise: loadCalendars(() => connectedCount.value === count).finally(() => {
        if (inFlight === current) inFlight = null;
      }),
    };
    inFlight = current;
    return current.promise;
  };

  return {
    calendars,
    calendarIds,
    calendarNames,
    primaryCalendarId,
    isConnected,
    needsReconnect,
    fetchGoogleCalendars,
    calendarReloadToken,
    triggerCalendarReload,
  };
};

export const useGoogleCalendar = createSharedComposable(useGoogleCalendarImpl);
