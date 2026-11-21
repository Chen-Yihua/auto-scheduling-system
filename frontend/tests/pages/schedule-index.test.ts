// /schedule 頁：已登入顯示排程建議卡片，訪客顯示登入提示卡
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, enableAutoUnmount } from '@vue/test-utils'
import { ref, defineComponent, h } from 'vue'

import SchedulePage from '~/pages/schedule/index.vue'

enableAutoUnmount(afterEach)

const isSignedInRef = ref<boolean | undefined>(true)
vi.mock('@clerk/vue', () => ({ useUser: () => ({ isSignedIn: isSignedInRef }) }))

const stubs = {
  AppHeader: true,
  ScheduleSuggestion: true,
  UCard: defineComponent({
    setup: (_p, { slots }) => () => h('div', [slots.header?.(), slots.default?.()]),
  }),
  UIcon: true,
}

describe('pages/schedule/index.vue', () => {
  beforeEach(() => {
    isSignedInRef.value = true
  })

  it('AC30：已登入時掛載排程建議卡片', () => {
    const wrapper = mount(SchedulePage, { global: { stubs } })

    expect(wrapper.findComponent({ name: 'ScheduleSuggestion' }).exists()).toBe(true)
    expect(wrapper.text()).not.toContain('登入後即可')
  })

  it('AC35：訪客顯示「排程建議」登入提示卡，不掛載排程建議卡片', () => {
    isSignedInRef.value = false
    const wrapper = mount(SchedulePage, { global: { stubs } })

    expect(wrapper.text()).toContain('排程建議')
    expect(wrapper.text()).toContain('登入後即可查看排程建議')
    expect(wrapper.findComponent({ name: 'ScheduleSuggestion' }).exists()).toBe(false)
  })
})
