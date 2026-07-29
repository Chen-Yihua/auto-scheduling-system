<script setup lang="ts">
import { useUser, useAuth } from '@clerk/vue';

const { getToken } = useAuth();
const token = ref<string | null>(null);

onMounted(async () => {
  token.value = await getToken.value({ template: 'jwt' });
});

const toast = useToast();

const copy = async () => {
  if (token.value) {
    await navigator.clipboard.writeText(token.value);
    toast.add({
      title: 'Token 已複製',
      description: '已複製 JWT Token，可用於 API 測試',
      color: 'success',
    });
  }
};
</script>

<template>
  <div class="flex flex-col items-center justify-center min-h-[70vh] px-6 py-12 space-y-6">
    <div class="text-center space-y-2">
      <h1 class="text-2xl font-bold">開發用 JWT Token</h1>
      <p class="text-gray-500">這個 Token 可用來測試你的 API。</p>
    </div>

    <div v-if="token" class="w-full max-w-2xl space-y-4">
      <UTextarea readonly :value="token" class="w-full text-sm font-mono p-4" autosize />
      <div class="flex justify-end">
        <UButton @click="copy" color="primary" variant="solid"> 複製 Token </UButton>
      </div>
    </div>

    <div v-else>
      <UButton loading>載入中...</UButton>
    </div>
  </div>
</template>
