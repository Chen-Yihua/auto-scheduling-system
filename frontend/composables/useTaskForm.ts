import type { FormError, FormSubmitEvent } from '@nuxt/ui';
import { DateFormatter, getLocalTimeZone, fromDate, toZoned, type DateValue } from '@internationalized/date'
import { ref, computed, reactive, shallowRef } from 'vue'
import { createSharedComposable } from '@vueuse/core'
import type { Task, TaskWithSubtasks } from '~/types/manualTask'
import { getErrorDetail, getFriendlyErrorTitle, isAuthError, logApiError } from '@/utils/errorMessages'
import { useGoogleCalendarAuth } from '@/composables/useGoogleCalendarAuth'
import { priorityLabel } from '@/utils/labels'

// 和後端 MAX_SUBTASKS 一致
const MAX_SUBTASKS = 10

// toast 的說明文字預設不分行，'\n' 會被當成空白
const MULTILINE_TOAST_UI = { description: 'whitespace-pre-line' }

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
        logApiError(fallbackTitle, err)
        toast.add({
            title: getFriendlyErrorTitle(err, fallbackTitle),
            description: getErrorDetail(err),
            color: 'error',
            icon: 'i-lucide-x',
        })
    }

    function showDeleteError(err: unknown) {
        if (isAuthError(err)) {
            logApiError('刪除失敗', err)
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

    /**
     * 後端自動調整 AI 推斷的優先序時，提示要寫出哪個階段、從什麼改成什麼、為什麼；沒有可顯示的調整時回傳 undefined。
     * 每個階段一行，用 '\n' 分隔，toast 要搭配 MULTILINE_TOAST_UI 才會分行。
     * @param result 建立任務或新增階段的回應；階段標題從同一個回應的 subtasks 依 id 找。
     */
    function adjustedStagesText(result: TaskWithSubtasks): string | undefined {
        const subtasks = result.subtasks ?? []
        const lines = (result.priority_adjustments ?? []).flatMap((a) => {
            const adjustedIndex = subtasks.findIndex((s) => s.id === a.subtask_id)
            const comparedIndex = subtasks.findIndex((s) => s.id === a.compared_subtask_id)
            // 重送前在別的分頁刪掉了
            if (adjustedIndex < 0 || comparedIndex < 0) return []
            const compared = comparedIndex < adjustedIndex ? '前一個階段' : '後面的階段'
            // 調整就是改成比較的階段當時的值，所以比較的階段的值用 to_priority，不讀它目前的值
            return [
                `「${subtasks[adjustedIndex]!.title}」：AI 判斷為「${priorityLabel(a.from_priority)}」，`
                + `但${compared}「${subtasks[comparedIndex]!.title}」是「${priorityLabel(a.to_priority)}」，`
                + `已改成「${priorityLabel(a.to_priority)}」`,
            ]
        })
        if (!lines.length) return undefined
        return ['因後面階段比前面優先序高，已自動調整優先序：', ...lines].join('\n')
    }

    function buildStagedSummary(result: TaskWithSubtasks): { title: string; description?: string } {
        return {
            title: `已建立主任務和 ${result.subtasks?.length ?? 0} 個階段`,
            description: adjustedStagesText(result),
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
            logApiError('任務列表載入失敗', err)
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
                    ui: staged ? MULTILINE_TOAST_UI : undefined,
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
            toast.add({
                title: '已新增階段',
                description: adjustedStagesText(result),
                color: 'success',
                icon: 'i-lucide-check',
                ui: MULTILINE_TOAST_UI,
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

    // 一次只送一個刪除，避免連點重複送出；任務本身與每個階段的「刪除」共用
    const deleting = ref(false)

    /**
     * 判斷子任務是不是所屬主任務唯一的子任務。
     * 用前端已載入的任務清單判斷；另一個分頁剛改過子任務時，結果可能和後端不同。
     * @param subtask 要判斷的子任務；用它的 parent_id 找同一個主任務的子任務。
     */
    function isOnlySubtask(subtask: Task): boolean {
        return all_tasks.value.filter((t) => t.parent_id === subtask.parent_id).length <= 1
    }

    /**
     * 刪除子任務時的確認文字。從主任務的階段列表、從子任務自己的編輯視窗刪除都用這個。
     * @param subtask 要刪的子任務；同一個主任務的其他子任務與主任務名稱從已載入的任務清單找。
     */
    function subtaskDeleteConfirmMessage(subtask: Task): string {
        const question = `你確定要刪除「${subtask.title}」這個階段嗎？`
        if (!isOnlySubtask(subtask)) return question
        const parent = all_tasks.value.find((t) => t.id === subtask.parent_id)
        return `${question}\n這是最後一個階段，刪除後「${parent?.title ?? ''}」整個任務都會刪除。`
    }

    /**
     * 刪除主任務時的確認文字，依階段順序列出會一起刪除的子任務。
     * @param subtasks 這個主任務的子任務，已依階段排序。
     */
    function parentDeleteConfirmMessage(subtasks: Task[]): string {
        return [
            `這個主任務和底下 ${subtasks.length} 個子任務會一起刪除：`,
            ...subtasks.map((s, index) => `${index + 1}. ${s.title}`),
            '確定嗎？',
        ].join('\n')
    }

    /**
     * 使用者確認後送出 DELETE，成功後重抓任務清單。另一個刪除送出中時直接回傳，不送出。
     * 成功後 closeAfterDelete 為 true，或編輯中的任務已經不在重抓的清單裡時，關閉編輯視窗。
     * 失敗時顯示錯誤（授權失效時顯示重新連接 Google Calendar 的提示），編輯視窗保持開著。
     * @param task 要刪的任務（主任務、子任務或一般任務）。
     * @param confirmMessage 確認對話框的文字；使用者按取消就不刪。
     * @param closeAfterDelete 刪除成功後是否一定關閉編輯視窗；用送出前已載入的清單判斷編輯中的任務會不會一起刪掉。
     */
    async function deleteTask(task: Task, confirmMessage: string, closeAfterDelete: boolean) {
        if (deleting.value) return
        if (!window.confirm(confirmMessage)) return
        deleting.value = true
        try {
            const token = await getToken.value()
            await $fetch(`${BASE_URL}/manual-tasks/${task.id}`, {
                method: 'DELETE',
                headers: { Authorization: `Bearer ${token}` },
            })
            toast.add({ title: '刪除成功', color: 'success', icon: 'i-lucide-trash-2' })
            const editingId = editing_task.value?.id
            await fetchTasks()
            const editingGone = !!editingId && !all_tasks.value.some((t) => t.id === editingId)
            if (closeAfterDelete || editingGone) resetAndClose()
        } catch (err) {
            showDeleteError(err)
        } finally {
            deleting.value = false
        }
    }

    /**
     * 從主任務的階段列表刪除一個子任務。
     * 刪的是唯一的子任務時，主任務也一起刪掉，成功後關閉編輯視窗；
     * 已載入的清單過期（例如另一個分頁已刪掉其他階段）、重抓後主任務已經不在時也關閉；否則編輯視窗保持開著。
     * @param subtask 要刪的子任務。
     */
    async function onDeleteSubtask(subtask: Task) {
        await deleteTask(subtask, subtaskDeleteConfirmMessage(subtask), isOnlySubtask(subtask))
    }

    /**
     * 刪除編輯視窗中的任務，成功後關閉編輯視窗。
     * 確認文字依任務種類選：主任務列出會一起刪除的子任務，子任務用子任務的確認文字，一般任務用通用的確認文字。
     */
    async function onDelete() {
        const task = editing_task.value
        if (!task?.id) return
        let confirmMessage = '你確定要刪除這個任務嗎？'
        if (task.is_parent) confirmMessage = parentDeleteConfirmMessage(editingSubtasks.value)
        else if (task.parent_id) confirmMessage = subtaskDeleteConfirmMessage(task)
        await deleteTask(task, confirmMessage, true)
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
        deleting,
    }
}

export const useTaskForm = createSharedComposable(useTaskFormImpl)


