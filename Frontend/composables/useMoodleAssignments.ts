// composables/useMoodleAssignments.ts
import { ref } from 'vue';
import { useAuth } from '@clerk/vue';
import { useRuntimeConfig } from '#imports';
import { useToast } from '#imports';

export const useMoodleAssignments = () => {
  const config = useRuntimeConfig();
  const BASE_URL = config.public.apiBaseUrl;
  const toast = useToast();
  const { isLoaded, getToken } = useAuth();

  const moodleAssignments = ref<any[]>([]);
  const loading = ref(false); // 等待排蟲爬完
  const hasAccount = ref(false); // 是否有 moodle 帳號

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
    const data = await $fetch<any[]>(
    `${BASE_URL}/moodle/assignments`,
    {
        method: 'GET',
        headers: { Authorization: `Bearer ${token}` },
    },
    );
    moodleAssignments.value = data ?? [];
    } catch (err) {
      console.error('Moodle 抓取失敗', err);
      toast.add({
        title: 'Moodle 資料抓取失敗',
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
    fetchMoodleAssignments,
    openMoodleAssignments,
    checkMoodleAccount
  };
};
