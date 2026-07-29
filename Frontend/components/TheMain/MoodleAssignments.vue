<script setup lang="ts">
import { useMoodleAssignments } from '~/composables/useMoodleAssignments';
import { onMounted } from 'vue'
const { moodleAssignments, loading, fetchMoodleAssignments, openMoodleAssignments, hasAccount } = useMoodleAssignments();
onMounted(fetchMoodleAssignments); // 頁面載入時抓取作業資料
</script>


<template>
  <div class="text-xl font-bold mb-4">Moodle 作業</div>
  
  <!-- 尚未綁定 Moodle 帳號 -->
  <div v-if="!hasAccount" class="font-medium">
    尚未綁定 Moodle 帳號，請先設定
  </div>

  <!-- Loading -->
  <div v-else-if="loading" class="flex justify-center items-center">
    <UIcon name="i-lucide-loader" class="animate-spin w-6 h-6 text-primary" />
    <span class="ml-2 text-primary">載入中...</span>
  </div>

  <!-- empty -->
  <template v-else-if="moodleAssignments.length === 0">
    <p>目前沒有未繳作業</p>
  </template>

  <template v-else>
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
      <UCard 
        v-for="item in moodleAssignments"
        @click="openMoodleAssignments(item.assignment_url)"
        class="rounded-lg bg-default ring ring-default divide-y divide-default cursor-pointer hover:shadow-lg transition-transform duration-300 ease-in-out transform scale-100 hover:scale-105"
      >
        <template #header>
          <div class="text-sm font-semibold">課程名稱 : {{ item.course_name }}</div>
        </template>

          <div class="font-medium mb-2">作業標題 : {{ item.assignment_title }}</div>

        <template #footer>
          <div class="text-sm text-gray-500">截止日期 : {{ item.due_date }}</div>
        </template>
      </UCard>
    </div>
  </template>
</template>

