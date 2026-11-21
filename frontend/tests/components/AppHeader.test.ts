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

  it('訪客也看得到「新增任務」按鈕（位置跟登入後一樣），但不能按、按了也不會開 Modal', async () => {
    wrapper = mount(AppHeader, { global: { stubs } })

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
    wrapper = mount(AppHeader, { global: { stubs } })

    const button = wrapper.find('button[aria-label="新增任務"]')
    expect(button.attributes('disabled')).toBeUndefined()
    expect(button.attributes('title')).toBeUndefined()

    await button.trigger('click')
    expect(showEditModal.value).toBe(true)
    expect(wrapper.text()).toContain('陳小明')
  })

  it('AC4：已登入時，標題列自己掛著新增任務的視窗，按按鈕就打開；不需要頁面上有 TaskForm', async () => {
    isSignedInRef.value = true
    userRef.value = { id: 'user_1', fullName: '陳小明', firstName: '小明', lastName: '陳' }
    wrapper = mount(AppHeader, { global: { stubs } })

    expect(wrapper.find('[data-testid="edit-modal"]').attributes('data-open')).toBe('false')
    await wrapper.find('button[aria-label="新增任務"]').trigger('click')
    expect(wrapper.find('[data-testid="edit-modal"]').attributes('data-open')).toBe('true')
  })

  it('AC1：有「首頁」「任務管理」「排程」「分析」4 個連結，依序連到 /、/tasks、/schedule、/productivity', () => {
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
  ])('AC2：在 %s 時只有「%s」有 aria-current="page"', (path, label) => {
    routePath.value = path
    wrapper = mount(AppHeader, { global: { stubs } })

    const current = wrapper.findAll('nav a').filter((a) => a.attributes('aria-current') === 'page')
    expect(current.map((a) => a.text())).toEqual([label])
  })

  it('AC3：不再有「工作效率」圖示按鈕', () => {
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
