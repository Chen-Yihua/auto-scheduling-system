<script setup lang="ts">
import { computed } from 'vue'
import type { MoodleAssignment } from '~/types/moodle'
import StaleDataBanner from './StaleDataBanner.vue'
const props = defineProps<{
  assignments: MoodleAssignment[]
  loading: boolean
  isStale?: boolean
  syncedAt?: string | null
  authError?: boolean
  notLinked?: boolean
  // 不給就顯示全部——dashboard 卡片用小數字避免無限拉長，
  // /moodle 這個完整清單頁面則不傳
  limit?: number
}>()

const displayedAssignments = computed(() =>
  props.limit ? props.assignments.slice(0, props.limit) : props.assignments
)
const hasMoreAssignments = computed(() => !!props.limit && props.assignments.length > props.limit)

const openAssignment = (url: string) => {
  window.open(url, '_blank')
}
</script>


<template>
  <UCard>
    <template #header>
      <div class="flex items-center gap-2">
        <UIcon name="custom:moodle" class="w-5 h-5" />
        <span class="text-lg font-semibold text-gray-900 dark:text-white">Moodle 作業</span>
      </div>
    </template>

    <StaleDataBanner :stale="isStale ?? false" :synced-at="syncedAt ?? null" :auth-error="authError ?? false" platform-label="Moodle" />

    <!-- 尚未綁定 Moodle 帳號 -->
    <div
      v-if="notLinked"
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
    <div v-else-if="assignments.length === 0" class="text-center text-sm text-gray-500 dark:text-gray-400 py-6">
      目前沒有未繳作業
    </div>

    <div v-else class="grid grid-cols-1 gap-4">
      <UCard
        v-for="item in displayedAssignments"
        :key="item.url"
        class="rounded-lg bg-default ring ring-default divide-y divide-default cursor-pointer hover:shadow-lg transition-transform duration-300 ease-in-out transform scale-100 hover:scale-105"
        @click="openAssignment(item.url)"
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
        查看全部（{{ assignments.length }}）
      </NuxtLink>
    </template>
  </UCard>
</template>

