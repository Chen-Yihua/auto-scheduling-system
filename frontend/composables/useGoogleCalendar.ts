import { useAuth } from '@clerk/vue';
import { watch } from 'vue';
import { createSharedComposable } from '@vueuse/core';
import type { CalendarListEntry } from '@/types/google';
import { isAuthError, isNotLinkedError, logApiError } from '@/utils/errorMessages';
import { useGoogleCalendarAuth } from '@/composables/useGoogleCalendarAuth';

// 這一次查詢的結果；unknown 是不知道有沒有連接（狀態查詢失敗、暫時性錯誤，或結果已經不是最新）
export type GoogleConnectionCheck = 'connected' | 'not_linked' | 'reauth' | 'unknown';

// 共用狀態：確認排程後要讓 GoogleCalendarEmbed 重新整理 iframe
const useGoogleCalendarImpl = () => {
  const config = useRuntimeConfig();
  const { getToken, isLoaded, userId } = useAuth();
  const { connectedCount } = useGoogleCalendarAuth();

  const BASE_URL = config.public.apiBaseUrl;

  // 帳號設定的「已連接」標記：狀態檢查說已連接，而且沒有遇到要重新連接的錯誤
  const isConnected = ref(false);
  // 沒有可顯示的行事曆，也不知道是否已連接或要重新連接：卡片顯示「暫時無法載入」
  const unavailable = ref(false);
  // 這個使用者還沒有任何查詢結果：卡片顯示載入中，不能先顯示成需要連接
  const awaitingFirstResult = ref(true);
  const calendars = ref<CalendarListEntry[]>([]);
  const primaryCalendarId = ref('');
  const calendarIds = computed(() => calendars.value.map((c) => c.id));
  const calendarNames = computed(() => calendars.value.map((c) => c.summary));

  // 最近一次已知的結果，只存在記憶體、只屬於 ownerUserId；前置檢查失敗或暫時性錯誤時維持它
  let knownResult: 'loaded' | 'not_linked' | 'reauth' | null = null;
  let ownerUserId: string | null = null;

  const resetKnownResult = () => {
    knownResult = null;
    awaitingFirstResult.value = true;
    isConnected.value = false;
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

  // 授權剛完成，最近一次的結果已經不準：等重新查詢回來再顯示
  watch(connectedCount, () => {
    awaitingFirstResult.value = true;
  });

  const setNotLinked = () => {
    knownResult = 'not_linked';
    awaitingFirstResult.value = false;
    isConnected.value = false;
    unavailable.value = false;
    calendars.value = [];
  };

  // 遞增後當作 iframe 的 key，強制重新載入嵌入的行事曆
  const calendarReloadToken = ref(0);
  const triggerCalendarReload = () => {
    calendarReloadToken.value++;
  };

  // 只有發出時的連接次數還是最新的，結果才寫回狀態：重新連接前發出的請求比較晚回來時，不能蓋掉新的結果
  const loadCalendars = async (isCurrent: () => boolean): Promise<GoogleConnectionCheck> => {
    try {
      if (!isLoaded.value) return 'unknown';
      switchOwner(userId?.value ?? null);

      const token = await getToken.value();
      if (!token) throw new Error('找不到 JWT');

      // 先確認是否已授權，避免呼叫注定失敗的 API；這個檢查失敗時維持最近一次已知的結果
      let status: { connected: boolean };
      try {
        status = await $fetch<{ connected: boolean }>(`${BASE_URL}/oauth/status`, {
          method: 'GET',
          headers: { Authorization: `Bearer ${token}` },
        });
      } catch (err) {
        logApiError('Google Calendar 授權狀態檢查失敗', err);
        if (!isCurrent()) return 'unknown';
        if (knownResult === null) unavailable.value = true;
        awaitingFirstResult.value = false;
        return 'unknown';
      }

      if (!isCurrent()) return 'unknown';
      if (!status.connected) {
        setNotLinked();
        return 'not_linked';
      }

      const res = await $fetch<{ items: CalendarListEntry[] }>(`${BASE_URL}/oauth/calendars`, {
        method: 'GET',
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (!isCurrent()) return 'unknown';
      knownResult = 'loaded';
      awaitingFirstResult.value = false;
      calendars.value = res.items || [];
      isConnected.value = true;
      unavailable.value = false;

      const primary = calendars.value.find((item) => item.primary);
      primaryCalendarId.value = primary?.id || '';
      return 'connected';
    } catch (error) {
      if (!isCurrent()) return 'unknown';
      logApiError('Google Calendar 資料抓取失敗', error);

      // 檢查後到呼叫前授權可能剛好被移除
      if (isNotLinkedError(error)) {
        setNotLinked();
        return 'not_linked';
      }

      if (isAuthError(error)) {
        knownResult = 'reauth';
        awaitingFirstResult.value = false;
        isConnected.value = false;
        unavailable.value = false;
        calendars.value = [];
        return 'reauth';
      }

      // 限流、Google 故障等暫時性錯誤：仍是已連接，之前載入成功的清單照常嵌入
      awaitingFirstResult.value = false;
      isConnected.value = true;
      unavailable.value = knownResult !== 'loaded';
      return 'unknown';
    }
  };

  // 首頁和帳號設定掛載時都會呼叫；同時進行的呼叫共用一個請求，才不會重複發請求。
  // 重新連接後（連接次數變了）要重新發請求，不能沿用連接前的
  let inFlight: { count: number; promise: Promise<GoogleConnectionCheck> } | null = null;
  const fetchGoogleCalendars = (): Promise<GoogleConnectionCheck> => {
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
    awaitingFirstResult,
    unavailable,
    fetchGoogleCalendars,
    calendarReloadToken,
    triggerCalendarReload,
  };
};

export const useGoogleCalendar = createSharedComposable(useGoogleCalendarImpl);
