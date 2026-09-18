// composables/useMoodleAssignments.ts
import { ref } from 'vue';
import { useAuth } from '@clerk/vue';
import { useRuntimeConfig } from '#imports';
import { useToast } from '#imports';
import { getFriendlyErrorTitle, isAuthError } from '@/utils/errorMessages';

export const useMoodleAssignments = () => {
  const config = useRuntimeConfig();
  const BASE_URL = config.public.apiBaseUrl;
  const toast = useToast();
  const { isLoaded, getToken } = useAuth();

  const moodleAssignments = ref<any[]>([]);
  const loading = ref(false); // 等待排蟲爬完
  const hasAccount = ref(false); // 是否有 moodle 帳號
  const isStale = ref(false);
  const syncedAt = ref<string | null>(null);
  const authError = ref(false);

  // 檢查帳密
  const checkMoodleAccount = async (): Promise<boolean> => {
    const token = await getToken.value();
    const linkedAccounts = await $fetch<any[]>(`${BASE_URL}/user/linked-accounts/me`, {
        method: 'GET',
        headers: { Authorization: `Bearer ${token}` },
    });
    // 看有沒有 moodle 的帳號
    const moodleAccount = linkedAccounts.find(acc => acc.platform === 'moodle');
    return moodleAccount && moodleAccount.username && moodleAccount.password;
};

  // 取得 Moodle 作業資料
  const fetchMoodleAssignments = async () => {
    try {
      if (!isLoaded.value) return;

    // 檢查是否有 Moodle 帳號
    const checkAccount = await checkMoodleAccount();
    if (!checkAccount) {
        toast.add({
        title: '尚未綁定 Moodle 帳號，請先設定',
        color: 'warning',
        icon: 'i-lucide-alert-triangle',
        });
        return;
    }

    hasAccount.value = checkAccount; // 更新是否有帳號
    loading.value = true;

    const token = await getToken.value();
    const res = await $fetch.raw<any[]>(
    `${BASE_URL}/moodle/assignments`,
    {
        method: 'GET',
        headers: { Authorization: `Bearer ${token}` },
    },
    );
    moodleAssignments.value = res._data ?? [];
    isStale.value = res.headers.get('X-Data-Stale') === 'true';
    syncedAt.value = res.headers.get('X-Synced-At');
    authError.value = res.headers.get('X-Auth-Error') === 'true';
    } catch (err) {
      console.error('Moodle 抓取失敗', err);
      // 後端帳密驗證失敗、且完全沒有快取可退時會回 401；有快取的話後端會正常回 200
      // 加 X-Auth-Error header，不會走到這個 catch
      authError.value = isAuthError(err);
      toast.add({
        title: authError.value
          ? 'Moodle 帳號或密碼已失效，請重新連結帳號'
          : getFriendlyErrorTitle(err, 'Moodle 資料抓取失敗'),
        color: 'error',
        icon: 'i-lucide-x',
      });
    } finally {
      loading.value = false;
    }
  };

  // 開啟 Moodle 作業連結
  const openMoodleAssignments = (url: string) => {
    window.open(url, '_blank');
  };

  return {
    moodleAssignments,
    loading,
    hasAccount,
    isStale,
    syncedAt,
    authError,
    fetchMoodleAssignments,
    openMoodleAssignments,
    checkMoodleAccount
  };
};
