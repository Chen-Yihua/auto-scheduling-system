import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { onMounted, ref, type Ref } from 'vue'

import OAuthCallback from '~/pages/oauth/callback.vue'

vi.stubGlobal('onMounted', onMounted)

// ---------- 可由測試控制的 route / router / Clerk / toast / $fetch ----------
const route = { query: {} as Record<string, string> }
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

const stubs = { UIcon: true }

describe('pages/oauth/callback.vue', () => {
  beforeEach(() => {
    route.query = {}
    replaceSpy.mockReset()
    stateStore.clear()
    toastAddSpy.mockReset()
    fetchSpy.mockReset()
    getTokenSpy.mockReset()
    getTokenSpy.mockResolvedValue('jwt-token')
    vi.spyOn(console, 'error').mockImplementation(() => {})
  })

  it('有授權碼：先回首頁，換 token 在背景進行，這段期間「連接中」狀態為 true', async () => {
    route.query.code = 'auth-code'
    let finish: (value: unknown) => void = () => {}
    fetchSpy.mockReturnValue(new Promise((resolve) => { finish = resolve })) // 先不回應

    mount(OAuthCallback, { global: { stubs } })
    await flushPromises()

    // 後端還沒回應：已經回首頁了，而且狀態是「連接中」
    expect(replaceSpy).toHaveBeenCalledWith('/')
    expect(stateStore.get('googleCalendarConnecting')?.value).toBe(true)
    expect(toastAddSpy).not.toHaveBeenCalled()

    finish({ message: 'ok' })
    await flushPromises()
    expect(stateStore.get('googleCalendarConnecting')?.value).toBe(false)
  })

  it('有授權碼：帶著登入 token 把授權碼交給後端，成功後回首頁並提示成功', async () => {
    route.query.code = 'auth-code'
    fetchSpy.mockResolvedValueOnce({ message: 'ok' })

    mount(OAuthCallback, { global: { stubs } })
    await flushPromises()

    expect(fetchSpy).toHaveBeenCalledTimes(1)
    expect(fetchSpy).toHaveBeenCalledWith('http://api.test/oauth/callback', {
      method: 'POST',
      headers: { Authorization: 'Bearer jwt-token' },
      body: { code: 'auth-code' },
    })
    expect(replaceSpy).toHaveBeenCalledWith('/')
    expect(toastAddSpy).toHaveBeenCalledWith(expect.objectContaining({ title: '成功連接 Google Calendar', color: 'success' }))
    // 成功後通知首頁重新查一次連接狀態
    expect(stateStore.get('googleCalendarConnectedCount')?.value).toBe(1)
    expect(stateStore.get('googleCalendarConnecting')?.value).toBe(false)
  })

  it('後端換 token 失敗（例如 502）：回首頁並提示失敗，不會提示成功', async () => {
    route.query.code = 'auth-code'
    fetchSpy.mockRejectedValueOnce(new Error('502 Bad Gateway'))

    mount(OAuthCallback, { global: { stubs } })
    await flushPromises()

    expect(replaceSpy).toHaveBeenCalledWith('/')
    expect(toastAddSpy).toHaveBeenCalledTimes(1)
    expect(toastAddSpy).toHaveBeenCalledWith(expect.objectContaining({ title: '連接 Google Calendar 失敗', color: 'error' }))
    // 失敗不該通知重新查詢，「連接中」也要結束，卡片才不會一直轉圈
    expect(stateStore.get('googleCalendarConnectedCount')?.value).toBe(0)
    expect(stateStore.get('googleCalendarConnecting')?.value).toBe(false)
  })

  it('Google 導回時帶 error（例如使用者按取消）：不呼叫後端，提示授權失敗並回首頁', async () => {
    route.query.error = 'access_denied'

    mount(OAuthCallback, { global: { stubs } })
    await flushPromises()

    expect(fetchSpy).not.toHaveBeenCalled()
    expect(toastAddSpy).toHaveBeenCalledWith(expect.objectContaining({ title: 'Google 授權失敗：access_denied' }))
    expect(replaceSpy).toHaveBeenCalledWith('/')
  })

  it('直接打開這個網址、沒有授權碼：不呼叫後端，直接回首頁，也不會卡在「連接中」', async () => {
    mount(OAuthCallback, { global: { stubs } })
    await flushPromises()

    expect(fetchSpy).not.toHaveBeenCalled()
    expect(replaceSpy).toHaveBeenCalledWith('/')
    expect(stateStore.get('googleCalendarConnecting')?.value ?? false).toBe(false)
  })
})
