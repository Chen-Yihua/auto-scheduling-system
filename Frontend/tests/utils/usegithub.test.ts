// tests/utils/usegithub.test.ts
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ref as vueRef } from 'vue'

vi.mock('@clerk/vue', () => ({
  useAuth: () => ({
    getToken: { value: vi.fn().mockResolvedValue('jwt-token') },
  }),
}))

vi.stubGlobal('ref', vueRef)

const toastSpy = { add: vi.fn() }
vi.stubGlobal('useToast', () => toastSpy)
vi.stubGlobal('useRuntimeConfig', () => ({ public: { apiBaseUrl: 'http://api' } }))

let fetchSpy = vi.fn()
let fetchRawSpy = vi.fn()
vi.stubGlobal(
  '$fetch',
  Object.assign((...args: any[]) => fetchSpy(...args), {
    raw: (...args: any[]) => fetchRawSpy(...args),
  }),
)

import { useGithub } from '~/composables/useGithub'

describe('useGithub composable', () => {
  beforeEach(() => {
    fetchSpy = vi.fn()
    fetchRawSpy = vi.fn()
    toastSpy.add.mockClear()
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
        title: 'GitHub 資料抓取失敗',
        color: 'error',
      }),
    )
    expect(issues.value).toEqual([])
  })
})
