<script setup lang="ts">
// 全站的提醒（尚未連結、要重新連結等）共用同一種外框，語氣和位置才一致
withDefaults(defineProps<{ icon?: string }>(), { icon: 'i-lucide-info' })
</script>

<template>
  <div class="flex items-start gap-3 rounded-xl border border-steel-200 bg-steel-50 px-4 py-3 text-sm text-left">
    <UIcon :name="icon" class="size-5 shrink-0 mt-0.5 text-steel-700" />
    <p class="min-w-0"><slot /></p>
  </div>
</template>
