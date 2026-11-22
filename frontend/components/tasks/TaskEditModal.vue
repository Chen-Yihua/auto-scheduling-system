<script setup lang="ts">
import { useTaskForm } from '~/composables/useTaskForm';
import { useSchedulableTasks } from '~/composables/useSchedulableTasks';
import { onMounted, computed } from 'vue';
import type { FormSubmitEvent } from '@nuxt/ui';
import type { Task } from '~/types/manualTask';

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
  isEditMode,
  fetchTasks,
  onSubmit,
  onEdit,
  onDelete,
  onCancel,
  maxSubtasks,
  addSubtaskRow,
  removeSubtaskRow,
  isEditingParent,
  isEditingSubtask,
  editingSubtasks,
  splitBlockedReason,
  subtaskDraft,
  showSubtaskDraft,
  startAddSubtask,
  cancelAddSubtask,
  onAddSubtask,
  onDeleteSubtask,
  deleting,
  willReschedule,
} = useTaskForm();

// 主任務的優先序、時長、給 AI 的提醒由子任務決定，表單上不顯示
const hidesOwnSchedulingFields = computed(() => isEditingParent.value || (!isEditMode.value && state.subtasks.length > 0))

const { fetchSchedulableTasks } = useSchedulableTasks()

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
  await fetchSchedulableTasks();
}

async function handleAddSubtask() {
  await onAddSubtask()
  await fetchSchedulableTasks();
}

async function handleDeleteSubtask(subtask: Task) {
  await onDeleteSubtask(subtask)
  await fetchSchedulableTasks();
}

// 今日卡片、任務列表按「編輯」時要從 all_tasks 找完整的任務資料，所以這裡負責讀；錯誤由 fetchTasks 自己處理
onMounted(async () => {
  await waitForUser(user)
  await fetchTasks()
})
</script>

<template>
  <!-- 放在 AppHeader：今日卡片（首頁）與任務列表（任務管理頁）都要打開這個視窗 -->
  <template v-if="user">
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
              class="flex flex-col min-h-0 gap-6 shadow-xl rounded-2xl p-8 w-full max-w-xl bg-gray-100" 
              @submit="handleSubmit"
          >
            <h2 class="shrink-0 text-2xl font-bold text-gray-800">
              {{ isEditMode ? '編輯任務' : '新增任務' }}
            </h2>

            <div class="flex-1 min-h-0 overflow-y-auto space-y-6">

            <div v-if="willReschedule" data-testid="reschedule-note" class="flex items-start gap-2 rounded-lg bg-amber-50 text-amber-800 text-sm px-4 py-3">
              <UIcon name="i-lucide-calendar-x" class="w-4 h-4 flex-shrink-0 mt-0.5" />
              <p>儲存後會從 Google 日曆移除這個任務的時段（後面已排程的階段也會一起移除），任務回到排程清單。</p>
            </div>

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
              <label v-if="!hidesOwnSchedulingFields" class="w-26 whitespace-nowrap text-gray-700">優先級</label>
              <UFormField
                v-if="!hidesOwnSchedulingFields"
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

            <div v-if="!hidesOwnSchedulingFields" class="flex flex-nowrap items-center mb-4 text-m gap-x-6">
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

            <div v-if="!hidesOwnSchedulingFields" class="flex flex-nowrap items-start mb-4 text-m gap-x-6">
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

            <!-- 新增任務時一起拆成階段 -->
            <div v-if="!isEditMode" class="space-y-2">
              <div class="flex items-center justify-between">
                <span class="text-sm font-semibold text-gray-700">拆成階段（選填）</span>
                <UButton
                  type="button"
                  size="xs"
                  variant="soft"
                  icon="i-lucide-plus"
                  :disabled="state.subtasks.length >= maxSubtasks"
                  @click="addSubtaskRow"
                >
                  新增階段
                </UButton>
              </div>
              <p v-if="state.subtasks.length > 0" class="text-xs text-gray-500">
                依順序成為階段 1～{{ state.subtasks.length }}（最多 {{ maxSubtasks }} 個）；後面階段的優先級不能高於前面的階段，
                優先級和時長留空由 AI 評估。
              </p>
              <div
                v-for="(subtask, index) in state.subtasks"
                :key="index"
                class="flex flex-wrap items-center gap-2 rounded-md border border-default px-2 py-2"
              >
                <span class="text-xs text-gray-500 whitespace-nowrap">階段 {{ index + 1 }}</span>
                <UInput v-model="subtask.title" placeholder="階段標題" size="sm" class="flex-1 min-w-32" />
                <USelect v-model="subtask.priority" placeholder="優先級" :items="priorityItems" size="sm" class="w-24" />
                <UInput v-model="subtask.duration" type="number" min="1" placeholder="分鐘" size="sm" class="w-20" />
                <UInput v-model="subtask.due_date" type="date" size="sm" class="w-36" />
                <UButton type="button" size="xs" variant="ghost" color="error" @click="removeSubtaskRow(index)">
                  移除
                </UButton>
              </div>
            </div>

            <!-- 編輯主任務：列出階段，可以在指定位置插入或刪除 -->
            <div v-if="isEditingParent" class="space-y-2">
              <span class="text-sm font-semibold text-gray-700">階段</span>
              <div
                v-for="subtask in editingSubtasks"
                :key="subtask.id"
                class="subtask-edit-row flex items-center gap-2 rounded-md border border-default px-2 py-1"
              >
                <span class="text-xs text-gray-500 whitespace-nowrap">階段 {{ subtask.stage }}</span>
                <span class="text-sm truncate flex-1">{{ subtask.title }}</span>
                <UButton
                  type="button"
                  size="xs"
                  variant="ghost"
                  :disabled="editingSubtasks.length >= maxSubtasks"
                  @click="startAddSubtask(subtask.stage ?? 1)"
                >
                  在前面插入
                </UButton>
                <UButton
                  type="button"
                  size="xs"
                  variant="ghost"
                  color="error"
                  :disabled="deleting"
                  @click="handleDeleteSubtask(subtask)"
                >
                  刪除
                </UButton>
              </div>
              <UButton
                type="button"
                size="xs"
                variant="soft"
                icon="i-lucide-plus"
                :disabled="editingSubtasks.length >= maxSubtasks"
                @click="startAddSubtask()"
              >
                新增階段到最後
              </UButton>
            </div>

            <!-- 編輯一般任務：可以拆成階段 -->
            <div v-else-if="isEditMode && !isEditingSubtask && !showSubtaskDraft" class="text-sm">
              <p v-if="splitBlockedReason" class="text-xs text-gray-500">{{ splitBlockedReason }}</p>
              <UButton v-else type="button" size="xs" variant="soft" icon="i-lucide-list-tree" @click="startAddSubtask()">
                拆成階段
              </UButton>
            </div>

            <div v-if="showSubtaskDraft" class="space-y-2 rounded-md border border-default px-3 py-3">
              <p class="text-xs text-gray-500">
                新增為階段 {{ subtaskDraft.position }}{{ isEditingParent ? '，後面的階段編號會依序加 1' : '；這個任務會變成主任務，本身的優先級和時長改由階段決定' }}
              </p>
              <div class="flex flex-wrap items-center gap-2">
                <UInput v-model="subtaskDraft.title" placeholder="階段標題" size="sm" class="flex-1 min-w-32" />
                <USelect v-model="subtaskDraft.priority" placeholder="優先級" :items="priorityItems" size="sm" class="w-24" />
                <UInput v-model="subtaskDraft.duration" type="number" min="1" placeholder="分鐘" size="sm" class="w-20" />
                <UInput v-model="subtaskDraft.due_date" type="date" size="sm" class="w-36" />
              </div>
              <div class="flex justify-end gap-2">
                <UButton type="button" size="xs" variant="link" @click="cancelAddSubtask">取消</UButton>
                <UButton
                  type="button"
                  size="xs"
                  :loading="submitting"
                  :disabled="submitting || !subtaskDraft.title.trim()"
                  @click="handleAddSubtask"
                >
                  新增階段
                </UButton>
              </div>
            </div>
            </div>

            <div class="flex items-end space-x-3 shrink-0">
              <UButton 
                v-if="isEditMode" 
                type="button" 
                color="error"
                variant="soft"
                icon="i-lucide-trash-2"
                :disabled="deleting"
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
</template>
