import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'

import { h, defineComponent } from 'vue'

import MoodleAssignmentsList from '~/components/platforms/MoodleAssignmentsList.vue'
import type { MoodleAssignment } from '~/types/moodle'

const openSpy = vi.fn()
vi.stubGlobal('open', openSpy)

// UCard 預設的 stub 不渲染 slot，改用會渲染 slot 的假元件
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

const uiStubs = {
  UCard: UCardStub,
  UIcon: true,
  UAlert: true,
  NuxtLink: { template: '<a><slot /></a>' },
}
const render = (props: { assignments?: MoodleAssignment[]; loading?: boolean; notLinked?: boolean; limit?: number } = {}) =>
  mount(MoodleAssignmentsList, {
    props: { assignments: [], loading: false, ...props },
    global: { stubs: uiStubs },
  })

describe('MoodleAssignmentsList.vue', () => {
  it('未綁定帳號時顯示提示', () => {
    const wrapper = render({ notLinked: true })
    expect(wrapper.text()).toContain('尚未綁定 Moodle 帳號')
    // 只有外層容器的卡片，沒有作業卡片
    expect(wrapper.findAll('.u-card-stub').length).toBe(1)
  })

  it('Loading 顯示 icon', () => {
    const wrapper = render({ loading: true })
    expect(wrapper.find('u-icon-stub').exists()).toBe(true)
  })

  it('有作業時渲染卡片並可點擊開啟', async () => {
    const wrapper = render({
      assignments: [{ course_name: '課程 A', title: 'Moodle 作業', due_date: '2025-07-01', url: 'https://moodle/hw1' }],
    })
    // index 0 是外層的區塊容器卡片，index 1 才是這筆作業自己的卡片
    const cards = wrapper.findAll('.u-card-stub')
    expect(cards.length).toBe(2)
    expect(wrapper.text()).toContain('Moodle 作業')

    await cards[1].trigger('click')
    expect(openSpy).toHaveBeenCalledWith('https://moodle/hw1', '_blank')
  })

  it('帶 limit 且作業數超過限制時，只顯示前 limit 筆，並顯示「查看全部」連結', () => {
    const wrapper = render({
      assignments: [
        { course_name: '課程 A', title: '作業一', due_date: '2025-07-01', url: 'https://moodle/hw1' },
        { course_name: '課程 B', title: '作業二', due_date: '2025-07-02', url: 'https://moodle/hw2' },
        { course_name: '課程 C', title: '作業三', due_date: '2025-07-03', url: 'https://moodle/hw3' },
      ],
      limit: 2,
    })

    expect(wrapper.text()).toContain('作業一')
    expect(wrapper.text()).toContain('作業二')
    expect(wrapper.text()).not.toContain('作業三')
    expect(wrapper.text()).toContain('查看全部（3）')
  })

  it('已綁定、載入完成但沒有作業時，顯示「目前沒有未繳作業」', () => {
    const wrapper = render()

    expect(wrapper.text()).toContain('目前沒有未繳作業')
    expect(wrapper.findAll('.u-card-stub').length).toBe(1)
  })
})
