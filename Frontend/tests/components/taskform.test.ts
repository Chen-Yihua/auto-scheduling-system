// Frontend/tests/components/taskform.test.ts
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { shallowMount, flushPromises } from '@vue/test-utils'
import { ref, defineComponent, h } from 'vue'

// ---------- 1. Nuxt/全域依賴 Stub ----------
const tokenSpy = vi.fn().mockResolvedValue('dummy-token')
const toastSpy = { add: vi.fn() }
let fetchSpy = vi.fn()

vi.stubGlobal('useAuth',         () => ({ getToken: { value: tokenSpy } }))
vi.stubGlobal('useUser',         () => ({ user: ref({ id: 'u1' }) }))
vi.stubGlobal('useToast',        () => toastSpy)
vi.stubGlobal('useRuntimeConfig',() => ({ public: { apiBaseUrl: 'http://localhost:8000' } }))
vi.stubGlobal('$fetch',          (...args: any[]) => fetchSpy(...args))

// ---------- 2. 被測元件 ----------
import TaskForm from '~/components/TheMain/TaskForm.vue'

// ---------- 3. UI 元件 Stub ----------
// 可點擊的 UButton
const StubButton = defineComponent({
  name: 'UButton',
  emits: ['click'],
  setup(_, { emit, slots }) {
    return () =>
      h('button', { onClick: () => emit('click') }, slots.default ? slots.default() : '')
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
const uiStubs: Record<string, any> = {
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
}

// ---------- 4. 假任務工具 ----------
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

// ---------- 5. 測試 ----------
describe('TaskForm.vue (render)', () => {
  beforeEach(() => {
    fetchSpy = vi.fn()
    toastSpy.add.mockClear()
    tokenSpy.mockClear()
  })

  it('空任務時顯示 Skeleton', async () => {
    fetchSpy.mockResolvedValueOnce([])

    const wrapper = shallowMount(TaskForm, { global: { stubs: uiStubs } })
    await flushPromises()

    expect(wrapper.findAll('u-skeleton-stub').length).toBe(3)
  })

  it('有任務時顯示卡片並含正確標題', async () => {
    const tasks = fakeTasks(2)
    fetchSpy.mockResolvedValueOnce(tasks)

    const wrapper = shallowMount(TaskForm, { global: { stubs: uiStubs } })
    await flushPromises()

    // Slot 已渲染：文字應包含每個任務標題
    tasks.forEach(t => expect(wrapper.text()).toContain(t.title))
    // Skeleton 不存在
    expect(wrapper.find('u-skeleton-stub').exists()).toBe(false)
  })

  it('點擊右上角按鈕會開啟 Modal', async () => {
    fetchSpy.mockResolvedValueOnce([])

    const wrapper = shallowMount(TaskForm, { global: { stubs: uiStubs } })
    await flushPromises()

    // 初始 data-open 為 false
    expect(wrapper.find('.u-modal-stub').attributes('data-open')).toBe('false')

    // 點擊右上角 UButton
    await wrapper.find('button').trigger('click')
    await flushPromises()

    // data-open 變 true 代表 showEditModal 已被設為 true
    expect(wrapper.find('.u-modal-stub').attributes('data-open')).toBe('true')
  })
})
