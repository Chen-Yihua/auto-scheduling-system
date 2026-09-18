<script setup lang="ts">
import { useMoodleAssignments } from '~/composables/useMoodleAssignments';
import { onMounted } from 'vue'
import StaleDataBanner from './StaleDataBanner.vue'
const { moodleAssignments, loading, fetchMoodleAssignments, openMoodleAssignments, hasAccount, isStale, syncedAt, authError } = useMoodleAssignments();
onMounted(fetchMoodleAssignments); // 頁面載入時抓取作業資料
</script>


<template>
  <h2 class="flex items-center gap-2 text-lg font-semibold text-gray-900 dark:text-white mb-4">
    <UIcon name="custom:moodle" class="w-5 h-5" />
    Moodle 作業
  </h2>
  <StaleDataBanner :stale="isStale" :synced-at="syncedAt" :auth-error="authError" platform-label="Moodle" />

  <!-- 尚未綁定 Moodle 帳號 -->
  <div
    v-if="!hasAccount"
    class="text-center text-sm text-gray-500 dark:text-gray-400 py-8 px-4 border border-dashed border-gray-300 dark:border-gray-700 rounded-lg"
  >
    尚未綁定 Moodle 帳號，請先設定
  </div>

  <!-- Loading -->
  <div v-else-if="loading" class="flex justify-center items-center">
    <UIcon name="i-lucide-loader" class="animate-spin w-6 h-6 text-primary" />
    <span class="ml-2 text-primary">載入中...</span>
  </div>

  <!-- empty -->
  <template v-else-if="moodleAssignments.length === 0">
    <div class="text-center text-sm text-gray-500 dark:text-gray-400 py-8 px-4 border border-dashed border-gray-300 dark:border-gray-700 rounded-lg">
      目前沒有未繳作業
    </div>
  </template>

  <template v-else>
    <div class="grid grid-cols-1 gap-4">
      <UCard 
        v-for="item in moodleAssignments"
        @click="openMoodleAssignments(item.url)"
        class="rounded-lg bg-default ring ring-default divide-y divide-default cursor-pointer hover:shadow-lg transition-transform duration-300 ease-in-out transform scale-100 hover:scale-105"
      >
        <template #header>
          <div class="text-sm font-semibold">課程名稱 : {{ item.course_name }}</div>
        </template>

          <div class="font-medium mb-2">作業標題 : {{ item.title }}</div>

        <template #footer>
          <div class="text-sm text-gray-500">截止日期 : {{ item.due_date }}</div>
        </template>
      </UCard>
    </div>
  </template>
</template>

