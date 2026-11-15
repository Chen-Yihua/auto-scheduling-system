import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import GoogleCalendarEmbed from '~/components/dashboard/GoogleCalendarEmbed.vue'

// UCard 預設的 stub 不渲染 slot，改用會渲染 slot 的假元件
const UCardStub = defineComponent({
  name: 'UCard',
  setup(_, { slots }) {
    return () => h('div', { class: 'u-card-stub' }, [slots.header?.(), slots.default?.()])
  },
})

const USkeletonStub = defineComponent({
  name: 'USkeleton',
  setup() {
    return () => h('div', { class: 'u-skeleton-stub' })
  },
})

const uiStubs = { UIcon: true, UCard: UCardStub, USkeleton: USkeletonStub }

const NEEDS_CONNECT_TEXT = 'Google Calendar 未連接或授權已失效，請前往 帳號設定 連接。'

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

  it('AC1、AC3：connect=false 時顯示需要連接的文字（帳號設定用粗體）、沒有 iframe，也不再出現舊文字', () => {
    const wrapper = mount(GoogleCalendarEmbed, {
      props: { calendarIds: [], id: 'bar', connect: false },
      global: { stubs: uiStubs },
    })

    expect(wrapper.find('iframe').exists()).toBe(false)
    expect(wrapper.text()).toContain(NEEDS_CONNECT_TEXT)
    expect(wrapper.find('strong').text()).toBe('帳號設定')
    expect(wrapper.text()).not.toContain('尚未連接')
    expect(wrapper.text()).not.toContain('請重新連接。')
  })

  it('AC6：connect=true 時有 iframe，不顯示需要連接的文字', () => {
    const wrapper = mount(GoogleCalendarEmbed, {
      props: { calendarIds: ['cal1'], id: 'foo', connect: true },
      global: { stubs: uiStubs },
    })

    expect(wrapper.find('iframe').exists()).toBe(true)
    expect(wrapper.text()).not.toContain('未連接或授權已失效')
  })

  it('AC7：第一次查詢還沒有結果（loading）時顯示灰色方塊，沒有需要連接、暫時無法載入的文字，也沒有 iframe', () => {
    const wrapper = mount(GoogleCalendarEmbed, {
      props: { calendarIds: [], id: 'bar', connect: false, loading: true, unavailable: true },
      global: { stubs: uiStubs },
    })

    expect(wrapper.findComponent({ name: 'USkeleton' }).exists()).toBe(true)
    expect(wrapper.text()).not.toContain('未連接或授權已失效')
    expect(wrapper.text()).not.toContain('暫時無法載入')
    expect(wrapper.find('iframe').exists()).toBe(false)
  })

  it('AC7、AC4：正在連接和載入中同時成立時，顯示「正在連接」，沒有灰色方塊', () => {
    const wrapper = mount(GoogleCalendarEmbed, {
      props: { calendarIds: [], id: 'bar', connect: false, connecting: true, loading: true },
      global: { stubs: uiStubs },
    })

    expect(wrapper.text()).toContain('正在連接 Google Calendar，請稍候…')
    expect(wrapper.findComponent({ name: 'USkeleton' }).exists()).toBe(false)
  })

  it('AC4：connecting=true 時只在這張卡片顯示「連接中」，不顯示需要連接的文字，也沒有 iframe', () => {
    const wrapper = mount(GoogleCalendarEmbed, {
      props: { calendarIds: [], id: 'baz', connect: false, connecting: true },
      global: { stubs: uiStubs },
    })

    expect(wrapper.text()).toContain('正在連接 Google Calendar，請稍候…')
    expect(wrapper.text()).not.toContain('未連接或授權已失效')
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
    // key 改變要建立新的 iframe 元素，瀏覽器才會重新請求
    expect(wrapper.find('iframe').element).not.toBe(firstIframe)
  })

  it('AC5：從沒載入成功過又遇到暫時性錯誤（unavailable）→ 顯示暫時無法載入，不顯示需要連接的文字，也沒有 iframe', () => {
    const wrapper = mount(GoogleCalendarEmbed, {
      props: { calendarIds: [], id: 'bar', connect: true, unavailable: true },
      global: { stubs: uiStubs },
    })

    expect(wrapper.text()).toContain('Google 行事曆暫時無法載入，請稍後再試')
    expect(wrapper.text()).not.toContain('未連接或授權已失效')
    expect(wrapper.find('iframe').exists()).toBe(false)
  })
})
