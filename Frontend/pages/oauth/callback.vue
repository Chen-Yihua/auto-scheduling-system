<script setup lang="ts">
import { useRouter, useRoute } from 'vue-router';
import { onMounted } from 'vue';
import { useAuth } from '@clerk/vue';
import { useGoogleCalendarAuth } from '~/composables/useGoogleCalendarAuth';

const toast = useToast();
const router = useRouter();
const route = useRoute();
const { getToken } = useAuth();
const { connecting, connectedCount } = useGoogleCalendarAuth();

const config = useRuntimeConfig();

const BASE_URL = config.public.apiBaseUrl;

onMounted(async () => {
  const code = route.query.code as string | undefined;
  const error = route.query.error as string | undefined;

  if (error) {
    toast.add({
      title: `Google 授權失敗：${error}`,
      color: 'error',
    });
    router.replace('/');
    return;
  }

  // 直接打開這個網址、沒有授權碼：沒有事情可做，回首頁
  if (!code) {
    router.replace('/');
    return;
  }

  // 先回首頁，讓畫面照常顯示，只有行事曆卡片顯示「連接中」（見 GoogleCalendarEmbed.vue）；
  // 換 token 在背景繼續做。用 replace 是為了讓網址列不再留著授權碼，
  // 按「上一頁」也不會回到這個一次性的網址
  connecting.value = true;
  router.replace('/');

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
  } catch (error) {
    console.error('OAuth callback failed', error);
    toast.add({
      title: '連接 Google Calendar 失敗',
      color: 'error',
      icon: 'i-lucide-x',
    });
  } finally {
    connecting.value = false;
  }
});
</script>

<template>
  <!-- 一進來就會馬上導回首頁（見上面 onMounted），這裡只是導頁前那一瞬間的畫面，
  避免出現空白（沒有 template 時 Vue 會警告） -->
  <div class="flex flex-col items-center justify-center py-32 text-gray-500 dark:text-gray-400">
    <UIcon name="i-lucide-loader" class="animate-spin w-8 h-8 text-primary mb-3" />
    <p>正在連接 Google Calendar，請稍候…</p>
  </div>
</template>
