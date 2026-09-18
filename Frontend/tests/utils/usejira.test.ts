// tests/composables/useJira.test.ts
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ref as vueRef } from 'vue'

// mock @clerk/vue
vi.mock('@clerk/vue', () => ({
  useAuth: () => ({
    getToken: { value: vi.fn().mockResolvedValue('jwt-token') },
    isLoaded: { value: true },
  }),
}))

// 全域 stub
vi.stubGlobal('ref', vueRef)

const toastSpy = { add: vi.fn() }
const fetchKeysSpy = vi.fn().mockResolvedValue(undefined)
const linkedKeys = ref([
  { platform: 'jira', domain: 'https://example.atlassian.net' },
])

vi.stubGlobal('useToast',           () => toastSpy)
vi.stubGlobal('useRuntimeConfig',   () => ({ public: { apiBaseUrl: 'http://api' } }))
vi.stubGlobal('useLinkedAccount',   () => ({
  keys: linkedKeys,
  fetchKeys: fetchKeysSpy,
}))

let fetchSpy = vi.fn()
let fetchRawSpy = vi.fn()
vi.stubGlobal(
  '$fetch',
  Object.assign((...args: any[]) => fetchSpy(...args), {
    raw: (...args: any[]) => fetchRawSpy(...args),
  }),
)

// ---------- 被測 Composable ----------
import { useJira } from '~/composables/useJira'

describe('useJira composable', () => {
  beforeEach(() => {
    fetchSpy  = vi.fn()
    fetchRawSpy = vi.fn()
    toastSpy.add.mockClear()
    fetchKeysSpy.mockClear()
  })

  it('成功取得 Jira Issues（後端已回傳最終顯示格式，不用前端再轉換）', async () => {
    // 後端 transform_jira_item 已經把巢狀結構拉平，前端直接使用
    const flat = [
      { id: '1', key: 'ISSUE-1', summary: 'a', status: 'Open', updated: '', assignee: '', avatar: '', type: '', iconUrl: '' },
      { id: '2', key: 'ISSUE-2', summary: 'b', status: 'Done', updated: '', assignee: '', avatar: '', type: '', iconUrl: '' },
    ]
    fetchRawSpy.mockResolvedValueOnce({
      _data: flat,
      headers: new Headers({ 'X-Data-Stale': 'false', 'X-Synced-At': '2026-09-03T00:00:00Z' }),
    })

    const { issues, fetchJiraIssues, domain, isStale, syncedAt } = useJira()
    await fetchJiraIssues()

    // 1) 已先抓 LinkedAccount
    expect(fetchKeysSpy).toHaveBeenCalledTimes(1)

    // 2) 正確呼叫 API + Bearer
    expect(fetchRawSpy).toHaveBeenCalledWith(
      'http://api/jira/issues',
      expect.objectContaining({
        headers: { Authorization: 'Bearer jwt-token' },
      }),
    )

    // 3) 後端回傳的就是最終格式，直接放進 issues，不需要前端再轉換
    expect(issues.value).toEqual(flat)

    // 4) domain 去掉 protocol
    expect(domain.value).toBe('example.atlassian.net')

    // 5) stale 相關資訊也正確傳出
    expect(isStale.value).toBe(false)
    expect(syncedAt.value).toBe('2026-09-03T00:00:00Z')
  })

  it('API 失敗時 toast.add 會被呼叫', async () => {
    fetchRawSpy.mockRejectedValueOnce(new Error('爆炸'))

    const { fetchJiraIssues, issues } = useJira()
    await fetchJiraIssues()

    expect(toastSpy.add).toHaveBeenCalledWith(
      expect.objectContaining({
        title: 'Jira 資料抓取失敗',
        color: 'error',
      }),
    )
    expect(issues.value).toEqual([])
  })

  it('API 回傳 X-Auth-Error 時 authError 會是 true（token 失效但仍有快取）', async () => {
    fetchRawSpy.mockResolvedValueOnce({
      _data: [],
      headers: new Headers({ 'X-Data-Stale': 'true', 'X-Auth-Error': 'true', 'X-Synced-At': '2026-09-02T00:00:00Z' }),
    })

    const { fetchJiraIssues, authError } = useJira()
    await fetchJiraIssues()

    expect(authError.value).toBe(true)
  })

  it('token 失效且完全沒有快取（401）時，顯示授權失效的訊息', async () => {
    fetchRawSpy.mockRejectedValueOnce({ response: { status: 401 } })

    const { fetchJiraIssues, authError } = useJira()
    await fetchJiraIssues()

    expect(authError.value).toBe(true)
    expect(toastSpy.add).toHaveBeenCalledWith(
      expect.objectContaining({
        title: 'Jira 授權已失效，請重新連結帳號',
        color: 'error',
      }),
    )
  })

  it('尚未連結帳號（400）時，設定 notLinked 但不跳任何 toast', async () => {
    fetchRawSpy.mockRejectedValueOnce({ response: { status: 400 } })

    const { fetchJiraIssues, notLinked } = useJira()
    await fetchJiraIssues()

    expect(notLinked.value).toBe(true)
    expect(toastSpy.add).not.toHaveBeenCalled()
  })
})
