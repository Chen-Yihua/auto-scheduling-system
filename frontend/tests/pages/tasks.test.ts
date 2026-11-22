// /tasks 頁：訪客只看到登入提示卡，不掛載任務列表、不呼叫需要登入的 API
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, enableAutoUnmount } from '@vue/test-utils'
import { ref, nextTick, defineComponent, h } from 'vue'

import TasksPage from '~/pages/tasks.vue'

enableAutoUnmount(afterEach)

const isSignedInRef = ref<boolean | undefined>(false)
vi.mock('@clerk/vue', () => ({ useUser: () => ({ isSignedIn: isSignedInRef }) }))

const showEditModal = ref(false)
vi.mock('~/composables/useTaskForm', () => ({ useTaskForm: () => ({ showEditModal }) }))

const fetchSpy = vi.fn()
vi.stubGlobal('$fetch', fetchSpy)

const stubs = {
  AppHeader: true,
  TaskForm: true,
  TaskEditModal: true,
  NuxtLink: { template: '<a><slot /></a>' },
  UCard: defineComponent({
    setup: (_p, { slots }) => () => h('div', [slots.header?.(), slots.default?.()]),
  }),
  UIcon: true,
  UButton: defineComponent({
    emits: ['click'],
    setup: (_p, { attrs, emit }) => () => h('button', { ...attrs, onClick: () => emit('click') }),
  }),
}

describe('pages/tasks.vue', () => {
  beforeEach(() => {
    fetchSpy.mockClear()
    isSignedInRef.value = false
  })

  it('issue-178 AC31：訪客顯示「任務列表」登入提示卡，沒有掛載 TaskForm、沒有呼叫需要登入的 API', () => {
    const wrapper = mount(TasksPage, { global: { stubs } })

    expect(wrapper.text()).toContain('任務列表')
    expect(wrapper.text()).toContain('登入後即可查看')
    expect(wrapper.findComponent({ name: 'TaskForm' }).exists()).toBe(false)
    expect(wrapper.findComponent({ name: 'TaskEditModal' }).exists()).toBe(false)
    expect(fetchSpy).not.toHaveBeenCalled()
  })

  it('issue-178 AC22：已登入時，任務列表與新增、編輯用的視窗一起掛載', () => {
    isSignedInRef.value = true
    const wrapper = mount(TasksPage, { global: { stubs } })

    expect(wrapper.findComponent({ name: 'TaskForm' }).exists()).toBe(true)
    expect(wrapper.findComponent({ name: 'TaskEditModal' }).exists()).toBe(true)
  })

  it('issue-178 AC43：沒有「返回主頁」連結', () => {
    isSignedInRef.value = true
    const wrapper = mount(TasksPage, { global: { stubs } })

    expect(wrapper.text()).not.toContain('返回主頁')
  })

  describe('回到頂端按鈕', () => {
    const scrollTo = vi.fn()
    const BUTTON = 'button[aria-label="回到頂端"]'

    const scrollToY = async (y: number) => {
      Object.defineProperty(window, 'scrollY', { value: y, configurable: true })
      window.dispatchEvent(new Event('scroll'))
      await nextTick()
    }
    const mountSignedIn = () => {
      isSignedInRef.value = true
      return mount(TasksPage, { global: { stubs } })
    }

    beforeEach(() => {
      showEditModal.value = false
      scrollTo.mockClear()
      window.scrollTo = scrollTo
      Object.defineProperty(window, 'innerHeight', { value: 800, configurable: true })
      Object.defineProperty(window, 'scrollY', { value: 0, configurable: true })
    })

    it('fit-viewport-layout AC34：頁面在頂端時沒有按鈕', () => {
      const wrapper = mountSignedIn()

      expect(wrapper.find(BUTTON).exists()).toBe(false)
    })

    it('fit-viewport-layout AC35：捲動超過一個視窗高度才出現，回到門檻內就隱藏', async () => {
      const wrapper = mountSignedIn()

      await scrollToY(801)
      expect(wrapper.find(BUTTON).exists()).toBe(true)

      await scrollToY(799)
      expect(wrapper.find(BUTTON).exists()).toBe(false)
    })

    it('fit-viewport-layout AC36：按下去平滑捲回最上面', async () => {
      const wrapper = mountSignedIn()
      await scrollToY(801)

      await wrapper.find(BUTTON).trigger('click')

      expect(scrollTo).toHaveBeenCalledTimes(1)
      expect(scrollTo).toHaveBeenCalledWith({ top: 0, behavior: 'smooth' })
    })

    it('fit-viewport-layout AC37：新增／編輯任務視窗打開時隱藏，關閉後再出現', async () => {
      const wrapper = mountSignedIn()
      await scrollToY(801)

      showEditModal.value = true
      await nextTick()
      expect(wrapper.find(BUTTON).exists()).toBe(false)

      showEditModal.value = false
      await nextTick()
      expect(wrapper.find(BUTTON).exists()).toBe(true)
    })
  })
})
