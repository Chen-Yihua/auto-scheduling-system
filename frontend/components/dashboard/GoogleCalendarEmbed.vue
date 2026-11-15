<script setup lang="ts">
import { computed } from 'vue';

const props = defineProps<{
  calendarIds: string[];
  id: string;
  connect: boolean;
  connecting?: boolean; // 後端正在完成授權
  loading?: boolean; // 這個使用者第一次查詢還沒有結果
  unavailable?: boolean; // 沒有可顯示的行事曆，也不知道連接狀態（例如 Google 或伺服器暫時故障）
  // 遞增時強制 iframe 重新載入，否則看不到新寫入的事件
  reloadToken?: number;
}>();

const calendarUrl = computed(() => {
  const query = props.calendarIds.map((id) => `src=${encodeURIComponent(id)}`).join('&');
  const cacheBust = props.reloadToken ? `&_r=${props.reloadToken}` : '';
  return `https://calendar.google.com/calendar/embed?${query}&ctz=Asia%2FTaipei${cacheBust}`;
});
</script>

<template>
  <UCard>
    <template #header>
      <div class="flex items-center gap-2">
        <UIcon name="i-lucide-calendar" class="w-5 h-5" />
        <span class="text-lg font-semibold text-gray-900 dark:text-white">Google 行事曆</span>
      </div>
    </template>

    <div v-if="connecting" class="flex justify-center items-center py-6">
      <UIcon name="i-lucide-loader" class="animate-spin w-6 h-6 text-primary" />
      <span class="ml-2 text-primary">正在連接 Google Calendar，請稍候…</span>
    </div>

    <div v-else-if="loading">
      <USkeleton class="h-[600px] w-full" />
    </div>

    <div
      v-else-if="unavailable"
      class="text-center text-sm text-gray-500 dark:text-gray-400 py-6"
    >
      Google 行事曆暫時無法載入，請稍後再試
    </div>

    <div v-else-if="connect" class="rounded-lg overflow-hidden">
      <iframe
        :key="reloadToken"
        :src="calendarUrl"
        class="w-full h-[600px] border-0"
        frameborder="0"
        scrolling="no"
      />
    </div>

    <div
      v-else
      class="text-center text-sm text-gray-500 dark:text-gray-400 py-6"
    >
      Google Calendar 未連接或授權已失效，請前往 <strong>帳號設定</strong> 連接。
    </div>
  </UCard>
</template>
