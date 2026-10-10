import { onMounted } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { useAuth } from '@clerk/vue';
import { useGoogleCalendarAuth } from '~/composables/useGoogleCalendarAuth';

// 處理 Google 授權後導回的 /oauth/callback。這個頁面和首頁相同，授權碼在背景交給後端換 token
export const useGoogleOAuthCallback = () => {
  const toast = useToast();
  const router = useRouter();
  const route = useRoute();
  const { getToken } = useAuth();
  const { connecting, connectedCount } = useGoogleCalendarAuth();

  const BASE_URL = useRuntimeConfig().public.apiBaseUrl;

  const code = route.query.code as string | undefined;
  const error = route.query.error as string | undefined;

  if (route.path !== '/oauth/callback') return;

  // 例如直接打開這個網址
  if (!code && !error) {
    onMounted(() => router.replace('/'));
    return;
  }

  // 在 setup 設定，SSR 輸出時就是「連接中」
  if (code) connecting.value = true;

  onMounted(async () => {
    // 從網址列移除一次性的授權碼
    router.replace('/');

    if (error) {
      toast.add({
        title: `Google 授權失敗：${error}`,
        color: 'error',
      });
      return;
    }

    try {
      const token = await getToken.value();
      if (!token) throw new Error('找不到 JWT');

      await $fetch(`${BASE_URL}/oauth/callback`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
        },
        body: { code },
      });

      connectedCount.value++;
      toast.add({
        title: '成功連接 Google Calendar',
        color: 'success',
        icon: 'i-lucide-check',
      });
    } catch (err) {
      console.error('OAuth callback failed', err);
      toast.add({
        title: '連接 Google Calendar 失敗',
        color: 'error',
        icon: 'i-lucide-x',
      });
    } finally {
      connecting.value = false;
    }
  });
};
