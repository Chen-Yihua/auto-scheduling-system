// tests/components/googleCalendarEmbed.test.ts
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import GoogleCalendarEmbed from '~/components/TheMain/GoogleCalendarEmbed.vue'

describe('GoogleCalendarEmbed.vue', () => {
  it('connect=true 且有 calendarIds 時會嵌入 Google Calendar iframe', () => {
    const ids = ['cal1@group', '特殊字串 2']
    const wrapper = mount(GoogleCalendarEmbed, {
      props: { calendarIds: ids, id: 'foo', connect: true },
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
    })

    expect(wrapper.find('iframe').exists()).toBe(false)
    expect(wrapper.text()).toContain('尚未連接 Google Calendar')
  })
})
