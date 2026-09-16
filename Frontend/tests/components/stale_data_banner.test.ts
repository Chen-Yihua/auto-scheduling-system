import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import StaleDataBanner from '~/components/TheMain/StaleDataBanner.vue'

describe('StaleDataBanner.vue', () => {
  it('stale=false 時不顯示任何提示', () => {
    const wrapper = mount(StaleDataBanner, {
      props: { stale: false, syncedAt: '2026-09-03T11:00:00Z' },
      global: { stubs: { UAlert: true } },
    })

    expect(wrapper.find('u-alert-stub').exists()).toBe(false)
  })

  it('stale=true 時顯示提示，並帶上相對時間', () => {
    vi.useFakeTimers().setSystemTime(new Date('2026-09-03T11:15:00Z'))

    const wrapper = mount(StaleDataBanner, {
      props: { stale: true, syncedAt: '2026-09-03T11:00:00Z' },
      global: { stubs: { UAlert: true } },
    })

    const alert = wrapper.find('u-alert-stub')
    expect(alert.exists()).toBe(true)
    expect(alert.attributes('title')).toBe('資料可能非即時，上次同步：15 分鐘前')

    vi.useRealTimers()
  })
})
