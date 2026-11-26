<script setup lang="ts">
import NoticeBox from '~/components/NoticeBox.vue';
import CardTitle from '~/components/CardTitle.vue';
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
  <UCard :ui="{ root: 'lg:flex-1 lg:flex lg:flex-col', body: 'lg:flex-1 lg:min-h-0 lg:flex lg:flex-col' }">
    <template #header>
      <CardTitle icon="i-lucide-calendar" title="Google 行事曆" />
    </template>

    <div v-if="connecting" class="flex justify-center items-center py-6">
      <UIcon name="i-lucide-loader" class="animate-spin w-6 h-6 text-primary" />
      <span class="ml-2 text-primary">正在連接 Google Calendar，請稍候…</span>
    </div>

    <div v-else-if="loading" class="lg:flex-1 lg:flex lg:flex-col">
      <USkeleton class="h-[600px] w-full lg:h-auto lg:flex-1 lg:min-h-[400px]" />
    </div>

    <div
      v-else-if="unavailable"
      class="text-center text-sm text-muted py-6"
    >
      Google 行事曆暫時無法載入，請稍後再試
    </div>

    <div v-else-if="connect" class="rounded-lg overflow-hidden lg:flex-1 lg:flex lg:flex-col">
      <iframe
        :key="reloadToken"
        :src="calendarUrl"
        class="w-full h-[600px] border-0 lg:h-auto lg:flex-1 lg:min-h-[400px]"
        frameborder="0"
        scrolling="no"
      />
    </div>

    <NoticeBox v-else icon="i-lucide-calendar-x">
      Google Calendar 未連接或授權已失效。點右上角的頭像，在 <strong>金鑰</strong> 頁連接。
    </NoticeBox>
  </UCard>
</template>
