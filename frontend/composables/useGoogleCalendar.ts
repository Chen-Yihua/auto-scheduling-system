import { useAuth } from '@clerk/vue';
import { createSharedComposable } from '@vueuse/core';
import type { CalendarListEntry } from '@/types/google';
import { getFriendlyErrorTitle, isAuthError, isNotLinkedError } from '@/utils/errorMessages';

// 共用狀態：確認排程後要讓 GoogleCalendarEmbed 重新整理 iframe
const useGoogleCalendarImpl = () => {
  const toast = useToast();
  const config = useRuntimeConfig();
  const { getToken, isLoaded } = useAuth();

  const BASE_URL = config.public.apiBaseUrl;

  const isConnected = ref(false);
  const calendars = ref<CalendarListEntry[]>([]);
  const primaryCalendarId = ref('');
  const calendarIds = computed(() => calendars.value.map((c) => c.id));
  const calendarNames = computed(() => calendars.value.map((c) => c.summary));

  // 遞增後當作 iframe 的 key，強制重新載入嵌入的行事曆
  const calendarReloadToken = ref(0);
  const triggerCalendarReload = () => {
    calendarReloadToken.value++;
  };

  const fetchGoogleCalendars = async () => {
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
        isConnected.value = false;
        calendars.value = [];
        return;
      }

      if (!status.connected) {
        isConnected.value = false;
        calendars.value = [];
        return;
      }

      const res = await $fetch<{ items: CalendarListEntry[] }>(`${BASE_URL}/oauth/calendars`, {
        method: 'GET',
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      calendars.value = res.items || [];
      isConnected.value = true;

      const primary = calendars.value.find((item) => item.primary);
      primaryCalendarId.value = primary?.id || '';
    } catch (error) {
      isConnected.value = false;
      calendars.value = [];

      // 檢查後到呼叫前授權可能剛好被移除
      if (isNotLinkedError(error)) return;

      const authFailed = isAuthError(error);
      toast.add({
        title: authFailed ? 'Google Calendar 授權已失效' : getFriendlyErrorTitle(error, 'Google Calendar 資料暫時無法取得'),
        description: authFailed
          ? '你的 Google 授權可能已過期或被撤銷，請重新點擊「連接 Google Calendar」'
          : '伺服器暫時連不上 Google 或發生錯誤，請稍後再試一次',
        color: 'error',
        icon: 'i-lucide-x',
      });
    }
  };

  return {
    calendars,
    calendarIds,
    calendarNames,
    primaryCalendarId,
    isConnected,
    fetchGoogleCalendars,
    calendarReloadToken,
    triggerCalendarReload,
  };
};

export const useGoogleCalendar = createSharedComposable(useGoogleCalendarImpl);
