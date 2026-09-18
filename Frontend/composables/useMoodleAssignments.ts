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
    if (!isLoaded.value) return;

    // 先查有沒有連結 Moodle 帳號，還沒連結就不用真的觸發爬蟲，
    // 省一次注定會失敗（而且成本很高，要開 headless Chrome）的請求。
    // 這個檢查本身如果失敗（例如網路／授權問題），也不跳 toast——這只是背景
    // 資料的其中一項，失敗了安靜降級成「尚未綁定」的提示就好，不用打斷使用者，
    // 重新整理或等連線恢復自然會抓到正確狀態
    let checkAccount: boolean;
    try {
      checkAccount = await checkMoodleAccount();
    } catch (err) {
      console.error('Moodle 帳號檢查失敗', err);
      hasAccount.value = false;
      return;
    }

    if (!checkAccount) {
      // 還沒連結 Moodle 帳號是正常狀態——不跳通知，
      // 畫面上直接顯示提示文字就好（見 MoodleAssignments.vue 的 hasAccount）
      hasAccount.value = false;
      return;
    }

    hasAccount.value = true;
    loading.value = true;

    try {
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
      // 走到這裡已經排除「還沒連結帳號」的可能性，是真正的錯誤——
      // 訊息要講清楚：是帳密失效要重新連結，還是暫時性問題等等重試就好
      console.error('Moodle 抓取失敗', err);
      authError.value = isAuthError(err);
      toast.add({
        title: authError.value ? 'Moodle 帳號或密碼已失效' : getFriendlyErrorTitle(err, 'Moodle 資料暫時無法取得'),
        description: authError.value
          ? '你的 Moodle 帳號或密碼可能已經變更，請至右上角頭像 → Key 分頁重新輸入'
          : '伺服器暫時連不上 Moodle 或發生錯誤，請稍後再試一次；如果一直失敗，請確認帳號密碼是否仍然正確',
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
