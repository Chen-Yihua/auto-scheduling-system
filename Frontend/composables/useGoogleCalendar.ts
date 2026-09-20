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

      // 先查有沒有做過 Google OAuth 授權，還沒授權就不用真的打 Google Calendar API，
      // 省一次注定會失敗的請求，也不會讓使用者看到「抓取失敗」的錯覺。
      // 這個檢查本身如果失敗（網路／認證問題），也不跳 toast——這只是背景
      // 資料的其中一項，失敗了安靜降級成「未連接」的畫面就好，不用打斷使用者，
      // 重新整理或等連線恢復自然會抓到正確狀態
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
        // 還沒做過 OAuth 授權是正常狀態，畫面上本來就有一顆隨時看得到的
        // 「連接 Google Calendar」按鈕，不用打行事曆 API，也不用跳通知
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

      // 保險起見：萬一 /oauth/status 跟實際呼叫之間狀態剛好變化，
      // 還是可能拿到「尚未連接」的 400，這種情況也不用跳錯誤通知
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
