import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ref } from 'vue'
import { fromDate, getLocalTimeZone } from '@internationalized/date'

// ======== 被測 hook ========
import { useTaskForm } from '~/composables/useTaskForm'
import type { Task } from '~/types/manualTask'

// ======== Nuxt auto-import 的 global mock ========
const tokenSpy  = vi.fn().mockResolvedValue('dummy-token')
const toastSpy  = { add: vi.fn() }
const fetchSpy  = vi.fn().mockResolvedValue([])

vi.stubGlobal('useAuth',         () => ({ getToken: { value: tokenSpy } }))
vi.stubGlobal('useUser',         () => ({ user: ref({ id: 'u1' }) }))
vi.stubGlobal('useToast',        () => toastSpy)
vi.stubGlobal('useRuntimeConfig',() => ({ public: { apiBaseUrl: 'http://localhost:8000' } }))
vi.stubGlobal('$fetch',          fetchSpy)

// ======== 共用工具 ========
function fakeTask(id = 't1'): Task {
  return {
    id,
    user_id: 'u1',
    title: '標題',
    description: '敘述',
    priority: 'High',
    status: 'To Do',
    due_date: new Date('2025-06-01T00:00:00Z').toISOString(),
  }
}

// 送出表單的事件，測試只需要 data 這個欄位；型別直接跟著 onSubmit / onEdit 的參數走
type SubmitEvent = Parameters<ReturnType<typeof useTaskForm>['onSubmit']>[0]
const submitEvent = (state: unknown) => ({ data: state }) as unknown as SubmitEvent

// ======== 測試 ========
describe('useTaskForm', () => {
  beforeEach(() => {
    fetchSpy.mockClear()
    toastSpy.add.mockClear()
    tokenSpy.mockClear()
  })

  it('預設狀態正確', () => {
    const ctx = useTaskForm()
    expect(ctx.showEditModal.value).toBe(false)
    expect(ctx.editing_task.value).toBe(null)
    expect(ctx.isEditMode.value).toBe(false)
    // 一開始還沒抓過資料，loading 應該是 true，不能跟「抓完發現沒有任務」混在一起判斷
    expect(ctx.loading.value).toBe(true)
  })

  it('startEditTask 能切換為編輯模式', () => {
    const ctx = useTaskForm()
    const t = fakeTask()
    ctx.startEditTask(t)
    expect(ctx.editing_task.value).toEqual(t)
    expect(ctx.isEditMode.value).toBe(true)
    expect(ctx.showEditModal.value).toBe(true)
  })

  it('validate 只要求 title——description/priority 都留給 AI 評估也能送出', () => {
    const ctx = useTaskForm()
    ctx.state.title = '標題'
    ctx.state.description = ''
    ctx.state.priority = ''

    expect(ctx.validate(ctx.state)).toEqual([])
  })

  it('validate 標題沒填時擋下來', () => {
    const ctx = useTaskForm()
    ctx.state.title = ''

    expect(ctx.validate(ctx.state)).toEqual([{ name: 'title', message: 'Required' }])
  })

  it('clearDueDate 把 modelValue 設成 null，displayDate 顯示「無期限」', () => {
    const ctx = useTaskForm()
    ctx.modelValue.value = fromDate(new Date('2025-07-01T00:00:00Z'), getLocalTimeZone())

    ctx.clearDueDate()

    expect(ctx.modelValue.value).toBe(null)
    expect(ctx.displayDate.value).toBe('無期限')
  })

  it('startEditTask 遇到 due_date 是 null 的任務時，modelValue 設成 null 而不是噴例外', () => {
    const ctx = useTaskForm()
    const t = { ...fakeTask(), due_date: null }

    expect(() => ctx.startEditTask(t)).not.toThrow()
    expect(ctx.modelValue.value).toBe(null)
  })

  it('startEditTask 會把既有的 duration/inference_hint 帶進表單', () => {
    const ctx = useTaskForm()
    const t = fakeTask()
    t.duration = 120
    t.inference_hint = '之前留給 AI 的提醒'
    ctx.startEditTask(t)

    expect(ctx.state.duration).toBe(120)
    expect(ctx.state.inference_hint).toBe('之前留給 AI 的提醒')
  })

  it('fetchTasks 會帶 token 呼叫正確路徑，並在結束後把 loading 設回 false', async () => {
    const ctx = useTaskForm()
    await ctx.fetchTasks()
    expect(fetchSpy).toHaveBeenCalledWith(
      'http://localhost:8000/manual-tasks/me',
      expect.objectContaining({
        method: 'GET',
        headers: { Authorization: 'Bearer dummy-token' },
      }),
    )
    expect(ctx.loading.value).toBe(false)
  })

  // onSubmit/onEdit 內部會等 300ms，要先呼叫、推進 fake timer，最後才 await
  async function submitAndFlushTimers(promiseFactory: () => Promise<unknown>) {
    vi.useFakeTimers()
    const promise = promiseFactory()
    await vi.runAllTimersAsync()
    await promise
    vi.useRealTimers()
  }

  // ---------- 新增任務 ----------
  it('onSubmit 會 POST 任務並刷新列表', async () => {
    const ctx = useTaskForm()
    ctx.state.title       = '新任務'
    ctx.state.description = '內容'
    ctx.state.priority    = 'Medium'
    ctx.modelValue.value  = fromDate(new Date('2025-07-01T00:00:00Z'), getLocalTimeZone())

    await submitAndFlushTimers(() => ctx.onSubmit(submitEvent(ctx.state)))

    // 第一次呼叫：POST
    expect(fetchSpy).toHaveBeenNthCalledWith(
      1,
      'http://localhost:8000/manual-tasks/',
      expect.objectContaining({ method: 'POST' }),
    )
    // 第二次呼叫：GET (由 fetchTasks)
    expect(fetchSpy).toHaveBeenNthCalledWith(
      2,
      'http://localhost:8000/manual-tasks/me',
      expect.objectContaining({ method: 'GET' }),
    )
    // Toast 成功訊息
    expect(toastSpy.add).toHaveBeenCalledWith(
      expect.objectContaining({ title: '儲存成功', color: 'success' }),
    )
    // 送出流程結束後，按鈕要恢復成可以再按一次的狀態
    expect(ctx.submitting.value).toBe(false)
  })

  it('送出期間重複呼叫 onSubmit 會被擋下來，不會送出第二次請求', async () => {
    const ctx = useTaskForm()
    ctx.state.title       = '新任務'
    ctx.state.description = '內容'
    ctx.state.priority    = 'Medium'
    ctx.modelValue.value  = fromDate(new Date('2025-07-01T00:00:00Z'), getLocalTimeZone())

    vi.useFakeTimers()
    const first = ctx.onSubmit(submitEvent(ctx.state))
    const second = ctx.onSubmit(submitEvent(ctx.state)) // 在第一次還沒結束前手速很快地再按一次
    await vi.runAllTimersAsync()
    await Promise.all([first, second])
    vi.useRealTimers()

    // POST 只會被打一次，不會因為連點兩下就建出兩筆任務
    const postCalls = fetchSpy.mock.calls.filter(([, options]) => options?.method === 'POST')
    expect(postCalls).toHaveLength(1)
  })

  it('onSubmit 沒填 priority 時，送給後端的是 null（不是空字串）——留給 AI 評估', async () => {
    const ctx = useTaskForm()
    ctx.state.title       = '新任務'
    ctx.state.description = '內容'
    ctx.state.priority    = ''
    ctx.modelValue.value  = fromDate(new Date('2025-07-01T00:00:00Z'), getLocalTimeZone())

    await submitAndFlushTimers(() => ctx.onSubmit(submitEvent(ctx.state)))

    expect(fetchSpy).toHaveBeenNthCalledWith(
      1,
      'http://localhost:8000/manual-tasks/',
      expect.objectContaining({ body: expect.objectContaining({ priority: null }) }),
    )
  })

  it('onSubmit 沒填 duration 時，送給後端的是 null（不是空字串）', async () => {
    const ctx = useTaskForm()
    ctx.state.title       = '新任務'
    ctx.state.description = '內容'
    ctx.state.priority    = 'Medium'
    ctx.state.duration    = ''
    ctx.modelValue.value  = fromDate(new Date('2025-07-01T00:00:00Z'), getLocalTimeZone())

    await submitAndFlushTimers(() => ctx.onSubmit(submitEvent(ctx.state)))

    expect(fetchSpy).toHaveBeenNthCalledWith(
      1,
      'http://localhost:8000/manual-tasks/',
      expect.objectContaining({ body: expect.objectContaining({ duration: null }) }),
    )
  })

  it('onSubmit 選了「無期限」時，送給後端的 due_date 是 null', async () => {
    const ctx = useTaskForm()
    ctx.state.title       = '新任務'
    ctx.state.description = ''
    ctx.state.priority    = 'Medium'
    ctx.clearDueDate()

    await submitAndFlushTimers(() => ctx.onSubmit(submitEvent(ctx.state)))

    expect(fetchSpy).toHaveBeenNthCalledWith(
      1,
      'http://localhost:8000/manual-tasks/',
      expect.objectContaining({ body: expect.objectContaining({ due_date: null }) }),
    )
  })

  it('onSubmit 有填 inference_hint 時，會一起送給後端', async () => {
    const ctx = useTaskForm()
    ctx.state.title          = '新任務'
    ctx.state.description    = '內容'
    ctx.state.priority       = 'Medium'
    ctx.state.duration       = ''
    ctx.state.inference_hint = '這比想像中難，可能要抓長一點'
    ctx.modelValue.value     = fromDate(new Date('2025-07-01T00:00:00Z'), getLocalTimeZone())

    await submitAndFlushTimers(() => ctx.onSubmit(submitEvent(ctx.state)))

    expect(fetchSpy).toHaveBeenNthCalledWith(
      1,
      'http://localhost:8000/manual-tasks/',
      expect.objectContaining({
        body: expect.objectContaining({ inference_hint: '這比想像中難，可能要抓長一點' }),
      }),
    )
  })

  it('onSubmit 沒填 inference_hint 時，送給後端的是 null', async () => {
    const ctx = useTaskForm()
    ctx.state.title          = '新任務'
    ctx.state.description    = '內容'
    ctx.state.priority       = 'Medium'
    ctx.state.duration       = ''
    ctx.state.inference_hint = ''
    ctx.modelValue.value     = fromDate(new Date('2025-07-01T00:00:00Z'), getLocalTimeZone())

    await submitAndFlushTimers(() => ctx.onSubmit(submitEvent(ctx.state)))

    expect(fetchSpy).toHaveBeenNthCalledWith(
      1,
      'http://localhost:8000/manual-tasks/',
      expect.objectContaining({ body: expect.objectContaining({ inference_hint: null }) }),
    )
  })

  it('onSubmit 有填 duration 時，送給後端的是數字', async () => {
    const ctx = useTaskForm()
    ctx.state.title       = '新任務'
    ctx.state.description = '內容'
    ctx.state.priority    = 'Medium'
    ctx.state.duration    = '90'
    ctx.modelValue.value  = fromDate(new Date('2025-07-01T00:00:00Z'), getLocalTimeZone())

    await submitAndFlushTimers(() => ctx.onSubmit(submitEvent(ctx.state)))

    expect(fetchSpy).toHaveBeenNthCalledWith(
      1,
      'http://localhost:8000/manual-tasks/',
      expect.objectContaining({ body: expect.objectContaining({ duration: 90 }) }),
    )
  })

  it('後端回傳 inferred_fields 時，顯示 AI 補值提示而不是「儲存成功」', async () => {
    const ctx = useTaskForm()
    ctx.state.title       = '新任務'
    ctx.state.description = '內容'
    ctx.state.priority    = 'Medium'
    ctx.state.duration    = ''
    ctx.modelValue.value  = fromDate(new Date('2025-07-01T00:00:00Z'), getLocalTimeZone())

    fetchSpy.mockResolvedValueOnce({
      id: 't1',
      priority: 'Medium',
      duration: 180,
      inferred_fields: ['duration'],
      inference_reason: '報告類任務通常需要較長時間準備',
    })

    await submitAndFlushTimers(() => ctx.onSubmit(submitEvent(ctx.state)))

    expect(toastSpy.add).toHaveBeenCalledWith(
      expect.objectContaining({
        title: '已建立，AI 幫你補上 預估時長：180 分鐘',
        description: '報告類任務通常需要較長時間準備',
        color: 'info',
      }),
    )
    expect(toastSpy.add).not.toHaveBeenCalledWith(
      expect.objectContaining({ title: '儲存成功' }),
    )
  })

  it('後端沒有推斷任何欄位時，維持顯示「儲存成功」', async () => {
    const ctx = useTaskForm()
    ctx.state.title       = '新任務'
    ctx.state.description = '內容'
    ctx.state.priority    = 'Medium'
    ctx.state.duration    = '60'
    ctx.modelValue.value  = fromDate(new Date('2025-07-01T00:00:00Z'), getLocalTimeZone())

    fetchSpy.mockResolvedValueOnce({
      id: 't1',
      priority: 'Medium',
      duration: 60,
      inferred_fields: [],
      inference_reason: null,
    })

    await submitAndFlushTimers(() => ctx.onSubmit(submitEvent(ctx.state)))

    expect(toastSpy.add).toHaveBeenCalledWith(
      expect.objectContaining({ title: '儲存成功', color: 'success' }),
    )
  })

  // ---------- 編輯任務 ----------
  it('onEdit 會 PUT 任務並刷新列表', async () => {
    const ctx = useTaskForm()
    const t = fakeTask('t2')
    ctx.startEditTask(t)
    ctx.state.title = '更新後標題'

    await submitAndFlushTimers(() => ctx.onEdit(submitEvent(ctx.state)))

    expect(fetchSpy).toHaveBeenNthCalledWith(
      1,
      `http://localhost:8000/manual-tasks/${t.id}`,
      expect.objectContaining({ method: 'PUT' }),
    )
    expect(fetchSpy).toHaveBeenNthCalledWith(
      2,
      'http://localhost:8000/manual-tasks/me',
      expect.objectContaining({ method: 'GET' }),
    )
    expect(toastSpy.add).toHaveBeenCalledWith(
      expect.objectContaining({ title: '儲存成功', color: 'success' }),
    )
  })

  // ---------- 刪除任務 ----------
  it('onDelete 會 DELETE 任務並刷新列表', async () => {
    const ctx = useTaskForm()
    const t = fakeTask('t3')
    ctx.startEditTask(t)

    // 讓 confirm 一定回 true
    vi.stubGlobal('window', Object.assign({}, globalThis.window, {
      confirm: () => true,
    }))

    vi.useFakeTimers()
    await ctx.onDelete()

    expect(fetchSpy).toHaveBeenNthCalledWith(
      1,
      `http://localhost:8000/manual-tasks/${t.id}`,
      expect.objectContaining({ method: 'DELETE' }),
    )
    await vi.runAllTimersAsync()
    expect(fetchSpy).toHaveBeenNthCalledWith(
      2,
      'http://localhost:8000/manual-tasks/me',
      expect.objectContaining({ method: 'GET' }),
    )
    expect(toastSpy.add).toHaveBeenCalledWith(
      expect.objectContaining({ title: '刪除成功', color: 'success' }),
    )
    vi.useRealTimers()
  })
  // ---------- 顯示、表單開關 ----------
  it('startEditTask(null) 切換成新增模式並清空表單，但一樣打開 Modal', () => {
    const ctx = useTaskForm()
    ctx.startEditTask(fakeTask())
    ctx.state.title = '舊的標題'

    ctx.startEditTask(null)

    expect(ctx.editing_task.value).toBe(null)
    expect(ctx.isEditMode.value).toBe(false)
    expect(ctx.state.title).toBe('')
    expect(ctx.showEditModal.value).toBe(true)
  })

  it('onCancel 清空表單、離開編輯模式並關閉 Modal', () => {
    const ctx = useTaskForm()
    ctx.startEditTask(fakeTask())

    ctx.onCancel()

    expect(ctx.showEditModal.value).toBe(false)
    expect(ctx.editing_task.value).toBe(null)
    expect(ctx.state.title).toBe('')
  })

  // ---------- 載入任務失敗 ----------
  it('fetchTasks API 失敗時保留原本的清單，loading 一樣會結束', async () => {
    const ctx = useTaskForm()
    ctx.all_tasks.value = [fakeTask('keep')]
    fetchSpy.mockRejectedValueOnce(new Error('boom'))
    vi.spyOn(console, 'error').mockImplementationOnce(() => {})

    await ctx.fetchTasks()

    expect(ctx.all_tasks.value.map((t) => t.id)).toEqual(['keep'])
    expect(ctx.loading.value).toBe(false)
  })

  // ---------- 新增任務：邊界情況 ----------
  it('onSubmit：duration 不是數字時送 null，不能送 NaN 給後端', async () => {
    const ctx = useTaskForm()
    ctx.startEditTask(null)
    ctx.state.title = '任務'
    ctx.state.duration = 'abc'
    fetchSpy.mockResolvedValueOnce({ id: 't1' })

    await submitAndFlushTimers(() => ctx.onSubmit(submitEvent(ctx.state)))

    expect(fetchSpy.mock.calls[0][1].body.duration).toBe(null)
  })

  it('onSubmit 失敗時顯示錯誤、Modal 保持開著讓使用者重試，送出狀態要恢復', async () => {
    const ctx = useTaskForm()
    ctx.startEditTask(null)
    ctx.state.title = '任務'
    fetchSpy.mockRejectedValueOnce(new Error('boom'))
    vi.spyOn(console, 'error').mockImplementationOnce(() => {})

    await ctx.onSubmit(submitEvent(ctx.state))

    expect(toastSpy.add).toHaveBeenCalledWith(expect.objectContaining({ title: '儲存失敗', color: 'error' }))
    expect(ctx.showEditModal.value).toBe(true)
    expect(ctx.state.title).toBe('任務') // 使用者填的內容不能被清掉
    expect(ctx.submitting.value).toBe(false)
  })

  // ---------- 編輯任務：邊界情況 ----------
  it('送出期間重複呼叫 onEdit 會被擋下來，不會送出第二次請求', async () => {
    const ctx = useTaskForm()
    ctx.startEditTask(fakeTask('t2'))

    await submitAndFlushTimers(async () => {
      const first = ctx.onEdit(submitEvent(ctx.state))
      const second = ctx.onEdit(submitEvent(ctx.state))
      await Promise.all([first, second])
    })

    const putCalls = fetchSpy.mock.calls.filter(([, opts]) => opts?.method === 'PUT')
    expect(putCalls).toHaveLength(1)
  })

  it('onEdit 改成「無期限」時，送給後端的 due_date 是 null', async () => {
    const ctx = useTaskForm()
    ctx.startEditTask(fakeTask('t2'))
    ctx.clearDueDate()

    await submitAndFlushTimers(() => ctx.onEdit(submitEvent(ctx.state)))

    expect(fetchSpy.mock.calls[0][1].body.due_date).toBe(null)
  })

  it('onEdit 失敗時顯示錯誤，Modal 保持開著', async () => {
    const ctx = useTaskForm()
    ctx.startEditTask(fakeTask('t2'))
    fetchSpy.mockRejectedValueOnce(new Error('boom'))
    vi.spyOn(console, 'error').mockImplementationOnce(() => {})

    await ctx.onEdit(submitEvent(ctx.state))

    expect(toastSpy.add).toHaveBeenCalledWith(expect.objectContaining({ title: '儲存失敗', color: 'error' }))
    expect(ctx.showEditModal.value).toBe(true)
    expect(ctx.submitting.value).toBe(false)
  })

  // ---------- 刪除任務：邊界情況 ----------
  it('onDelete 使用者在確認框按取消時不刪除', async () => {
    const ctx = useTaskForm()
    ctx.startEditTask(fakeTask('t3'))
    vi.stubGlobal('window', Object.assign({}, globalThis.window, { confirm: () => false }))

    await ctx.onDelete()

    expect(fetchSpy).not.toHaveBeenCalled()
    expect(ctx.showEditModal.value).toBe(true)
  })

  it('onDelete 失敗時顯示錯誤，Modal 保持開著', async () => {
    const ctx = useTaskForm()
    ctx.startEditTask(fakeTask('t3'))
    vi.stubGlobal('window', Object.assign({}, globalThis.window, { confirm: () => true }))
    fetchSpy.mockRejectedValueOnce(new Error('boom'))
    vi.spyOn(console, 'error').mockImplementationOnce(() => {})

    await ctx.onDelete()

    expect(toastSpy.add).toHaveBeenCalledWith(expect.objectContaining({ title: '刪除失敗', color: 'error' }))
    expect(ctx.showEditModal.value).toBe(true)
  })
})
