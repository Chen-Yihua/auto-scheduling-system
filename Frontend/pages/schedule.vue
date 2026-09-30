<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useUser } from '@clerk/vue'
import { useSchedulableTasks } from '~/composables/useSchedulableTasks'
import { useSchedule } from '~/composables/useSchedule'
import { useScheduleWizard, PRIORITIES, type PriorityKey } from '~/composables/useScheduleWizard'
import TheHeader from '~/components/TheHeader/index.vue'
import LoginRequiredCard from '~/components/TheMain/LoginRequiredCard.vue'
import { priorityLabel } from '~/utils/labels'
import type { SchedulableTask } from '~/types/schedulableTask'
import type { BlockedRecurringRule, BlockedException } from '~/types/schedule'

const router = useRouter()
const { isSignedIn } = useUser()
const { tasks: schedulableTasks, fetchSchedulableTasks } = useSchedulableTasks()
const { fetchScheduleSuggestion } = useSchedule()
const {
  step, columns, saving, hasTasks, preferences, sanitizedPreferences,
  initWizard, moveTask, confirmOrder, backToStep1, updateDueDate, updateDuration, finish,
  addBlockedRecurringRule, removeBlockedRecurringRule, addBlockedException, removeBlockedException,
} = useScheduleWizard()

onMounted(async () => {
  if (!isSignedIn.value) return
  await fetchSchedulableTasks()
  initWizard(schedulableTasks.value)
})

const columnLabel: Record<PriorityKey, string> = { Low: '低', Medium: '中', High: '高' }
const columnColor: Record<PriorityKey, 'success' | 'warning' | 'error'> = {
  Low: 'success', Medium: 'warning', High: 'error',
}

const sourceIcon: Record<SchedulableTask['source'], string> = {
  manual: 'i-lucide-list-todo',
  github: 'mdi:github',
  jira: 'mdi:jira',
  moodle: 'custom:moodle',
}

// 步驟指示：目前只有前兩步是這個頁面自己的內容，第三步只是告訴使用者
// 「送出後會發生什麼事」，不是這個頁面會畫出來的畫面
const steps = [
  { n: 1, label: '拖拉排序優先權' },
  { n: 2, label: '確認截止日期與時長' },
  { n: 3, label: '查看排程建議' },
]

// 拖拉：記住被拖動的任務原本在哪一欄、哪個位置
const dragSource = ref<{ column: PriorityKey; index: number } | null>(null)

function onDragStart(column: PriorityKey, index: number) {
  dragSource.value = { column, index }
}

function onDropOnRow(targetColumn: PriorityKey, targetIndex: number) {
  if (!dragSource.value) return
  moveTask(dragSource.value.column, dragSource.value.index, targetColumn, targetIndex)
  dragSource.value = null
}

function onDropOnColumnEnd(targetColumn: PriorityKey) {
  if (!dragSource.value) return
  moveTask(dragSource.value.column, dragSource.value.index, targetColumn, columns[targetColumn].length)
  dragSource.value = null
}

async function handleConfirmOrder() {
  await confirmOrder()
}

async function handleFinish() {
  await finish(async () => {
    await fetchScheduleSuggestion(sanitizedPreferences.value)
    router.push('/')
  })
}

function cancel() {
  router.push('/')
}

// <input type="datetime-local"> 要的格式是本地時間 "YYYY-MM-DDTHH:mm"（不含時區），
// 但 task.due_date 存的是 ISO 字串（通常帶 Z），兩邊要各自轉換
function toDatetimeLocalValue(dueDate: string | undefined | null): string {
  if (!dueDate) return ''
  const d = new Date(dueDate)
  if (Number.isNaN(d.getTime())) return ''
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

function onDueDateInput(task: SchedulableTask, event: Event) {
  const value = (event.target as HTMLInputElement).value
  if (!value) {
    updateDueDate(task.id, null)
    return
  }
  updateDueDate(task.id, new Date(value).toISOString())
}

function onDurationInput(task: SchedulableTask, event: Event) {
  const value = (event.target as HTMLInputElement).value
  updateDuration(task.id, value === '' ? null : Number(value))
}

const allTasksFlat = computed(() => PRIORITIES.flatMap((p) => columns[p]))

// 排程偏好設定：不工作時段（每週固定規律 + 這次額外加的例外時段）跟緩衝時間／
// 每天上限，見 useScheduleWizard 的 preferences（每次精靈重新選，不存資料庫）
const dayLabels = ['一', '二', '三', '四', '五', '六', '日'] // 對齊後端 Python weekday()：0=一...6=日

function toggleRuleDay(rule: BlockedRecurringRule, day: number) {
  const idx = rule.days_of_week.indexOf(day)
  if (idx === -1) rule.days_of_week.push(day)
  else rule.days_of_week.splice(idx, 1)
}

function onDailyMaxMinutesInput(event: Event) {
  const value = (event.target as HTMLInputElement).value
  preferences.value.daily_max_minutes = value === '' ? null : Number(value)
}

function onExceptionStartInput(exception: BlockedException, event: Event) {
  const value = (event.target as HTMLInputElement).value
  exception.start = value ? new Date(value).toISOString() : ''
}

function onExceptionEndInput(exception: BlockedException, event: Event) {
  const value = (event.target as HTMLInputElement).value
  exception.end = value ? new Date(value).toISOString() : ''
}
</script>

<template>
  <div>
    <TheHeader />

    <div v-if="isSignedIn === false" class="p-4 max-w-2xl mx-auto mt-4">
      <LoginRequiredCard title="排程精靈" icon="i-lucide-calendar-clock" message="登入後即可使用排程精靈" />
    </div>

    <div v-else-if="isSignedIn" class="p-4 max-w-3xl mx-auto mt-4">
      <!-- 步驟指示 -->
      <div class="flex items-center justify-center gap-2 mb-6">
        <template v-for="(s, i) in steps" :key="s.n">
          <div class="flex items-center gap-2">
            <div
              class="w-7 h-7 rounded-full flex items-center justify-center text-sm font-semibold"
              :class="s.n === step
                ? 'bg-primary text-white'
                : s.n < step
                  ? 'bg-primary/20 text-primary'
                  : 'bg-gray-200 dark:bg-gray-700 text-gray-500'"
            >
              {{ s.n }}
            </div>
            <span
              class="text-sm"
              :class="s.n === step ? 'font-semibold text-gray-900 dark:text-white' : 'text-gray-500'"
            >
              {{ s.label }}
            </span>
          </div>
          <UIcon v-if="i < steps.length - 1" name="i-lucide-chevron-right" class="w-4 h-4 text-gray-400" />
        </template>
      </div>

      <!-- Step 1：三欄拖拉排序 -->
      <div v-if="step === 1">
        <p class="text-sm text-gray-500 dark:text-gray-400 mb-4 text-center">
          把任務拖到對應的優先權欄位；同一欄內的上下順序也會影響排程的先後。
        </p>

        <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div
            v-for="p in PRIORITIES"
            :key="p"
            class="rounded-xl border border-default bg-gray-50 dark:bg-gray-900 p-3 min-h-[200px]"
            @dragover.prevent
            @drop.prevent="onDropOnColumnEnd(p)"
          >
            <div class="flex items-center gap-2 mb-3">
              <UBadge :color="columnColor[p]" variant="soft" size="sm">{{ columnLabel[p] }}</UBadge>
              <span class="text-xs text-gray-400">({{ columns[p].length }})</span>
            </div>

            <div class="space-y-2">
              <div
                v-for="(task, index) in columns[p]"
                :key="task.id"
                class="flex items-center gap-2 rounded-lg border border-default bg-white dark:bg-gray-800 px-3 py-2 cursor-move"
                draggable="true"
                @dragstart="onDragStart(p, index)"
                @dragover.prevent
                @drop.stop.prevent="onDropOnRow(p, index)"
              >
                <UIcon name="i-lucide-grip-vertical" class="w-4 h-4 text-gray-400 flex-shrink-0" />
                <UIcon :name="sourceIcon[task.source]" class="w-3.5 h-3.5 text-gray-400 flex-shrink-0" />
                <span class="text-sm truncate flex-1">{{ task.title }}</span>
              </div>
            </div>

            <div v-if="columns[p].length === 0" class="text-center text-xs text-gray-400 py-6">
              拖任務到這裡
            </div>
          </div>
        </div>

        <div class="flex justify-end gap-3 mt-6">
          <UButton type="button" variant="link" class="bg-gray-200 text-black hover:bg-gray-300" @click="cancel">
            取消
          </UButton>
          <UButton :disabled="!hasTasks" loading-auto :loading="saving" @click="handleConfirmOrder">
            下一步
          </UButton>
        </div>
      </div>

      <!-- Step 2：確認截止日期與所需時長、排程偏好設定 -->
      <div v-else class="space-y-3">
        <p class="text-sm text-gray-500 dark:text-gray-400 mb-2 text-center">
          這裡可以調整截止日期與所需時長；優先權跟順序已經鎖定，回上一步才能改。
        </p>

        <div class="rounded-lg border border-default bg-gray-50 dark:bg-gray-900 p-4 space-y-4 mb-4">
          <p class="text-sm font-semibold text-gray-700 dark:text-gray-300">排程偏好設定</p>

          <div class="flex flex-wrap gap-4">
            <label class="text-xs text-gray-500 dark:text-gray-400 flex flex-col gap-1">
              任務間緩衝時間（分鐘）
              <input
                v-model.number="preferences.buffer_minutes"
                type="number"
                min="0"
                class="border border-default rounded-md px-2 py-1 text-sm bg-transparent w-32"
              >
            </label>
            <label class="text-xs text-gray-500 dark:text-gray-400 flex flex-col gap-1">
              每天最多排多少分鐘（留空＝不限制）
              <input
                type="number"
                min="1"
                class="border border-default rounded-md px-2 py-1 text-sm bg-transparent w-40"
                :value="preferences.daily_max_minutes ?? ''"
                @change="onDailyMaxMinutesInput"
              >
            </label>
          </div>

          <div>
            <div class="flex items-center justify-between mb-2">
              <span class="text-xs font-semibold text-gray-600 dark:text-gray-400">每週固定不工作時段</span>
              <UButton size="xs" variant="soft" @click="addBlockedRecurringRule">新增規律</UButton>
            </div>
            <p v-if="preferences.blocked_recurring.length === 0" class="text-xs text-gray-400">
              沒有設定，代表整週空檔都可以排
            </p>
            <div
              v-for="(rule, index) in preferences.blocked_recurring"
              :key="index"
              class="flex flex-wrap items-center gap-2 mb-2 rounded-md border border-default px-2 py-2"
            >
              <div class="flex gap-1">
                <button
                  v-for="(label, day) in dayLabels"
                  :key="day"
                  type="button"
                  class="w-6 h-6 rounded-full text-xs"
                  :class="rule.days_of_week.includes(day)
                    ? 'bg-primary text-white'
                    : 'bg-gray-200 dark:bg-gray-700 text-gray-500'"
                  @click="toggleRuleDay(rule, day)"
                >
                  {{ label }}
                </button>
              </div>
              <label class="text-xs text-gray-500 flex items-center gap-1">
                <input v-model="rule.all_day" type="checkbox">
                整天
              </label>
              <template v-if="!rule.all_day">
                <input v-model="rule.start_time" type="time" class="border border-default rounded-md px-1 py-0.5 text-xs bg-transparent">
                <span class="text-xs text-gray-400">～</span>
                <input v-model="rule.end_time" type="time" class="border border-default rounded-md px-1 py-0.5 text-xs bg-transparent">
              </template>
              <UButton size="xs" variant="ghost" color="error" @click="removeBlockedRecurringRule(index)">移除</UButton>
            </div>
          </div>

          <div>
            <div class="flex items-center justify-between mb-2">
              <span class="text-xs font-semibold text-gray-600 dark:text-gray-400">這次額外不排的時段</span>
              <UButton size="xs" variant="soft" @click="addBlockedException">新增例外時段</UButton>
            </div>
            <p v-if="preferences.blocked_exceptions.length === 0" class="text-xs text-gray-400">
              沒有這次額外的例外時段
            </p>
            <div
              v-for="(exception, index) in preferences.blocked_exceptions"
              :key="index"
              class="flex flex-wrap items-center gap-2 mb-2"
            >
              <input
                type="datetime-local"
                class="border border-default rounded-md px-2 py-1 text-xs bg-transparent"
                :value="toDatetimeLocalValue(exception.start)"
                @change="onExceptionStartInput(exception, $event)"
              >
              <span class="text-xs text-gray-400">～</span>
              <input
                type="datetime-local"
                class="border border-default rounded-md px-2 py-1 text-xs bg-transparent"
                :value="toDatetimeLocalValue(exception.end)"
                @change="onExceptionEndInput(exception, $event)"
              >
              <UButton size="xs" variant="ghost" color="error" @click="removeBlockedException(index)">移除</UButton>
            </div>
          </div>
        </div>

        <div
          v-for="task in allTasksFlat"
          :key="task.id"
          class="rounded-lg border border-default bg-white dark:bg-gray-800 px-3 py-3 space-y-2"
        >
          <div class="flex items-center gap-2">
            <UIcon :name="sourceIcon[task.source]" class="w-4 h-4 text-gray-400 flex-shrink-0" />
            <UBadge :color="columnColor[task.priority as PriorityKey]" variant="soft" size="sm">
              {{ priorityLabel(task.priority) }}
            </UBadge>
            <span class="text-sm font-medium truncate">{{ task.title }}</span>
          </div>
          <div class="flex flex-wrap gap-4">
            <label class="text-xs text-gray-500 dark:text-gray-400 flex flex-col gap-1">
              截止日期
              <input
                type="datetime-local"
                class="border border-default rounded-md px-2 py-1 text-sm bg-transparent"
                :value="toDatetimeLocalValue(task.due_date)"
                @change="onDueDateInput(task, $event)"
              >
            </label>
            <label class="text-xs text-gray-500 dark:text-gray-400 flex flex-col gap-1">
              所需時長（分鐘）
              <input
                type="number"
                min="1"
                class="border border-default rounded-md px-2 py-1 text-sm bg-transparent w-28"
                :value="task.duration ?? ''"
                @change="onDurationInput(task, $event)"
              >
            </label>
          </div>
        </div>

        <div class="flex justify-end gap-3 mt-4">
          <UButton type="button" variant="link" class="bg-gray-200 text-black hover:bg-gray-300" @click="backToStep1">
            上一步
          </UButton>
          <UButton loading-auto :loading="saving" @click="handleFinish">
            確認並產生排程建議
          </UButton>
        </div>
      </div>
    </div>
  </div>
</template>
