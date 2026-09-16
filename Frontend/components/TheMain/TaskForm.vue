<script setup lang="ts">
import { useTaskForm } from '~/composables/useTaskForm'
import { onMounted } from 'vue'

const {
  user,
  showEditModal,
  state,
  modelValue,
  minDate,
  displayDate,
  priorityItems,
  validate,
  all_tasks,
  editing_task,
  isEditMode,
  fetchTasks,
  startEditTask,
  onSubmit,
  onEdit,
  onDelete,
  onCancel,
} = useTaskForm()


const getPriorityColor = (priority: string | undefined) => {
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


// 等待 user 有值再 resolve
function waitForUser(userRef: Ref<any>) {
  return new Promise(resolve => {
    if (userRef.value) return resolve(userRef.value)
    const stop = watch(userRef, (val) => {
      if (val) {
        stop()
        resolve(val)
      }
    })
  })
}


// 提交表單時的處理函數
function handleSubmit(e: any) {
  if (isEditMode.value) {
    onEdit(e)
  } else {
    onSubmit(e)
  }
}

onMounted(async () => {
  try {
    await waitForUser(user)
    await fetchTasks()
  } catch (err) {
    // 可以根據 err 處理 403 或顯示提示
    console.error('❌ 載入任務失敗', err)
  }
})
</script>

<template>
  <div class="space-y-8">
    <template v-if="user">
      <div class="absolute top-18 right-6">
        <UButton 
          size="md"
          icon='mdi-file-edit' 
          color="neutral"
          @click="showEditModal = true"
          class="w-8 h-8 mb-4"
        />
      </div>

      <UModal 
        v-model:open="showEditModal"
        :dismissible="false" 
        :close-on-esc="false"
      >    
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

            <UInput 
              name="Title"
              v-model="state.title" 
              :placeholder="isEditMode ? '編輯代辦事項' : '新增代辦事項'"
              size="xl" 
              required
              class="w-full bg-transparent"
            />

            <UTextarea 
              name="Description"
              v-model="state.description" 
              :placeholder="isEditMode ? '編輯附註' : '新增附註'"
              size="xl"
              required
              class="w-full" 
            />

            <div class="flex flex-nowrap items-center mb-4 text-m gap-x-6">
              <label class="w-26 whitespace-nowrap text-gray-700">優先級</label>
              <UFormField
                name="Priority"
                size="lg"
                required
                class="flex-1"
              >
                <USelect v-model="state.priority" placeholder="選擇優先級" :items="priorityItems" />
              </UFormField>

              <label class="w-26 whitespace-nowrap text-gray-700">截止日期</label>
              <UFormField
                size="lg"
                hint="Optional"
                class="flex-shrink-0"
              >
                <UPopover>
                    <UButton class="justify-start text-left w-full" color="neutral" variant="subtle" icon="i-lucide-calendar">
                        {{ displayDate }}
                    </UButton>
                    <template #content>
                        <UCalendar v-model="modelValue" :min-value="minDate" class="p-2" />
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
                hint="優先權/時長留空讓 AI 評估時，這裡可以補充你知道、但標題描述看不出來的資訊，例如「這比想像中難」"
                class="flex-1"
              >
                <UTextarea
                  v-model="state.inference_hint"
                  placeholder="選填，例如：這個作業其實蠻花時間的"
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
                @click="onDelete"
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
                    loading-auto 
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
  </div>

  <!-- 任務清單區塊 -->
  <div class="space-y-4">
    <h2 class="text-xl font-bold mt-10 mb-4 px-4">📝 任務列表</h2>
    <div v-if="all_tasks.length === 0">
      <USkeleton class="h-24 mb-4" v-for="i in 3" :key="i" />
    </div>
    <div v-else-if="user" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
      <UCard 
        v-for="task in all_tasks"
        :key="task.id"
        :ui="{
          root: 'cursor-pointer hover:shadow-lg transition-transform duration-300 ease-in-out transform scale-100 hover:scale-105',
        }"
      >
        <template #header>
          <div class="flex justify-between items-center w-full">
            <div class="flex text-sm font-semibold truncate items-center">{{ task.title }}</div>
            <div class="flex flex-wrap items-center">
              <UBadge class="mx-1" :color="getPriorityColor(task.priority)" variant="soft" size="sm">
                {{ task.priority }}
              </UBadge>
              <UBadge class="mx-1" color="info" variant="soft" size="sm">
                {{ task.status }}
              </UBadge>
            </div>
          </div>
        </template>

        <div>
          <div class="font-medium mb-2 text-gray-800 dark:text-white truncate">
            {{ task.description }}
          </div>
          <div class="flex items-center gap-2 mb-1">
            <UIcon name="i-lucide-calendar" class="w-4 h-4 text-gray-400" />
            <span class="text-xs text-gray-500">截止：{{ new Date(task.due_date).toLocaleString() }}</span>
          </div>
        </div>

        <template #footer>
          <UButton
            icon="i-lucide-pencil"
            size="xs"
            @click.stop="startEditTask(task)"
            color="info"
            variant="soft"
          >
            編輯
          </UButton>
        </template>
      </UCard>
    </div>
  </div>
</template>

