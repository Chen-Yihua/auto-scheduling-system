<script setup lang="ts">
import { computed } from 'vue'
import { formatRelativeTime } from '@/utils/time'

const props = defineProps<{
  stale: boolean
  syncedAt: string | null
}>()

const message = computed(() => `資料可能非即時，上次同步：${formatRelativeTime(props.syncedAt)}`)
</script>

<template>
  <UAlert
    v-if="stale"
    color="warning"
    variant="soft"
    icon="i-lucide-clock-alert"
    :title="message"
    class="mb-2"
  />
</template>
