import type { FormError, FormSubmitEvent } from '@nuxt/ui'
import { DateFormatter, getLocalTimeZone, fromDate, toZoned, type DateValue } from '@internationalized/date'
import { ref, computed, reactive, shallowRef } from 'vue'
import { createSharedComposable } from '@vueuse/core'
import type { Task } from '~/types/manualTask'
import { getFriendlyErrorTitle } from '@/utils/errorMessages'

// 共用狀態：AppHeader 的「+」按鈕要能打開 TaskForm 裡的 Modal
function useTaskFormImpl() {
    const showEditModal = ref(false)

    const { getToken } = useAuth()
    const { user } = useUser()
    const currentUserId = computed(() => user.value?.id ?? '')
    const toast = useToast()

    const config = useRuntimeConfig()
    const BASE_URL = config.public.apiBaseUrl

    const priorityItems = ref([
      { label: '高', value: 'High' },
      { label: '中', value: 'Medium' },
      { label: '低', value: 'Low' },
    ])

    const df = new DateFormatter('zh-TW', { dateStyle: 'medium' })
    const timeZone = getLocalTimeZone()
    const today = fromDate(new Date(), timeZone)
    // null 代表「無期限」
    // UCalendar 可能給三種 DateValue，轉 Date 前要先用 toZoned 統一
    const modelValue = shallowRef<DateValue | null>(today)
    const minDate = today
    const toJsDate = (value: DateValue) => toZoned(value, timeZone).toDate()
    const displayDate = computed(() =>
        modelValue.value
            ? df.format(toJsDate(modelValue.value))
            : '無期限'
    )
    function clearDueDate() {
        modelValue.value = null
    }

    // 和「沒有任務」分開判斷，否則沒有任務時會一直顯示 Skeleton
    const loading = ref(true)
    const all_tasks = ref<Task[]>([])
    const editing_task = ref<Task | null>(null)
    const isEditMode = computed(() => editing_task.value !== null)

    // 擋重複送出，避免連點建出重複任務
    const submitting = ref(false)

    const state = reactive({
        user_id: currentUserId.value,
        title: '',
        description: '',
        status: 'To Do',
        priority: '',
        duration: '' as string | number, // 留空由後端用 AI 推斷
        inference_hint: '',
    })

    // 只有標題必填，其他欄位留空由 AI 推斷
    const validate = (s: typeof state): FormError[] => {
        const errors: FormError[] = []
        if (!s.title) errors.push({ name: 'title', message: 'Required' })
        return errors
    }

    function resetForm() {
        state.title = ''
        state.description = ''
        state.priority = ''
        state.duration = ''
        state.inference_hint = ''
        modelValue.value = today
        editing_task.value = null
    }

    // 留空要送 null，後端的 Optional[int] 收到 "" 會驗證失敗
    function parseDuration(value: string | number): number | null {
        if (value === '' || value === null || value === undefined) return null
        const n = Number(value)
        return Number.isFinite(n) ? n : null
    }

    function buildInferenceSummary(result: Task): { title: string; description?: string } | null {
        const inferredFields: string[] = result?.inferred_fields ?? []
        if (!inferredFields.length) return null

        const labelMap: Record<string, string> = {
            priority: `優先權：${result.priority}`,
            duration: `預估時長：${result.duration} 分鐘`,
        }
        const parts = inferredFields.map((f) => labelMap[f] ?? f)

        return {
            title: `已建立，AI 幫你補上 ${parts.join('、')}`,
            description: result?.inference_reason ?? undefined,
        }
    }

    function resetAndClose() {
        resetForm()
        showEditModal.value = false
    }


    async function fetchTasks() {
        loading.value = true
        try{
            const token = await getToken.value()
            if (!token) {
                throw new Error('JWT token is missing or invalid');
            }
            const res = await $fetch<Task[]>(`${BASE_URL}/manual-tasks/me`, {
                method: 'GET',
                headers: { Authorization: `Bearer ${token}`}
            })
            all_tasks.value = res
        } catch (err) {
            console.error(err)
        } finally {
            loading.value = false
        }
    }
 

    function startEditTask(task: Task | null) {
        if (task) {
            editing_task.value = task
            state.user_id = task.user_id
            state.title = task.title
            state.description = task.description
            state.priority = task.priority
            state.status = task.status
            state.duration = task.duration ?? ''
            state.inference_hint = task.inference_hint ?? ''
            modelValue.value = task.due_date ? fromDate(new Date(task.due_date), timeZone) : null
        } else { // 如果沒有傳入任務，則重置表單
            editing_task.value = null
            resetForm()
        }
        showEditModal.value = true
    }

    function delay(ms: number) {
        return new Promise((resolve) => setTimeout(resolve, ms))
    }

    async function onSubmit(_e: FormSubmitEvent<typeof state>) {
        if (submitting.value) return
        submitting.value = true
        try {
            const token = await getToken.value()
            const dueDate = modelValue.value ? toJsDate(modelValue.value).toISOString() : null
            const payload = {
                user_id: state.user_id,
                title: state.title,
                description: state.description,
                priority: state.priority || null,
                due_date: dueDate,
                status: state.status,
                duration: parseDuration(state.duration),
                inference_hint: state.inference_hint || null,
            }
            const result = await $fetch<Task>(`${BASE_URL}/manual-tasks/`, {
                method: 'POST',
                body: payload,
                headers: { Authorization: `Bearer ${token}` }
            })

            const inferenceSummary = buildInferenceSummary(result)
            if (inferenceSummary) {
                toast.add({
                    title: inferenceSummary.title,
                    description: inferenceSummary.description,
                    color: 'info',
                    icon: 'i-lucide-sparkles',
                })
            } else {
                toast.add({ title: '儲存成功', color: 'success', icon: 'i-lucide-check' })
            }

            // 讓使用者看到 toast 再關閉 Modal，這段時間按鈕仍不能按
            await delay(300)
            await fetchTasks()
            resetAndClose()
        } catch (err) {
            console.error(err)
            toast.add({ title: getFriendlyErrorTitle(err, '儲存失敗'), color: 'error', icon: 'i-lucide-x' })
        } finally {
            submitting.value = false
        }
    }

    async function onEdit(_e: FormSubmitEvent<typeof state>) {
        if( !editing_task.value ) return
        if (submitting.value) return
        submitting.value = true
        try {
            const token = await getToken.value()
            const dueDate = modelValue.value ? toJsDate(modelValue.value).toISOString() : null
            const payload = {
                user_id: state.user_id,
                title: state.title,
                description: state.description,
                priority: state.priority || null,
                due_date: dueDate,
                status: state.status,
                duration: parseDuration(state.duration),
                inference_hint: state.inference_hint || null,
            }
            await $fetch(`${BASE_URL}/manual-tasks/${editing_task.value?.id}`, {
                method: 'PUT',
                body: payload,
                headers: { Authorization: `Bearer ${token}` }
            })
            toast.add({ title: '儲存成功', color: 'success', icon: 'i-lucide-check' })
            await delay(300)
            await fetchTasks()
            resetAndClose()
        } catch (err) {
            console.error(err)
            toast.add({ title: getFriendlyErrorTitle(err, '儲存失敗'), color: 'error', icon: 'i-lucide-x' })
        } finally {
            submitting.value = false
        }
    }


    async function onDelete() {
        if (!editing_task.value?.id) return
        if (!window.confirm('你確定要刪除這個任務嗎？')) return

        try {
            const token = await getToken.value()
            await $fetch(`${BASE_URL}/manual-tasks/${editing_task.value.id}`, {
                method: 'DELETE',
                headers: { Authorization: `Bearer ${token}` }
            })
            toast.add({ title: '刪除成功', color: 'success', icon: 'i-lucide-trash-2' })
            await fetchTasks()
            resetAndClose()
        } catch (err) {
            console.error(err)
            toast.add({ title: getFriendlyErrorTitle(err, '刪除失敗'), color: 'error', icon: 'i-lucide-x' })
        }
    }


    function onCancel() {
        resetAndClose()
    }

    return {
        user,
        showEditModal,
        state,
        modelValue,
        minDate,
        displayDate,
        clearDueDate,
        priorityItems,
        validate,
        loading,
        submitting,
        all_tasks,
        editing_task,
        isEditMode,
        fetchTasks,
        startEditTask,
        onSubmit,
        onEdit,
        onDelete,
        onCancel,
    }
}

export const useTaskForm = createSharedComposable(useTaskFormImpl)


