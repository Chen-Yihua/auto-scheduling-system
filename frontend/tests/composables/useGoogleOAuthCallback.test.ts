import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createSSRApp, defineComponent, ref, type Ref } from 'vue'
import { renderToString } from 'vue/server-renderer'

import { useGoogleOAuthCallback } from '~/composables/useGoogleOAuthCallback'

// ---------- 可由測試控制的 route / router / Clerk / toast / $fetch ----------
const route = { path: '/oauth/callback', query: {} as Record<string, string> }
const replaceSpy = vi.fn()
const toastAddSpy = vi.fn()
const fetchSpy = vi.fn()
const getTokenSpy = vi.fn()

vi.mock('vue-router', () => ({
  useRoute: () => route,
  useRouter: () => ({ replace: replaceSpy }),
}))
vi.mock('@clerk/vue', () => ({
  useAuth: () => ({ getToken: { value: getTokenSpy } }),
}))
vi.stubGlobal('useToast', () => ({ add: toastAddSpy }))
vi.stubGlobal('useRuntimeConfig', () => ({ public: { apiBaseUrl: 'http://api.test' } }))
vi.stubGlobal('$fetch', fetchSpy)

// Nuxt 的 useState：同一個 key 在所有元件之間共用同一份狀態
const stateStore = new Map<string, Ref<unknown>>()
vi.stubGlobal('useState', (key: string, init: () => unknown) => {
  if (!stateStore.has(key)) stateStore.set(key, ref(init()))
  return stateStore.get(key)
})

const connecting = () => stateStore.get('googleCalendarConnecting')?.value ?? false
const connectedCount = () => stateStore.get('googleCalendarConnectedCount')?.value ?? 0

// composable 要在元件的 setup 裡呼叫，用一個空元件來承載
const Host = defineComponent({
  setup() {
    useGoogleOAuthCallback()
    return () => null
  },
})

describe('useGoogleOAuthCallback', () => {
  beforeEach(() => {
    route.path = '/oauth/callback'
    route.query = {}
    replaceSpy.mockReset()
    toastAddSpy.mockReset()
    fetchSpy.mockReset()
    getTokenSpy.mockReset()
    getTokenSpy.mockResolvedValue('jwt-token')
    stateStore.clear()
    vi.spyOn(console, 'error').mockImplementation(() => {})
  })

  it('有授權碼：伺服器端渲染時就已經是「連接中」（不用等瀏覽器載入完 JavaScript）', async () => {
    route.query.code = 'auth-code'

    // 伺服器端渲染不會執行 onMounted，只會跑 setup；這時狀態就要是 true，
    // 導回來的第一份 HTML 裡行事曆卡片才會直接是「連接中」
    await renderToString(createSSRApp(Host))

    expect(connecting()).toBe(true)
    expect(fetchSpy).not.toHaveBeenCalled()
  })

  it('有授權碼：先把網址換成 /，換 token 在背景進行，這段期間仍是「連接中」', async () => {
    route.query.code = 'auth-code'
    let finish: (value: unknown) => void = () => {}
    fetchSpy.mockReturnValue(new Promise((resolve) => { finish = resolve })) // 先不回應

    mount(Host)
    await flushPromises()

    // 後端還沒回應：網址已經換掉，而且狀態是「連接中」、還沒有任何提示
    expect(replaceSpy).toHaveBeenCalledWith('/')
    expect(connecting()).toBe(true)
    expect(toastAddSpy).not.toHaveBeenCalled()

    finish({ message: 'ok' })
    await flushPromises()
    expect(connecting()).toBe(false)
  })

  it('有授權碼：帶著登入 token 把授權碼交給後端，成功後提示成功並通知重新查詢', async () => {
    route.query.code = 'auth-code'
    fetchSpy.mockResolvedValueOnce({ message: 'ok' })

    mount(Host)
    await flushPromises()

    expect(fetchSpy).toHaveBeenCalledTimes(1)
    expect(fetchSpy).toHaveBeenCalledWith('http://api.test/oauth/callback', {
      method: 'POST',
      headers: { Authorization: 'Bearer jwt-token' },
      body: { code: 'auth-code' },
    })
    expect(toastAddSpy).toHaveBeenCalledWith(expect.objectContaining({ title: '成功連接 Google Calendar', color: 'success' }))
    expect(connectedCount()).toBe(1)
    expect(connecting()).toBe(false)
  })

  it('後端換 token 失敗（例如 502）：提示失敗、不通知重新查詢，「連接中」也要結束', async () => {
    route.query.code = 'auth-code'
    fetchSpy.mockRejectedValueOnce(new Error('502 Bad Gateway'))

    mount(Host)
    await flushPromises()

    expect(toastAddSpy).toHaveBeenCalledTimes(1)
    expect(toastAddSpy).toHaveBeenCalledWith(expect.objectContaining({ title: '連接 Google Calendar 失敗', color: 'error' }))
    expect(connectedCount()).toBe(0)
    expect(connecting()).toBe(false)
  })

  it('拿不到登入 token：不呼叫後端，提示失敗，「連接中」結束', async () => {
    route.query.code = 'auth-code'
    getTokenSpy.mockResolvedValue(null)

    mount(Host)
    await flushPromises()

    expect(fetchSpy).not.toHaveBeenCalled()
    expect(toastAddSpy).toHaveBeenCalledWith(expect.objectContaining({ title: '連接 Google Calendar 失敗' }))
    expect(connecting()).toBe(false)
  })

  it('Google 導回時帶 error（例如使用者按取消）：不呼叫後端、不進入「連接中」，提示授權失敗並換回 /', async () => {
    route.query.error = 'access_denied'

    mount(Host)
    await flushPromises()

    expect(fetchSpy).not.toHaveBeenCalled()
    expect(connecting()).toBe(false)
    expect(toastAddSpy).toHaveBeenCalledWith(expect.objectContaining({ title: 'Google 授權失敗：access_denied' }))
    expect(replaceSpy).toHaveBeenCalledWith('/')
  })

  it('直接打開 /oauth/callback、沒有授權碼：不呼叫後端，直接回首頁，也不會卡在「連接中」', async () => {
    mount(Host)
    await flushPromises()

    expect(fetchSpy).not.toHaveBeenCalled()
    expect(replaceSpy).toHaveBeenCalledWith('/')
    expect(connecting()).toBe(false)
  })

  it('一般進首頁（不是 /oauth/callback）：什麼都不做，即使網址剛好帶 code 參數', async () => {
    route.path = '/'
    route.query.code = 'something-else'

    mount(Host)
    await flushPromises()

    expect(fetchSpy).not.toHaveBeenCalled()
    expect(replaceSpy).not.toHaveBeenCalled()
    expect(toastAddSpy).not.toHaveBeenCalled()
    expect(connecting()).toBe(false)
  })
})
