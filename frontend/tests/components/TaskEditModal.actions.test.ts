// TaskEditModal.vue 怎麼呼叫 composable（composable 全部 mock）
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { shallowMount, flushPromises, enableAutoUnmount } from '@vue/test-utils'
import { ref, computed, reactive, watch, defineComponent, h } from 'vue'

import TaskEditModal from '~/components/tasks/TaskEditModal.vue'

vi.stubGlobal('watch', watch)
enableAutoUnmount(afterEach)

// ---------- useTaskForm mock ----------
const userRef = ref<{ id: string } | null>({ id: 'u1' })
const isEditModeRef = ref(false)
const onSubmitSpy = vi.fn()
const onEditSpy = vi.fn()
const onDeleteSpy = vi.fn()
const fetchTasksSpy = vi.fn()
const isEditingParentRef = ref(false)
const editingSubtasksRef = ref<{ id: string; title: string; stage: number }[]>([])
const onDeleteSubtaskSpy = vi.fn()
const startAddSubtaskSpy = vi.fn()
const deletingRef = ref(false)

vi.mock('~/composables/useTaskForm', () => ({
  useTaskForm: () => ({
    user: userRef,
    showEditModal: ref(true),
    state: reactive({ title: '', description: '', priority: '', duration: '', inference_hint: '', subtasks: [] }),
    modelValue: ref(null),
    minDate: null,
    displayDate: computed(() => '無期限'),
    clearDueDate: vi.fn(),
    priorityItems: ref([]),
    validate: vi.fn(() => []),
    submitting: ref(false),
    isEditMode: isEditModeRef,
    fetchTasks: fetchTasksSpy,
    onSubmit: onSubmitSpy,
    onEdit: onEditSpy,
    onDelete: onDeleteSpy,
    onCancel: vi.fn(),
    addSubtaskRow: vi.fn(),
    removeSubtaskRow: vi.fn(),
    maxSubtasks: 10,
    isEditingParent: isEditingParentRef,
    isEditingSubtask: ref(false),
    editingSubtasks: editingSubtasksRef,
    splitBlockedReason: ref(null),
    subtaskDraft: reactive({ title: '', priority: '', duration: '', due_date: '', position: 1 }),
    showSubtaskDraft: ref(false),
    startAddSubtask: startAddSubtaskSpy,
    cancelAddSubtask: vi.fn(),
    onAddSubtask: vi.fn(),
    onDeleteSubtask: onDeleteSubtaskSpy,
    deleting: deletingRef,
    willReschedule: ref(false),
  }),
}))

const fetchSchedulableTasksSpy = vi.fn()
vi.mock('~/composables/useSchedulableTasks', () => ({
  useSchedulableTasks: () => ({ fetchSchedulableTasks: fetchSchedulableTasksSpy }),
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
  UModal: SlotStub('UModal'),
  UForm: SlotStub('UForm'),
  UInput: true, UTextarea: true, UFormField: true, USelect: true,
  UPopover: true, UCalendar: true, UIcon: true,
}

const render = () => shallowMount(TaskEditModal, { global: { stubs } })

describe('TaskEditModal.vue 接線邏輯', () => {
  beforeEach(() => {
    userRef.value = { id: 'u1' }
    isEditModeRef.value = false
    isEditingParentRef.value = false
    editingSubtasksRef.value = []
    deletingRef.value = false
    for (const spy of [onSubmitSpy, onEditSpy, onDeleteSpy, fetchTasksSpy, fetchSchedulableTasksSpy, onDeleteSubtaskSpy, startAddSubtaskSpy]) {
      spy.mockReset()
    }
  })

  it('issue-178 AC8：使用者還沒載入時先不讀 all_tasks，等使用者出現才讀', async () => {
    userRef.value = null
    render()
    await flushPromises()

    expect(fetchTasksSpy).not.toHaveBeenCalled()

    userRef.value = { id: 'u1' }
    await flushPromises()

    expect(fetchTasksSpy).toHaveBeenCalledTimes(1)
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

  it('編輯主任務時列出子任務，按子任務的「刪除」呼叫 onDeleteSubtask，完成後重抓統一清單', async () => {
    isEditModeRef.value = true
    isEditingParentRef.value = true
    editingSubtasksRef.value = [{ id: 's1', title: '第一階段', stage: 1 }, { id: 's2', title: '第二階段', stage: 2 }]
    const wrapper = render()
    await flushPromises()
    fetchSchedulableTasksSpy.mockClear()

    expect(wrapper.text()).toContain('第一階段')
    const row = wrapper.findAll('.subtask-edit-row').find((r) => r.text().includes('第二階段'))
    await row!.findAll('button').find((b) => b.text().includes('刪除'))!.trigger('click')
    await flushPromises()

    expect(onDeleteSubtaskSpy).toHaveBeenCalledWith(editingSubtasksRef.value[1])
    expect(fetchSchedulableTasksSpy).toHaveBeenCalledTimes(1)
  })

  it('刪除送出中時，任務本身與每個階段的「刪除」都停用；送出完成後恢復', async () => {
    isEditModeRef.value = true
    isEditingParentRef.value = true
    editingSubtasksRef.value = [{ id: 's1', title: '第一階段', stage: 1 }, { id: 's2', title: '第二階段', stage: 2 }]
    const wrapper = render()
    await flushPromises()
    const deleteButtons = () => wrapper.findAll('button').filter((b) => b.text().includes('刪除'))

    deletingRef.value = true
    await flushPromises()
    expect(deleteButtons().map((b) => b.attributes('disabled'))).toEqual(['', '', ''])

    deletingRef.value = false
    await flushPromises()
    expect(deleteButtons().map((b) => b.attributes('disabled'))).toEqual([undefined, undefined, undefined])
  })

  it('編輯主任務時可以選在某個階段前面插入子任務', async () => {
    isEditModeRef.value = true
    isEditingParentRef.value = true
    editingSubtasksRef.value = [{ id: 's1', title: '第一階段', stage: 1 }, { id: 's2', title: '第二階段', stage: 2 }]
    const wrapper = render()
    await flushPromises()

    const row = wrapper.findAll('.subtask-edit-row').find((r) => r.text().includes('第二階段'))
    await row!.findAll('button').find((b) => b.text().includes('插入'))!.trigger('click')

    expect(startAddSubtaskSpy).toHaveBeenCalledWith(2)
  })
})
