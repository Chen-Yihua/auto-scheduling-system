<script setup lang="ts">
import { useTaskForm } from '~/composables/useTaskForm'
import { useSchedulableTasks } from '~/composables/useSchedulableTasks'
import { onMounted, computed } from 'vue'
import type { FormSubmitEvent } from '@nuxt/ui'
import type { SchedulableTask } from '~/types/schedulableTask'
import { priorityLabel } from '~/utils/labels'

// 不傳 limit 則顯示全部
const props = defineProps<{ limit?: number }>()

const {
  user,
  showEditModal,
  state,
  modelValue,
  minDate,
  displayDate,
  clearDueDate,
  priorityItems,
  validate,
  submitting,
  all_tasks,
  isEditMode,
  fetchTasks,
  startEditTask,
  onSubmit,
  onEdit,
  onDelete,
  onCancel,
} = useTaskForm()

// 列表顯示所有來源的項目，但只有手動任務能編輯；all_tasks 用來取得編輯表單需要的完整欄位
const { tasks: schedulableTasks, loading, fetchSchedulableTasks, toggleDone } = useSchedulableTasks()

const displayedTasks = computed(() =>
  props.limit ? schedulableTasks.value.slice(0, props.limit) : schedulableTasks.value
)
const hasMoreTasks = computed(() => !!props.limit && schedulableTasks.value.length > props.limit)

const sourceIcon: Record<SchedulableTask['source'], string> = {
  manual: 'i-lucide-list-todo',
  github: 'mdi:github',
  jira: 'mdi:jira',
  moodle: 'custom:moodle',
}

function startEditSchedulableTask(item: SchedulableTask) {
  // 去掉 "manual:" 前綴才是原始 id
  const rawId = item.id.replace(/^manual:/, '')
  const task = all_tasks.value.find((t) => t.id === rawId)
  if (task) startEditTask(task)
}

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

function compactDueDate(dueDate: string): string {
  const d = new Date(dueDate)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getMonth() + 1}/${d.getDate()} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}


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


// 必須 await，UButton 的 loading-auto 才追蹤得到非同步流程
async function handleSubmit(e: FormSubmitEvent<typeof state>) {
  if (isEditMode.value) {
    await onEdit(e)
  } else {
    await onSubmit(e)
  }
  await fetchSchedulableTasks()
}

async function handleDelete() {
  await onDelete()
  await fetchSchedulableTasks()
}

// 兩個 fetch 各自處理錯誤，不用再包 try/catch
onMounted(async () => {
  await waitForUser(user)
  await Promise.all([fetchTasks(), fetchSchedulableTasks()])
})
</script>

<template>
  <!-- 要用單一根節點：外層用 space-y 排版，多個 root 會多出間距 -->
  <div>
    <template v-if="user">
      <!-- 新增按鈕在 AppHeader，透過共用的 showEditModal 打開這個 Modal -->
      <UModal
        v-model:open="showEditModal"
        :dismissible="false" 
        :close-on-esc="false"
      >    
        <!-- Nuxt UI 3.1.0 的 slot 型別和新版 Vue 不相容（誤報）；升級後不再報錯時 vue-tsc 會提示移除 -->
        <!-- @vue-expect-error -->
        <template #content>
          <UForm 
              :validate="validate"
              :state="state" 
              class="space-y-6 shadow-xl rounded-2xl p-8 w-full max-w-xl bg-gray-100" 
              @submit="handleSubmit"
          >
            <h2 class="text-2xl font-bold text-gray-800">
              {{ isEditMode ? '編輯任務' : '新增任務' }}
            </h2>

            <div class="flex items-start gap-2 rounded-lg bg-blue-50 text-blue-800 text-sm px-4 py-3">
              <UIcon name="i-lucide-sparkles" class="w-4 h-4 flex-shrink-0 mt-0.5" />
              <p>
                「優先級」「預估時長」不確定的話都可以先留空，AI 會依照標題和描述自動幫你判斷。
                如果有標題、描述講不清楚、但會影響判斷的細節（例如這份報告的老師改得特別嚴格），
                可以寫在下面的「給 AI 的提醒」欄位，AI 判斷時會一併參考。
              </p>
            </div>

            <UInput
              v-model="state.title"
              name="Title" 
              :placeholder="isEditMode ? '編輯代辦事項' : '新增代辦事項'"
              size="xl" 
              required
              class="w-full bg-transparent"
            />

            <UTextarea
              v-model="state.description"
              name="Description"
              :placeholder="isEditMode ? '編輯附註（選填）' : '新增附註（選填）'"
              size="xl"
              class="w-full"
            />

            <div class="flex flex-nowrap items-center mb-4 text-m gap-x-6">
              <label class="w-26 whitespace-nowrap text-gray-700">優先級</label>
              <UFormField
                name="Priority"
                size="lg"
                hint="不確定可留空，AI 會幫你評估"
                class="flex-1"
              >
                <USelect v-model="state.priority" placeholder="留空讓 AI 評估" :items="priorityItems" />
              </UFormField>

              <label class="w-26 whitespace-nowrap text-gray-700">截止日期</label>
              <UFormField
                size="lg"
                hint="選填"
                class="flex-shrink-0"
              >
                <UPopover>
                    <UButton class="justify-start text-left w-full" color="neutral" variant="subtle" icon="i-lucide-calendar">
                        {{ displayDate }}
                    </UButton>
                    <!-- Nuxt UI 3.1.0 的 slot 型別和新版 Vue 不相容（誤報）；升級後不再報錯時 vue-tsc 會提示移除 -->
                    <!-- @vue-expect-error -->
                    <template #content>
                        <div class="p-2">
                            <UCalendar v-model="modelValue" :min-value="minDate" />
                            <UButton
                                block
                                variant="ghost"
                                color="neutral"
                                size="sm"
                                class="mt-1"
                                @click="clearDueDate"
                            >
                                無期限
                            </UButton>
                        </div>
                    </template>
                </UPopover>
              </UFormField>
            </div>

            <div class="flex flex-nowrap items-center mb-4 text-m gap-x-6">
              <label class="w-26 whitespace-nowrap text-gray-700">預估時長</label>
              <UFormField
                size="lg"
                hint="不確定可留空，AI 會幫你評估"
                class="flex-1"
              >
                <UInput
                  v-model="state.duration"
                  type="number"
                  min="1"
                  placeholder="分鐘，例如 60"
                  class="w-full"
                />
              </UFormField>
            </div>

            <div class="flex flex-nowrap items-start mb-4 text-m gap-x-6">
              <label class="w-26 whitespace-nowrap text-gray-700 mt-2">給 AI 的提醒</label>
              <UFormField
                size="lg"
                hint="優先權/時長留空讓 AI 評估時，這裡可以補充你知道、但標題描述看不出來的資訊，例如「老師改得特別嚴格」"
                class="flex-1"
              >
                <UTextarea
                  v-model="state.inference_hint"
                  placeholder="選填，例如：這份報告的老師改得特別嚴格，需要多留一點準備時間"
                  :rows="2"
                  class="w-full"
                />
              </UFormField>
            </div>

            <div class="flex items-end space-x-3 mt-2">
              <UButton 
                v-if="isEditMode" 
                type="button" 
                color="error"
                variant="soft"
                icon="i-lucide-trash-2"
                @click="handleDelete"
              >
                刪除
              </UButton>

              <div class="flex space-x-3 ml-auto">
                <UButton 
                    type="button" 
                    variant="link"
                    class="bg-gray-200 text-black hover:bg-gray-300" 
                    @click="onCancel"
                >
                    取消
                </UButton>
                <UButton
                    type="submit"
                    :loading="submitting"
                    :disabled="submitting"
                    class="bg-green-500 text-white hover:bg-green-600"

                >
                    {{ isEditMode ? '儲存變更' : '提交' }}
                </UButton>
              </div>
            </div>
          </UForm>
        </template>
      </UModal>
    </template>

    <UCard>
      <template #header>
        <div class="flex items-center gap-2">
          <UIcon name="i-lucide-list-todo" class="w-5 h-5" />
          <span class="text-lg font-semibold text-gray-900 dark:text-white">任務列表</span>
        </div>
      </template>

      <div v-if="loading">
        <USkeleton v-for="i in 3" :key="i" class="h-24 mb-4" />
      </div>
      <div
        v-else-if="schedulableTasks.length === 0"
        class="text-center text-sm text-gray-500 dark:text-gray-400 py-6"
      >
        目前沒有任務，點擊右上角的編輯圖示新增一個吧
      </div>
      <div v-else class="space-y-2">
        <div
          v-for="task in displayedTasks"
          :key="task.id"
          class="task-row rounded-lg border border-default px-3 py-2"
          :class="task.source !== 'manual' ? 'cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800' : ''"
          @click="task.source === 'manual' ? undefined : openSchedulableTask(task)"
        >
          <div class="flex items-center gap-1.5 min-w-0">
            <UIcon :name="sourceIcon[task.source]" class="w-4 h-4 flex-shrink-0 text-gray-400" />
            <span class="text-sm font-semibold truncate flex-1">{{ task.title }}</span>
            <UBadge v-if="task.priority" :color="getPriorityColor(task.priority)" variant="soft" size="sm">
              {{ priorityLabel(task.priority) }}
            </UBadge>
          </div>
          <div class="flex items-center justify-between gap-2 mt-1">
            <span v-if="task.due_date" class="text-xs text-gray-500 truncate">
              截止：{{ compactDueDate(task.due_date) }}
            </span>
            <span v-else class="text-xs text-gray-400">無期限</span>
            <div class="flex items-center gap-1 flex-shrink-0">
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
              <UButton
                icon="i-lucide-check"
                size="xs"
                :color="task.status === 'Done' ? 'neutral' : 'success'"
                variant="ghost"
                @click.stop="toggleDone(task)"
              >
                {{ task.status === 'Done' ? '取消完成' : '標記完成' }}
              </UButton>
            </div>
          </div>
        </div>
      </div>

      <template v-if="hasMoreTasks" #footer>
        <NuxtLink to="/tasks" class="text-sm text-primary hover:underline">
          查看全部（{{ schedulableTasks.length }}）
        </NuxtLink>
      </template>
    </UCard>
  </div>
</template>

