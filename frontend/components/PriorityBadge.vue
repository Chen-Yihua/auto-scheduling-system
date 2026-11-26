<script setup lang="ts">
import { computed } from 'vue';
import { priorityLabel } from '~/utils/labels';
import { priorityColors } from '~/utils/priorityColor';

const props = defineProps<{ priority: string | null | undefined }>()

const background = computed(() => (props.priority ? priorityColors[props.priority] : undefined) ?? 'var(--ui-bg-elevated)')
</script>

<template>
  <span
    class="inline-flex items-center justify-center min-w-9 rounded-md px-2.5 py-0.5 text-sm font-semibold text-black"
    :style="{ backgroundColor: background }"
  >
    {{ priorityLabel(priority) }}
  </span>
</template>
