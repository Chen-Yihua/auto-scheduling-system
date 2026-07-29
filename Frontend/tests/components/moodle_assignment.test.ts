import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'

// mock Nuxt 的 #imports
vi.mock('#imports', () => ({
  useRuntimeConfig: () => ({ public: { apiBaseUrl: 'http://api' } }),
  useToast: () => ({ add: vi.fn() }),
}))

// 建立可變的 ref 供元件使用
import { ref as vueRef } from 'vue'
const loadingRef = vueRef(false)
const hasAccountRef = vueRef(true)
const assignmentsRef = vueRef<any[]>([])
const openSpy = vi.fn()

// 先 mock Composable ---------- */
vi.mock('~/composables/useMoodleAssignments', () => ({
  useMoodleAssignments: () => ({
    loading: loadingRef,
    hasAccount: hasAccountRef,
    moodleAssignments: assignmentsRef,
    fetchMoodleAssignments: vi.fn(), 
    openMoodleAssignments: openSpy,
  }),
}))

// 自訂 UCard stub，渲染 slot
const UCardStub = {
  name: 'UCard',
  emits: ['click'],
  setup(
    _props: Record<string, unknown>,
    context: { slots: Record<string, () => any>; emit: (event: string, ...args: any[]) => void }
  ) {
    const { slots, emit } = context;
    return () =>
      h(
        'div',
        { class: 'u-card-stub', onClick: () => emit('click') },
        [
          slots.header?.(),
          slots.default?.(),
          slots.footer?.(),
        ],
      )
  },
}

// 再引入元件
import MoodleAssignments from '~/components/TheMain/MoodleAssignments.vue'

// 將 UCardStub 註冊為全域 stub
const uiStubs = { UCard: true, UIcon: true }
// 
const render = () =>
  mount(MoodleAssignments, {
    global: { stubs: uiStubs },
  })

describe('MoodleAssignments.vue', () => {
  it('未綁定帳號時顯示提示', () => {
    hasAccountRef.value = false
    loadingRef.value = false
    assignmentsRef.value = []

    const wrapper = render()
    expect(wrapper.text()).toContain('尚未綁定 Moodle 帳號')
    expect(wrapper.find('u-card-stub').exists()).toBe(false)
  })

  it('Loading 顯示 icon', () => {
    hasAccountRef.value = true
    loadingRef.value = true
    assignmentsRef.value = []

    const wrapper = render()
    expect(wrapper.find('u-icon-stub').exists()).toBe(true)
  })

  it('有作業時渲染卡片並可點擊開啟', async () => {
    hasAccountRef.value = true
    loadingRef.value = false
    assignmentsRef.value = [
      {
        course_name: '課程 A',
        assignment_title: 'Moodle 作業',
        due_date: '2025-07-01',
        assignment_url: 'https://moodle/hw1',
      },
    ]

    const wrapper = render()
    const card = wrapper.find('u-card-stub')
    expect(card.exists()).toBe(true)
    expect(wrapper.text()).toContain('Moodle 作業')

    await card.trigger('click')
    expect(openSpy).toHaveBeenCalledWith('https://moodle/hw1')
  })
})
