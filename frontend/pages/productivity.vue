<script setup lang="ts">
import { computed, watch } from 'vue'
import { useUser } from '@clerk/vue'
import { useProductivity } from '~/composables/useProductivity'
import AppHeader from '~/components/header/AppHeader.vue'
import LoginRequiredCard from '~/components/LoginRequiredCard.vue'
import WeeklyBarChart from '~/components/productivity/WeeklyBarChart.vue'
import ProgressList from '~/components/productivity/ProgressList.vue'
import { formatDateTime, formatMinutes, formatPercent } from '~/utils/format'
import { priorityLabel, sourceLabel } from '~/utils/labels'

const { isSignedIn } = useUser()
const { summary, loading, error, fetchSummary, startAutoRefresh, stopAutoRefresh } = useProductivity()

// Clerk 初始化完成才知道有沒有登入，所以用 watch 而不是 onMounted
watch(isSignedIn, (signedIn) => {
  if (signedIn) {
    fetchSummary()
    startAutoRefresh()
  } else {
    stopAutoRefresh()
  }
}, { immediate: true })

const sourceItems = computed(() =>
  (summary.value?.by_source ?? []).map((s) => ({ key: s.source, label: sourceLabel(s.source), done: s.done, total: s.total })),
)

const priorityItems = computed(() =>
  (summary.value?.by_priority ?? []).map((p) => ({
    key: p.priority ?? 'none',
    label: p.priority ? priorityLabel(p.priority) : '未設定',
    done: p.done,
    total: p.total,
  })),
)
</script>

<template>
  <div>
    <AppHeader />
    <div class="p-4 max-w-4xl mx-auto mt-4">
      <NuxtLink to="/" class="inline-flex items-center gap-1 text-sm text-primary hover:underline mb-4">
        <UIcon name="i-lucide-arrow-left" class="w-4 h-4" />
        返回主頁
      </NuxtLink>

      <LoginRequiredCard
        v-if="isSignedIn === false"
        title="工作效率"
        icon="i-lucide-chart-column"
        message="登入後即可查看工作效率統計"
      />

      <template v-else-if="isSignedIn">
        <div class="flex flex-wrap items-baseline justify-between gap-2 mb-4">
          <h1 class="text-xl font-semibold text-gray-900 dark:text-white">工作效率</h1>
          <p v-if="summary" data-testid="generated-at" class="text-xs text-gray-500 dark:text-gray-400">
            統計時間：{{ formatDateTime(summary.generated_at) }}
          </p>
        </div>

        <p v-if="loading && !summary" class="text-sm text-gray-500 dark:text-gray-400">統計資料載入中，請稍候…</p>

        <UCard v-else-if="error && !summary" data-testid="error">
          <p class="text-center text-sm text-gray-500 dark:text-gray-400 py-6">
            統計資料載入失敗，系統會在下次自動更新時重試，請稍候
          </p>
        </UCard>

        <UCard v-else-if="summary && summary.total === 0" data-testid="empty">
          <p class="text-center text-sm text-gray-500 dark:text-gray-400 py-6">
            目前沒有可統計的資料
          </p>
        </UCard>

        <div v-else-if="summary" class="space-y-6">
          <div class="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <UCard data-testid="kpi-completion">
              <p class="text-sm text-gray-500 dark:text-gray-400">完成率</p>
              <p class="text-3xl font-semibold text-gray-900 dark:text-white">{{ formatPercent(summary.completion_rate) }}</p>
              <p class="text-xs text-gray-500 dark:text-gray-400">已完成 {{ summary.done }} / {{ summary.total }}</p>
            </UCard>
            <UCard data-testid="kpi-overdue">
              <p class="text-sm text-gray-500 dark:text-gray-400">逾期</p>
              <p class="text-3xl font-semibold text-gray-900 dark:text-white">{{ summary.overdue }}</p>
              <p class="text-xs text-gray-500 dark:text-gray-400">未完成且已過截止日</p>
            </UCard>
            <UCard data-testid="kpi-remaining">
              <p class="text-sm text-gray-500 dark:text-gray-400">剩餘預估工時</p>
              <p class="text-3xl font-semibold text-gray-900 dark:text-white">{{ formatMinutes(summary.remaining_minutes) }}</p>
              <p class="text-xs text-gray-500 dark:text-gray-400">
                已完成 {{ formatMinutes(summary.done_minutes) }}
                <template v-if="summary.unestimated_remaining">· {{ summary.unestimated_remaining }} 個未估時</template>
              </p>
            </UCard>
            <UCard data-testid="kpi-on-time">
              <p class="text-sm text-gray-500 dark:text-gray-400">準時完成率</p>
              <p class="text-3xl font-semibold text-gray-900 dark:text-white">{{ formatPercent(summary.on_time.rate) }}</p>
              <p class="text-xs text-gray-500 dark:text-gray-400">
                近 {{ summary.weekly.length }} 週有截止日的 {{ summary.on_time.completed_with_due }} 個中準時 {{ summary.on_time.on_time }} 個
              </p>
            </UCard>
          </div>

          <UCard>
            <template #header>
              <span class="font-semibold text-gray-900 dark:text-white">近 {{ summary.weekly.length }} 週完成數</span>
            </template>
            <WeeklyBarChart :weeks="summary.weekly" />
            <p v-if="summary.untracked_done" class="mt-3 text-xs text-gray-500 dark:text-gray-400">
              有 {{ summary.untracked_done }} 個任務在開始記錄完成時間前就已完成，沒有列入每週趨勢和準時完成率。
            </p>
          </UCard>

          <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <UCard data-testid="by-source">
              <template #header>
                <span class="font-semibold text-gray-900 dark:text-white">依來源</span>
              </template>
              <ProgressList :items="sourceItems" />
            </UCard>
            <UCard data-testid="by-priority">
              <template #header>
                <span class="font-semibold text-gray-900 dark:text-white">依優先度</span>
              </template>
              <ProgressList :items="priorityItems" />
            </UCard>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>
