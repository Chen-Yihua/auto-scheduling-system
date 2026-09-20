<script setup lang="ts">
import { computed, defineProps } from 'vue';

const props = defineProps<{
  calendarIds: string[]; // 所有calendar ID
  id: string;
  connect: boolean; // 是否已連接Google Calendar
}>();

const calendarUrl = computed(() => {
  const query = props.calendarIds.map((id) => `src=${encodeURIComponent(id)}`).join('&');
  return `https://calendar.google.com/calendar/embed?${query}&ctz=Asia%2FTaipei`;
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

    <div v-if="connect" class="rounded-lg overflow-hidden">
      <iframe
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
