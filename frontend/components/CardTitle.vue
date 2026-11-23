<script setup lang="ts">
// 卡片標題：圖示和方框用同一個色系（淺底深圖示）；品牌圖示（GitHub、LeetCode 等）傳 iconClass 保留自己的顏色
defineProps<{
  title: string;
  icon: string;
  iconClass?: string;
}>();
</script>

<template>
  <div class="flex items-center gap-3 min-w-0">
    <span class="size-9 shrink-0 rounded-xl bg-steel-100 flex items-center justify-center">
      <UIcon :name="icon" :class="['size-5', iconClass ?? 'text-steel-700']" />
    </span>
    <h2 class="text-lg font-semibold text-highlighted truncate">{{ title }}</h2>
  </div>
</template>
