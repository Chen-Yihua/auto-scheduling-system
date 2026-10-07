<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useSchedule } from '~/composables/useSchedule'
import { priorityLabel } from '~/utils/labels'

const { loading, scheduled, unscheduled, notLinked, hasFetched, confirming, confirmSchedule } = useSchedule()
const router = useRouter()

// 產生／重新產生排程建議前一律先過拖拉排序精靈（獨立頁面，見 pages/schedule.vue）；
// 精靈完成後會自己呼叫 fetchScheduleSuggestion 再導回這裡
function startWizard() {
  router.push('/schedule')
}

const getPriorityColor = (priority: string | undefined) => {
  switch (priority) {
    case 'Low':
      return 'success'
    case 'Medium':
      return 'warning'
    case 'High':
      return 'error'
    default:
      return 'neutral'
  }
}

// scheduled 的 start/end 都是同一天的機率很高，只在跨日才重複顯示日期，
// 畫面上比較不擁擠
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
  <UCard>
    <template #header>
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-2">
          <UIcon name="i-lucide-calendar-clock" class="w-5 h-5" />
          <span class="text-lg font-semibold text-gray-900 dark:text-white">排程建議</span>
        </div>
        <UButton
          v-if="hasFetched"
          icon="i-lucide-refresh-cw"
          size="xs"
          color="neutral"
          variant="ghost"
          loading-auto
          @click="startWizard"
        >
          重新產生
        </UButton>
      </div>
    </template>

    <div v-if="!hasFetched && !loading" class="text-center py-6">
      <p class="text-sm text-gray-500 dark:text-gray-400 mb-3">尚未產生排程建議</p>
      <UButton icon="i-lucide-sparkles" loading-auto @click="startWizard">
        產生排程建議
      </UButton>
    </div>

    <div v-else-if="loading">
      <USkeleton v-for="i in 2" :key="i" class="h-16 mb-4" />
    </div>

    <div
      v-else-if="notLinked"
      class="text-center text-sm text-gray-500 dark:text-gray-400 py-6"
    >
      尚未連接 Google Calendar，請先在右側卡片完成連接
    </div>

    <div
      v-else-if="scheduled.length === 0 && unscheduled.length === 0"
      class="text-center text-sm text-gray-500 dark:text-gray-400 py-6"
    >
      目前沒有可排程的任務或空檔
    </div>

    <div v-else class="space-y-4">
      <div v-if="scheduled.length > 0">
        <div class="flex items-center justify-between mb-2">
          <div class="text-sm font-semibold text-gray-700 dark:text-gray-300">已排入時段</div>
          <UButton
            size="xs"
            icon="i-lucide-calendar-check"
            loading-auto
            :loading="confirming"
            @click="confirmSchedule"
          >
            確認排程並寫入 Calendar
          </UButton>
        </div>
        <div class="grid grid-cols-1 gap-2">
          <div
            v-for="item in scheduled"
            :key="item.task_id"
            class="flex items-center justify-between rounded-lg border border-default px-3 py-2"
          >
            <div class="flex items-center gap-2 min-w-0">
              <UBadge :color="getPriorityColor(item.priority)" variant="soft" size="sm">
                {{ priorityLabel(item.priority) }}
              </UBadge>
              <span class="text-sm truncate">{{ item.title }}</span>
            </div>
            <span class="text-xs text-gray-500 whitespace-nowrap ml-2">{{ formatRange(item.start, item.end) }}</span>
          </div>
        </div>
      </div>

      <div v-if="unscheduled.length > 0">
        <div class="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">排不進去</div>
        <div class="grid grid-cols-1 gap-2">
          <div
            v-for="item in unscheduled"
            :key="item.task_id"
            class="rounded-lg border border-default px-3 py-2"
          >
            <div class="flex items-center gap-2 min-w-0">
              <UBadge :color="getPriorityColor(item.priority)" variant="soft" size="sm">
                {{ priorityLabel(item.priority) }}
              </UBadge>
              <span class="text-sm truncate">{{ item.title }}</span>
            </div>
            <div class="text-xs text-gray-500 mt-1">{{ item.reason }}</div>
          </div>
        </div>
      </div>
    </div>
  </UCard>
</template>
