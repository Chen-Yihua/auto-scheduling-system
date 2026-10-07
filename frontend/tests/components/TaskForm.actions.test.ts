// TaskForm.vue 本身的接線邏輯：表單送出／刪除後要重抓統一清單、等使用者載入完才抓資料。
// useTaskForm／useSchedulableTasks 本身的行為
// 各有自己的測試，這裡整個換成 mock，只驗證元件怎麼呼叫它們。
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { shallowMount, flushPromises, enableAutoUnmount } from '@vue/test-utils'
import { ref, computed, reactive, watch, defineComponent, h } from 'vue'
import type { SchedulableTask } from '~/types/schedulableTask'

// vi.mock 會被 Vitest 提到所有 import 之前執行，所以元件寫在最上面一樣會拿到 mock 過的 composable
import TaskForm from '~/components/tasks/TaskForm.vue'

vi.stubGlobal('watch', watch)
enableAutoUnmount(afterEach)

// ---------- useTaskForm mock ----------
const userRef = ref<{ id: string } | null>({ id: 'u1' })
const isEditModeRef = ref(false)
const onSubmitSpy = vi.fn()
const onEditSpy = vi.fn()
const onDeleteSpy = vi.fn()
const fetchTasksSpy = vi.fn()
const startEditTaskSpy = vi.fn()
const allTasksRef = ref([{ id: 't1', title: '完整任務' }])

vi.mock('~/composables/useTaskForm', () => ({
  useTaskForm: () => ({
    user: userRef,
    showEditModal: ref(true),
    state: reactive({ title: '', description: '', priority: '', duration: '', inference_hint: '' }),
    modelValue: ref(null),
    minDate: null,
    displayDate: computed(() => '無期限'),
    clearDueDate: vi.fn(),
    priorityItems: ref([]),
    validate: vi.fn(() => []),
    submitting: ref(false),
    all_tasks: allTasksRef,
    isEditMode: isEditModeRef,
    fetchTasks: fetchTasksSpy,
    startEditTask: startEditTaskSpy,
    onSubmit: onSubmitSpy,
    onEdit: onEditSpy,
    onDelete: onDeleteSpy,
    onCancel: vi.fn(),
  }),
}))

// ---------- useSchedulableTasks mock ----------
const tasksRef = ref<SchedulableTask[]>([])
const fetchSchedulableTasksSpy = vi.fn()
vi.mock('~/composables/useSchedulableTasks', () => ({
  useSchedulableTasks: () => ({
    tasks: tasksRef,
    loading: ref(false),
    fetchSchedulableTasks: fetchSchedulableTasksSpy,
    toggleDone: vi.fn(),
  }),
}))

// ---------- UI stubs ----------
const SlotStub = (name: string) => defineComponent({
  name,
  setup: (_, { slots }) => () => h('div', [slots.header?.(), slots.default?.(), slots.content?.(), slots.footer?.()]),
})
const StubButton = defineComponent({
  name: 'UButton',
  emits: ['click'],
  setup: (_, { emit, slots }) => () => h('button', { onClick: (e: Event) => emit('click', e) }, slots.default?.()),
})
const stubs = {
  UButton: StubButton,
  UCard: SlotStub('UCard'),
  UModal: SlotStub('UModal'),
  UForm: SlotStub('UForm'),
  UBadge: true,
  UInput: true, UTextarea: true, UFormField: true, USelect: true,
  UPopover: true, UCalendar: true, USkeleton: true, UIcon: true,
  NuxtLink: { template: '<a><slot /></a>' },
}

const render = () => shallowMount(TaskForm, { global: { stubs } })

describe('TaskForm.vue 接線邏輯', () => {
  beforeEach(() => {
    userRef.value = { id: 'u1' }
    isEditModeRef.value = false
    tasksRef.value = []
    for (const spy of [onSubmitSpy, onEditSpy, onDeleteSpy, fetchTasksSpy, startEditTaskSpy, fetchSchedulableTasksSpy]) {
      spy.mockReset()
    }
  })

  it('使用者還沒載入時先不抓資料，等使用者出現才抓', async () => {
    userRef.value = null
    render()
    await flushPromises()

    expect(fetchTasksSpy).not.toHaveBeenCalled()
    expect(fetchSchedulableTasksSpy).not.toHaveBeenCalled()

    userRef.value = { id: 'u1' }
    await flushPromises()

    expect(fetchTasksSpy).toHaveBeenCalledTimes(1)
    expect(fetchSchedulableTasksSpy).toHaveBeenCalledTimes(1)
  })

  it('新增模式送出表單：呼叫 onSubmit，完成後重抓統一清單', async () => {
    const wrapper = render()
    await flushPromises()
    fetchSchedulableTasksSpy.mockClear()
    const event = { data: {} }

    wrapper.findComponent({ name: 'UForm' }).vm.$emit('submit', event)
    await flushPromises()

    expect(onSubmitSpy).toHaveBeenCalledWith(event)
    expect(onEditSpy).not.toHaveBeenCalled()
    expect(fetchSchedulableTasksSpy).toHaveBeenCalledTimes(1)
  })

  it('編輯模式送出表單：呼叫 onEdit，完成後重抓統一清單', async () => {
    isEditModeRef.value = true
    const wrapper = render()
    await flushPromises()
    fetchSchedulableTasksSpy.mockClear()

    wrapper.findComponent({ name: 'UForm' }).vm.$emit('submit', { data: {} })
    await flushPromises()

    expect(onEditSpy).toHaveBeenCalledTimes(1)
    expect(onSubmitSpy).not.toHaveBeenCalled()
    expect(fetchSchedulableTasksSpy).toHaveBeenCalledTimes(1)
  })

  it('按「刪除」：呼叫 onDelete，完成後重抓統一清單', async () => {
    isEditModeRef.value = true
    const wrapper = render()
    await flushPromises()
    fetchSchedulableTasksSpy.mockClear()

    const deleteButton = wrapper.findAll('button').find((b) => b.text().includes('刪除'))
    await deleteButton!.trigger('click')
    await flushPromises()

    expect(onDeleteSpy).toHaveBeenCalledTimes(1)
    expect(fetchSchedulableTasksSpy).toHaveBeenCalledTimes(1)
  })

})
