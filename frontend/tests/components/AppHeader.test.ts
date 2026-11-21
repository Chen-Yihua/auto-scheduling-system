import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { mount } from '@vue/test-utils';
import { ref, watch, h, defineComponent } from 'vue';
import type { SetupContext } from 'vue';

import AppHeader from '~/components/header/AppHeader.vue';

vi.stubGlobal('watch', watch);

// ---------- Clerk mock：isSignedIn／user 可由測試動態控制 ----------
const isSignedInRef = ref<boolean | undefined>(undefined);
const userRef = ref<{ id: string; fullName: string; firstName: string; lastName: string } | null>(null)

vi.mock('@clerk/vue', () => ({
  useUser: () => ({ user: userRef, isSignedIn: isSignedInRef }),
}))

// 跟 TaskEditModal 共用的 Modal 開關
const showEditModal = ref(false)
vi.mock('~/composables/useTaskForm', () => ({
  useTaskForm: () => ({ showEditModal }),
}))

const ensureUserRecordSpy = vi.fn()
vi.mock('~/composables/useUserSync', () => ({
  useUserSync: () => ({ ensureUserRecord: ensureUserRecordSpy }),
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

// 假的 TaskEditModal：只反映共用的 showEditModal，證明標題列自己帶著這個視窗，不靠頁面放 TaskForm
const TaskEditModalStub = defineComponent({
  name: 'TaskEditModal',
  setup: () => () => h('div', { 'data-testid': 'edit-modal', 'data-open': showEditModal.value ? 'true' : 'false' }),
})

// 路徑可由測試動態控制
const routePath = ref('/')
vi.stubGlobal('useRoute', () => ({ path: routePath.value }))

// NuxtLink 畫成 a：保留 to 當 href，其他屬性（aria-current）原樣轉傳
const NuxtLinkStub = defineComponent({
  props: { to: { type: String, default: '' } },
  setup: (props, { slots, attrs }) => () => h('a', { ...attrs, href: props.to }, slots.default?.()),
})

const stubs = {
  TaskEditModal: TaskEditModalStub,
  NuxtLink: NuxtLinkStub,
  UIcon: true,
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

describe('header/AppHeader.vue', () => {
  let wrapper: ReturnType<typeof mount> | null = null

  beforeEach(() => {
    showEditModal.value = false
    routePath.value = '/'
    userRef.value = null
    isSignedInRef.value = false
    ensureUserRecordSpy.mockClear()
  })

  afterEach(() => {
    wrapper?.unmount()
    wrapper = null
  })

  it.each(['/', '/tasks', '/schedule', '/productivity'])('issue-178 AC4：在 %s 的標題列沒有新增任務按鈕（訪客與已登入都一樣），但仍掛著編輯視窗，歡迎文字保留', (path) => {
    routePath.value = path
    for (const signedIn of [false, true]) {
      isSignedInRef.value = signedIn
      userRef.value = signedIn ? { id: 'user_1', fullName: '陳小明', firstName: '小明', lastName: '陳' } : null
      wrapper = mount(AppHeader, { global: { stubs } })

      expect(wrapper.find('[aria-label="新增任務"]').exists()).toBe(false)
      expect(wrapper.text()).not.toContain('新增任務')
      expect(wrapper.find('[data-testid="edit-modal"]').exists()).toBe(true)
      expect(wrapper.text()).toContain(signedIn ? '陳小明' : '訪客，請先登入')
      wrapper.unmount()
    }
    wrapper = null
  })

  it('issue-178 AC1：有「首頁」「任務管理」「排程」「分析」4 個連結，依序連到 /、/tasks、/schedule、/productivity', () => {
    wrapper = mount(AppHeader, { global: { stubs } })

    const links = wrapper.findAll('nav a').map((a) => [a.text(), a.attributes('href')])
    expect(links).toEqual([
      ['首頁', '/'],
      ['任務管理', '/tasks'],
      ['排程', '/schedule'],
      ['分析', '/productivity'],
    ])
  })

  it.each([
    ['/', '首頁'],
    ['/tasks', '任務管理'],
    ['/schedule', '排程'],
    ['/productivity', '分析'],
  ])('issue-178 AC2：在 %s 時只有「%s」有 aria-current="page"', (path, label) => {
    routePath.value = path
    wrapper = mount(AppHeader, { global: { stubs } })

    const current = wrapper.findAll('nav a').filter((a) => a.attributes('aria-current') === 'page')
    expect(current.map((a) => a.text())).toEqual([label])
  })

  it('issue-178 AC3：不再有「工作效率」圖示按鈕', () => {
    wrapper = mount(AppHeader, { global: { stubs } })

    expect(wrapper.find('[aria-label="工作效率"]').exists()).toBe(false)
  })

  it('使用者登入（user 從 null 變成有值）時，確認後端有這個使用者；登出不會呼叫', async () => {
    wrapper = mount(AppHeader, { global: { stubs } })
    const user = { id: 'user_1', fullName: '陳小明', firstName: '小明', lastName: '陳' }

    userRef.value = user
    await wrapper.vm.$nextTick()
    expect(ensureUserRecordSpy).toHaveBeenCalledWith(user)

    ensureUserRecordSpy.mockClear()
    userRef.value = null
    await wrapper.vm.$nextTick()
    expect(ensureUserRecordSpy).not.toHaveBeenCalled()
  })

})
