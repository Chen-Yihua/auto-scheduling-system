<script setup lang="ts">
import { computed } from 'vue';

const props = defineProps<{
  calendarIds: string[];
  id: string;
  connect: boolean;
  connecting?: boolean; // 後端正在完成授權
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
      尚未連接 Google Calendar，請前往 <strong>帳號設定</strong> 以完成連接。
    </div>
  </UCard>
</template>
