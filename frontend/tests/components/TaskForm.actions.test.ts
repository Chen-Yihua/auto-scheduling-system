// TaskForm.vue 怎麼呼叫 composable（composable 全部 mock）；編輯視窗的接線見 TaskEditModal.actions.test.ts
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { shallowMount, flushPromises, enableAutoUnmount } from '@vue/test-utils'
import { ref, watch, defineComponent, h } from 'vue'
import type { SchedulableTask } from '~/types/schedulableTask'

import TaskForm from '~/components/tasks/TaskForm.vue'

vi.stubGlobal('watch', watch)
vi.stubGlobal('useLinkedAccount', () => ({ keys: ref([]), fetchKeys: vi.fn().mockResolvedValue(undefined) }))
enableAutoUnmount(afterEach)

// ---------- useTaskForm mock ----------
const userRef = ref<{ id: string } | null>({ id: 'u1' })
const startEditTaskSpy = vi.fn()
const allTasksRef = ref([{ id: 't0', title: '完整任務' }])

vi.mock('~/composables/useTaskForm', () => ({
  useTaskForm: () => ({ user: userRef, all_tasks: allTasksRef, startEditTask: startEditTaskSpy }),
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

vi.mock('~/composables/usePlatformItems', () => ({
  usePlatformItems: () => ({ syncNow: vi.fn() }),
}))

// ---------- UI stubs ----------
const StubButton = defineComponent({
  name: 'UButton',
  emits: ['click'],
  setup: (_, { emit, slots }) => () => h('button', { onClick: (e: Event) => emit('click', e) }, slots.default?.()),
})
const stubs = {
  UButton: StubButton,
  UCard: defineComponent({ setup: (_, { slots }) => () => h('div', [slots.header?.(), slots.default?.()]) }),
  UBadge: true, USkeleton: true, UIcon: true,
}

describe('TaskForm.vue 接線邏輯', () => {
  beforeEach(() => {
    userRef.value = { id: 'u1' }
    tasksRef.value = []
    startEditTaskSpy.mockReset()
    fetchSchedulableTasksSpy.mockReset()
  })

  it('使用者還沒載入時先不讀任務列表，等使用者出現才讀', async () => {
    userRef.value = null
    shallowMount(TaskForm, { global: { stubs } })
    await flushPromises()

    expect(fetchSchedulableTasksSpy).not.toHaveBeenCalled()

    userRef.value = { id: 'u1' }
    await flushPromises()

    expect(fetchSchedulableTasksSpy).toHaveBeenCalledTimes(1)
  })

  it('AC19：按手動任務的「編輯」：用去掉 "manual:" 前綴的 id 找到 all_tasks 裡的完整資料，呼叫 startEditTask', async () => {
    tasksRef.value = [{
      id: 'manual:t0', source: 'manual', title: '任務0', status: 'To Do', priority: 'Low', due_date: null, url: null,
    }]
    const wrapper = shallowMount(TaskForm, { global: { stubs } })
    await flushPromises()

    await wrapper.findAll('button').find((b) => b.text().includes('編輯'))!.trigger('click')

    expect(startEditTaskSpy).toHaveBeenCalledWith(allTasksRef.value[0])
  })
})
