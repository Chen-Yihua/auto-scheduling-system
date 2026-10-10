<script setup lang="ts">
// 訪客看到的卡片，標題和登入後相同，讓版面不變
defineProps<{
  title: string
  icon: string
  iconClass?: string
  message: string
}>()
</script>

<template>
  <UCard>
    <template #header>
      <div class="flex items-center gap-2">
        <UIcon :name="icon" :class="['w-5 h-5', iconClass]" />
        <span class="text-lg font-semibold text-gray-900 dark:text-white">{{ title }}</span>
      </div>
    </template>

    <div class="text-center text-sm text-gray-500 dark:text-gray-400 py-6">
      {{ message }}
    </div>
  </UCard>
</template>
