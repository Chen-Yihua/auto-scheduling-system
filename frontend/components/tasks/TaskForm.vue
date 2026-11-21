<script setup lang="ts">
import { useTaskForm } from '~/composables/useTaskForm';
import { useSchedulableTasks } from '~/composables/useSchedulableTasks';
import { usePlatformItems } from '~/composables/usePlatformItems';
import { onMounted, computed, ref } from 'vue';
import type { SchedulableTask } from '~/types/schedulableTask';
import { priorityLabel, scheduleStatusLabel, sourceLabel, taskStatusLabel } from '~/utils/labels';
import { isOverdue } from '~/utils/todayTasks';

// 新增、編輯任務的視窗在同一頁的 TaskEditModal（tasks.vue 掛載）；這裡只負責列表
const { user, all_tasks, startEditTask, showEditModal } = useTaskForm();

// 列表顯示所有來源的項目，但只有手動任務能編輯；all_tasks 用來取得編輯表單需要的完整欄位
const { tasks: schedulableTasks, loading, fetchSchedulableTasks, toggleDone } = useSchedulableTasks()

const topLevelTasks = computed(() => schedulableTasks.value.filter((t) => !t.parent_id))
const subtasksByParent = computed(() => {
  const groups: Record<string, SchedulableTask[]> = {}
  for (const task of schedulableTasks.value) {
    if (!task.parent_id) continue
    ;(groups[task.parent_id] ??= []).push(task)
  }
  for (const group of Object.values(groups)) group.sort((a, b) => (a.stage ?? 0) - (b.stage ?? 0))
  return groups
})

const expandedParents = ref(new Set<string>())
function toggleExpanded(parentId: string) {
  const next = new Set(expandedParents.value)
  if (next.has(parentId)) next.delete(parentId)
  else next.add(parentId)
  expandedParents.value = next
}

// 展開的主任務後面接著它的階段，整份列表用同一種列
const visibleRows = computed(() =>
  topLevelTasks.value.flatMap((task) => [
    { task, isStage: false },
    ...(task.is_parent && expandedParents.value.has(task.id)
      ? (subtasksByParent.value[task.id] ?? []).map((stage) => ({ task: stage, isStage: true }))
      : []),
  ])
)

function progressText(parentId: string): string {
  const subtasks = subtasksByParent.value[parentId] ?? []
  return `${subtasks.filter((t) => t.status === 'Done').length}/${subtasks.length}`
}

function startEditSchedulableTask(item: SchedulableTask) {
  // 去掉 "manual:" 前綴才是原始 id
  const rawId = item.id.replace(/^manual:/, '')
  const task = all_tasks.value.find((t) => t.id === rawId)
  if (task) startEditTask(task)
};

function openSchedulableTask(item: SchedulableTask) {
  if (item.url) window.open(item.url, '_blank')
}

const getPriorityColor = (priority: string | null | undefined) => {
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

const statusColor = (status: string) => (status === 'Done' ? 'success' : status === 'In Progress' ? 'info' : 'neutral')

const pad = (n: number) => String(n).padStart(2, '0')
const monthDay = (d: Date) => `${d.getMonth() + 1}/${d.getDate()}`
const clock = (d: Date) => `${pad(d.getHours())}:${pad(d.getMinutes())}`

function compactDueDate(dueDate: string): string {
  const d = new Date(dueDate)
  return `${monthDay(d)} ${clock(d)}`
}

// 跨日時結束時間也帶日期
function scheduleTime(task: SchedulableTask): string {
  if (task.is_parent || !task.scheduled_start || !task.scheduled_end) return '—'
  const start = new Date(task.scheduled_start)
  const end = new Date(task.scheduled_end)
  const sameDay = monthDay(start) === monthDay(end)
  return `${monthDay(start)} ${clock(start)}–${sameDay ? '' : monthDay(end) + ' '}${clock(end)}`
}

const overdue = (task: SchedulableTask) => isOverdue(task, new Date())

// ---------- 立即同步外部平台 ----------
const github = usePlatformItems('github')
const jira = usePlatformItems('jira')
const moodle = usePlatformItems('moodle')

const syncingAll = ref(false)
// 三個平台同時同步；各自處理自己的錯誤訊息，一個失敗不影響其他
async function syncAllPlatforms() {
  syncingAll.value = true
  try {
    await Promise.allSettled([github.syncNow(), jira.syncNow(), moodle.syncNow()])
    await fetchSchedulableTasks()
  } finally {
    syncingAll.value = false
  }
}

// 帳號資料讀取失敗時不知道有沒有連結，仍讓使用者同步
const { keys, fetchKeys } = useLinkedAccount()
const accountStatus = ref<'loading' | 'ready' | 'failed'>('loading')
async function loadAccounts() {
  try {
    await fetchKeys()
    accountStatus.value = 'ready'
  } catch {
    accountStatus.value = 'failed'
  }
}
// 「要重新連結」的平台已經連結過，算有金鑰
const hasLinkedPlatform = computed(() => keys.value.some((k) => k.value || k.needsReauth))
const showSyncButton = computed(() => accountStatus.value === 'failed' || (accountStatus.value === 'ready' && hasLinkedPlatform.value))
const showNotLinked = computed(() => accountStatus.value === 'ready' && !hasLinkedPlatform.value)

function waitForUser<T>(userRef: Ref<T>): Promise<NonNullable<T>> {
  return new Promise(resolve => {
    if (userRef.value) return resolve(userRef.value as NonNullable<T>)
    const stop = watch(userRef, (val) => {
      if (val) {
        stop()
        resolve(val as NonNullable<T>)
      }
    })
  })
}

onMounted(async () => {
  await waitForUser(user)
  void loadAccounts()
  await fetchSchedulableTasks()
})
</script>

<template>
  <UCard>
    <template #header>
      <div class="flex items-center justify-between gap-2">
        <div class="flex items-center gap-2">
          <UIcon name="i-lucide-list-todo" class="w-5 h-5" />
          <span class="text-lg font-semibold text-gray-900 dark:text-white">任務列表</span>
        </div>
        <div class="flex items-center gap-2">
          <UButton
            v-if="showSyncButton"
            data-testid="tasks-sync-now"
            size="sm"
            variant="soft"
            icon="i-lucide-refresh-cw"
            :loading="syncingAll"
            :disabled="syncingAll"
            @click="syncAllPlatforms"
          >
            立即同步外部平台
          </UButton>
          <UButton data-testid="tasks-add" icon="mdi-file-edit" size="sm" @click="() => { showEditModal = true }">
            新增任務
          </UButton>
        </div>
      </div>
    </template>

    <p
      v-if="showNotLinked"
      data-testid="tasks-not-linked"
      class="text-center text-sm text-gray-500 dark:text-gray-400 pb-4"
    >
      尚未連結外部平台，請前往 <strong>帳號設定 → 金鑰</strong> 新增
    </p>

    <div v-if="loading">
      <USkeleton v-for="i in 3" :key="i" class="h-12 mb-4" />
    </div>
    <div
      v-else-if="schedulableTasks.length === 0"
      class="text-center text-sm text-gray-500 dark:text-gray-400 py-6"
    >
      目前沒有任務，點擊右上角的「新增任務」新增一個吧
    </div>
    <div v-else class="overflow-x-auto">
      <div class="min-w-[960px] space-y-2">
        <div class="task-grid px-3 text-xs text-gray-500 dark:text-gray-400">
          <span>名稱</span>
          <span>截止日</span>
          <span>優先級</span>
          <span>完成狀態</span>
          <span>排程狀態</span>
          <span>排程時間</span>
          <span />
        </div>

        <div
          v-for="{ task, isStage } in visibleRows"
          :key="task.id"
          class="task-row task-grid rounded-lg border border-default px-3 py-2"
          :class="[isStage ? 'subtask-row' : '', task.source !== 'manual' ? 'cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800' : '']"
          @click="task.source === 'manual' ? undefined : openSchedulableTask(task)"
        >
          <div class="flex items-center gap-1.5 min-w-0" :class="isStage ? 'pl-6' : ''">
            <span v-if="isStage" class="text-xs text-gray-500 flex-shrink-0">
              階段 {{ task.stage }}/{{ task.stage_count }}
            </span>
            <UBadge v-if="task.source !== 'manual'" data-testid="task-source" color="neutral" variant="outline" size="sm" class="flex-shrink-0">
              {{ sourceLabel(task.source) }}
            </UBadge>
            <span class="text-sm truncate flex-1" :class="isStage ? '' : 'font-semibold'">{{ task.title }}</span>
            <UBadge v-if="overdue(task)" data-testid="task-overdue" color="error" variant="soft" size="sm" class="flex-shrink-0">已逾期</UBadge>
            <span v-if="task.is_parent" class="text-xs text-gray-500 flex-shrink-0">
              進度 {{ progressText(task.id) }}
            </span>
          </div>

          <span data-testid="task-due" class="text-xs truncate" :class="task.due_date ? 'text-gray-500' : 'text-gray-400'">
            {{ task.due_date ? compactDueDate(task.due_date) : '無期限' }}
          </span>

          <span data-testid="task-priority" class="text-xs">
            <UBadge v-if="task.priority" :color="getPriorityColor(task.priority)" variant="soft" size="sm">
              {{ priorityLabel(task.priority) }}
            </UBadge>
            <template v-else>—</template>
          </span>

          <span data-testid="task-status" class="text-xs">
            <UBadge :color="statusColor(task.status)" variant="soft" size="sm">{{ taskStatusLabel(task.status) }}</UBadge>
          </span>

          <span data-testid="task-schedule-status" class="text-xs text-gray-500">
            {{ task.is_parent ? '—' : scheduleStatusLabel(!!task.calendar_event_id) }}
          </span>

          <span data-testid="task-schedule-time" class="text-xs text-gray-500 truncate">{{ scheduleTime(task) }}</span>

          <div class="flex items-center gap-1 justify-end">
            <UButton
              v-if="task.is_parent"
              :icon="expandedParents.has(task.id) ? 'i-lucide-chevron-up' : 'i-lucide-chevron-down'"
              size="xs"
              color="neutral"
              variant="ghost"
              @click.stop="toggleExpanded(task.id)"
            >
              {{ expandedParents.has(task.id) ? '收合階段' : '展開階段' }}
            </UButton>
            <UButton
              v-if="task.source === 'manual'"
              icon="i-lucide-pencil"
              size="xs"
              color="info"
              variant="ghost"
              @click.stop="startEditSchedulableTask(task)"
            >
              編輯
            </UButton>
            <!-- 主任務的狀態依子任務自動計算，不能手動標記 -->
            <UButton
              icon="i-lucide-check"
              size="xs"
              :color="task.status === 'Done' ? 'neutral' : 'success'"
              variant="ghost"
              :disabled="task.is_parent"
              :title="task.is_parent ? '依階段的完成狀態自動計算' : undefined"
              @click.stop="task.is_parent ? undefined : toggleDone(task)"
            >
              {{ task.status === 'Done' ? '取消完成' : '標記完成' }}
            </UButton>
          </div>
        </div>
      </div>
    </div>
  </UCard>
</template>

<style scoped>
.task-grid {
  display: grid;
  grid-template-columns: minmax(160px, 1fr) 80px 64px 72px 72px 150px 250px;
  column-gap: 0.75rem;
  align-items: center;
}
</style>
