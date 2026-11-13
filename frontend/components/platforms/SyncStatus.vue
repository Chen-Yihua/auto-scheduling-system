<script setup lang="ts">
import { formatRelativeTime } from '@/utils/time'

defineProps<{
  syncedAt: string | null
  // 有傳才顯示「立即同步」按鈕：平台頁面有，儀表板的卡片沒有
  onSync?: () => void | Promise<void>
  syncing?: boolean
}>()
</script>

<template>
  <div class="flex items-center justify-between gap-2 mb-2 text-xs text-gray-500 dark:text-gray-400">
    <span data-testid="synced-at">{{ syncedAt ? `上次同步：${formatRelativeTime(syncedAt)}` : '尚未同步' }}</span>
    <UButton
      v-if="onSync"
      data-testid="sync-now"
      size="xs"
      variant="soft"
      icon="i-lucide-refresh-cw"
      :loading="syncing"
      :disabled="syncing"
      @click="onSync?.()"
    >
      立即同步
    </UButton>
  </div>
</template>
