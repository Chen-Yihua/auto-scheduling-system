import type { FormError, FormSubmitEvent } from '@nuxt/ui'
import { DateFormatter, getLocalTimeZone, fromDate } from '@internationalized/date'
import { ref, computed, reactive, shallowRef } from 'vue'
import type { Task } from '~/types/task'

export function useTaskForm() {
    // 控制 Modal 開關
    const showEditModal = ref(false)

    // 取得使用者資訊
    const { getToken } = useAuth()
    const { user } = useUser()
    const currentUserId = computed(() => user.value?.id ?? '')
    const toast = useToast()

    // 取得 API Base URL
    const config = useRuntimeConfig()
    const BASE_URL = config.public.apiBaseUrl

    // 優先度
    const priorityItems = ref<string[]>(['High', 'Medium', 'Low'])

    // 日期設定
    const df = new DateFormatter('zh-TW', { dateStyle: 'medium' })
    const timeZone = getLocalTimeZone()
    const today = fromDate(new Date(), timeZone)
    const modelValue = shallowRef(today)
    const minDate = today
    const displayDate = computed(() =>
        modelValue.value
            ? df.format((modelValue.value as any).toDate(timeZone as any))
            : 'Select a date'
    )

    // **所有任務**
    const all_tasks = ref<Task[]>([])
    // **目前編輯的任務**
    const editing_task = ref<Task | null>(null)
    // 判斷是否編輯模式
    const isEditMode = computed(() => editing_task.value !== null)

    // 表單狀態
    const state = reactive({
        user_id: currentUserId.value,
        title: '',
        description: '',
        status: 'To Do',
        priority: '',
        due_date: '',
    })

    // 驗證表單是否填寫完成
    const validate = (s: typeof state): FormError[] => {
        const errors: FormError[] = []
        if (!s.title) errors.push({ name: 'title', message: 'Required' })
        if (!s.description) errors.push({ name: 'description', message: 'Required' })
        if (!s.priority) errors.push({ name: 'priority', message: 'Required' })
        return errors
    }

    // 重置表單
    function resetForm() {
        state.title = ''
        state.description = ''
        state.priority = ''
        state.due_date = ''
        modelValue.value = today
        editing_task.value = null
    }

    // 重置表單 並 關閉 Modal
    function resetAndClose() {
        resetForm()
        showEditModal.value = false
    }


    // 1. 載入所有任務
    async function fetchTasks() {
        try{
            const token = await getToken.value()
            if (!token) {
                throw new Error('JWT token is missing or invalid');
            }
            console.log('token', token)
            const res = await $fetch<Task[]>(`${BASE_URL}/manual_tasks/me`, {
                method: 'GET',
                headers: { Authorization: `Bearer ${token}`}
            })
            all_tasks.value = res
        } catch (err) {
            console.error(err)
        }
    }
 

    // 進入 "編輯" 模式
    function startEditTask(task: Task | null) {
        if (task) {
            editing_task.value = task
            state.user_id = task.user_id
            state.title = task.title
            state.description = task.description
            state.priority = task.priority
            state.status = task.status
            state.due_date = task.due_date
            modelValue.value = fromDate(new Date(task.due_date), timeZone)
        } else { // 如果沒有傳入任務，則重置表單
            editing_task.value = null
            resetForm()
        }
        showEditModal.value = true
    }

    // 2. 新增任務
    async function onSubmit(e: FormSubmitEvent<typeof state>) {
        try {
            const token = await getToken.value()
            const dueDate = (modelValue.value as any).toDate(timeZone as any).toISOString()
            const payload = {
                user_id: state.user_id,
                title: state.title,
                description: state.description,
                priority: state.priority,
                due_date: dueDate,
                status: state.status,
            }
            await $fetch(`${BASE_URL}/manual_tasks/`, {
                method: 'POST',
                body: payload,
                headers: { Authorization: `Bearer ${token}` }
            })
            toast.add({ title: '儲存成功', color: 'success', icon: 'i-lucide-check' })
            setTimeout(() => {
                fetchTasks()
                resetAndClose()
            }, 300)
        } catch (err) {
            console.error(err)
            toast.add({ title: '儲存失敗', color: 'error', icon: 'i-lucide-x' })
        }
    }

    // 3. 編輯任務
    async function onEdit(e: FormSubmitEvent<typeof state>) {
        if( !editing_task.value ) return
        try {
            const token = await getToken.value()
            const dueDate = (modelValue.value as any).toDate(timeZone as any).toISOString()
            const payload = {
                user_id: state.user_id,
                title: state.title,
                description: state.description,
                priority: state.priority,
                due_date: dueDate,
                status: state.status,
            }
            await $fetch(`${BASE_URL}/manual_tasks/${editing_task.value?.id}`, {
                method: 'PUT',
                body: payload,
                headers: { Authorization: `Bearer ${token}` }
            })
            toast.add({ title: '儲存成功', color: 'success', icon: 'i-lucide-check' })
            setTimeout(() => {
                fetchTasks()
                resetAndClose()
            }, 300)
        } catch (err) {
            console.error(err)
            toast.add({ title: '儲存失敗', color: 'error', icon: 'i-lucide-x' })
        }
    }


    // 4. 刪除任務
    async function onDelete() {
        if (!editing_task.value?.id) return
        if (!window.confirm('你確定要刪除這個任務嗎？')) return

        try {
            const token = await getToken.value()
            await $fetch(`${BASE_URL}/manual_tasks/${editing_task.value.id}`, {
                method: 'DELETE',
                headers: { Authorization: `Bearer ${token}` }
            })
            toast.add({ title: '刪除成功', color: 'success', icon: 'i-lucide-trash-2' })
            await fetchTasks()
            resetAndClose()
        } catch (err) {
            console.error(err)
            toast.add({ title: '刪除失敗', color: 'error', icon: 'i-lucide-x' })
        }
    }


    // 關閉 Modal
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
    }
}


