import { useAuth } from '@clerk/vue';
import { useRuntimeConfig } from '#imports';
import type { GitHubIssue } from '@/types/github';

// 處理驗證、抓資料、寫入 DB
export const useGithub = () => {
  const toast = useToast();
  const issues = ref<GitHubIssue[]>([]);
  const isStale = ref(false);
  const syncedAt = ref<string | null>(null);

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
    } catch (err) {
      console.error('GitHub 抓取失敗', err);
      toast.add({
        title: 'GitHub 資料抓取失敗',
        color: 'error',
        icon: 'i-lucide-x',
      });
    }
  };

  return { issues, fetchGithubIssues, isStale, syncedAt };
};
