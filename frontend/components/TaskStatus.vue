<script setup lang="ts">
import { computed } from 'vue';
import { taskStatusLabel } from '~/utils/labels';

const props = defineProps<{ status: string }>()

// 完成狀態用圓點＋文字，和旁邊優先級的色塊分開，不會看成同一種東西
const dots: Record<string, string> = {
  'To Do': 'ring-2 ring-inset ring-ash-400',
  'In Progress': 'bg-palette-1',
  Done: 'bg-palette-5',
}

const dot = computed(() => dots[props.status] ?? 'bg-ash-300')
</script>

<template>
  <span class="inline-flex items-center gap-1.5 text-sm text-highlighted whitespace-nowrap">
    <span class="size-2.5 rounded-full shrink-0" :class="dot" aria-hidden="true" />
    {{ taskStatusLabel(status) }}
  </span>
</template>
