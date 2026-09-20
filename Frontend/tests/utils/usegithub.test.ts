// tests/utils/usegithub.test.ts
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ref as vueRef } from 'vue'

import { useGithub } from '~/composables/useGithub'

vi.mock('@clerk/vue', () => ({
  useAuth: () => ({
    getToken: { value: vi.fn().mockResolvedValue('jwt-token') },
  }),
}))

vi.stubGlobal('ref', vueRef)

const toastSpy = { add: vi.fn() }
const fetchKeysSpy = vi.fn().mockResolvedValue(undefined)
// value 是遮罩過的 apiKey——有值代表「已連結」，這是 fetchGithubIssues 用來判斷
// 要不要打 API 的依據，預設模擬「已連結」，個別測試要測「未連結」再覆寫
const linkedKeys = vueRef([{ platform: 'github', value: 'GKEY****' }])

vi.stubGlobal('useToast', () => toastSpy)
vi.stubGlobal('useRuntimeConfig', () => ({ public: { apiBaseUrl: 'http://api' } }))
vi.stubGlobal('useLinkedAccount', () => ({
  keys: linkedKeys,
  fetchKeys: fetchKeysSpy,
}))

let fetchSpy = vi.fn()
let fetchRawSpy = vi.fn()
vi.stubGlobal(
  '$fetch',
  Object.assign((...args: unknown[]) => fetchSpy(...args), {
    raw: (...args: unknown[]) => fetchRawSpy(...args),
  }),
)

describe('useGithub composable', () => {
  beforeEach(() => {
    fetchSpy = vi.fn()
    fetchRawSpy = vi.fn()
    toastSpy.add.mockClear()
    fetchKeysSpy.mockClear()
    linkedKeys.value = [{ platform: 'github', value: 'GKEY****' }]
  })

  it('只呼叫後端 /github/issues，不直接打 GitHub API', async () => {
    const backendIssues = [
      { id: 1, title: 'Fix bug', state: 'open', created_at: '2024-01-01T00:00:00Z', url: 'https://github.com/x/y/issues/1', isPR: false },
    ]
    fetchRawSpy.mockResolvedValueOnce({
      _data: backendIssues,
      headers: new Headers({ 'X-Data-Stale': 'false', 'X-Synced-At': '2026-09-03T00:00:00Z' }),
    })

    const { issues, fetchGithubIssues, isStale, syncedAt } = useGithub()
    await fetchGithubIssues()

    // 只打過一次 fetch，而且是後端網址
    expect(fetchRawSpy).toHaveBeenCalledTimes(1)
    expect(fetchRawSpy).toHaveBeenCalledWith(
      'http://api/github/issues',
      expect.objectContaining({
        headers: { Authorization: 'Bearer jwt-token' },
      }),
    )

    // 沒有任何一次呼叫是打去 api.github.com
    const calledUrls = fetchRawSpy.mock.calls.map((call) => call[0])
    expect(calledUrls.some((url) => String(url).includes('api.github.com'))).toBe(false)

    // 後端回傳的格式已經是最終格式，直接放進 issues，不需要前端再轉換
    expect(issues.value).toEqual(backendIssues)
    expect(isStale.value).toBe(false)
    expect(syncedAt.value).toBe('2026-09-03T00:00:00Z')
  })

  it('API 回傳 stale 資料時 isStale 會是 true', async () => {
    const cachedIssues = [{ id: 1, title: 'Cached issue', state: 'open', created_at: '2024-01-01T00:00:00Z', url: 'https://github.com/x/y/issues/1', isPR: false }]
    fetchRawSpy.mockResolvedValueOnce({
      _data: cachedIssues,
      headers: new Headers({ 'X-Data-Stale': 'true', 'X-Synced-At': '2026-09-02T00:00:00Z' }),
    })

    const { issues, fetchGithubIssues, isStale, syncedAt } = useGithub()
    await fetchGithubIssues()

    expect(issues.value).toEqual(cachedIssues)
    expect(isStale.value).toBe(true)
    expect(syncedAt.value).toBe('2026-09-02T00:00:00Z')
  })

  it('API 失敗時 toast.add 會被呼叫', async () => {
    fetchRawSpy.mockRejectedValueOnce(new Error('爆炸'))

    const { issues, fetchGithubIssues } = useGithub()
    await fetchGithubIssues()

    expect(toastSpy.add).toHaveBeenCalledWith(
      expect.objectContaining({
        title: 'GitHub 資料暫時無法取得',
        description: expect.stringContaining('稍後再試'),
        color: 'error',
      }),
    )
    expect(issues.value).toEqual([])
  })

  it('API 回傳 X-Auth-Error 時 authError 會是 true（token 失效但仍有快取）', async () => {
    const cachedIssues = [{ id: 1, title: 'Cached issue', state: 'open', created_at: '2024-01-01T00:00:00Z', url: 'https://github.com/x/y/issues/1', isPR: false }]
    fetchRawSpy.mockResolvedValueOnce({
      _data: cachedIssues,
      headers: new Headers({ 'X-Data-Stale': 'true', 'X-Auth-Error': 'true', 'X-Synced-At': '2026-09-02T00:00:00Z' }),
    })

    const { fetchGithubIssues, authError } = useGithub()
    await fetchGithubIssues()

    expect(authError.value).toBe(true)
  })

  it('token 失效且完全沒有快取（401）時，顯示授權失效的訊息', async () => {
    fetchRawSpy.mockRejectedValueOnce({
      response: { status: 401 },
    })

    const { fetchGithubIssues, authError } = useGithub()
    await fetchGithubIssues()

    expect(authError.value).toBe(true)
    expect(toastSpy.add).toHaveBeenCalledWith(
      expect.objectContaining({
        title: 'GitHub 授權已失效',
        description: expect.stringContaining('重新連結'),
        color: 'error',
      }),
    )
  })

  it('被限流（429）時，toast 顯示「請求太頻繁」而不是一般的抓取失敗訊息', async () => {
    fetchRawSpy.mockRejectedValueOnce({
      data: { error_code: 'RATE_LIMITED', detail: '請求太頻繁，請稍後再試' },
      response: { status: 429 },
    })

    const { fetchGithubIssues } = useGithub()
    await fetchGithubIssues()

    expect(toastSpy.add).toHaveBeenCalledWith(
      expect.objectContaining({
        title: '請求太頻繁，請稍後再試',
        color: 'error',
      }),
    )
  })

  it('尚未連結帳號時，根本不打 API，也不跳任何 toast', async () => {
    // 模擬 keys 裡沒有遮罩過的 apiKey，代表這個平台還沒連結
    linkedKeys.value = [{ platform: 'github', value: '' }]

    const { fetchGithubIssues, notLinked, loading } = useGithub()
    await fetchGithubIssues()

    expect(notLinked.value).toBe(true)
    expect(fetchRawSpy).not.toHaveBeenCalled()
    expect(toastSpy.add).not.toHaveBeenCalled()
    // 抓取結束一定要把 loading 收回 false，不然畫面會永遠卡在 Skeleton
    expect(loading.value).toBe(false)
  })

  it('連結帳號檢查本身失敗（例如網路問題）時，安靜降級成尚未綁定，不跳 toast，也不會卡住 loading', async () => {
    fetchKeysSpy.mockRejectedValueOnce(new Error('網路爆炸'))

    const { fetchGithubIssues, notLinked, loading } = useGithub()
    await fetchGithubIssues()

    expect(notLinked.value).toBe(true)
    expect(fetchRawSpy).not.toHaveBeenCalled()
    expect(toastSpy.add).not.toHaveBeenCalled()
    expect(loading.value).toBe(false)
  })
})
