import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { onMounted } from 'vue'

import OAuthCallback from '~/pages/oauth/callback.vue'

vi.stubGlobal('onMounted', onMounted)

// ---------- 可由測試控制的 route / router / Clerk / toast / $fetch ----------
const route = { query: {} as Record<string, string> }
const pushSpy = vi.fn()
const toastAddSpy = vi.fn()
const fetchSpy = vi.fn()
const getTokenSpy = vi.fn()

vi.mock('vue-router', () => ({
  useRoute: () => route,
  useRouter: () => ({ push: pushSpy }),
}))
vi.mock('@clerk/vue', () => ({
  useAuth: () => ({ getToken: { value: getTokenSpy } }),
}))
vi.stubGlobal('useToast', () => ({ add: toastAddSpy }))
vi.stubGlobal('useRuntimeConfig', () => ({ public: { apiBaseUrl: 'http://api.test' } }))
vi.stubGlobal('$fetch', fetchSpy)

const stubs = { UIcon: true }

describe('pages/oauth/callback.vue', () => {
  beforeEach(() => {
    route.query = {}
    pushSpy.mockReset()
    toastAddSpy.mockReset()
    fetchSpy.mockReset()
    getTokenSpy.mockReset()
    getTokenSpy.mockResolvedValue('jwt-token')
    vi.spyOn(console, 'error').mockImplementation(() => {})
  })

  it('等後端跟 Google 換 token 的期間要有畫面，不能是空白（先前缺 template）', async () => {
    route.query.code = 'auth-code'
    fetchSpy.mockReturnValue(new Promise(() => {})) // 一直沒回應

    const wrapper = mount(OAuthCallback, { global: { stubs } })
    await flushPromises()

    expect(wrapper.text()).toContain('正在連接 Google Calendar')
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
    expect(pushSpy).toHaveBeenCalledWith('/')
    expect(toastAddSpy).toHaveBeenCalledWith(expect.objectContaining({ title: '成功連接 Google Calendar', color: 'success' }))
  })

  it('後端換 token 失敗（例如 502）：回首頁並提示失敗，不會提示成功', async () => {
    route.query.code = 'auth-code'
    fetchSpy.mockRejectedValueOnce(new Error('502 Bad Gateway'))

    mount(OAuthCallback, { global: { stubs } })
    await flushPromises()

    expect(pushSpy).toHaveBeenCalledWith('/')
    expect(toastAddSpy).toHaveBeenCalledTimes(1)
    expect(toastAddSpy).toHaveBeenCalledWith(expect.objectContaining({ title: '連接 Google Calendar 失敗', color: 'error' }))
  })

  it('Google 導回時帶 error（例如使用者按取消）：不呼叫後端，提示授權失敗並回首頁', async () => {
    route.query.error = 'access_denied'

    mount(OAuthCallback, { global: { stubs } })
    await flushPromises()

    expect(fetchSpy).not.toHaveBeenCalled()
    expect(toastAddSpy).toHaveBeenCalledWith(expect.objectContaining({ title: 'Google 授權失敗：access_denied' }))
    expect(pushSpy).toHaveBeenCalledWith('/')
  })
})
