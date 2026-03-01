import { useAuth } from '@clerk/vue';
import type { CalendarListEntry } from '@/types/google'; // 你可以自行定義這型別

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

      toast.add({
        title: 'Google Calendar 抓取失敗',
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
