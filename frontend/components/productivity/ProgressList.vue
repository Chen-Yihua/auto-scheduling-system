<script setup lang="ts">
defineProps<{ items: { key: string; label: string; done: number; total: number }[] }>()
</script>

<template>
  <ul class="space-y-3">
    <li v-for="item in items" :key="item.key">
      <div class="flex justify-between text-sm mb-1">
        <span class="text-gray-900 dark:text-gray-100">{{ item.label }}</span>
        <span class="text-gray-500 dark:text-gray-400 tabular-nums">{{ item.done }} / {{ item.total }}</span>
      </div>
      <div
        role="progressbar"
        :aria-label="`${item.label} 完成進度`"
        :aria-valuenow="item.done"
        :aria-valuemax="item.total"
        class="h-2 rounded-full bg-gray-200 dark:bg-gray-800 overflow-hidden"
      >
        <div
          class="h-full rounded-full bg-[#2a78d6] dark:bg-[#3987e5]"
          :style="{ width: `${(item.done / item.total) * 100}%` }"
        />
      </div>
    </li>
  </ul>
</template>
