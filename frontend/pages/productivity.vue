<script setup lang="ts">
import { computed, watch } from 'vue';
import { useUser } from '@clerk/vue';
import { useProductivity } from '~/composables/useProductivity';
import AppHeader from '~/components/header/AppHeader.vue';
import LoginRequiredCard from '~/components/LoginRequiredCard.vue';
import WeeklyBarChart from '~/components/productivity/WeeklyBarChart.vue';
import ProgressList from '~/components/productivity/ProgressList.vue';
import CardTitle from '~/components/CardTitle.vue';
import { platformBrands } from '~/utils/platformBrand';
import { priorityColors } from '~/utils/priorityColor';
import { formatDateTime, formatMinutes, formatPercent } from '~/utils/format';
import { formatRelativeTime } from '~/utils/time';
import { priorityLabel, sourceLabel } from '~/utils/labels';

const { isSignedIn } = useUser();
const { summary, loading, error, fetchSummary, startAutoRefresh, stopAutoRefresh } = useProductivity()
const { keys, fetchKeys } = useLinkedAccount()

// 統計只讀資料庫，讓使用者知道各平台的資料是什麼時候同步的；已連結（含憑證無法讀取）的平台才顯示
const platformSyncTimes = computed(() =>
  keys.value
    .filter((k) => k.value || k.needsReauth)
    .map((k) => ({
      platform: k.platform,
      label: sourceLabel(k.platform),
      text: k.lastSyncedAt ? formatRelativeTime(k.lastSyncedAt) : '尚未同步',
    })),
)

async function loadPlatformSyncTimes() {
  try {
    await fetchKeys()
  } catch {
    // 只是輔助資訊，讀不到就不顯示，不影響統計
  }
}

// Clerk 初始化完成才知道有沒有登入，所以用 watch 而不是 onMounted
watch(isSignedIn, (signedIn) => {
  if (signedIn) {
    fetchSummary()
    startAutoRefresh()
    loadPlatformSyncTimes()
  } else {
    stopAutoRefresh()
  }
}, { immediate: true })

const sourceItems = computed(() =>
  (summary.value?.by_source ?? []).map((s) => ({ key: s.source, label: sourceLabel(s.source), done: s.done, total: s.total, color: platformBrands[s.source]?.background })),
)

const priorityItems = computed(() =>
  (summary.value?.by_priority ?? []).map((p) => ({
    key: p.priority ?? 'none',
    label: p.priority ? priorityLabel(p.priority) : '未設定',
    done: p.done,
    total: p.total,
    color: p.priority ? priorityColors[p.priority] : 'var(--color-ash-300)',
  })),
)

const kpis = computed(() => {
  const s = summary.value
  if (!s) return []
  return [
    {
      id: 'completion', label: '完成率', icon: 'i-lucide-circle-check-big',
      value: formatPercent(s.completion_rate), note: `已完成 ${s.done} / ${s.total}`,
      tile: 'bg-steel-200 text-steel-700',
    },
    {
      id: 'overdue', label: '逾期', icon: 'i-lucide-alarm-clock',
      value: String(s.overdue), note: '未完成且已過截止日',
      tile: 'bg-blush-200 text-blush-800',
    },
    {
      id: 'remaining', label: '剩餘預估工時', icon: 'i-lucide-hourglass',
      value: formatMinutes(s.remaining_minutes),
      note: `已完成 ${formatMinutes(s.done_minutes)}${s.unestimated_remaining ? `，${s.unestimated_remaining} 個未估時` : ''}`,
      tile: 'bg-sand-200 text-sand-800',
    },
    {
      id: 'on-time', label: '準時完成率', icon: 'i-lucide-target',
      value: formatPercent(s.on_time.rate),
      note: `近 ${s.weekly.length} 週有截止日的 ${s.on_time.completed_with_due} 個中準時 ${s.on_time.on_time} 個`,
      tile: 'bg-fern-200 text-fern-800',
    },
  ]
})
</script>

<template>
  <div class="lg:min-h-dvh lg:flex lg:flex-col">
    <AppHeader class="shrink-0" />
    <div class="p-4 max-w-4xl lg:max-w-6xl w-full mx-auto mt-4 lg:flex-1 lg:flex lg:flex-col">
      <LoginRequiredCard
        v-if="isSignedIn === false"
        title="工作效率"
        icon="i-lucide-chart-column"
        message="登入後即可查看工作效率統計"
      />

      <template v-else-if="isSignedIn">
        <div class="flex flex-wrap items-baseline justify-between gap-2 mb-4">
          <h1 class="text-2xl font-bold text-highlighted">工作效率</h1>
          <p v-if="summary" data-testid="generated-at" class="text-xs text-muted">
            統計時間：{{ formatDateTime(summary.generated_at) }}
          </p>
        </div>

        <p v-if="platformSyncTimes.length" data-testid="platform-synced-at" class="text-xs text-muted mb-4">
          外部平台上次同步：
          <span v-for="(p, i) in platformSyncTimes" :key="p.platform">{{ i ? '、' : '' }}{{ p.label }} {{ p.text }}</span>
        </p>

        <p v-if="loading && !summary" class="text-sm text-muted">統計資料載入中，請稍候…</p>

        <UCard v-else-if="error && !summary" data-testid="error">
          <p class="text-center text-sm text-muted py-6">
            統計資料載入失敗，系統會在下次自動更新時重試，請稍候
          </p>
        </UCard>

        <UCard v-else-if="summary && summary.total === 0" data-testid="empty">
          <p class="text-center text-sm text-muted py-6">
            目前沒有可統計的資料
          </p>
        </UCard>

        <div v-else-if="summary" class="space-y-6 lg:space-y-0 lg:grid lg:grid-cols-4 lg:gap-4 lg:flex-1">
          <div class="grid grid-cols-2 lg:flex lg:flex-col gap-4">
            <UCard
              v-for="k in kpis"
              :key="k.id"
              :data-testid="`kpi-${k.id}`"
              :ui="{ body: 'p-4 sm:p-5' }"
            >
              <div class="flex items-center gap-2">
                <span class="size-9 rounded-xl flex items-center justify-center shrink-0" :class="k.tile">
                  <UIcon :name="k.icon" class="size-5" />
                </span>
                <p class="text-sm font-medium">{{ k.label }}</p>
              </div>
              <p class="mt-3 text-4xl font-bold tabular-nums">{{ k.value }}</p>
              <p class="mt-1 text-xs">{{ k.note }}</p>
            </UCard>
          </div>

          <div class="space-y-6 lg:space-y-0 lg:col-span-3 lg:flex lg:flex-col lg:gap-4">
          <!-- 寬螢幕時圖表用 absolute 填滿剩下的高度：它不撐高卡片，卡片高度才由視窗決定 -->
          <UCard :ui="{ root: 'lg:flex-1 lg:flex lg:flex-col', body: 'lg:flex-1 lg:flex lg:flex-col' }">
            <template #header>
              <CardTitle :title="`近 ${summary.weekly.length} 週完成數`" icon="i-lucide-chart-column" />
            </template>
            <div class="lg:relative lg:flex-1 lg:min-h-[160px]">
              <div class="lg:absolute lg:inset-0">
                <WeeklyBarChart :weeks="summary.weekly" />
              </div>
            </div>
            <p v-if="summary.untracked_done" class="mt-3 text-xs text-muted">
              有 {{ summary.untracked_done }} 個任務在開始記錄完成時間前就已完成，沒有列入每週趨勢和準時完成率。
            </p>
          </UCard>

          <div class="grid grid-cols-1 md:grid-cols-2 gap-4 lg:shrink-0">
            <UCard data-testid="by-source">
              <template #header>
                <CardTitle title="依來源" icon="i-lucide-layers" />
              </template>
              <ProgressList :items="sourceItems" />
            </UCard>
            <UCard data-testid="by-priority">
              <template #header>
                <CardTitle title="依優先度" icon="i-lucide-flag" />
              </template>
              <ProgressList :items="priorityItems" />
            </UCard>
          </div>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>
