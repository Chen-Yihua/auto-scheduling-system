import { describe, it, expect, vi, beforeEach } from 'vitest'
import { shallowMount, flushPromises } from '@vue/test-utils'
import { ref, defineComponent, h } from 'vue'
import type { Component } from 'vue'

// ---------- 2. 被測元件 ----------
import TaskForm from '~/components/tasks/TaskForm.vue'
import { useTaskForm } from '~/composables/useTaskForm'

// ---------- 1. Nuxt/全域依賴 Stub ----------
const tokenSpy = vi.fn().mockResolvedValue('dummy-token')
const toastSpy = { add: vi.fn() }
let fetchSpy = vi.fn()

vi.stubGlobal('useAuth',         () => ({ getToken: { value: tokenSpy } }))
vi.stubGlobal('useUser',         () => ({ user: ref({ id: 'u1' }) }))
vi.stubGlobal('useToast',        () => toastSpy)
vi.stubGlobal('useRuntimeConfig',() => ({ public: { apiBaseUrl: 'http://localhost:8000' } }))
vi.stubGlobal('$fetch',          (...args: unknown[]) => fetchSpy(...args))

// useSchedulableTasks 明確 import useAuth，stubGlobal 攔不到，要 mock 整個模組
vi.mock('@clerk/vue', () => ({
  useAuth: () => ({ getToken: { value: tokenSpy } }),
}))

// ---------- 3. UI 元件 Stub ----------
// 要轉傳原生事件，否則 @click.stop 會對 undefined 呼叫 stopPropagation
const StubButton = defineComponent({
  name: 'UButton',
  emits: ['click'],
  setup(_, { emit, slots }) {
    return () =>
      h('button', { onClick: (e: Event) => emit('click', e) }, slots.default ? slots.default() : '')
  },
})

// 帶 slot 的 UCard（讓任務標題渲染出來）
const StubCard = defineComponent({
  name: 'UCard',
  setup(_, { slots }) {
    return () => 
        h('div', { class: 'u-card-stub' }, [
            slots.header && slots.header(),
            slots.default && slots.default(),
            slots.footer && slots.footer(),
        ])
  },
})

// 反映 open prop 的 UModal
const StubModal = defineComponent({
  name: 'UModal',
  props: { open: { type: Boolean, default: false } },
  setup(props, { slots }) {
    return () =>
      h(
        'div',
        { class: 'u-modal-stub', 'data-open': props.open ? 'true' : 'false' },
        slots.default ? slots.default() : '',
      )
  },
})

// 其他元件直接 true stub
const uiStubs: Record<string, boolean | Component> = {
  UButton: StubButton,
  UCard: StubCard,
  UModal: StubModal,
  UForm: true,
  UInput: true,
  UTextarea: true,
  UFormField: true,
  USelect: true,
  UPopover: true,
  UCalendar: true,
  USkeleton: true,
  UBadge: true,
  UIcon: true,
  NuxtLink: { template: '<a><slot /></a>' },
}

// ---------- 4. 假任務工具 ----------
// /manual-tasks/me 的完整資料，只給編輯表單用；列表用 fakeSchedulableTasks
const fakeTasks = (n = 1) =>
  Array.from({ length: n }, (_, i) => ({
    id: `t${i}`,
    user_id: 'u1',
    title: `任務${i}`,
    description: '測試內容',
    priority: 'Low',
    status: 'To Do',
    due_date: new Date().toISOString(),
  }))

const fakeSchedulableTasks = (n = 1) =>
  Array.from({ length: n }, (_, i) => ({
    id: `manual:t${i}`,
    source: 'manual',
    title: `任務${i}`,
    description: '測試內容',
    status: 'To Do',
    priority: 'Low',
    duration: null,
    due_date: new Date().toISOString(),
    sort_order: null,
    calendar_event_id: null,
    url: null,
  }))

// 依 URL 回傳對應的假資料，不依賴呼叫順序
function mockFetchByUrl(responses: Record<string, unknown>) {
  fetchSpy.mockImplementation(async (url: string) => {
    const match = Object.keys(responses).find((key) => url.includes(key))
    return match ? responses[match] : []
  })
}

// ---------- 5. 測試 ----------
describe('TaskForm.vue (render)', () => {
  beforeEach(() => {
    fetchSpy = vi.fn()
    toastSpy.add.mockClear()
    tokenSpy.mockClear()
  })

  it('沒有任務時顯示提示文字，抓取完成後不該一直卡在 Skeleton', async () => {
    mockFetchByUrl({ '/manual-tasks/me': [], '/schedule/tasks': [] })

    const wrapper = shallowMount(TaskForm, { global: { stubs: uiStubs } })
    await flushPromises()

    expect(wrapper.findAll('u-skeleton-stub').length).toBe(0)
    expect(wrapper.text()).toContain('目前沒有任務')
  })

  it('有任務時顯示卡片並含正確標題', async () => {
    const tasks = fakeSchedulableTasks(2)
    mockFetchByUrl({ '/manual-tasks/me': [], '/schedule/tasks': tasks })

    const wrapper = shallowMount(TaskForm, { global: { stubs: uiStubs } })
    await flushPromises()

    // Slot 已渲染：文字應包含每個任務標題
    tasks.forEach(t => expect(wrapper.text()).toContain(t.title))
    // Skeleton 不存在
    expect(wrapper.find('u-skeleton-stub').exists()).toBe(false)
  })

  it('任務列表只顯示緊湊資訊：不顯示描述，沒有截止日期時顯示「無期限」', async () => {
    const task = {
      id: 'manual:t0', source: 'manual', title: '任務0', description: '這段描述不該出現在列表上',
      status: 'To Do', priority: 'Low', duration: null, due_date: null,
      sort_order: null, calendar_event_id: null, url: null,
    }
    mockFetchByUrl({ '/manual-tasks/me': [], '/schedule/tasks': [task] })

    const wrapper = shallowMount(TaskForm, { global: { stubs: uiStubs } })
    await flushPromises()

    expect(wrapper.text()).not.toContain('這段描述不該出現在列表上')
    expect(wrapper.text()).toContain('無期限')
  })

  it('新增任務按鈕移到 Header，跟 TaskForm 共用同一份 showEditModal 狀態', async () => {
    // 按鈕在 AppHeader，這裡直接設定共用的 showEditModal 來模擬
    mockFetchByUrl({ '/manual-tasks/me': [], '/schedule/tasks': [] })

    const wrapper = shallowMount(TaskForm, { global: { stubs: uiStubs } })
    await flushPromises()

    // 初始 data-open 為 false
    expect(wrapper.find('.u-modal-stub').attributes('data-open')).toBe('false')

    const { showEditModal } = useTaskForm()
    showEditModal.value = true
    await flushPromises()

    // data-open 變 true 代表 showEditModal 已被設為 true
    expect(wrapper.find('.u-modal-stub').attributes('data-open')).toBe('true')
  })

  it('帶 limit 且任務數超過限制時，只顯示前 limit 筆，並顯示「查看全部」連結', async () => {
    const tasks = fakeSchedulableTasks(3)
    mockFetchByUrl({ '/manual-tasks/me': [], '/schedule/tasks': tasks })

    const wrapper = shallowMount(TaskForm, { props: { limit: 2 }, global: { stubs: uiStubs } })
    await flushPromises()

    expect(wrapper.text()).toContain('任務0')
    expect(wrapper.text()).toContain('任務1')
    expect(wrapper.text()).not.toContain('任務2')
    expect(wrapper.text()).toContain('查看全部（3）')
  })

  it('沒帶 limit 時顯示全部任務，不顯示「查看全部」連結', async () => {
    const tasks = fakeSchedulableTasks(3)
    mockFetchByUrl({ '/manual-tasks/me': [], '/schedule/tasks': tasks })

    const wrapper = shallowMount(TaskForm, { global: { stubs: uiStubs } })
    await flushPromises()

    tasks.forEach(t => expect(wrapper.text()).toContain(t.title))
    expect(wrapper.text()).not.toContain('查看全部')
  })

  it('外部平台項目（例如 GitHub）沒有編輯按鈕，點擊卡片會開啟原始連結', async () => {
    const githubTask = {
      id: 'github:42', source: 'github', title: 'GitHub Issue', description: null,
      status: 'To Do', priority: null, duration: null, due_date: null,
      sort_order: null, calendar_event_id: null, url: 'https://github.com/x/y/issues/42',
    }
    mockFetchByUrl({ '/manual-tasks/me': [], '/schedule/tasks': [githubTask] })
    const openSpy = vi.fn()
    vi.stubGlobal('open', openSpy)

    const wrapper = shallowMount(TaskForm, { global: { stubs: uiStubs } })
    await flushPromises()

    expect(wrapper.text()).toContain('GitHub Issue')
    expect(wrapper.text()).not.toContain('編輯')

    // 每筆任務現在是緊湊的一行（.task-row），不是獨立的 UCard
    const taskRow = wrapper.find('.task-row')
    await taskRow.trigger('click')

    expect(openSpy).toHaveBeenCalledWith('https://github.com/x/y/issues/42', '_blank')
  })

  it('按下「標記完成」會呼叫 PATCH /schedule/tasks/done', async () => {
    const task = fakeSchedulableTasks(1)[0]
    mockFetchByUrl({ '/manual-tasks/me': [], '/schedule/tasks': [task] })

    const wrapper = shallowMount(TaskForm, { global: { stubs: uiStubs } })
    await flushPromises()

    const doneButton = wrapper.findAll('button').find((b) => b.text().includes('標記完成'))
    await doneButton!.trigger('click')
    await flushPromises()

    expect(fetchSpy).toHaveBeenCalledWith(
      'http://localhost:8000/schedule/tasks/done',
      expect.objectContaining({ method: 'PATCH', body: { task_id: 'manual:t0', done: true } }),
    )
  })

  it('手動任務按「編輯」會用組合 id 去掉 "manual:" 前綴，找到 /manual-tasks/me 裡完整的任務資料並打開 Modal', async () => {
    // 編輯表單的完整欄位來自 /manual-tasks/me
    const fullTasks = fakeTasks(1)
    const schedulableTasks = fakeSchedulableTasks(1)
    mockFetchByUrl({ '/manual-tasks/me': fullTasks, '/schedule/tasks': schedulableTasks })

    const wrapper = shallowMount(TaskForm, { global: { stubs: uiStubs } })
    await flushPromises()

    const editButton = wrapper.findAll('button').find((b) => b.text().includes('編輯'))
    await editButton!.trigger('click')
    await flushPromises()

    expect(wrapper.find('.u-modal-stub').attributes('data-open')).toBe('true')
  })
})
