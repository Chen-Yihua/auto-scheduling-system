<script setup lang="ts">
import NoticeBox from '~/components/NoticeBox.vue';
import CardTitle from '~/components/CardTitle.vue';
import PriorityBadge from '~/components/PriorityBadge.vue';
import { useSchedule } from '~/composables/useSchedule';

// 排程精靈的第 3 步；「重新產生」交給精靈回到第 1 步
const emit = defineEmits<{ regenerate: [] }>()

const { loading, scheduled, unscheduled, notLinked, confirming, confirmSchedule } = useSchedule()


// 跨日時才重複顯示日期
const formatRange = (start: string, end: string) => {
  const startDate = new Date(start)
  const endDate = new Date(end)
  const sameDay = startDate.toDateString() === endDate.toDateString()
  const startText = startDate.toLocaleString()
  const endText = sameDay ? endDate.toLocaleTimeString() : endDate.toLocaleString()
  return `${startText} - ${endText}`
}
</script>

<template>
  <UCard :ui="{ root: 'lg:min-h-0 lg:flex lg:flex-col', body: 'lg:flex-1 lg:min-h-0 lg:overflow-y-auto' }">
    <template #header>
      <div class="flex flex-wrap items-center justify-between gap-2">
        <CardTitle icon="i-lucide-calendar-clock" title="排程建議" />
        <div class="flex items-center gap-2">
          <UButton
            icon="i-lucide-refresh-cw"
            size="xs"
            color="neutral"
            variant="ghost"
            @click="emit('regenerate')"
          >
            重新產生
          </UButton>
          <UButton
            v-if="!loading && !notLinked && scheduled.length > 0"
            size="xs"
            icon="i-lucide-calendar-check"
            loading-auto
            :loading="confirming"
            @click="confirmSchedule"
          >
            確認排程並寫入 Calendar
          </UButton>
        </div>
      </div>
    </template>

    <div v-if="loading">
      <USkeleton v-for="i in 2" :key="i" class="h-16 mb-4" />
    </div>

    <NoticeBox v-else-if="notLinked" icon="i-lucide-calendar-x">
      Google Calendar 未連接或授權已失效。點右上角的頭像，在 <strong>金鑰</strong> 頁連接。
    </NoticeBox>

    <div
      v-else-if="scheduled.length === 0 && unscheduled.length === 0"
      class="text-center text-sm text-muted py-6"
    >
      目前沒有可排程的任務或空檔
    </div>

    <div v-else class="space-y-4">
      <div v-if="scheduled.length > 0">
        <div class="text-sm font-semibold text-toned mb-2">已排入時段</div>
        <div class="grid grid-cols-1 gap-2">
          <div
            v-for="item in scheduled"
            :key="item.task_id"
            class="flex items-center justify-between rounded-lg border border-default px-3 py-2"
          >
            <div class="flex items-center gap-2 min-w-0">
              <PriorityBadge :priority="item.priority" />
              <span class="text-sm line-clamp-2 break-words text-balance min-w-0">{{ item.title }}</span>
            </div>
            <span class="text-xs text-muted whitespace-nowrap ml-2">{{ formatRange(item.start, item.end) }}</span>
          </div>
        </div>
      </div>

      <div v-if="unscheduled.length > 0">
        <div class="text-sm font-semibold text-toned mb-2">排不進去</div>
        <div class="grid grid-cols-1 gap-2">
          <div
            v-for="item in unscheduled"
            :key="item.task_id"
            class="rounded-lg border border-default px-3 py-2"
          >
            <div class="flex items-center gap-2 min-w-0">
              <PriorityBadge :priority="item.priority" />
              <span class="text-sm line-clamp-2 break-words text-balance min-w-0">{{ item.title }}</span>
            </div>
            <div class="text-xs text-muted mt-1">{{ item.reason }}</div>
          </div>
        </div>
      </div>
    </div>
  </UCard>
</template>
