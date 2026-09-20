// tests/utils/useusersync.test.ts
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useUserSync } from '~/composables/useUserSync'

// ---------- mock @clerk/vue：getToken 用可控的 spy ----------
const { tokenSpy } = vi.hoisted(() => ({ tokenSpy: vi.fn() }))
vi.mock('@clerk/vue', () => ({
  useAuth: () => ({ getToken: { value: tokenSpy } }),
}))

// ---------- Nuxt auto-import 的全域 stub ----------
const toastSpy = { add: vi.fn() }
const fetchSpy = vi.fn()
vi.stubGlobal('useToast', () => toastSpy)
vi.stubGlobal('useRuntimeConfig', () => ({ public: { apiBaseUrl: 'http://api' } }))
vi.stubGlobal('fetch', (...args: unknown[]) => fetchSpy(...args))

const clerkUser = {
  id: 'user_1',
  primaryEmailAddress: { emailAddress: 'a@b.com' },
  fullName: '王小明',
}

// 假的 fetch 回應：原生 fetch 遇到 4xx / 5xx 不會丟例外，只會把狀態放在 ok / status
const response = (status: number) => ({ ok: status >= 200 && status < 300, status }) as Response

// 依序回覆：第一次是 GET /users/me，第二次是 POST /users/
const replies = (...statuses: number[]) => {
  statuses.forEach((s) => fetchSpy.mockResolvedValueOnce(response(s)))
}

describe('useUserSync：登入後確認並建立後端使用者', () => {
  beforeEach(() => {
    fetchSpy.mockReset()
    toastSpy.add.mockClear()
    tokenSpy.mockReset().mockResolvedValue('jwt-token')
    vi.spyOn(console, 'error').mockImplementation(() => {})
  })

  it('後端已經有這個使用者時，不會再建立，也不跳任何提示', async () => {
    replies(200)

    await useUserSync().ensureUserRecord(clerkUser)

    expect(fetchSpy).toHaveBeenCalledTimes(1)
    expect(fetchSpy.mock.calls[0][0]).toBe('http://api/users/me')
    expect(toastSpy.add).not.toHaveBeenCalled()
  })

  it('後端沒有這個使用者（404）時建立它，帶上正確的資料與登入憑證，成功不跳提示', async () => {
    replies(404, 200)

    await useUserSync().ensureUserRecord(clerkUser)

    expect(fetchSpy).toHaveBeenCalledTimes(2)
    const [url, init] = fetchSpy.mock.calls[1]
    expect(url).toBe('http://api/users/')
    expect(init.method).toBe('POST')
    expect(init.headers.Authorization).toBe('Bearer jwt-token')
    expect(JSON.parse(init.body)).toEqual({ clerk_id: 'user_1', email: 'a@b.com', name: '王小明' })
    expect(toastSpy.add).not.toHaveBeenCalled()
  })

  it('建立時回 409（使用者剛好已被建好，例如另一個分頁）不算失敗，不跳提示', async () => {
    replies(404, 409)

    await useUserSync().ensureUserRecord(clerkUser)

    expect(toastSpy.add).not.toHaveBeenCalled()
  })

  it.each([
    [503, '資料庫暫時無法使用'],
    [500, '伺服器發生錯誤'],
    [429, '請求太頻繁'],
    [401, '登入狀態驗證失敗'],
  ])('建立失敗（狀態碼 %i）要讓使用者知道，並說明原因', async (status, expectedText) => {
    replies(404, status)

    await useUserSync().ensureUserRecord(clerkUser)

    expect(toastSpy.add).toHaveBeenCalledTimes(1)
    const toast = toastSpy.add.mock.calls[0][0]
    expect(toast.title).toBe('無法建立你的使用者資料')
    expect(toast.description).toContain(expectedText)
    expect(toast.color).toBe('error')
  })

  it('建立時根本連不上伺服器（網路錯誤）也要讓使用者知道', async () => {
    fetchSpy.mockResolvedValueOnce(response(404)).mockRejectedValueOnce(new TypeError('Failed to fetch'))

    await useUserSync().ensureUserRecord(clerkUser)

    expect(toastSpy.add).toHaveBeenCalledTimes(1)
    expect(toastSpy.add.mock.calls[0][0].description).toContain('無法連線到伺服器')
  })

  it('連「確認使用者是否存在」都失敗（伺服器錯誤）只是背景檢查，不打斷使用者、也不亂建立', async () => {
    replies(500)

    await useUserSync().ensureUserRecord(clerkUser)

    expect(fetchSpy).toHaveBeenCalledTimes(1) // 沒有進到建立那一步
    expect(toastSpy.add).not.toHaveBeenCalled()
  })

  it('確認使用者時連不上伺服器，一樣安靜，不跳提示', async () => {
    fetchSpy.mockRejectedValueOnce(new TypeError('Failed to fetch'))

    await useUserSync().ensureUserRecord(clerkUser)

    expect(toastSpy.add).not.toHaveBeenCalled()
  })

  it('拿不到登入憑證時什麼都不做（不打後端、不跳提示）', async () => {
    tokenSpy.mockRejectedValueOnce(new Error('no session'))

    await useUserSync().ensureUserRecord(clerkUser)

    expect(fetchSpy).not.toHaveBeenCalled()
    expect(toastSpy.add).not.toHaveBeenCalled()
  })

  it('同時觸發兩次只會跑一輪，已確認過的使用者之後不會再打後端', async () => {
    replies(404, 200)
    const { ensureUserRecord } = useUserSync()

    await Promise.all([ensureUserRecord(clerkUser), ensureUserRecord(clerkUser)])
    expect(fetchSpy).toHaveBeenCalledTimes(2) // GET + POST 各一次，不是兩倍

    await ensureUserRecord(clerkUser)
    expect(fetchSpy).toHaveBeenCalledTimes(2) // 已確認過，不再打
  })

  it('建立失敗的下次觸發會再試一次，這次成功就不再跳提示', async () => {
    replies(404, 503, 404, 200)
    const { ensureUserRecord } = useUserSync()

    await ensureUserRecord(clerkUser)
    expect(toastSpy.add).toHaveBeenCalledTimes(1)

    await ensureUserRecord(clerkUser)
    expect(fetchSpy).toHaveBeenCalledTimes(4)
    expect(toastSpy.add).toHaveBeenCalledTimes(1) // 沒有新增提示
  })
})
