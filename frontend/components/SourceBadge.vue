<script setup lang="ts">
import { computed } from 'vue';
import { sourceLabel } from '~/utils/labels';
import { platformBrands } from '~/utils/platformBrand';

const props = defineProps<{ source: string }>()

const brand = computed(() => platformBrands[props.source])
</script>

<template>
  <span
    class="inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-xs font-semibold whitespace-nowrap"
    :style="brand ? { backgroundColor: brand.background, color: brand.text } : undefined"
  >
    <UIcon v-if="brand" :name="brand.icon" class="size-3.5" />
    {{ sourceLabel(source) }}
  </span>
</template>
