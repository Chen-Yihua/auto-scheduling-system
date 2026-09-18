<script setup lang="ts">
import { computed } from 'vue'
import { formatRelativeTime } from '@/utils/time'

const props = defineProps<{
  stale: boolean
  syncedAt: string | null
  authError?: boolean
  platformLabel?: string // 例如 'GitHub'、'Jira'、'Moodle'，用來組出授權失效的提示文字
}>()

const message = computed(() => {
  if (props.authError) {
    const label = props.platformLabel ?? '帳號'
    return `${label} 授權可能已失效，目前顯示的是快取資料（上次同步：${formatRelativeTime(props.syncedAt)}），請重新連結帳號`
  }
  return `資料可能非即時，上次同步：${formatRelativeTime(props.syncedAt)}`
})
</script>

<template>
  <UAlert
    v-if="stale"
    :color="authError ? 'error' : 'warning'"
    variant="soft"
    :icon="authError ? 'i-lucide-shield-alert' : 'i-lucide-clock-alert'"
    :title="message"
    class="mb-2"
  />
</template>
