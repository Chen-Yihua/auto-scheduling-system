import { useAuth } from '@clerk/vue';
import { watch } from 'vue';
import { createSharedComposable } from '@vueuse/core';
import type { CalendarListEntry } from '@/types/google';
import { describeError, getFriendlyErrorTitle, isAuthError, isNotLinkedError, logApiError } from '@/utils/errorMessages';
import { useGoogleCalendarAuth } from '@/composables/useGoogleCalendarAuth';

// 共用狀態：確認排程後要讓 GoogleCalendarEmbed 重新整理 iframe
const useGoogleCalendarImpl = () => {
  const toast = useToast();
  const config = useRuntimeConfig();
  const { getToken, isLoaded, userId } = useAuth();
  const { connectedCount, reauthToast } = useGoogleCalendarAuth();

  const BASE_URL = config.public.apiBaseUrl;

  // 帳號設定的「已連接」標記：狀態檢查說已連接，而且沒有遇到要重新連接的錯誤
  const isConnected = ref(false);
  // 後端回 REAUTH_REQUIRED：token 不能用，要重新連接，卡片不能顯示成「尚未連接」
  const needsReconnect = ref(false);
  // 沒有可顯示的行事曆，也不知道是否已連接或要重新連接：卡片顯示「暫時無法載入」
  const unavailable = ref(false);
  const calendars = ref<CalendarListEntry[]>([]);
  const primaryCalendarId = ref('');
  const calendarIds = computed(() => calendars.value.map((c) => c.id));
  const calendarNames = computed(() => calendars.value.map((c) => c.summary));

  // 最近一次已知的結果，只存在記憶體、只屬於 ownerUserId；前置檢查失敗或暫時性錯誤時維持它
  let knownResult: 'loaded' | 'not_linked' | 'reauth' | null = null;
  let ownerUserId: string | null = null;

  const resetKnownResult = () => {
    knownResult = null;
    isConnected.value = false;
    needsReconnect.value = false;
    unavailable.value = false;
    calendars.value = [];
    primaryCalendarId.value = '';
  };

  // 登出或換成另一個使用者時清掉，不顯示前一個使用者的行事曆
  const switchOwner = (current: string | null) => {
    if (current === ownerUserId) return;
    ownerUserId = current;
    resetKnownResult();
  };
  watch(() => userId?.value ?? null, switchOwner);

  const setNotLinked = () => {
    knownResult = 'not_linked';
    isConnected.value = false;
    needsReconnect.value = false;
    unavailable.value = false;
    calendars.value = [];
  };

  // 遞增後當作 iframe 的 key，強制重新載入嵌入的行事曆
  const calendarReloadToken = ref(0);
  const triggerCalendarReload = () => {
    calendarReloadToken.value++;
  };

  // 只有發出時的連接次數還是最新的，結果才寫回狀態：重新連接前發出的請求比較晚回來時，不能蓋掉新的結果
  const loadCalendars = async (isCurrent: () => boolean) => {
    try {
      if (!isLoaded.value) return;
      switchOwner(userId?.value ?? null);

      const token = await getToken.value();
      if (!token) throw new Error('找不到 JWT');

      // 先確認是否已授權，避免呼叫注定失敗的 API；這個檢查失敗時不跳 toast，維持最近一次已知的結果
      let status: { connected: boolean };
      try {
        status = await $fetch<{ connected: boolean }>(`${BASE_URL}/oauth/status`, {
          method: 'GET',
          headers: { Authorization: `Bearer ${token}` },
        });
      } catch (err) {
        logApiError('Google Calendar 授權狀態檢查失敗', err);
        if (!isCurrent()) return;
        if (knownResult === null) unavailable.value = true;
        return;
      }

      if (!isCurrent()) return;
      if (!status.connected) {
        setNotLinked();
        return;
      }

      const res = await $fetch<{ items: CalendarListEntry[] }>(`${BASE_URL}/oauth/calendars`, {
        method: 'GET',
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (!isCurrent()) return;
      knownResult = 'loaded';
      calendars.value = res.items || [];
      isConnected.value = true;
      needsReconnect.value = false;
      unavailable.value = false;

      const primary = calendars.value.find((item) => item.primary);
      primaryCalendarId.value = primary?.id || '';
    } catch (error) {
      if (!isCurrent()) return;
      logApiError('Google Calendar 資料抓取失敗', error);

      // 檢查後到呼叫前授權可能剛好被移除
      if (isNotLinkedError(error)) {
        setNotLinked();
        return;
      }

      if (isAuthError(error)) {
        knownResult = 'reauth';
        isConnected.value = false;
        needsReconnect.value = true;
        unavailable.value = false;
        calendars.value = [];
        toast.add(reauthToast());
        return;
      }

      // 限流、Google 故障等暫時性錯誤：仍是已連接，之前載入成功的清單照常嵌入
      isConnected.value = true;
      needsReconnect.value = false;
      unavailable.value = knownResult !== 'loaded';
      toast.add({
        title: getFriendlyErrorTitle(error, 'Google Calendar 資料暫時無法取得'),
        description: describeError(error, '伺服器暫時連不上 Google 或發生錯誤，請稍後再試一次'),
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
    unavailable,
    fetchGoogleCalendars,
    calendarReloadToken,
    triggerCalendarReload,
  };
};

export const useGoogleCalendar = createSharedComposable(useGoogleCalendarImpl);
