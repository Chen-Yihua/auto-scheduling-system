// tests/utils/components/LinkedAccount.test.ts
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick, defineComponent, ref, h } from 'vue'

vi.mock('~/composables/useLinkedAccount', () => {
  const refData = ref([
    {
        platform: 'github',
        avatar: 'https://example.com/avatar.png',
        label: 'GitHub Key',
        icon: 'i-lucide-github',
        value: 'ghp-abc123',
        inputValue: '',
        editing: false,
        showPassword: false,
        },
        {
        platform: 'jira',
        avatar: 'https://example.com/avatar.png',
        label: 'Jira Key',
        icon: 'i-lucide-jira',
        domain: 'example.atlassian.net',
        value: 'jrp-abc123',
        inputValue: '',
        editing: false,
        showPassword: false,
    },
    {
        platform: 'moodle',
        avatar: 'https://example.com/avatar.png',
        label: 'Moodle Key',
        icon: 'moodle',
        username:'abc',
        value: 'mdp-abc123',
        inputValue: '',
        editing: false,
        showPassword: false,
    }
  ])

  const mockLinked = {
    keys: refData,
    fetchKeys: vi.fn(),
    openEdit: vi.fn(),
    cancelEdit: vi.fn(),
    saveKey: vi.fn(),
    deleteKey: vi.fn(),
  }

  return {
    useLinkedAccount: () => mockLinked
  }
})

// ======== 被測 hook ========
import AccountSettings from '~/components/TheHeader/components/AccountSettings.vue' // 請依實際路徑修改
import { useLinkedAccount } from '~/composables/useLinkedAccount'

// ======== 被測元件 ========
vi.mock('@clerk/vue', () => {
  // 在 factory 內部再定義一次
  const UserButton = defineComponent({
    name: 'UserButton',
    setup(_, { slots }) {
      return () => h('div', { class: 'user-button-mock' }, slots.default?.())
    },
  })
  UserButton.UserProfilePage = defineComponent({
    name: 'UserProfilePage',
    setup(_, { slots }) {
      return () => h('div', { class: 'profile-page-mock' }, slots.default?.())
    },
  })

  return {
    useUser: () => ({ user: { id: 'mock-user-id', email: 'mock@mail.com' } }),
    useClerk: () => ({ signOut: vi.fn() }),
    ClerkProvider: defineComponent({ setup(_, { slots }) { return () => slots.default?.() } }),
    ClerkLoaded: defineComponent({ setup(_, { slots }) { return () => slots.default?.() } }),
    SignedIn: defineComponent({ setup(_, { slots }) { return () => slots.default?.() } }),
    SignedOut: defineComponent({ setup(_, { slots }) { return () => slots.default?.() } }),
    UserButton, // 回傳內部剛剛宣告的 UserButton
  }
})

// ======== Mock global function and variable ======== 
const tokenSpy = vi.fn().mockResolvedValue('dummy-token')
const toastSpy = { add: vi.fn() }
let fetchSpy = vi.fn()

vi.stubGlobal('useAuth',         () => ({ getToken: { value: tokenSpy } }))
vi.stubGlobal('useUser',         () => ({ user: ref({ id: 'u1' }) }))
vi.stubGlobal('useToast',        () => toastSpy)
vi.stubGlobal('useRuntimeConfig',() => ({ public: { apiBaseUrl: 'http://localhost:8000' } }))
vi.stubGlobal('$fetch',          (...args: any[]) => fetchSpy(...args))

// 可點擊的 UButton
const StubButton = defineComponent({
  name: 'UButton',
  emits: ['click'],
  props: ['disabled', 'loading', 'icon', 'color', 'size', 'ariaLabel'],
  setup(props, { emit, slots }) {
    return () => h(
        'button', 
        { 
            disabled: props.disabled,
            'aria-label': props.ariaLabel,
            onClick: () => emit('click') 
        }, 
        slots.default ? slots.default() : ''
    )
  },
})

// 其他元件直接 true stub
const uiStubs: Record<string, any> = {
    UButton: StubButton,
    UForm: true,
    UInput: true,
    UTextarea: true,
    UFormField: true,
    USelect: true,
    UPopover: true,
    UCalendar: true,
    USkeleton: true,
    UBadge: true,
    UIcon: true,
}


// ======== 測試 ========
describe('AccountSettings.vue (render)', () => {
    beforeEach(() => {
        fetchSpy = vi.fn()
        toastSpy.add.mockClear()
        tokenSpy.mockClear()

        const linked = useLinkedAccount()
        linked.keys.value[0].editing = false
        linked.keys.value[0].inputValue = ''
        linked.keys.value[0].value = 'ghp-abc123'

        linked.keys.value[1].editing = false
        linked.keys.value[1].inputValue = ''
        linked.keys.value[1].value = 'jrp-abc123'
        linked.keys.value[1].domain = 'example.atlassian.net'

        linked.keys.value[2].editing = false
        linked.keys.value[2].inputValue = ''
        linked.keys.value[2].value = 'mdp-abc123'
        linked.keys.value[2].username = 'abc'
        linked.keys.value[2].password = 'mdp-abc123'
    })

    it('元件載入時，onMounted(fetchKeys) 應該被呼叫', async () => {
        const linked = useLinkedAccount()
        fetchSpy.mockResolvedValueOnce([])
        mount(AccountSettings, { global: { stubs: uiStubs } })
        expect(linked.fetchKeys).toHaveBeenCalled()
    })

    it('點擊 Edit 按鈕會觸發 openEdit', async () => {
        fetchSpy.mockResolvedValueOnce([])
        const linked = useLinkedAccount()
        const wrapper = mount(AccountSettings, { global: { stubs: uiStubs } })
        await flushPromises()

        const editBtn = wrapper.findAllComponents(StubButton).filter(btn => btn.text() === 'Edit')
        expect(editBtn.length).toBe(3)
        await editBtn[0].trigger('click')
        await editBtn[1].trigger('click')
        await editBtn[2].trigger('click')
        expect(linked.openEdit).toHaveBeenCalled()
    })  

    it('copyKey 處理', async () => {
        const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
        Object.assign(navigator, {
            clipboard: {
                writeText: vi.fn().mockRejectedValue(new Error('copy fail'))
            }
        })

        fetchSpy.mockResolvedValueOnce([])
        const wrapper = mount(AccountSettings, { global: { stubs: uiStubs } })
        await flushPromises()

        const copyBtn = wrapper.findAllComponents(StubButton).filter(c => c.props('icon') === 'i-lucide-copy')
        await copyBtn[0].trigger('click')
        await copyBtn[1].trigger('click')
        await copyBtn[2].trigger('click')
        await nextTick()

        expect(errorSpy).toHaveBeenCalledWith('Failed to copy key: ', expect.any(Error))
        errorSpy.mockRestore()
    })

    // ======== GitHub ========
    it('在 GitHub 非編輯模式下，顯示帳號與遮蔽後的 API key', () => {
        const wrapper = mount(AccountSettings, { global: { stubs: uiStubs } })
        expect(wrapper.text()).toContain('GitHub Key')
        expect(wrapper.text()).toContain('****c123') // GitHub key
    })

    it('點 github 編輯按鈕，若後端有資料，顯示輸入框，且可以 Save', async () => {
        fetchSpy.mockResolvedValueOnce([])
        const linked = useLinkedAccount()
        const wrapper = mount(AccountSettings, { global: { stubs: uiStubs } })
        await flushPromises()

        const editBtns = wrapper.findAllComponents(StubButton).filter(btn => btn.text() === 'Edit')
        expect(editBtns.length).toBeGreaterThanOrEqual(3)
        await editBtns[0].trigger('click')
        expect(linked.openEdit).toHaveBeenCalledWith(linked.keys.value[0])

        linked.keys.value[0].editing = true
        await nextTick()
        expect(wrapper.find('u-input-stub[placeholder^="請輸入 API Token 或 Base64"]').exists()).toBe(true)
        const saveBtn = wrapper.findAllComponents(StubButton).find(b => b.text() === 'Save')!
        expect(saveBtn.props('disabled')).toBe(true)

        linked.keys.value[0].inputValue = 'new-ghp-123'
        await nextTick()
        expect(saveBtn.props('disabled')).toBe(false)

        await saveBtn.trigger('click')
        expect(linked.saveKey).toHaveBeenCalledWith(linked.keys.value[0])
    })

    it('點擊 Github Delete 按鈕會觸發 deleteKey', async () => {
        const linked = useLinkedAccount()
        linked.keys.value[0].editing = true
        await nextTick()

        fetchSpy.mockResolvedValueOnce([])
        const wrapper = mount(AccountSettings, { global: { stubs: uiStubs } })
        await flushPromises()

        const delBtn = wrapper.findAll('button').find(btn => btn.text() === 'Delete')
        expect(delBtn).toBeTruthy()
        await delBtn!.trigger('click')
        expect(linked.deleteKey).toHaveBeenCalled()
    })

    it('點擊 Github Save 按鈕，在輸入沒東西時會 disabled', async () => {
        const linked = useLinkedAccount()
        linked.keys.value[0].editing = true
        linked.keys.value[0].inputValue = ''
        await nextTick()

        fetchSpy.mockResolvedValueOnce([])
        const wrapper = mount(AccountSettings, { global: { stubs: uiStubs } })
        await flushPromises()
        
        const saveBtn = wrapper.findAllComponents(StubButton).filter(comp => comp.text() === 'Save')
        expect(saveBtn[0]!.props('disabled')).toBe(true)
    })

    it('點擊 Github Cancel 按鈕，會清空輸入框', async () => {
        const linked = useLinkedAccount()
        linked.keys.value[0].editing = true
        linked.keys.value[0].inputValue = ''
        await nextTick()

        fetchSpy.mockResolvedValueOnce([])
        const wrapper = mount(AccountSettings, { global: { stubs: uiStubs } })
        await flushPromises()

        const calBtn = wrapper.findAll('button').find(btn => btn.text() === 'Cancel')
        expect(calBtn).toBeTruthy()
        await calBtn!.trigger('click')
        expect(linked.keys.value[0].inputValue).toBe('')
        expect(linked.keys.value[0].value).toBe('ghp-abc123')
        expect(linked.cancelEdit).toHaveBeenCalled()
    })



    // ======== Jira ========
    it('在 Jira 非編輯模式下，顯示帳號與遮蔽後的 API key', () => {
        const wrapper = mount(AccountSettings, { global: { stubs: uiStubs } })
        expect(wrapper.text()).toContain('Jira Key')
        expect(wrapper.text()).toContain('****c123') // Jira Key      
    })

    it('點 jira 編輯按鈕，若後端有資料，顯示輸入框，且可以 Save', async () => {
        fetchSpy.mockResolvedValueOnce([])
        const linked = useLinkedAccount()
        const wrapper = mount(AccountSettings, { global: { stubs: uiStubs } })
        await flushPromises()

        const editBtns = wrapper.findAllComponents(StubButton).filter(btn => btn.text() === 'Edit')
        expect(editBtns.length).toBeGreaterThanOrEqual(3)
        await editBtns[1].trigger('click')
        expect(linked.openEdit).toHaveBeenCalledWith(linked.keys.value[1])

        linked.keys.value[1].editing = true
        await nextTick()
        expect(wrapper.find('u-input-stub[placeholder^="請輸入 API Token 或 Base64"]').exists()).toBe(true)
        expect(linked.keys.value[1].domain).toBe('example.atlassian.net')

        const saveBtn = wrapper.findAllComponents(StubButton).find(comp => comp.text() === 'Save')!
        expect(saveBtn.props('disabled')).toBe(true)

        linked.keys.value[1].inputValue = 'new-jrp-123'
        linked.keys.value[1].domain = 'new-domain'
        await nextTick()

        expect(saveBtn.props('disabled')).toBe(false)

        await saveBtn.trigger('click')
        expect(linked.saveKey).toHaveBeenCalledWith(linked.keys.value[1])
    })

    it('點擊 jira Delete 按鈕會觸發 deleteKey', async () => {
        const linked = useLinkedAccount()
        linked.keys.value[1].editing = true
        await nextTick()

        fetchSpy.mockResolvedValueOnce([])
        const wrapper = mount(AccountSettings, { global: { stubs: uiStubs } })
        await flushPromises()

        const delBtn = wrapper.findAll('button').find(btn => btn.text() === 'Delete')
        expect(delBtn).toBeTruthy()
        await delBtn!.trigger('click')
        expect(linked.deleteKey).toHaveBeenCalled()
    })

    it('點擊 jira Cancel 按鈕，會清空輸入框', async () => {
        const linked = useLinkedAccount()
        linked.keys.value[1].editing = true
        linked.keys.value[1].inputValue = ''
        linked.keys.value[1].domain = 'example.atlassian.net'
        await nextTick()

        fetchSpy.mockResolvedValueOnce([])
        const wrapper = mount(AccountSettings, { global: { stubs: uiStubs } })
        await flushPromises()

        const calBtn = wrapper.findAll('button').find(btn => btn.text() === 'Cancel')
        expect(calBtn).toBeTruthy()
        await calBtn!.trigger('click')
        expect(linked.keys.value[1].domain).toBe('example.atlassian.net')
        expect(linked.keys.value[1].inputValue).toBe('')
        expect(linked.cancelEdit).toHaveBeenCalled()
    })
    
    it('在 jira 編輯模式下，若後端沒資料，顯示輸入框，且 Save disabled', async () => {
        const linked = useLinkedAccount()
        linked.keys.value[1].editing = true
        linked.keys.value[1].domain = ''
        linked.keys.value[1].value = ''
        await nextTick()

        fetchSpy.mockResolvedValueOnce([])
        const wrapper = mount(AccountSettings, { global: { stubs: uiStubs } })
        await flushPromises()

        // 檢查是否有 API、Domain input
        expect(wrapper.find('u-input-stub[placeholder^="請輸入 Jira Domain"]').exists()).toBe(true)
        expect(wrapper.find('u-input-stub[placeholder^="請輸入 API Token 或 Base64"]').exists()).toBe(true)

        // Save 按鈕在輸入框沒東西時 disabled
        const saveBtn = wrapper.findAllComponents(StubButton).find(comp => comp.text() === 'Save')
        expect(saveBtn!.props('disabled')).toBe(true)
    })



    // ======== Moodle ========
    it('在 Moodle 非編輯模式下，顯示帳號與遮蔽後的 API key', () => {
        const wrapper = mount(AccountSettings, { global: { stubs: uiStubs } })
        expect(wrapper.text()).toContain('Moodle Key') 
        expect(wrapper.text()).toContain('abc') // Moodle 帳號
        expect(wrapper.text()).toContain('****c123') // Moodle 密碼
    })

    it('點 moodle 編輯按鈕，若後端有資料，顯示輸入框，且可以 Save', async () => {
        fetchSpy.mockResolvedValueOnce([])
        const linked = useLinkedAccount()
        const wrapper = mount(AccountSettings, { global: { stubs: uiStubs } })
        await flushPromises()

        const editBtns = wrapper.findAllComponents(StubButton).filter(btn => btn.text() === 'Edit')
        expect(editBtns.length).toBeGreaterThanOrEqual(3)
        await editBtns[2].trigger('click')
        expect(linked.openEdit).toHaveBeenCalledWith(linked.keys.value[2])

        linked.keys.value[2].editing = true
        await nextTick()
        expect(wrapper.find('u-input-stub[placeholder^="請輸入 Moodle 密碼"]').exists()).toBe(true)        
        expect(linked.keys.value[2].username).toBe('abc')

        const saveBtn = wrapper.findAllComponents(StubButton).find(comp => comp.text() === 'Save')!
        expect(saveBtn.props('disabled')).toBe(true)

        linked.keys.value[2].inputValue = 'new-jrp-123'
        linked.keys.value[2].username = 'new-username'
        await nextTick()

        expect(saveBtn.props('disabled')).toBe(false)

        await saveBtn.trigger('click')
        expect(linked.saveKey).toHaveBeenCalledWith(linked.keys.value[2])
    })

    it('點擊 moodle Delete 按鈕會觸發 deleteKey', async () => {
        const linked = useLinkedAccount()
        linked.keys.value[2].editing = true
        await nextTick()

        fetchSpy.mockResolvedValueOnce([])
        const wrapper = mount(AccountSettings, { global: { stubs: uiStubs } })
        await flushPromises()

        const delBtn = wrapper.findAll('button').find(btn => btn.text() === 'Delete')
        expect(delBtn).toBeTruthy()
        await delBtn!.trigger('click')
        expect(linked.deleteKey).toHaveBeenCalled()
    })
    
    it('點擊 moodle Cancel 按鈕，會清空輸入框', async () => {
        const linked = useLinkedAccount()
        linked.keys.value[2].editing = true
        linked.keys.value[2].username = 'abc' 
        await nextTick()

        fetchSpy.mockResolvedValueOnce([])
        const wrapper = mount(AccountSettings, { global: { stubs: uiStubs } })
        await flushPromises()

        const calBtn = wrapper.findAll('button').find(btn => btn.text() === 'Cancel')
        expect(calBtn).toBeTruthy()
        await calBtn!.trigger('click')
        expect(linked.keys.value[2].username).toBe('abc')
        expect(linked.keys.value[2].inputValue).toBe('')
        expect(linked.cancelEdit).toHaveBeenCalled()
    })

    it('在 moodle 編輯模式下，若後端沒資料，顯示輸入框，且 Save disabled', async () => {
        const linked = useLinkedAccount()
        linked.keys.value[2].editing = true
        linked.keys.value[2].username = ''
        linked.keys.value[2].password = ''
        await nextTick()

        fetchSpy.mockResolvedValueOnce([])
        const wrapper = mount(AccountSettings, { global: { stubs: uiStubs } })
        await flushPromises()

        // 檢查欄位
        expect(wrapper.find('u-input-stub[placeholder^="請輸入 Moodle 帳號"]').exists()).toBe(true)
        expect(wrapper.find('u-input-stub[placeholder^="請輸入 Moodle 密碼"]').exists()).toBe(true)

        // Save 按鈕在輸入框沒東西時 disabled
        const saveBtn = wrapper.findAllComponents(StubButton).find(comp => comp.text() === 'Save')
        expect(saveBtn!.props('disabled')).toBe(true)
    })
    

    // ======== Google ========
    it('當 token 正常且 fetch 回傳成功，isConnected 會變 true', async () => {
        tokenSpy.mockResolvedValueOnce('valid-token')
        fetchSpy.mockResolvedValueOnce({ calendars: [] })

        const wrapper = mount(AccountSettings, { global: { stubs: uiStubs } })
        await flushPromises()

        const vm = wrapper.vm as any
        expect(vm.isConnected).toBe(true)

        const googleBtn = wrapper.find('button[color="primary"][icon="i-lucide-calendar"]')
        expect(googleBtn.exists()).toBe(false)
    })

    it('Google Calendar token 無效時 isConnected 會變 false', async () => {
        tokenSpy.mockResolvedValueOnce(null) // 模擬 getToken 拿不到
        fetchSpy.mockResolvedValueOnce({ calendars: [] })
        const wrapper = mount(AccountSettings, { global: { stubs: uiStubs } })
        await flushPromises()
        const vm = wrapper.vm as any
        expect(vm.isConnected).toBe(false)
    })


    it('goToGoogleAuth 會導向 Google OAuth', () => {
        // 把 window.location 刪掉，避免無法寫入 href
        delete (window as any).location
        window.location = { href: '' } as any

        const wrapper = mount(AccountSettings, { global: { stubs: uiStubs } })
        ;(wrapper.vm as any).goToGoogleAuth()
        expect(window.location.href).toMatch(/^https:\/\/accounts\.google\.com/)
    })
})
