import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent, h, ref, watch, onMounted } from 'vue'

import AccountSettings from '~/components/header/AccountSettings.vue'

vi.stubGlobal('ref', ref)
vi.stubGlobal('watch', watch)
vi.stubGlobal('onMounted', onMounted)
vi.stubGlobal('useToast', () => ({ add: vi.fn() }))

// UserButton 與 UserProfilePage 只要把 slot 畫出來
vi.mock('@clerk/vue', async () => {
  const { defineComponent, h } = await import('vue')
  const passthrough = defineComponent({ setup: (_, { slots }) => () => h('div', slots.default?.()) })
  return { UserButton: Object.assign(passthrough, { UserProfilePage: passthrough }) }
})

const keys = ref<Record<string, unknown>[]>([])
vi.mock('~/composables/useLinkedAccount', () => ({
  useLinkedAccount: () => ({
    keys, fetchKeys: vi.fn(), openEdit: vi.fn(), cancelEdit: vi.fn(), saveKey: vi.fn(), deleteKey: vi.fn(),
  }),
}))

const isConnected = ref(false)
const needsReconnect = ref(false)
vi.mock('~/composables/useGoogleCalendar', () => ({
  useGoogleCalendar: () => ({ isConnected, needsReconnect, fetchGoogleCalendars: vi.fn() }),
}))
vi.mock('~/composables/useGoogleCalendarAuth', () => ({
  useGoogleCalendarAuth: () => ({ connectedCount: ref(0), goToGoogleAuth: vi.fn() }),
}))

const UButtonStub = defineComponent({ setup: (_, { slots }) => () => h('button', slots.default?.()) })
const UBadgeStub = defineComponent({ setup: (_, { slots }) => () => h('span', { class: 'badge' }, slots.default?.()) })
const stubs = { UButton: UButtonStub, UBadge: UBadgeStub, UIcon: true, Icon: true, UInput: true, UAvatar: true }

const key = (overrides: Record<string, unknown>) => ({
  platform: 'github', label: 'GitHub Key', value: '', inputValue: '', loading: false, editing: false,
  showPassword: false, icon: 'mdi:github', isMasked: false, ...overrides,
})

describe('AccountSettings.vue', () => {
  beforeEach(() => {
    keys.value = []
    isConnected.value = false
    needsReconnect.value = false
  })

  it('AC1(2)：Google 授權已失效（needsReconnect）→ 按鈕是「重新連接 Google Calendar」，沒有「已連接」標記', () => {
    needsReconnect.value = true
    const wrapper = mount(AccountSettings, { global: { stubs } })

    expect(wrapper.text()).toContain('重新連接 Google Calendar')
    expect(wrapper.find('.badge').exists()).toBe(false)
  })

  it('AC20(3)：從沒成功取得狀態（沒有已知的結果）→ 不顯示「已連接」，按鈕維持「連接 Google Calendar」', () => {
    const wrapper = mount(AccountSettings, { global: { stubs } })

    expect(wrapper.find('.badge').exists()).toBe(false)
    expect(wrapper.text()).toContain('連接 Google Calendar')
    expect(wrapper.text()).not.toContain('重新連接')
  })

  it('AC1(1)：已連接時顯示「已連接」標記', () => {
    isConnected.value = true
    const wrapper = mount(AccountSettings, { global: { stubs } })

    expect(wrapper.find('.badge').text()).toContain('已連接')
  })

  it('AC9：憑證無法讀取的帳號顯示「憑證無法讀取，請重新連結」與刪除按鈕；其他帳號照常顯示', () => {
    keys.value = [
      key({ platform: 'github', needsReauth: true }),
      key({ platform: 'jira', label: 'Jira Key', value: 'JKEY1234', isMasked: true, icon: 'mdi:jira' }),
    ]
    const wrapper = mount(AccountSettings, { global: { stubs } })

    expect(wrapper.text()).toContain('憑證無法讀取，請重新連結')
    expect(wrapper.findAll('button').map((b) => b.text())).toContain('刪除')
    expect(wrapper.text()).toContain('****1234')
  })
})
