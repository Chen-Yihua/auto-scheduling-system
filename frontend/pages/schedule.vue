<script setup lang="ts">
import { ref, reactive, computed, watch } from 'vue';
import { useUser } from '@clerk/vue';
import { useSchedulableTasks } from '~/composables/useSchedulableTasks';
import { toDatetimeLocal } from '~/utils/datetimeLocal';
import { useSchedule } from '~/composables/useSchedule';
import ScheduleSuggestion from '~/components/tasks/ScheduleSuggestion.vue';
import { useScheduleWizard, PRIORITIES, type PriorityKey } from '~/composables/useScheduleWizard';
import { useGoogleCalendar } from '~/composables/useGoogleCalendar';
import { useGoogleCalendarAuth } from '~/composables/useGoogleCalendarAuth';
import { useRemovedCalendarEvents } from '~/composables/useRemovedCalendarEvents';
import AppHeader from '~/components/header/AppHeader.vue';
import LoginRequiredCard from '~/components/LoginRequiredCard.vue';
import { priorityLabel } from '~/utils/labels';
import { stageMoveBlockReason } from '~/utils/stages';
import type { SchedulableTask } from '~/types/schedulableTask';
import type { BlockedRecurringRule, BlockedException, RemovedCalendarEvent } from '~/types/schedule'

const toast = useToast()
const { isSignedIn } = useUser()
const { tasks: schedulableTasks, loadFailed, fetchSchedulableTasks } = useSchedulableTasks()
const { fetchScheduleSuggestion } = useSchedule()
const {
  step, columns, saving, hasTasks, preferences, sanitizedPreferences,
  initWizard, loadSavedPreferences, savePreferences, toggleAllDay, moveTask, confirmOrder, backToStep1, updateDueDate, updateDuration, finish,
  addBlockedRecurringRule, removeBlockedRecurringRule, addBlockedException, removeBlockedException,
} = useScheduleWizard()

const { fetchGoogleCalendars } = useGoogleCalendar()
const { reauthToast, goToGoogleAuth } = useGoogleCalendarAuth()
const { items: removedItems, fetchRemovedEvents, resolveRemovedEvents } = useRemovedCalendarEvents()

// checking：連接狀態或進入精靈時的查詢還沒回來；missing：沒連接或授權已失效
const pageState = ref<'checking' | 'missing' | 'ready'>('checking')
// 進入精靈時查詢已刪除的事件失敗：顯示在精靈上方，不跳 toast（頁面自動查詢的結果）
const removedQueryNotice = ref<'reauth' | 'error' | null>(null)
// 這次進入精靈時有「處理已刪除的事件」這一步，步驟列才列出它
const hasRemovedStep = ref(false)
const inRemovedStep = ref(false)
const resolveFailed = ref(false)
const resolving = ref(false)
// 依 id 記住使用者取消的勾選：重新查詢後還在的項目沿用，新出現的預設勾選
const uncheckedIds = reactive(new Set<string>())

async function initPage() {
  const connection = await fetchGoogleCalendars()
  if (connection === 'not_linked' || connection === 'reauth') {
    pageState.value = 'missing'
    return
  }
  const [, query] = await Promise.all([fetchSchedulableTasks(), fetchRemovedEvents(), loadSavedPreferences()])
  initWizard(schedulableTasks.value)
  if (query !== 'ok') {
    removedQueryNotice.value = query
  } else if (removedItems.value.length > 0) {
    hasRemovedStep.value = true
    inRemovedStep.value = true
  }
  pageState.value = 'ready'
}

// 重新整理時 Clerk 還沒載入完，isSignedIn 是 undefined；等它變成 true 才初始化，而且只做一次
let started = false
watch(isSignedIn, (signedIn) => {
  if (!signedIn || started) return
  started = true
  void initPage()
}, { immediate: true })

// 精靈第 1 步沒有可排程的任務時，說明原因：只算不是主任務的任務
const emptyState = computed(() => {
  const own = schedulableTasks.value.filter((t) => !t.is_parent)
  return {
    total: own.length,
    scheduled: own.filter((t) => t.status !== 'Done' && !!t.calendar_event_id).length,
    done: own.filter((t) => t.status === 'Done').length,
  }
})

// 外部平台的項目不能刪除，一律重新排程
function isRescheduled(item: RemovedCalendarEvent): boolean {
  return item.source !== 'manual' || !uncheckedIds.has(item.id)
}

function onRescheduleToggle(item: RemovedCalendarEvent, event: Event) {
  if ((event.target as HTMLInputElement).checked) uncheckedIds.delete(item.id)
  else uncheckedIds.add(item.id)
}

function laterStagesNote(item: RemovedCalendarEvent): string | null {
  if (!isRescheduled(item) || item.later_stages.length === 0) return null
  return `後面的階段 ${item.later_stages.map((s) => s.stage).join('、')} 也會從 Google 日曆移除，一起重新排程`
}

// 數字是畫面載入時算的；後端處理時用當下的資料，兩者可能不同
function confirmMessage(toDelete: RemovedCalendarEvent[], toReschedule: RemovedCalendarEvent[]): string | null {
  const lines: string[] = []
  if (toDelete.length > 0) {
    lines.push(`沒勾的 ${toDelete.length} 個任務會從系統刪除，無法復原，確定嗎？`)
    const stagesByParent = new Map<string, RemovedCalendarEvent[]>()
    for (const item of toDelete) {
      if (item.parent_id) stagesByParent.set(item.parent_id, [...(stagesByParent.get(item.parent_id) ?? []), item])
    }
    for (const stages of stagesByParent.values()) {
      const first = stages[0]!
      if (stages.length === first.stage_count) lines.push(`主任務「${first.parent_title ?? ''}」會一起刪除`)
    }
  }
  const laterStageIds = new Set(toReschedule.flatMap((item) => item.later_stages.map((s) => s.task_id)))
  if (laterStageIds.size > 0) {
    lines.push(`會從 Google 日曆移除 ${laterStageIds.size} 個後面階段的事件（包括時間已經過去的事件），一起重新排程`)
  }
  return lines.length > 0 ? lines.join('\n') : null
}

// 「處理已刪除的事件」按「取消」也用這個：不送出處理請求，那些任務下次打開排程頁時還會再問
async function enterWizardAfterRemovedStep() {
  await fetchSchedulableTasks()
  initWizard(schedulableTasks.value)
  resolveFailed.value = false
  inRemovedStep.value = false
}

async function handleResolveRemoved() {
  const toReschedule = removedItems.value.filter(isRescheduled)
  const toDelete = removedItems.value.filter((item) => !isRescheduled(item))
  const message = confirmMessage(toDelete, toReschedule)
  if (message && !window.confirm(message)) return

  resolving.value = true
  try {
    const outcome = await resolveRemovedEvents(toReschedule.map((item) => item.id), toDelete.map((item) => item.id))
    if (outcome === 'done') {
      await enterWizardAfterRemovedStep()
      return
    }
    // toast 已說明原因並附重新連接的按鈕，不再顯示「處理失敗，請重試」
    if (outcome === 'reauth') {
      resolveFailed.value = false
      toast.add(reauthToast())
      return
    }
    const query = await fetchRemovedEvents()
    if (query === 'ok' && removedItems.value.length === 0) {
      await enterWizardAfterRemovedStep()
      return
    }
    resolveFailed.value = true
    if (query === 'reauth') toast.add(reauthToast())
  } finally {
    resolving.value = false
  }
}

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

type StepKey = 'removed' | 1 | 2 | 3
const steps = computed<{ key: StepKey; label: string }[]>(() => [
  ...(hasRemovedStep.value ? [{ key: 'removed' as const, label: '處理已刪除的事件' }] : []),
  { key: 1, label: '拖拉排序優先權' },
  { key: 2, label: '確認截止日期與時長' },
  { key: 3, label: '查看排程建議' },
])
const currentStepIndex = computed(() => {
  const current: StepKey = inRemovedStep.value ? 'removed' : step.value
  return steps.value.findIndex((s) => s.key === current)
})

const dragSource = ref<{ column: PriorityKey; index: number } | null>(null)

function onDragStart(column: PriorityKey, index: number) {
  dragSource.value = { column, index }
}

// 違反階段限制的拖拉在前端直接擋下，不移動也不送出
function moveIfAllowed(targetColumn: PriorityKey, targetIndex: number) {
  if (!dragSource.value) return
  const { column, index } = dragSource.value
  dragSource.value = null
  const reason = stageMoveBlockReason(columns, schedulableTasks.value, column, index, targetColumn, targetIndex)
  if (reason) {
    toast.add({ title: '不能這樣排', description: reason, color: 'warning', icon: 'i-lucide-alert-triangle' })
    return
  }
  moveTask(column, index, targetColumn, targetIndex)
}

function onDropOnRow(targetColumn: PriorityKey, targetIndex: number) {
  moveIfAllowed(targetColumn, targetIndex)
};

function onDropOnColumnEnd(targetColumn: PriorityKey) {
  moveIfAllowed(targetColumn, columns[targetColumn].length)
}

function stageLabel(task: SchedulableTask): string {
  return `${task.parent_title ?? ''} · 階段 ${task.stage}/${task.stage_count}`
}

async function handleConfirmOrder() {
  await confirmOrder()
}

async function handleFinish() {
  await finish(async () => {
    const ok = await fetchScheduleSuggestion(sanitizedPreferences.value)
    if (ok) await savePreferences()
    step.value = 3
  })
}

// 確認排程後任務已寫進日曆，回到第 1 步要重新讀任務，已排程的才不會留在三欄裡
async function regenerate() {
  await fetchSchedulableTasks()
  initWizard(schedulableTasks.value)
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
    <AppHeader />

    <div v-if="isSignedIn === false" class="p-4 max-w-2xl mx-auto mt-4">
      <LoginRequiredCard title="排程精靈" icon="i-lucide-calendar-clock" message="登入後即可使用排程精靈" />
    </div>

    <div v-else-if="isSignedIn" class="p-4 max-w-3xl mx-auto mt-4">
      <div
        v-if="pageState === 'missing'"
        class="rounded-xl border border-default text-center text-sm text-gray-500 dark:text-gray-400 py-10"
      >
        Google Calendar 未連接或授權已失效，請前往 <strong>帳號設定</strong> 連接。
      </div>

      <div v-else-if="pageState === 'checking'" class="space-y-3">
        <USkeleton v-for="i in 3" :key="i" class="h-16" />
      </div>

      <template v-else>
        <div class="flex flex-wrap items-center justify-center gap-2 mb-6">
          <template v-for="(s, i) in steps" :key="s.key">
            <div class="flex items-center gap-2">
              <div
                class="w-7 h-7 rounded-full flex items-center justify-center text-sm font-semibold"
                :class="i === currentStepIndex
                  ? 'bg-primary text-white'
                  : i < currentStepIndex
                    ? 'bg-primary/20 text-primary'
                    : 'bg-gray-200 dark:bg-gray-700 text-gray-500'"
              >
                {{ i + 1 }}
              </div>
              <span
                class="text-sm"
                :class="i === currentStepIndex ? 'font-semibold text-gray-900 dark:text-white' : 'text-gray-500'"
              >
                {{ s.label }}
              </span>
            </div>
            <UIcon v-if="i < steps.length - 1" name="i-lucide-chevron-right" class="w-4 h-4 text-gray-400" />
          </template>
        </div>

        <div
          v-if="removedQueryNotice === 'reauth'"
          class="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-error/40 bg-error/10 px-3 py-2 mb-4 text-sm"
        >
          <span>Google Calendar 授權已失效，無法確認 Google 日曆上的事件</span>
          <UButton size="xs" color="error" variant="soft" @click="goToGoogleAuth">重新連接 Google Calendar</UButton>
        </div>
        <div
          v-else-if="removedQueryNotice === 'error'"
          class="rounded-lg border border-warning/40 bg-warning/10 px-3 py-2 mb-4 text-sm"
        >
          暫時無法確認 Google 日曆上的事件，排程未更新
        </div>

        <!-- 處理已刪除的事件：勾選的重新排程，沒勾的手動任務從系統刪除 -->
        <div v-if="inRemovedStep" class="space-y-3">
          <div v-if="resolveFailed" class="rounded-lg border border-error/40 bg-error/10 px-3 py-2 text-sm">
            處理失敗，請重試
          </div>
          <p class="text-sm text-gray-500 dark:text-gray-400 text-center">
            勾選要重新排程的任務；沒勾的任務會從系統刪除。
          </p>

          <label
            v-for="item in removedItems"
            :key="item.id"
            class="flex items-start gap-3 rounded-lg border border-default bg-white dark:bg-gray-800 px-3 py-3"
          >
            <input
              type="checkbox"
              class="mt-1"
              :checked="isRescheduled(item)"
              :disabled="item.source !== 'manual'"
              @change="onRescheduleToggle(item, $event)"
            >
            <div class="min-w-0 flex-1 space-y-0.5">
              <div class="flex items-center gap-2">
                <UIcon :name="sourceIcon[item.source]" class="w-3.5 h-3.5 text-gray-400 flex-shrink-0" />
                <span class="text-sm font-medium truncate">{{ item.title }}</span>
              </div>
              <p v-if="item.parent_id" class="text-xs text-gray-400 truncate">{{ stageLabel(item) }}</p>
              <p class="text-xs text-gray-500 dark:text-gray-400">Google 日曆上的事件已被刪除</p>
              <p v-if="item.source !== 'manual'" class="text-xs text-gray-500 dark:text-gray-400">外部平台的項目會重新排程</p>
              <p v-if="laterStagesNote(item)" class="text-xs text-warning">{{ laterStagesNote(item) }}</p>
            </div>
          </label>

          <div class="flex justify-end gap-3 mt-6">
            <UButton type="button" variant="link" class="bg-gray-200 text-black hover:bg-gray-300" @click="enterWizardAfterRemovedStep">
              取消
            </UButton>
            <UButton :loading="resolving" :disabled="resolving" @click="handleResolveRemoved">
              下一步
            </UButton>
          </div>
        </div>

        <!-- Step 1 沒有可排程的任務：說明原因 -->
        <div v-else-if="step === 1 && !hasTasks" data-testid="wizard-empty" class="text-center space-y-3 py-8">
          <template v-if="loadFailed">
            <p class="text-sm text-gray-700 dark:text-gray-300">暫時無法載入任務</p>
          </template>
          <template v-else-if="emptyState.total === 0">
            <p class="text-sm text-gray-700 dark:text-gray-300">目前沒有任務</p>
          </template>
          <template v-else>
            <p class="text-sm text-gray-700 dark:text-gray-300">目前沒有可以排程的任務。</p>
            <ul class="text-sm text-gray-500 dark:text-gray-400 space-y-1">
              <li>已排進 Google 日曆的任務：{{ emptyState.scheduled }} 個</li>
              <li>已完成的任務：{{ emptyState.done }} 個</li>
            </ul>
            <p class="text-sm text-gray-500 dark:text-gray-400">已逾期的任務可以在首頁的今日卡片重新排程。</p>
          </template>
        </div>

        <!-- Step 1：三欄拖拉排序 -->
        <div v-else-if="step === 1">
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
                  <div class="min-w-0 flex-1">
                    <p class="text-sm truncate">{{ task.title }}</p>
                    <p v-if="task.parent_id" class="text-xs text-gray-400 truncate">{{ stageLabel(task) }}</p>
                  </div>
                </div>
              </div>

              <div v-if="columns[p].length === 0" class="text-center text-xs text-gray-400 py-6">
                拖任務到這裡
              </div>
            </div>
          </div>

          <div class="flex justify-end gap-3 mt-6">
            <UButton :disabled="!hasTasks" loading-auto :loading="saving" @click="handleConfirmOrder">
              下一步
            </UButton>
          </div>
        </div>

        <!-- Step 2：確認截止日期與所需時長、排程偏好設定 -->
        <div v-else-if="step === 2" class="space-y-3">
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
                  <input type="checkbox" :checked="rule.all_day" @change="toggleAllDay(rule, ($event.target as HTMLInputElement).checked)">
                  整天
                </label>
                <input v-model="rule.start_time" type="time" :disabled="rule.all_day" class="border border-default rounded-md px-1 py-0.5 text-xs bg-transparent disabled:opacity-50">
                <span class="text-xs text-gray-400">～</span>
                <input v-model="rule.end_time" type="time" :disabled="rule.all_day" class="border border-default rounded-md px-1 py-0.5 text-xs bg-transparent disabled:opacity-50">
                <UButton size="xs" variant="ghost" color="error" @click="removeBlockedRecurringRule(index)">移除</UButton>
              </div>
            </div>

            <div>
              <div class="flex items-center justify-between mb-2">
                <span class="text-xs font-semibold text-gray-600 dark:text-gray-400">額外不排的時段（過了就自動移除）</span>
                <UButton size="xs" variant="soft" @click="addBlockedException">新增例外時段</UButton>
              </div>
              <p v-if="preferences.blocked_exceptions.length === 0" class="text-xs text-gray-400">
                沒有額外的例外時段
              </p>
              <div
                v-for="(exception, index) in preferences.blocked_exceptions"
                :key="index"
                class="flex flex-wrap items-center gap-2 mb-2"
              >
                <input
                  type="datetime-local"
                  class="border border-default rounded-md px-2 py-1 text-xs bg-transparent"
                  :value="toDatetimeLocal(exception.start)"
                  @change="onExceptionStartInput(exception, $event)"
                >
                <span class="text-xs text-gray-400">～</span>
                <input
                  type="datetime-local"
                  class="border border-default rounded-md px-2 py-1 text-xs bg-transparent"
                  :value="toDatetimeLocal(exception.end)"
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
              <span v-if="task.parent_id" class="text-xs text-gray-400 truncate">{{ stageLabel(task) }}</span>
            </div>
            <div class="flex flex-wrap gap-4">
              <label class="text-xs text-gray-500 dark:text-gray-400 flex flex-col gap-1">
                截止日期
                <input
                  type="datetime-local"
                  class="border border-default rounded-md px-2 py-1 text-sm bg-transparent"
                  :value="toDatetimeLocal(task.due_date)"
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

        <!-- Step 3：排程建議 -->
        <ScheduleSuggestion v-else @regenerate="regenerate" />
      </template>
    </div>
  </div>
</template>
