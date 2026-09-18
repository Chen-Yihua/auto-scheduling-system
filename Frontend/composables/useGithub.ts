import { useAuth } from '@clerk/vue';
import { useRuntimeConfig } from '#imports';
import type { GitHubIssue } from '@/types/github';
import { getFriendlyErrorTitle, isAuthError, isNotLinkedError } from '@/utils/errorMessages';

// 處理驗證、抓資料、寫入 DB
export const useGithub = () => {
  const toast = useToast();
  const issues = ref<GitHubIssue[]>([]);
  const isStale = ref(false);
  const syncedAt = ref<string | null>(null);
  const authError = ref(false);
  const notLinked = ref(false);

  const config = useRuntimeConfig();
  const BASE_URL = config.public.apiBaseUrl;

  const { getToken } = useAuth();

  const fetchGithubIssues = async () => {
    try {
      const token = await getToken.value();

      const res = await $fetch.raw<GitHubIssue[]>(`${BASE_URL}/github/issues`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      issues.value = res._data ?? [];
      isStale.value = res.headers.get('X-Data-Stale') === 'true';
      syncedAt.value = res.headers.get('X-Synced-At');
      authError.value = res.headers.get('X-Auth-Error') === 'true';
    } catch (err) {
      // 還沒連結 GitHub 帳號是正常狀態（新使用者本來就還沒設定），
      // 不是抓取失敗，不用嚇使用者看到紅色錯誤
      if (isNotLinkedError(err)) {
        notLinked.value = true;
        toast.add({
          title: '尚未連結 GitHub 帳號',
          description: '請點擊右上角頭像 → Key 分頁連結帳號',
          color: 'warning',
          icon: 'i-lucide-info',
        });
        return;
      }

      console.error('GitHub 抓取失敗', err);
      // 後端在 token 失效、且完全沒有快取可退時會回 401；有快取的話後端會正常回 200
      // 加 X-Auth-Error header，不會走到這個 catch
      authError.value = isAuthError(err);
      toast.add({
        title: authError.value
          ? 'GitHub 授權已失效，請重新連結帳號'
          : getFriendlyErrorTitle(err, 'GitHub 資料抓取失敗'),
        color: 'error',
        icon: 'i-lucide-x',
      });
    }
  };

  return { issues, fetchGithubIssues, isStale, syncedAt, authError, notLinked };
};
