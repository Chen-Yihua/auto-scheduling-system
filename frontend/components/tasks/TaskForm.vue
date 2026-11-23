<script setup lang="ts">
import NoticeBox from '~/components/NoticeBox.vue';
import CardTitle from '~/components/CardTitle.vue';
import PriorityBadge from '~/components/PriorityBadge.vue';
import SourceBadge from '~/components/SourceBadge.vue';
import TaskStatus from '~/components/TaskStatus.vue';
import { useTaskForm } from '~/composables/useTaskForm';
import { useSchedulableTasks } from '~/composables/useSchedulableTasks';
import { usePlatformItems } from '~/composables/usePlatformItems';
import { onMounted, computed, nextTick, ref, watch } from 'vue';
import type { SchedulableTask } from '~/types/schedulableTask';
import { scheduleStatusLabel } from '~/utils/labels';
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

const PAGE_SIZE = 30
const page = ref(1)
const pageCount = computed(() => Math.max(1, Math.ceil(topLevelTasks.value.length / PAGE_SIZE)))
// 筆數變少、目前這頁不存在時改到最後一頁；寫回 page，之後筆數變多才不會跳回舊頁碼
watch(pageCount, (count) => {
  if (page.value > count) page.value = count
})

const cardRef = ref<{ $el: HTMLElement } | null>(null)
// 只有使用者按分頁按鈕才捲動，上面自動修正頁碼時不捲，避免刪除任務後畫面跳動
async function onPageChange(next: number) {
  page.value = next
  await nextTick()
  cardRef.value?.$el.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

// 展開的主任務和它的階段放在同一組，畫面上框在一起；階段不算進每頁的筆數
const visibleGroups = computed(() =>
  topLevelTasks.value.slice((page.value - 1) * PAGE_SIZE, page.value * PAGE_SIZE).map((task) => {
    const stages = task.is_parent && expandedParents.value.has(task.id) ? (subtasksByParent.value[task.id] ?? []) : []
    return {
      task,
      expanded: stages.length > 0,
      rows: [{ task, isStage: false }, ...stages.map((stage) => ({ task: stage, isStage: true }))],
    }
  })
)

// 左邊色條：逾期紅、完成綠、其他藍灰；完成的整列淡綠底，和表頭分得開
function rowTone(task: SchedulableTask): string {
  if (overdue(task)) return 'border-l-error'
  if (task.status === 'Done') return 'border-l-fern-400 bg-fern-100/70'
  return 'border-l-palette-1'
}

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
  <UCard ref="cardRef">
    <template #header>
      <div class="flex items-center justify-between gap-2">
        <CardTitle icon="i-lucide-list-todo" title="任務列表" />
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

    <NoticeBox v-if="showNotLinked" data-testid="tasks-not-linked" icon="i-lucide-link" class="mb-4">
      尚未綁定外部平台。點右上角的頭像，在 <strong>金鑰</strong> 頁加入 GitHub、Jira 或 Moodle，那些平台的任務也會列在這裡。
    </NoticeBox>

    <div v-if="loading">
      <USkeleton v-for="i in 3" :key="i" class="h-12 mb-4" />
    </div>
    <div
      v-else-if="schedulableTasks.length === 0"
      class="text-center text-sm text-muted py-6"
    >
      目前沒有任務，點擊右上角的「新增任務」新增一個吧
    </div>
    <div v-else class="overflow-x-auto">
      <div class="min-w-[1100px] space-y-2">
        <div class="task-grid border-b-2 border-palette-2 px-3 pt-1 pb-2 text-sm font-semibold">
          <span>名稱</span>
          <span>截止日</span>
          <span>優先級</span>
          <span>完成狀態</span>
          <span>排程狀態</span>
          <span>排程時間</span>
          <span />
        </div>

        <div
          v-for="group in visibleGroups"
          :key="group.task.id"
          :class="group.expanded ? 'rounded-lg border border-palette-1 overflow-hidden' : ''"
        >
          <div
            v-for="{ task, isStage } in group.rows"
            :key="task.id"
            class="task-row task-grid border-l-4 px-3 py-2.5"
            :class="[
              isStage ? 'subtask-row border-t border-steel-200' : '',
              group.expanded ? '' : 'rounded-lg border border-default',
              task.source !== 'manual' ? 'cursor-pointer hover:bg-muted' : '',
              rowTone(task),
              isStage && task.status !== 'Done' ? 'bg-steel-50' : '',
            ]"
            @click="task.source === 'manual' ? undefined : openSchedulableTask(task)"
          >
            <!-- 名稱可以換到第二行，不截斷；來源、逾期這些標籤放在名稱下面，不跟名稱搶寬度 -->
            <div class="min-w-0 space-y-1 relative" :class="isStage ? 'pl-7' : ''">
              <UIcon v-if="isStage" name="i-lucide-corner-down-right" class="absolute left-1 top-0.5 size-4 text-steel-700" />
              <p
                data-testid="task-title"
                class="line-clamp-2 break-words text-balance"
                :class="[isStage ? 'text-sm' : 'text-base', isStage || task.status === 'Done' ? 'font-normal' : 'font-semibold']"
              >
                {{ task.title }}
              </p>
              <div
                v-if="isStage || task.source !== 'manual' || overdue(task) || task.is_parent"
                class="flex flex-wrap items-center gap-1.5"
              >
                <span v-if="isStage" class="text-xs">階段 {{ task.stage }}/{{ task.stage_count }}</span>
                <SourceBadge v-if="task.source !== 'manual'" data-testid="task-source" :source="task.source" />
                <UBadge v-if="overdue(task)" data-testid="task-overdue" color="error" variant="soft" size="sm">已逾期</UBadge>
                <span v-if="task.is_parent" class="text-xs">進度 {{ progressText(task.id) }}</span>
              </div>
            </div>

            <span data-testid="task-due" class="text-sm" :class="!task.due_date ? 'text-dimmed' : overdue(task) ? 'text-error font-semibold' : ''">
              {{ task.due_date ? compactDueDate(task.due_date) : '無期限' }}
            </span>

            <span data-testid="task-priority" class="text-sm">
              <PriorityBadge v-if="task.priority" :priority="task.priority" />
              <template v-else>—</template>
            </span>

            <span data-testid="task-status">
              <TaskStatus :status="task.status" />
            </span>

            <span data-testid="task-schedule-status" class="text-sm">
              {{ task.is_parent ? '—' : scheduleStatusLabel(!!task.calendar_event_id) }}
            </span>

            <span data-testid="task-schedule-time" class="text-sm">{{ scheduleTime(task) }}</span>

            <div class="flex flex-wrap items-center gap-1 justify-end">
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
    </div>
    <UPagination
      v-if="!loading && topLevelTasks.length > PAGE_SIZE"
      class="mt-4 flex justify-center"
      :page="page"
      :total="topLevelTasks.length"
      :items-per-page="PAGE_SIZE"
      @update:page="onPageChange"
    />
  </UCard>
</template>

<style scoped>
.task-grid {
  display: grid;
  grid-template-columns: minmax(240px, 1fr) 100px 72px 92px 84px 150px 220px;
  column-gap: 0.75rem;
  align-items: center;
}
</style>
