import { onMounted } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { useAuth } from '@clerk/vue';
import { useGoogleCalendarAuth } from '~/composables/useGoogleCalendarAuth';

// 處理 Google 授權完成後導回來的網址（/oauth/callback?code=...）。
// 這個網址跟首頁共用同一個畫面（見 pages/index.vue），所以導回來的第一眼就是完整的首頁，
// 只有行事曆卡片顯示「連接中」；把授權碼交給後端換 token 在背景進行。
export const useGoogleOAuthCallback = () => {
  const toast = useToast();
  const router = useRouter();
  const route = useRoute();
  const { getToken } = useAuth();
  const { connecting, connectedCount } = useGoogleCalendarAuth();

  const BASE_URL = useRuntimeConfig().public.apiBaseUrl;

  const code = route.query.code as string | undefined;
  const error = route.query.error as string | undefined;

  // 不是從 Google 導回來的（一般進首頁），什麼都不用做
  if (route.path !== '/oauth/callback') return;

  // 沒有授權碼也沒有錯誤（例如直接打開這個網址）：沒有事情可做，回首頁
  if (!code && !error) {
    onMounted(() => router.replace('/'));
    return;
  }

  // 在 setup 階段就設好，伺服器端渲染出來的 HTML 裡行事曆卡片就已經是「連接中」，
  // 不用等瀏覽器載入完 JavaScript 才變
  if (code) connecting.value = true;

  onMounted(async () => {
    // 換成 / 是為了讓網址列不再留著一次性的授權碼，按「上一頁」也不會回到這個網址
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

      // 通知首頁的行事曆卡片、帳號設定重新查一次連接狀態
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
