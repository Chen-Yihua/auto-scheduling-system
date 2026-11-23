<script setup lang="ts">
defineProps<{ items: { key: string; label: string; done: number; total: number; color?: string }[] }>();

const percent = (done: number, total: number) => (total === 0 ? 0 : Math.round((done / total) * 100));
</script>

<template>
  <ul class="space-y-4">
    <li v-for="item in items" :key="item.key">
      <div class="flex items-baseline justify-between gap-2 text-sm mb-1.5">
        <span class="inline-flex items-center gap-2 font-medium text-highlighted">
          <span class="size-3 rounded-sm shrink-0" :style="{ backgroundColor: item.color ?? 'var(--ui-primary)' }" aria-hidden="true" />
          {{ item.label }}
        </span>
        <span class="tabular-nums text-highlighted">
          {{ item.done }} / {{ item.total }}
          <span class="ml-1 font-semibold">{{ percent(item.done, item.total) }}%</span>
        </span>
      </div>
      <div
        role="progressbar"
        :aria-label="`${item.label} 完成進度`"
        :aria-valuenow="item.done"
        :aria-valuemax="item.total"
        class="h-3 rounded-full bg-elevated overflow-hidden"
      >
        <div
          class="h-full rounded-full"
          :style="{ width: `${percent(item.done, item.total)}%`, backgroundColor: item.color ?? 'var(--ui-primary)' }"
        />
      </div>
    </li>
  </ul>
</template>
