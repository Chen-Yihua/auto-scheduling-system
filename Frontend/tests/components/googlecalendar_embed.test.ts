// tests/components/googleCalendarEmbed.test.ts
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import GoogleCalendarEmbed from '~/components/TheMain/GoogleCalendarEmbed.vue'

// UCard 的預設 auto-stub（`true`）不會渲染 slot 內容，這裡改用會渲染
// header/default slot 的 stub，元件整個區塊現在都包在 UCard 裡
const UCardStub = defineComponent({
  name: 'UCard',
  setup(_, { slots }) {
    return () => h('div', { class: 'u-card-stub' }, [slots.header?.(), slots.default?.()])
  },
})

const uiStubs = { UIcon: true, UCard: UCardStub }

describe('GoogleCalendarEmbed.vue', () => {
  it('connect=true 且有 calendarIds 時會嵌入 Google Calendar iframe', () => {
    const ids = ['cal1@group', '特殊字串 2']
    const wrapper = mount(GoogleCalendarEmbed, {
      props: { calendarIds: ids, id: 'foo', connect: true },
      global: { stubs: uiStubs },
    })

    const html = wrapper.html()
    expect(html).toContain('calendar.google.com')
    ids.forEach((id) =>
      expect(html).toContain(`src=${encodeURIComponent(id)}`),
    )
    expect(html).toContain('ctz=Asia%2FTaipei')
  })

  it('connect=false 時顯示未連線提示文字且無 iframe', () => {
    const wrapper = mount(GoogleCalendarEmbed, {
      props: { calendarIds: [], id: 'bar', connect: false },
      global: { stubs: uiStubs },
    })

    expect(wrapper.find('iframe').exists()).toBe(false)
    expect(wrapper.text()).toContain('尚未連接 Google Calendar')
  })
})
