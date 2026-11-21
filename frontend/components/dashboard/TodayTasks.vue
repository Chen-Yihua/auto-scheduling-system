<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useSchedulableTasks } from '~/composables/useSchedulableTasks'
import { useTaskForm } from '~/composables/useTaskForm'
import { useGoogleCalendarAuth } from '~/composables/useGoogleCalendarAuth'
import { toDatetimeLocal } from '~/utils/datetimeLocal'
import { buildTodayView, type TodayLabel, type TodayRow } from '~/utils/todayTasks'
import { afterSaveRescheduleToast, batchRescheduleToast } from '~/utils/rescheduleToasts'
import type { SchedulableTask } from '~/types/schedulableTask'

const toast = useToast()
const { tasks, loading, loadFailed, fetchSchedulableTasks, rescheduleTasks, saveTaskFields } = useSchedulableTasks()
const { all_tasks, startEditTask, onDeleteTask } = useTaskForm()
const { reauthToast } = useGoogleCalendarAuth()

onMounted(() => { void fetchSchedulableTasks() })

const view = computed(() => buildTodayView(tasks.value, new Date()))
const hasRows = computed(() => view.value.overdue.length > 0 || view.value.today.length > 0)

const labelColor: Record<TodayLabel, 'error' | 'success' | 'info' | 'neutral'> = {
  已逾期: 'error', 已完成: 'success', 進行中: 'info', 未開始: 'neutral',
}

const pad = (n: number) => String(n).padStart(2, '0')
const clock = (d: Date) => `${pad(d.getHours())}:${pad(d.getMinutes())}`
const monthDay = (d: Date) => `${d.getMonth() + 1}/${d.getDate()}`

function dateText(task: SchedulableTask): string {
  const parts: string[] = []
  if (task.scheduled_start && task.scheduled_end) {
    const start = new Date(task.scheduled_start)
    parts.push(`時段 ${monthDay(start)} ${clock(start)}–${clock(new Date(task.scheduled_end))}`)
  }
  if (task.due_date) {
    const due = new Date(task.due_date)
    parts.push(`截止 ${monthDay(due)} ${clock(due)}`)
  }
  return parts.join('・') || '無期限'
}

const stageText = (task: SchedulableTask) => task.parent_id ? `${task.parent_title ?? ''} · 階段 ${task.stage}/${task.stage_count}` : ''

const externalTask = ref<SchedulableTask | null>(null)
const externalDue = ref('')
const externalDuration = ref<string | number>('')
const externalSaving = ref(false)

function rawManualTask(task: SchedulableTask) {
  // 去掉 "manual:" 前綴才是原始 id
  return all_tasks.value.find((t) => t.id === task.id.replace(/^manual:/, ''))
}

function onEdit(task: SchedulableTask) {
  if (task.source === 'manual') {
    const manual = rawManualTask(task)
    if (manual) startEditTask(manual, { fromToday: true })
    return
  }
  externalTask.value = task
  externalDue.value = toDatetimeLocal(task.due_date)
  externalDuration.value = task.duration ?? ''
}

function closeExternal() {
  externalTask.value = null
}

async function saveExternal() {
  const task = externalTask.value
  if (!task || externalSaving.value) return
  externalSaving.value = true
  try {
    const saved = await saveTaskFields(task.id, {
      due_date: externalDue.value ? new Date(externalDue.value).toISOString() : null,
      duration: externalDuration.value === '' ? null : Number(externalDuration.value),
    })
    if (!saved) return
    // 儲存成功才重新排程：儲存失敗時 Google 日曆上的事件不會先被刪掉
    if (task.calendar_event_id) {
      toast.add(afterSaveRescheduleToast(task.id, await rescheduleTasks([task.id]), reauthToast))
    } else {
      toast.add({ title: '儲存成功', color: 'success', icon: 'i-lucide-check' })
      await fetchSchedulableTasks()
    }
    closeExternal()
  } finally {
    externalSaving.value = false
  }
}

async function onDelete(task: SchedulableTask) {
  const manual = rawManualTask(task)
  if (!manual) return
  await onDeleteTask(manual)
  await fetchSchedulableTasks()
}

const rescheduling = ref(false)

async function batchReschedule() {
  const { batchIds, laterStageCount } = view.value
  const lines = [`會從 Google 日曆移除 ${batchIds.length} 個任務的時段，放回排程清單，確定嗎？`]
  if (laterStageCount > 0) lines.push(`另外 ${laterStageCount} 個後面階段的時段也會一起移除`)
  if (!window.confirm(lines.join('\n'))) return

  rescheduling.value = true
  try {
    const outcome = await rescheduleTasks(batchIds)
    const titleOf = (id: string) => tasks.value.find((t) => t.id === id)?.title ?? id
    toast.add(batchRescheduleToast(outcome, batchIds.length, titleOf, reauthToast))
  } finally {
    rescheduling.value = false
  }
}
</script>

<template>
  <div>
    <UModal v-if="externalTask" :open="true" :dismissible="false" :close-on-esc="false">
      <!-- Nuxt UI 3.1.0 的 slot 型別和新版 Vue 不相容（誤報）；升級後不再報錯時 vue-tsc 會提示移除 -->
      <!-- @vue-expect-error -->
      <template #content>
        <div class="space-y-4 shadow-xl rounded-2xl p-8 w-full max-w-xl bg-gray-100" data-testid="external-form">
          <h2 class="text-2xl font-bold text-gray-800">修改任務</h2>
          <p class="text-sm text-gray-700">{{ externalTask.title }}</p>
          <div
            v-if="externalTask.calendar_event_id"
            data-testid="reschedule-note"
            class="flex items-start gap-2 rounded-lg bg-amber-50 text-amber-800 text-sm px-4 py-3"
          >
            <UIcon name="i-lucide-calendar-x" class="w-4 h-4 flex-shrink-0 mt-0.5" />
            <p>儲存後會從 Google 日曆移除這個任務的時段（後面已排程的階段也會一起移除），任務回到排程清單。</p>
          </div>
          <label class="text-sm text-gray-700 flex flex-col gap-1">
            截止日期
            <input v-model="externalDue" type="datetime-local" data-testid="external-due" class="border border-default rounded-md px-2 py-1 bg-white">
          </label>
          <label class="text-sm text-gray-700 flex flex-col gap-1">
            所需時長（分鐘）
            <input v-model="externalDuration" type="number" min="1" data-testid="external-duration" class="border border-default rounded-md px-2 py-1 bg-white">
          </label>
          <div class="flex justify-end gap-3">
            <UButton type="button" variant="link" class="bg-gray-200 text-black hover:bg-gray-300" @click="closeExternal">
              取消
            </UButton>
            <UButton data-testid="external-save" :loading="externalSaving" :disabled="externalSaving" @click="saveExternal">
              儲存變更
            </UButton>
          </div>
        </div>
      </template>
    </UModal>

    <UCard>
      <template #header>
        <div class="flex items-center justify-between gap-2">
          <div class="flex items-center gap-2">
            <UIcon name="i-lucide-calendar-check" class="w-5 h-5" />
            <span class="text-lg font-semibold text-gray-900 dark:text-white">今日</span>
          </div>
          <UButton
            v-if="view.batchIds.length > 0"
            data-testid="today-batch-reschedule"
            size="xs"
            color="warning"
            variant="soft"
            :loading="rescheduling"
            :disabled="rescheduling"
            @click="batchReschedule"
          >
            批次重新排程
          </UButton>
        </div>
      </template>

      <div v-if="loading" data-testid="today-loading">
        <USkeleton v-for="i in 2" :key="i" class="h-16 mb-3" />
      </div>
      <div v-else-if="loadFailed" data-testid="today-error" class="text-center text-sm text-gray-500 dark:text-gray-400 py-6">
        暫時無法載入任務
      </div>
      <div v-else-if="!hasRows" data-testid="today-empty" class="text-center text-sm text-gray-500 dark:text-gray-400 py-6">
        今天沒有排程的任務，也沒有已逾期的任務
      </div>
      <div v-else class="space-y-2">
        <div
          v-for="row in ([...view.overdue, ...view.today] as TodayRow[])"
          :key="row.task.id"
          data-testid="today-row"
          class="rounded-lg border border-default px-3 py-2"
        >
          <div class="flex items-center gap-1.5 min-w-0">
            <span class="text-sm font-semibold truncate flex-1">{{ row.task.title }}</span>
            <UBadge data-testid="today-label" :color="labelColor[row.label]" variant="soft" size="sm">{{ row.label }}</UBadge>
          </div>
          <p v-if="row.task.parent_id" class="text-xs text-gray-400 truncate">{{ stageText(row.task) }}</p>
          <div class="flex items-center justify-between gap-2 mt-1">
            <span
              data-testid="today-date"
              class="text-xs truncate"
              :class="row.overdue ? 'text-red-600 dark:text-red-400' : 'text-gray-500'"
            >
              {{ dateText(row.task) }}
            </span>
            <div v-if="row.task.status !== 'Done'" class="flex items-center gap-1 flex-shrink-0">
              <UButton data-testid="today-edit" icon="i-lucide-pencil" size="xs" color="info" variant="ghost" @click="onEdit(row.task)">
                修改
              </UButton>
              <UButton
                v-if="row.task.source === 'manual'"
                data-testid="today-delete"
                icon="i-lucide-trash-2"
                size="xs"
                color="error"
                variant="ghost"
                @click="onDelete(row.task)"
              >
                刪除
              </UButton>
            </div>
          </div>
        </div>
      </div>
    </UCard>
  </div>
</template>
