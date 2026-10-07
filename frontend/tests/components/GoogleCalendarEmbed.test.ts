import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import GoogleCalendarEmbed from '~/components/dashboard/GoogleCalendarEmbed.vue'

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

  it('connecting=true 時只在這張卡片顯示「連接中」，不顯示未連線提示，也沒有 iframe', () => {
    const wrapper = mount(GoogleCalendarEmbed, {
      props: { calendarIds: [], id: 'baz', connect: false, connecting: true },
      global: { stubs: uiStubs },
    })

    expect(wrapper.text()).toContain('正在連接 Google Calendar')
    expect(wrapper.text()).not.toContain('尚未連接')
    expect(wrapper.find('iframe').exists()).toBe(false)
    // 標題列仍在，卡片位置不變
    expect(wrapper.text()).toContain('Google 行事曆')
  })

  it('reloadToken 改變時，iframe 的 src 帶上新值當 cache-busting 參數，且整個 iframe 元素重新建立', async () => {
    const wrapper = mount(GoogleCalendarEmbed, {
      props: { calendarIds: ['cal1'], id: 'foo', connect: true, reloadToken: 1 },
      global: { stubs: uiStubs },
    })
    const firstIframe = wrapper.find('iframe').element
    expect(wrapper.find('iframe').attributes('src')).toContain('_r=1')

    await wrapper.setProps({ reloadToken: 2 })

    expect(wrapper.find('iframe').attributes('src')).toContain('_r=2')
    // :key 改變 → Vue 整個重新建立這個 DOM 節點，不是同一個 iframe 元素
    // 沿用舊的（沿用的話瀏覽器可能不會真的重新請求）
    expect(wrapper.find('iframe').element).not.toBe(firstIframe)
  })
})
