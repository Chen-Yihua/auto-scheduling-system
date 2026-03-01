import { useLinkedAccount } from '@/composables/useLinkedAccount';
import { useAuth } from '@clerk/vue';
import { useRuntimeConfig } from '#imports';
import { transformGitHubItem, transformGitHubItemForSync } from '@/utils/github';
import type { GitHubAPIRawItem , GitHubIssue} from '@/types/github';

export const useGithub = () => {
  const toast = useToast();
  const issues = ref<GitHubIssue[]>([]);

  const config = useRuntimeConfig();
  const BASE_URL = config.public.apiBaseUrl;

  const { keys, fetchKeys } = useLinkedAccount();
  const { getToken } = useAuth();

  const fetchGithubIssues = async () => {
    await fetchKeys();

    try {
      const githubAccount = keys.value.find((k) => k.platform === 'github');
      if (!githubAccount?.value) throw new Error('尚未設定 GitHub Key');

      const githubToken = githubAccount.value;
      const token = await getToken.value();

      const queries = ['involves:@me is:issue', 'involves:@me is:pull-request'];
      const allItems: GitHubAPIRawItem[] = [];

      for (const q of queries) {
        const res = await $fetch<{ items: GitHubAPIRawItem[] }>('https://api.github.com/search/issues', {
          headers: {
            Authorization: `Bearer ${githubToken}`,
            Accept: 'application/vnd.github+json',
          },
          query: { q },
        });

        allItems.push(...res.items);
      }

      issues.value = allItems.map(transformGitHubItem); // 給前端顯示
      const payload = allItems.map(transformGitHubItemForSync); // 給後端儲存

      await $fetch(`${BASE_URL}/github/sync`, {
        method: 'POST',
        body: payload,
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

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
