import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { ref, watch, h, defineComponent } from 'vue'
import type { SetupContext } from 'vue'

import TheHeader from '~/components/TheHeader/index.vue'

vi.stubGlobal('watch', watch)

// ---------- Clerk mock：isSignedIn／user 可由測試動態控制 ----------
const isSignedInRef = ref<boolean | undefined>(undefined)
const userRef = ref<{ id: string; fullName: string; firstName: string; lastName: string } | null>(null)

vi.mock('@clerk/vue', () => ({
  useUser: () => ({ user: userRef, isSignedIn: isSignedInRef }),
}))

// 跟 TaskForm 共用的 Modal 開關
const showEditModal = ref(false)
vi.mock('~/composables/useTaskForm', () => ({
  useTaskForm: () => ({ showEditModal }),
}))

vi.mock('~/composables/useUserSync', () => ({
  useUserSync: () => ({ ensureUserRecord: vi.fn() }),
}))

// 假的 UButton：把 disabled／aria-label／title 畫成真的 button 屬性
const UButtonStub = defineComponent({
  props: { disabled: Boolean },
  emits: ['click'],
  setup(props, { slots, emit, attrs }) {
    return () =>
      h('button', { ...attrs, disabled: props.disabled, onClick: () => emit('click') }, slots.default?.())
  },
})

const stubs = {
  UButton: UButtonStub,
  ColorModeButton: true,
  AccountSettings: true,
  SignedIn: {
    setup(_props: unknown, { slots }: SetupContext) {
      return () => (isSignedInRef.value ? slots.default?.() : null)
    },
  },
  SignedOut: {
    setup(_props: unknown, { slots }: SetupContext) {
      return () => (!isSignedInRef.value ? slots.default?.() : null)
    },
  },
  SignInButton: { setup: (_p: unknown, { slots }: SetupContext) => () => h('div', slots.default?.()) },
}

describe('TheHeader/index.vue', () => {
  let wrapper: ReturnType<typeof mount> | null = null

  beforeEach(() => {
    showEditModal.value = false
    userRef.value = null
    isSignedInRef.value = false
  })

  afterEach(() => {
    wrapper?.unmount()
    wrapper = null
  })

  it('訪客也看得到「新增任務」按鈕（位置跟登入後一樣），但不能按、按了也不會開 Modal', async () => {
    wrapper = mount(TheHeader, { global: { stubs } })

    const button = wrapper.find('button[aria-label="新增任務"]')
    expect(button.exists()).toBe(true)
    expect(button.attributes('disabled')).toBeDefined()
    expect(button.attributes('title')).toBe('登入後才能新增任務')

    await button.trigger('click')
    expect(showEditModal.value).toBe(false)
    expect(wrapper.text()).toContain('訪客，請先登入')
  })

  it('登入後「新增任務」按鈕可以按，按下去會打開 Modal', async () => {
    isSignedInRef.value = true
    userRef.value = { id: 'user_1', fullName: '陳小明', firstName: '小明', lastName: '陳' }
    wrapper = mount(TheHeader, { global: { stubs } })

    const button = wrapper.find('button[aria-label="新增任務"]')
    expect(button.attributes('disabled')).toBeUndefined()
    expect(button.attributes('title')).toBeUndefined()

    await button.trigger('click')
    expect(showEditModal.value).toBe(true)
    expect(wrapper.text()).toContain('陳小明')
  })
})
