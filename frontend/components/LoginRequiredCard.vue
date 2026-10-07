<script setup lang="ts">
// 訪客（還沒登入）看到的卡片：標題列跟登入後的真實卡片一樣，內容區改放一句提示，
// 樣式跟「尚未綁定 XX 帳號」的提示相同，這樣登入前後每張卡片的位置都不會變
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
