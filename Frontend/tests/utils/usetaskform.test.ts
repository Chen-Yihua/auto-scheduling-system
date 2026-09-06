// Frontend/tests/utils/useTaskForm.test.ts
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ref } from 'vue'
import { fromDate, getLocalTimeZone } from '@internationalized/date'

// ======== Nuxt auto-import 的 global mock ========
const tokenSpy  = vi.fn().mockResolvedValue('dummy-token')
const toastSpy  = { add: vi.fn() }
const fetchSpy  = vi.fn().mockResolvedValue([])

vi.stubGlobal('useAuth',         () => ({ getToken: { value: tokenSpy } }))
vi.stubGlobal('useUser',         () => ({ user: ref({ id: 'u1' }) }))
vi.stubGlobal('useToast',        () => toastSpy)
vi.stubGlobal('useRuntimeConfig',() => ({ public: { apiBaseUrl: 'http://localhost:8000' } }))
vi.stubGlobal('$fetch',          fetchSpy)

// ======== 被測 hook ========
import { useTaskForm } from '~/composables/useTaskForm'

// ======== 共用工具 ========
function fakeTask(id = 't1') {
  return {
    id,
    user_id: 'u1',
    title: '標題',
    description: '敘述',
    priority: 'High',
    status: 'To Do',
    due_date: new Date('2025-06-01T00:00:00Z').toISOString(),
  } as any
}

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
  })

  it('startEditTask 能切換為編輯模式', () => {
    const ctx = useTaskForm()
    const t = fakeTask()
    ctx.startEditTask(t)
    expect(ctx.editing_task.value).toEqual(t)
    expect(ctx.isEditMode.value).toBe(true)
    expect(ctx.showEditModal.value).toBe(true)
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

  it('fetchTasks 會帶 token 呼叫正確路徑', async () => {
    const ctx = useTaskForm()
    await ctx.fetchTasks()
    expect(fetchSpy).toHaveBeenCalledWith(
      'http://localhost:8000/manual_tasks/me',
      expect.objectContaining({
        method: 'GET',
        headers: { Authorization: 'Bearer dummy-token' },
      }),
    )
  })

  // ---------- 新增任務 ----------
  it('onSubmit 會 POST 任務並刷新列表', async () => {
    const ctx = useTaskForm()
    ctx.state.title       = '新任務'
    ctx.state.description = '內容'
    ctx.state.priority    = 'Medium'
    ctx.modelValue.value  = fromDate(new Date('2025-07-01T00:00:00Z'), getLocalTimeZone())

    vi.useFakeTimers()
    await ctx.onSubmit({ data: ctx.state } as any)

    // 第一次呼叫：POST
    expect(fetchSpy).toHaveBeenNthCalledWith(
      1,
      'http://localhost:8000/manual_tasks/',
      expect.objectContaining({ method: 'POST' }),
    )

    // 手動推進 300 ms，觸發 fetchTasks
    await vi.runAllTimersAsync()

    // 第二次呼叫：GET (由 fetchTasks)
    expect(fetchSpy).toHaveBeenNthCalledWith(
      2,
      'http://localhost:8000/manual_tasks/me',
      expect.objectContaining({ method: 'GET' }),
    )

    // Toast 成功訊息
    expect(toastSpy.add).toHaveBeenCalledWith(
      expect.objectContaining({ title: '儲存成功', color: 'success' }),
    )
    vi.useRealTimers()
  })

  it('onSubmit 沒填 duration 時，送給後端的是 null（不是空字串）', async () => {
    const ctx = useTaskForm()
    ctx.state.title       = '新任務'
    ctx.state.description = '內容'
    ctx.state.priority    = 'Medium'
    ctx.state.duration    = ''
    ctx.modelValue.value  = fromDate(new Date('2025-07-01T00:00:00Z'), getLocalTimeZone())

    vi.useFakeTimers()
    await ctx.onSubmit({ data: ctx.state } as any)

    expect(fetchSpy).toHaveBeenNthCalledWith(
      1,
      'http://localhost:8000/manual_tasks/',
      expect.objectContaining({ body: expect.objectContaining({ duration: null }) }),
    )
    await vi.runAllTimersAsync()
    vi.useRealTimers()
  })

  it('onSubmit 有填 inference_hint 時，會一起送給後端', async () => {
    const ctx = useTaskForm()
    ctx.state.title          = '新任務'
    ctx.state.description    = '內容'
    ctx.state.priority       = 'Medium'
    ctx.state.duration       = ''
    ctx.state.inference_hint = '這比想像中難，可能要抓長一點'
    ctx.modelValue.value     = fromDate(new Date('2025-07-01T00:00:00Z'), getLocalTimeZone())

    vi.useFakeTimers()
    await ctx.onSubmit({ data: ctx.state } as any)

    expect(fetchSpy).toHaveBeenNthCalledWith(
      1,
      'http://localhost:8000/manual_tasks/',
      expect.objectContaining({
        body: expect.objectContaining({ inference_hint: '這比想像中難，可能要抓長一點' }),
      }),
    )
    await vi.runAllTimersAsync()
    vi.useRealTimers()
  })

  it('onSubmit 沒填 inference_hint 時，送給後端的是 null', async () => {
    const ctx = useTaskForm()
    ctx.state.title          = '新任務'
    ctx.state.description    = '內容'
    ctx.state.priority       = 'Medium'
    ctx.state.duration       = ''
    ctx.state.inference_hint = ''
    ctx.modelValue.value     = fromDate(new Date('2025-07-01T00:00:00Z'), getLocalTimeZone())

    vi.useFakeTimers()
    await ctx.onSubmit({ data: ctx.state } as any)

    expect(fetchSpy).toHaveBeenNthCalledWith(
      1,
      'http://localhost:8000/manual_tasks/',
      expect.objectContaining({ body: expect.objectContaining({ inference_hint: null }) }),
    )
    await vi.runAllTimersAsync()
    vi.useRealTimers()
  })

  it('onSubmit 有填 duration 時，送給後端的是數字', async () => {
    const ctx = useTaskForm()
    ctx.state.title       = '新任務'
    ctx.state.description = '內容'
    ctx.state.priority    = 'Medium'
    ctx.state.duration    = '90'
    ctx.modelValue.value  = fromDate(new Date('2025-07-01T00:00:00Z'), getLocalTimeZone())

    vi.useFakeTimers()
    await ctx.onSubmit({ data: ctx.state } as any)

    expect(fetchSpy).toHaveBeenNthCalledWith(
      1,
      'http://localhost:8000/manual_tasks/',
      expect.objectContaining({ body: expect.objectContaining({ duration: 90 }) }),
    )
    await vi.runAllTimersAsync()
    vi.useRealTimers()
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

    vi.useFakeTimers()
    await ctx.onSubmit({ data: ctx.state } as any)

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
    await vi.runAllTimersAsync()
    vi.useRealTimers()
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

    vi.useFakeTimers()
    await ctx.onSubmit({ data: ctx.state } as any)

    expect(toastSpy.add).toHaveBeenCalledWith(
      expect.objectContaining({ title: '儲存成功', color: 'success' }),
    )
    await vi.runAllTimersAsync()
    vi.useRealTimers()
  })

  // ---------- 編輯任務 ----------
  it('onEdit 會 PUT 任務並刷新列表', async () => {
    const ctx = useTaskForm()
    const t = fakeTask('t2')
    ctx.startEditTask(t)
    ctx.state.title = '更新後標題'

    vi.useFakeTimers()
    await ctx.onEdit({ data: ctx.state } as any)

    expect(fetchSpy).toHaveBeenNthCalledWith(
      1,
      `http://localhost:8000/manual_tasks/${t.id}`,
      expect.objectContaining({ method: 'PUT' }),
    )
    await vi.runAllTimersAsync()
    expect(fetchSpy).toHaveBeenNthCalledWith(
      2,
      'http://localhost:8000/manual_tasks/me',
      expect.objectContaining({ method: 'GET' }),
    )
    expect(toastSpy.add).toHaveBeenCalledWith(
      expect.objectContaining({ title: '儲存成功', color: 'success' }),
    )
    vi.useRealTimers()
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
      `http://localhost:8000/manual_tasks/${t.id}`,
      expect.objectContaining({ method: 'DELETE' }),
    )
    await vi.runAllTimersAsync()
    expect(fetchSpy).toHaveBeenNthCalledWith(
      2,
      'http://localhost:8000/manual_tasks/me',
      expect.objectContaining({ method: 'GET' }),
    )
    expect(toastSpy.add).toHaveBeenCalledWith(
      expect.objectContaining({ title: '刪除成功', color: 'success' }),
    )
    vi.useRealTimers()
  })
})
