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

  it('authError=true 時顯示授權失效的訊息，而不是一般的過期提示', () => {
    vi.useFakeTimers().setSystemTime(new Date('2026-09-03T11:15:00Z'))

    const wrapper = mount(StaleDataBanner, {
      props: {
        stale: true,
        syncedAt: '2026-09-03T11:00:00Z',
        authError: true,
        platformLabel: 'GitHub',
      },
      global: { stubs: { UAlert: true } },
    })

    const alert = wrapper.find('u-alert-stub')
    expect(alert.exists()).toBe(true)
    expect(alert.attributes('title')).toBe(
      'GitHub 授權可能已失效，目前顯示的是快取資料（上次同步：15 分鐘前），請重新連結帳號',
    )
    expect(alert.attributes('color')).toBe('error')

    vi.useRealTimers()
  })
})
