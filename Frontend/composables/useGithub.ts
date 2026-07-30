import { useAuth } from '@clerk/vue';
import { useRuntimeConfig } from '#imports';
import type { GitHubIssue } from '@/types/github';

// 處理驗證、抓資料、寫入 DB
export const useGithub = () => {
  const toast = useToast();
  const issues = ref<GitHubIssue[]>([]);

  const config = useRuntimeConfig();
  const BASE_URL = config.public.apiBaseUrl;

  const { getToken } = useAuth();

  const fetchGithubIssues = async () => {
    try {
      const token = await getToken.value();

      const res = await $fetch<GitHubIssue[]>(`${BASE_URL}/github/issues`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      issues.value = res;
    } catch (err) {
      console.error('GitHub 抓取失敗', err);
      toast.add({
        title: 'GitHub 資料抓取失敗',
        color: 'error',
        icon: 'i-lucide-x',
      });
    }
  };

  return { issues, fetchGithubIssues };
};
