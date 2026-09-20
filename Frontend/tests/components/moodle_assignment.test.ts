import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'

// 建立可變的 ref 供元件使用
import { ref as vueRef, h, defineComponent } from 'vue'

// 再引入元件
import MoodleAssignments from '~/components/TheMain/MoodleAssignments.vue'
import type { MoodleAssignment } from '~/types/moodle'

// mock Nuxt 的 #imports
vi.mock('#imports', () => ({
  useRuntimeConfig: () => ({ public: { apiBaseUrl: 'http://api' } }),
  useToast: () => ({ add: vi.fn() }),
}))
const loadingRef = vueRef(false)
const hasAccountRef = vueRef(true)
const assignmentsRef = vueRef<MoodleAssignment[]>([])
const isStaleRef = vueRef(false)
const syncedAtRef = vueRef<string | null>(null)
const openSpy = vi.fn()

// 先 mock Composable ---------- */
vi.mock('~/composables/useMoodleAssignments', () => ({
  useMoodleAssignments: () => ({
    loading: loadingRef,
    hasAccount: hasAccountRef,
    moodleAssignments: assignmentsRef,
    isStale: isStaleRef,
    syncedAt: syncedAtRef,
    fetchMoodleAssignments: vi.fn(),
    openMoodleAssignments: openSpy,
  }),
}))

// 自訂 UCard stub，渲染 slot（UCard 的預設 auto-stub 不會渲染 slot 內容，
// 但這個元件整個區塊、以及裡面每筆作業，現在都包在 UCard 裡）
const UCardStub = defineComponent({
  name: 'UCard',
  emits: ['click'],
  setup(_props, { slots, emit }) {
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
})

const uiStubs = { UCard: UCardStub, UIcon: true, UAlert: true }
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
    // 整個區塊現在固定包在一張 UCard 裡（跟 Hacker News 一樣的外框），
    // 差別只在於裡面沒有渲染任何一筆「作業」的卡片
    expect(wrapper.findAll('.u-card-stub').length).toBe(1)
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
        title: 'Moodle 作業',
        due_date: '2025-07-01',
        url: 'https://moodle/hw1',
      },
    ]

    const wrapper = render()
    // index 0 是外層的區塊容器卡片，index 1 才是這筆作業自己的卡片
    const cards = wrapper.findAll('.u-card-stub')
    expect(cards.length).toBe(2)
    expect(wrapper.text()).toContain('Moodle 作業')

    await cards[1].trigger('click')
    expect(openSpy).toHaveBeenCalledWith('https://moodle/hw1')
  })
})
