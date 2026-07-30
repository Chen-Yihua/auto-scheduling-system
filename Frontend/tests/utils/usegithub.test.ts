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
vi.stubGlobal('$fetch', (...args: any[]) => fetchSpy(...args))

import { useGithub } from '~/composables/useGithub'

describe('useGithub composable', () => {
  beforeEach(() => {
    fetchSpy = vi.fn()
    toastSpy.add.mockClear()
  })

  it('只呼叫後端 /github/issues，不直接打 GitHub API', async () => {
    const backendIssues = [
      { id: 1, title: 'Fix bug', state: 'open', created_at: '2024-01-01T00:00:00Z', url: 'https://github.com/x/y/issues/1', isPR: false },
    ]
    fetchSpy.mockResolvedValueOnce(backendIssues)

    const { issues, fetchGithubIssues } = useGithub()
    await fetchGithubIssues()

    // 只打過一次 fetch，而且是後端網址
    expect(fetchSpy).toHaveBeenCalledTimes(1)
    expect(fetchSpy).toHaveBeenCalledWith(
      'http://api/github/issues',
      expect.objectContaining({
        headers: { Authorization: 'Bearer jwt-token' },
      }),
    )

    // 沒有任何一次呼叫是打去 api.github.com
    const calledUrls = fetchSpy.mock.calls.map((call) => call[0])
    expect(calledUrls.some((url) => String(url).includes('api.github.com'))).toBe(false)

    // 後端回傳的格式已經是最終格式，直接放進 issues，不需要前端再轉換
    expect(issues.value).toEqual(backendIssues)
  })

  it('API 失敗時 toast.add 會被呼叫', async () => {
    fetchSpy.mockRejectedValueOnce(new Error('爆炸'))

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
