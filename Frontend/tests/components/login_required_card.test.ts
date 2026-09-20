import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { h, defineComponent } from 'vue'

import LoginRequiredCard from '~/components/TheMain/LoginRequiredCard.vue'

const stubs = {
  UCard: defineComponent({
    setup(_props, { slots }) {
      return () => h('div', { class: 'ucard' }, [slots.header?.(), slots.default?.()])
    },
  }),
  // 假元件把 name 印成屬性，才看得出用了哪個圖示
  UIcon: defineComponent({
    props: { name: { type: String, default: '' } },
    setup(props) {
      return () => h('i', { 'data-icon': props.name })
    },
  }),
}

describe('LoginRequiredCard.vue', () => {
  it('顯示跟真實卡片一樣的標題與圖示，內容區放提示文字', () => {
    const wrapper = mount(LoginRequiredCard, {
      props: { title: 'GitHub 參與項目', icon: 'mdi:github', message: '登入後即可查看 GitHub 參與項目' },
      global: { stubs },
    })

    expect(wrapper.text()).toContain('GitHub 參與項目')
    expect(wrapper.find('i').attributes('data-icon')).toBe('mdi:github')
    // 提示的樣式要跟「尚未綁定」的提示一樣（置中、灰色小字）
    expect(wrapper.find('.text-center').text()).toBe('登入後即可查看 GitHub 參與項目')
  })

  it('有指定 iconClass 時套用在圖示上（例如 Jira 的藍色）', () => {
    const wrapper = mount(LoginRequiredCard, {
      props: { title: 'Jira 指派任務', icon: 'mdi:jira', iconClass: 'text-blue-500', message: 'x' },
      global: { stubs },
    })

    expect(wrapper.find('i').classes()).toContain('text-blue-500')
  })
})
