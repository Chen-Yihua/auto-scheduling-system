<script setup lang="ts">
import { useRouter, useRoute } from 'vue-router';
import { onMounted } from 'vue';
import { useAuth } from '@clerk/vue';

const toast = useToast();
const router = useRouter();
const route = useRoute();
const { getToken } = useAuth();

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
    router.push('/'); // Redirect to home or show an error message
    return;
  }

  // Handle successful authorization with code
  if (code) {
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

      router.push('/'); // Or show success message
      toast.add({
        title: '成功連接 Google Calendar',
        color: 'success',
        icon: 'i-lucide-check',
      });
    } catch (error) {
      console.error('OAuth callback failed', error);
      router.push('/'); // Or show error message
      toast.add({
        title: '連接 Google Calendar 失敗',
        color: 'error',
        icon: 'i-lucide-x',
      });
    }
  }
});
</script>
