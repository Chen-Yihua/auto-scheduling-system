import { useAuth } from '@clerk/vue';
import type { CalendarListEntry } from '@/types/google'; // 你可以自行定義這型別
import { getFriendlyErrorTitle, isAuthError, isNotLinkedError } from '@/utils/errorMessages';

export const useGoogleCalendar = () => {
  const toast = useToast();
  const config = useRuntimeConfig();
  const { getToken, isLoaded } = useAuth();

  const BASE_URL = config.public.apiBaseUrl;

  const isConnected = ref(false);
  const calendars = ref<CalendarListEntry[]>([]);
  const primaryCalendarId = ref('');
  const calendarIds = computed(() => calendars.value.map((c) => c.id));
  const calendarNames = computed(() => calendars.value.map((c) => c.summary));

  const fetchGoogleCalendars = async () => {
    try {
      if (!isLoaded.value) return;

      const token = await getToken.value();
      if (!token) throw new Error('找不到 JWT');

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

      // 還沒連接 Google Calendar 是正常狀態，畫面上本來就有一顆隨時看得到的
      // 「連接 Google Calendar」按鈕，不用再跳錯誤通知重複提醒
      if (isNotLinkedError(error)) return;

      // 走到這裡是真正的錯誤——訊息要講清楚：是授權失效要重新連接，
      // 還是暫時性問題等等重試就好
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
  };
};
