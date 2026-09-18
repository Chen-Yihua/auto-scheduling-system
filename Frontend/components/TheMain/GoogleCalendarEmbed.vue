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
  <div class="space-y-4">
    <h2 class="flex items-center gap-2 text-lg font-semibold text-gray-900 dark:text-white">
      <UIcon name="i-lucide-calendar" class="w-5 h-5" />
      Google 行事曆
    </h2>

    <div v-if="connect">
      <div
        class="rounded-lg shadow hover:shadow-lg transition-transform duration-300 ease-in-out transform hover:scale-[1.01] border bg-white dark:bg-gray-900 overflow-hidden"
      >
        <iframe
          :src="calendarUrl"
          class="w-full h-[600px] border-0"
          frameborder="0"
          scrolling="no"
        />
      </div>
    </div>

    <div
      v-else
      class="text-center text-sm text-gray-500 dark:text-gray-400 py-8 px-4 border border-dashed border-gray-300 dark:border-gray-700 rounded-lg"
    >
      尚未連接 Google Calendar，請前往 <strong>帳號設定</strong> 以完成連接。
    </div>
  </div>
</template>
