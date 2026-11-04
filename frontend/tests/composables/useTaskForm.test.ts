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
// useGoogleCalendarAuth 用到 Nuxt 的 useState
vi.stubGlobal('useState',        (_key: string, init: () => unknown) => ref(init()))

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

  it('onSubmit 失敗後重試，兩次請求帶相同的 Idempotency-Key，後端才不會重複建立', async () => {
    const ctx = useTaskForm()
    ctx.startEditTask(null)
    ctx.state.title = '任務'
    fetchSpy.mockRejectedValueOnce(new Error('timeout'))
    vi.spyOn(console, 'error').mockImplementationOnce(() => {})

    await ctx.onSubmit(submitEvent(ctx.state))
    await submitAndFlushTimers(() => ctx.onSubmit(submitEvent(ctx.state)))

    const keys = fetchSpy.mock.calls
      .filter(([, options]) => options?.method === 'POST')
      .map(([, options]) => options.headers['Idempotency-Key'])
    expect(keys).toHaveLength(2)
    expect(keys[0]).toBeTruthy()
    expect(keys[1]).toBe(keys[0])
  })

  it('建立成功後再新增下一個任務，會換一個新的 Idempotency-Key', async () => {
    const ctx = useTaskForm()
    ctx.startEditTask(null)
    ctx.state.title = '第一個'
    await submitAndFlushTimers(() => ctx.onSubmit(submitEvent(ctx.state)))
    ctx.state.title = '第二個'
    await submitAndFlushTimers(() => ctx.onSubmit(submitEvent(ctx.state)))

    const keys = fetchSpy.mock.calls
      .filter(([, options]) => options?.method === 'POST')
      .map(([, options]) => options.headers['Idempotency-Key'])
    expect(keys).toHaveLength(2)
    expect(keys[1]).not.toBe(keys[0])
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

  // ---------- 階段任務 ----------

  // FetchError 的形狀：狀態碼和後端的 detail
  const httpError = (status: number, detail: string) => Object.assign(new Error(detail), { status, data: { detail } })

  function fillStagedForm(ctx: ReturnType<typeof useTaskForm>) {
    ctx.resetForm()
    ctx.state.title = '期末報告'
    ctx.state.description = '資料結構'
    ctx.addSubtaskRow()
    ctx.addSubtaskRow()
    ctx.state.subtasks[0]!.title = '蒐集資料'
    ctx.state.subtasks[0]!.priority = 'High'
    ctx.state.subtasks[0]!.duration = '30'
    ctx.state.subtasks[0]!.due_date = '2030-01-05'
    ctx.state.subtasks[1]!.title = '寫初稿'
  }

  const parentTask = (subtaskCount = 2): Task => ({
    ...fakeTask('p1'), priority: null, duration: null, is_parent: true,
    progress: { done: 0, total: subtaskCount },
  })
  const subtaskOf = (parentId: string, stage: number): Task => ({
    ...fakeTask(`${parentId}-s${stage}`), parent_id: parentId, stage, title: `階段${stage}`,
  })

  it('AC2：不加子任務時，送出的內容和現在一樣（帶 status，沒有 subtasks）', async () => {
    const ctx = useTaskForm()
    ctx.resetForm()
    ctx.state.title = '一般任務'
    ctx.state.priority = 'Low'

    await submitAndFlushTimers(() => ctx.onSubmit(submitEvent(ctx.state)))

    const body = fetchSpy.mock.calls[0]![1].body
    expect(body).toMatchObject({ title: '一般任務', status: 'To Do', priority: 'Low' })
    expect(body).not.toHaveProperty('subtasks')
  })

  it('AC1：加了子任務時，送出主任務的標題、描述、截止日和依順序排列的子任務；主任務不帶優先序、時長、提醒、狀態', async () => {
    const ctx = useTaskForm()
    fillStagedForm(ctx)
    fetchSpy.mockResolvedValueOnce({ id: 'p1', is_parent: true, subtasks: [], priority_adjusted_stages: [] })

    await submitAndFlushTimers(() => ctx.onSubmit(submitEvent(ctx.state)))

    const body = fetchSpy.mock.calls[0]![1].body
    expect(Object.keys(body).sort()).toEqual(['description', 'due_date', 'subtasks', 'title'])
    expect(body.subtasks).toEqual([
      { title: '蒐集資料', priority: 'High', duration: 30, due_date: new Date(2030, 0, 5).toISOString() },
      { title: '寫初稿', priority: null, duration: null, due_date: null },
    ])
  })

  it('最多只能加 10 個子任務列', () => {
    const ctx = useTaskForm()
    ctx.resetForm()
    for (let i = 0; i < 12; i++) ctx.addSubtaskRow()

    expect(ctx.state.subtasks).toHaveLength(10)
  })

  it('AC6：有階段的優先序被自動調整時，建立成功的提示說明是哪些階段', async () => {
    const ctx = useTaskForm()
    fillStagedForm(ctx)
    fetchSpy.mockResolvedValueOnce({ id: 'p1', is_parent: true, subtasks: [{}, {}], priority_adjusted_stages: [2] })

    await submitAndFlushTimers(() => ctx.onSubmit(submitEvent(ctx.state)))

    const toast = toastSpy.add.mock.calls[0]![0]
    expect(toast.title).toContain('2 個階段')
    expect(toast.description).toContain('階段 2')
  })

  it('AC4：一次建立失敗時保留整份表單（含子任務），並顯示後端說明的原因', async () => {
    const ctx = useTaskForm()
    fillStagedForm(ctx)
    fetchSpy.mockRejectedValueOnce(httpError(400, '階段 2 的截止日不能晚於主任務的截止日'))
    vi.spyOn(console, 'error').mockImplementationOnce(() => {})

    await ctx.onSubmit(submitEvent(ctx.state))

    expect(ctx.state.title).toBe('期末報告')
    expect(ctx.state.subtasks.map((s) => s.title)).toEqual(['蒐集資料', '寫初稿'])
    expect(toastSpy.add).toHaveBeenCalledWith(expect.objectContaining({
      color: 'error', description: '階段 2 的截止日不能晚於主任務的截止日',
    }))
  })

  it('AC12：對一般任務新增第 1 個子任務時，表單預先填入原本的優先序和時長', () => {
    const ctx = useTaskForm()
    ctx.startEditTask({ ...fakeTask('plain'), priority: 'High', duration: 90 })

    ctx.startAddSubtask()

    expect(ctx.subtaskDraft.priority).toBe('High')
    expect(ctx.subtaskDraft.duration).toBe(90)
    expect(ctx.subtaskDraft.position).toBe(1)
  })

  it('AC13：已完成或已寫入行事曆的一般任務不能拆成階段，並說明原因', () => {
    const ctx = useTaskForm()
    ctx.startEditTask({ ...fakeTask('done'), status: 'Done' })
    expect(ctx.splitBlockedReason.value).toContain('已完成')

    ctx.startEditTask({ ...fakeTask('scheduled'), calendar_event_id: 'ev-1' })
    expect(ctx.splitBlockedReason.value).toContain('行事曆')
  })

  it('AC10：在主任務指定的位置插入子任務，送到 POST /manual-tasks/{id}/subtasks', async () => {
    const ctx = useTaskForm()
    ctx.all_tasks.value = [parentTask(), subtaskOf('p1', 1), subtaskOf('p1', 2)]
    ctx.startEditTask(ctx.all_tasks.value[0]!)
    ctx.startAddSubtask(2)
    ctx.subtaskDraft.title = '插入的階段'
    ctx.subtaskDraft.priority = 'Medium'
    fetchSpy.mockResolvedValueOnce({ id: 'p1', is_parent: true, subtasks: [], priority_adjusted_stages: [] })
    fetchSpy.mockResolvedValueOnce([parentTask(3)])

    await ctx.onAddSubtask()

    expect(fetchSpy).toHaveBeenNthCalledWith(1, 'http://localhost:8000/manual-tasks/p1/subtasks', expect.objectContaining({
      method: 'POST',
      body: { title: '插入的階段', priority: 'Medium', duration: null, due_date: null, position: 2 },
    }))
  })

  it('AC19：編輯主任務只送出標題、描述、截止日', async () => {
    const ctx = useTaskForm()
    ctx.startEditTask(parentTask())
    ctx.state.title = '新標題'

    await submitAndFlushTimers(() => ctx.onEdit(submitEvent(ctx.state)))

    const body = fetchSpy.mock.calls[0]![1].body
    expect(Object.keys(body).sort()).toEqual(['description', 'due_date', 'title'])
  })

  it('AC28：刪除主任務的確認文字寫出會一起刪除幾個子任務', async () => {
    const ctx = useTaskForm()
    const confirmSpy = vi.fn((_message: string) => false)
    vi.stubGlobal('window', Object.assign({}, globalThis.window, { confirm: confirmSpy }))
    ctx.all_tasks.value = [parentTask(3), subtaskOf('p1', 1), subtaskOf('p1', 2), subtaskOf('p1', 3)]
    ctx.startEditTask(ctx.all_tasks.value[0]!)

    await ctx.onDelete()

    expect(confirmSpy.mock.calls[0]![0]).toContain('3 個子任務')
  })

  it('AC32：刪除時 Google 授權失效（401）→ 沿用重新連接 Google Calendar 的提示', async () => {
    const ctx = useTaskForm()
    vi.stubGlobal('window', Object.assign({}, globalThis.window, { confirm: () => true }))
    ctx.startEditTask(parentTask())
    fetchSpy.mockRejectedValueOnce(httpError(401, 'Google 授權已失效，請重新連接 Google Calendar'))
    vi.spyOn(console, 'error').mockImplementationOnce(() => {})

    await ctx.onDelete()

    expect(toastSpy.add).toHaveBeenCalledWith(expect.objectContaining({
      title: 'Google Calendar 授權已失效',
      actions: [expect.objectContaining({ label: '重新連接 Google Calendar' })],
    }))
  })

  it('AC30 / AC33：刪除子任務被擋或刪事件失敗時，顯示後端說明的原因（例如改刪主任務、請重試）', async () => {
    const ctx = useTaskForm()
    vi.stubGlobal('window', Object.assign({}, globalThis.window, { confirm: () => true }))
    fetchSpy.mockRejectedValueOnce(httpError(400, '主任務只剩這一個子任務，不能刪除；要刪除請改刪主任務'))
    vi.spyOn(console, 'error').mockImplementationOnce(() => {})

    await ctx.onDeleteSubtask(subtaskOf('p1', 1))

    expect(fetchSpy).toHaveBeenCalledWith('http://localhost:8000/manual-tasks/p1-s1', expect.objectContaining({ method: 'DELETE' }))
    expect(toastSpy.add).toHaveBeenCalledWith(expect.objectContaining({
      color: 'error', description: '主任務只剩這一個子任務，不能刪除；要刪除請改刪主任務',
    }))
  })
})
