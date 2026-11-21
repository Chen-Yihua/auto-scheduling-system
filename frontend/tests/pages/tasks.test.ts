// /tasks 頁：訪客只看到登入提示卡，不掛載任務列表、不呼叫需要登入的 API
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, enableAutoUnmount } from '@vue/test-utils'
import { ref, defineComponent, h } from 'vue'

import TasksPage from '~/pages/tasks.vue'

enableAutoUnmount(afterEach)

const isSignedInRef = ref<boolean | undefined>(false)
vi.mock('@clerk/vue', () => ({ useUser: () => ({ isSignedIn: isSignedInRef }) }))

const fetchSpy = vi.fn()
vi.stubGlobal('$fetch', fetchSpy)

const stubs = {
  AppHeader: true,
  TaskForm: true,
  NuxtLink: { template: '<a><slot /></a>' },
  UCard: defineComponent({
    setup: (_p, { slots }) => () => h('div', [slots.header?.(), slots.default?.()]),
  }),
  UIcon: true,
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
    expect(fetchSpy).not.toHaveBeenCalled()
  })

  it('issue-178 AC43：沒有「返回主頁」連結', () => {
    isSignedInRef.value = true
    const wrapper = mount(TasksPage, { global: { stubs } })

    expect(wrapper.text()).not.toContain('返回主頁')
  })
})
