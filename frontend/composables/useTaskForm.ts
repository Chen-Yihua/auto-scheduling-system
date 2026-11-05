import type { FormError, FormSubmitEvent } from '@nuxt/ui'
import { DateFormatter, getLocalTimeZone, fromDate, toZoned, type DateValue } from '@internationalized/date'
import { ref, computed, reactive, shallowRef } from 'vue'
import { createSharedComposable } from '@vueuse/core'
import type { Task, TaskWithSubtasks } from '~/types/manualTask'
import { getErrorDetail, getFriendlyErrorTitle, isAuthError } from '@/utils/errorMessages'
import { useGoogleCalendarAuth } from '@/composables/useGoogleCalendarAuth'

// 和後端 MAX_SUBTASKS 一致
const MAX_SUBTASKS = 10

// 子任務的截止日用日期輸入（YYYY-MM-DD），空字串代表無期限
interface SubtaskDraft {
    title: string
    priority: string
    duration: string | number
    due_date: string
}

const emptySubtaskDraft = (): SubtaskDraft => ({ title: '', priority: '', duration: '', due_date: '' })

// 共用狀態：AppHeader 的「+」按鈕要能打開 TaskForm 裡的 Modal
function useTaskFormImpl() {
    const showEditModal = ref(false)

    const { getToken } = useAuth()
    const { user } = useUser()
    const currentUserId = computed(() => user.value?.id ?? '')
    const toast = useToast()
    const { reauthToast } = useGoogleCalendarAuth()

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
        // 新增任務時拆成的階段，依順序成為階段 1～N
        subtasks: [] as SubtaskDraft[],
    })

    // 只有標題必填，其他欄位留空由 AI 推斷
    const validate = (s: typeof state): FormError[] => {
        const errors: FormError[] = []
        if (!s.title) errors.push({ name: 'title', message: 'Required' })
        return errors
    }

    // 同一個表單重送時帶相同的 key，後端才不會重複建立；換新任務時才重新產生
    let idempotencyKey = crypto.randomUUID()

    function resetForm() {
        idempotencyKey = crypto.randomUUID()
        state.title = ''
        state.description = ''
        state.priority = ''
        state.duration = ''
        state.inference_hint = ''
        state.subtasks = []
        modelValue.value = today
        editing_task.value = null
        cancelAddSubtask()
    }

    function addSubtaskRow() {
        if (state.subtasks.length >= MAX_SUBTASKS) return
        state.subtasks.push(emptySubtaskDraft())
    }

    function removeSubtaskRow(index: number) {
        state.subtasks.splice(index, 1)
    }

    const isEditingParent = computed(() => !!editing_task.value?.is_parent)
    const isEditingSubtask = computed(() => !!editing_task.value?.parent_id)
    const editingSubtasks = computed(() =>
        editing_task.value?.is_parent
            ? all_tasks.value
                .filter((t) => t.parent_id === editing_task.value?.id)
                .sort((a, b) => (a.stage ?? 0) - (b.stage ?? 0))
            : [],
    )

    // 一般任務不能拆成階段的原因；null 代表可以
    const splitBlockedReason = computed(() => {
        const task = editing_task.value
        if (!task || task.is_parent || task.parent_id) return null
        if (task.status === 'Done') return '已完成的任務不能拆成階段'
        if (task.calendar_event_id) return '已寫入行事曆的任務不能拆成階段'
        return null
    })

    // 編輯中的任務要插入的子任務
    const showSubtaskDraft = ref(false)
    const subtaskDraft = reactive({ ...emptySubtaskDraft(), position: 1 })

    function startAddSubtask(position?: number) {
        const task = editing_task.value
        if (!task) return
        Object.assign(subtaskDraft, emptySubtaskDraft())
        subtaskDraft.position = position ?? editingSubtasks.value.length + 1
        // 一般任務拆成階段時，原本的優先序和時長會被清空，先帶到第 1 個階段
        if (!task.is_parent) {
            subtaskDraft.priority = task.priority ?? ''
            subtaskDraft.duration = task.duration ?? ''
        }
        showSubtaskDraft.value = true
    }

    function cancelAddSubtask() {
        showSubtaskDraft.value = false
        Object.assign(subtaskDraft, emptySubtaskDraft(), { position: 1 })
    }

    // 日期輸入是當地日期，轉成當地午夜，和主任務 UCalendar 選的日期一致
    function dateInputToIso(value: string): string | null {
        if (!value) return null
        return new Date(`${value}T00:00`).toISOString()
    }

    function subtaskPayload(draft: SubtaskDraft) {
        return {
            title: draft.title,
            priority: draft.priority || null,
            duration: parseDuration(draft.duration),
            due_date: dateInputToIso(draft.due_date),
        }
    }

    function showError(err: unknown, fallbackTitle: string) {
        console.error(err)
        toast.add({
            title: getFriendlyErrorTitle(err, fallbackTitle),
            description: getErrorDetail(err),
            color: 'error',
            icon: 'i-lucide-x',
        })
    }

    function showDeleteError(err: unknown) {
        if (isAuthError(err)) {
            console.error(err)
            toast.add(reauthToast())
            return
        }
        showError(err, '刪除失敗')
    }

    // 留空要送 null，後端的 Optional[int] 收到 "" 會驗證失敗
    function parseDuration(value: string | number): number | null {
        if (value === '' || value === null || value === undefined) return null
        const n = Number(value)
        return Number.isFinite(n) ? n : null
    }

    // 後端會把 AI 推斷的優先序調到前後階段之間，往上、往下都有可能
    function adjustedStagesText(adjusted: number[]): string | undefined {
        if (!adjusted.length) return undefined
        return `AI 判斷的優先序和前後階段衝突，已把階段 ${adjusted.join('、')} 調成落在前後階段之間`
    }

    function buildStagedSummary(result: TaskWithSubtasks): { title: string; description?: string } {
        const adjusted = result.priority_adjusted_stages ?? []
        return {
            title: `已建立主任務和 ${result.subtasks?.length ?? 0} 個階段`,
            description: adjustedStagesText(adjusted),
        }
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
            state.priority = task.priority ?? ''
            state.status = task.status
            state.duration = task.duration ?? ''
            state.inference_hint = task.inference_hint ?? ''
            state.subtasks = []
            modelValue.value = task.due_date ? fromDate(new Date(task.due_date), timeZone) : null
            cancelAddSubtask()
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
            const staged = state.subtasks.length > 0
            // 主任務的優先序、時長、狀態由子任務決定，帶了後端會回 400
            const payload = staged
                ? {
                    title: state.title,
                    description: state.description,
                    due_date: dueDate,
                    subtasks: state.subtasks.map(subtaskPayload),
                }
                : {
                    user_id: state.user_id,
                    title: state.title,
                    description: state.description,
                    priority: state.priority || null,
                    due_date: dueDate,
                    status: state.status,
                    duration: parseDuration(state.duration),
                    inference_hint: state.inference_hint || null,
                }
            const result = await $fetch<TaskWithSubtasks>(`${BASE_URL}/manual-tasks/`, {
                method: 'POST',
                body: payload,
                headers: { Authorization: `Bearer ${token}`, 'Idempotency-Key': idempotencyKey }
            })

            const inferenceSummary = staged ? buildStagedSummary(result) : buildInferenceSummary(result)
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
            showError(err, '儲存失敗')
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
            // 主任務只能改標題、描述、截止日
            const payload = isEditingParent.value
                ? { title: state.title, description: state.description, due_date: dueDate }
                : {
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
            showError(err, '儲存失敗')
        } finally {
            submitting.value = false
        }
    }

    async function onAddSubtask() {
        const task = editing_task.value
        if (!task || submitting.value) return
        submitting.value = true
        try {
            const token = await getToken.value()
            const result = await $fetch<TaskWithSubtasks>(`${BASE_URL}/manual-tasks/${task.id}/subtasks`, {
                method: 'POST',
                body: { ...subtaskPayload(subtaskDraft), position: subtaskDraft.position },
                headers: { Authorization: `Bearer ${token}` },
            })
            const adjusted = result.priority_adjusted_stages ?? []
            toast.add({
                title: '已新增階段',
                description: adjustedStagesText(adjusted),
                color: 'success',
                icon: 'i-lucide-check',
            })
            cancelAddSubtask()
            await fetchTasks()
            // 一般任務新增第 1 個子任務後變成主任務，表單要換成主任務的樣子
            editing_task.value = all_tasks.value.find((t) => t.id === task.id) ?? result
        } catch (err) {
            showError(err, '新增階段失敗')
        } finally {
            submitting.value = false
        }
    }

    async function onDeleteSubtask(subtask: Task) {
        if (!window.confirm(`你確定要刪除「${subtask.title}」這個階段嗎？`)) return
        try {
            const token = await getToken.value()
            await $fetch(`${BASE_URL}/manual-tasks/${subtask.id}`, {
                method: 'DELETE',
                headers: { Authorization: `Bearer ${token}` },
            })
            toast.add({ title: '刪除成功', color: 'success', icon: 'i-lucide-trash-2' })
            await fetchTasks()
        } catch (err) {
            showDeleteError(err)
        }
    }

    async function onDelete() {
        if (!editing_task.value?.id) return
        const confirmMessage = editing_task.value.is_parent
            ? `這個主任務和底下 ${editing_task.value.progress?.total ?? editingSubtasks.value.length} 個子任務會一起刪除，確定嗎？`
            : '你確定要刪除這個任務嗎？'
        if (!window.confirm(confirmMessage)) return

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
            showDeleteError(err)
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
        resetForm,
        maxSubtasks: MAX_SUBTASKS,
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
    }
}

export const useTaskForm = createSharedComposable(useTaskFormImpl)


