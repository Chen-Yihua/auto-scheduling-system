<script setup lang="ts">
import { useMoodleAssignments } from '~/composables/useMoodleAssignments';
import { onMounted, computed } from 'vue'
import StaleDataBanner from './StaleDataBanner.vue'
// 不給就顯示全部——dashboard 卡片用小數字避免無限拉長，
// /moodle 這個完整清單頁面則不傳
const props = defineProps<{ limit?: number }>()
const { moodleAssignments, loading, fetchMoodleAssignments, openMoodleAssignments, hasAccount, isStale, syncedAt, authError } = useMoodleAssignments();
onMounted(fetchMoodleAssignments); // 頁面載入時抓取作業資料

const displayedAssignments = computed(() =>
  props.limit ? moodleAssignments.value.slice(0, props.limit) : moodleAssignments.value
)
const hasMoreAssignments = computed(() => !!props.limit && moodleAssignments.value.length > props.limit)
</script>


<template>
  <UCard>
    <template #header>
      <div class="flex items-center gap-2">
        <UIcon name="custom:moodle" class="w-5 h-5" />
        <span class="text-lg font-semibold text-gray-900 dark:text-white">Moodle 作業</span>
      </div>
    </template>

    <StaleDataBanner :stale="isStale" :synced-at="syncedAt" :auth-error="authError" platform-label="Moodle" />

    <!-- 尚未綁定 Moodle 帳號 -->
    <div
      v-if="!hasAccount"
      class="text-center text-sm text-gray-500 dark:text-gray-400 py-6"
    >
      尚未綁定 Moodle 帳號，請先設定
    </div>

    <!-- Loading -->
    <div v-else-if="loading" class="flex justify-center items-center py-6">
      <UIcon name="i-lucide-loader" class="animate-spin w-6 h-6 text-primary" />
      <span class="ml-2 text-primary">載入中...</span>
    </div>

    <!-- empty -->
    <div v-else-if="moodleAssignments.length === 0" class="text-center text-sm text-gray-500 dark:text-gray-400 py-6">
      目前沒有未繳作業
    </div>

    <div v-else class="grid grid-cols-1 gap-4">
      <UCard
        v-for="item in displayedAssignments"
        :key="item.url"
        class="rounded-lg bg-default ring ring-default divide-y divide-default cursor-pointer hover:shadow-lg transition-transform duration-300 ease-in-out transform scale-100 hover:scale-105"
        @click="openMoodleAssignments(item.url)"
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

    <template v-if="hasMoreAssignments" #footer>
      <NuxtLink to="/moodle" class="text-sm text-primary hover:underline">
        查看全部（{{ moodleAssignments.length }}）
      </NuxtLink>
    </template>
  </UCard>
</template>

