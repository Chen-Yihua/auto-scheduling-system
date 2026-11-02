<script setup lang="ts">
import { computed } from 'vue'
import type { WeeklyCompletion } from '~/types/analytics'
import { formatMinutes } from '~/utils/format'

const props = defineProps<{ weeks: WeeklyCompletion[] }>()

const COLUMN_WIDTH = 48
const BAR_WIDTH = 24
const RADIUS = 4
const TOP = 20 // 柱頂數值的空間
const PLOT_HEIGHT = 120
const BASELINE = TOP + PLOT_HEIGHT

const width = computed(() => props.weeks.length * COLUMN_WIDTH)

// week_start 是 YYYY-MM-DD；不用 new Date 解析，否則會被當成 UTC 而在西半球顯示成前一天
function weekLabel(weekStart: string): string {
  const [, month, day] = weekStart.split('-')
  return `${month}/${day}`
}

const columns = computed(() => {
  const max = Math.max(0, ...props.weeks.map((w) => w.completed))
  return props.weeks.map((week, index) => {
    const height = max === 0 ? 0 : (week.completed / max) * PLOT_HEIGHT
    const x = index * COLUMN_WIDTH + (COLUMN_WIDTH - BAR_WIDTH) / 2
    const y = BASELINE - height
    const r = Math.min(RADIUS, height)
    return {
      week,
      label: weekLabel(week.week_start),
      center: index * COLUMN_WIDTH + COLUMN_WIDTH / 2,
      height,
      y,
      // 只有柱頂圓角，底部貼齊基線
      path: `M${x},${BASELINE} V${y + r} Q${x},${y} ${x + r},${y} H${x + BAR_WIDTH - r} Q${x + BAR_WIDTH},${y} ${x + BAR_WIDTH},${y + r} V${BASELINE} Z`,
    }
  })
})
</script>

<template>
  <div>
    <svg
      :viewBox="`0 0 ${width} ${BASELINE + 20}`"
      class="w-full h-auto max-h-64"
      role="img"
      aria-label="近幾週每週完成的任務數"
    >
      <line :x1="0" :x2="width" :y1="BASELINE" :y2="BASELINE" class="stroke-gray-200 dark:stroke-gray-700" stroke-width="1" />
      <g v-for="col in columns" :key="col.week.week_start">
        <title>{{ col.label }} 那週：完成 {{ col.week.completed }} 個，預估 {{ formatMinutes(col.week.completed_minutes) }}</title>
        <!-- 整欄都是 hover 範圍，矮柱子也好指 -->
        <rect :x="col.center - COLUMN_WIDTH / 2" :y="0" :width="COLUMN_WIDTH" :height="BASELINE" fill="transparent" />
        <path
          v-if="col.height > 0"
          data-testid="bar"
          :data-height="col.height"
          :d="col.path"
          class="fill-[#2a78d6] dark:fill-[#3987e5]"
        />
        <text
          data-testid="bar-value"
          :x="col.center"
          :y="col.y - 6"
          text-anchor="middle"
          class="text-xs fill-gray-900 dark:fill-gray-100"
        >{{ col.week.completed }}</text>
        <text
          :x="col.center"
          :y="BASELINE + 14"
          text-anchor="middle"
          class="text-[10px] fill-gray-500 dark:fill-gray-400"
        >{{ col.label }}</text>
      </g>
    </svg>

    <table class="sr-only">
      <caption>每週完成數</caption>
      <thead>
        <tr><th>週一</th><th>完成數</th><th>預估工時</th></tr>
      </thead>
      <tbody>
        <tr v-for="col in columns" :key="col.week.week_start">
          <td>{{ col.label }}</td>
          <td>{{ col.week.completed }}</td>
          <td>{{ formatMinutes(col.week.completed_minutes) }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
