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
// value 是遮罩過的 apiKey——有值代表「已連結」，這是 fetchJiraIssues 用來判斷
// 要不要打 API 的依據，預設模擬「已連結」，個別測試要測「未連結」再覆寫
const linkedKeys = ref([
  { platform: 'jira', domain: 'https://example.atlassian.net', value: 'JKEY****' },
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
    linkedKeys.value = [
      { platform: 'jira', domain: 'https://example.atlassian.net', value: 'JKEY****' },
    ]
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
        title: 'Jira 資料暫時無法取得',
        description: expect.stringContaining('稍後再試'),
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
        title: 'Jira 授權已失效',
        description: expect.stringContaining('重新連結'),
        color: 'error',
      }),
    )
  })

  it('尚未連結帳號時，根本不打 API，也不跳任何 toast', async () => {
    // 模擬 keys 裡沒有遮罩過的 apiKey，代表這個平台還沒連結
    linkedKeys.value = [{ platform: 'jira', domain: '' }]

    const { fetchJiraIssues, notLinked, loading } = useJira()
    await fetchJiraIssues()

    expect(notLinked.value).toBe(true)
    expect(fetchRawSpy).not.toHaveBeenCalled()
    expect(toastSpy.add).not.toHaveBeenCalled()
    // 抓取結束一定要把 loading 收回 false，不然畫面會永遠卡在 Skeleton
    expect(loading.value).toBe(false)
  })

  it('連結帳號檢查本身失敗（例如網路問題）時，不會誤判成尚未連結，且不會卡住 loading', async () => {
    fetchKeysSpy.mockRejectedValueOnce(new Error('網路爆炸'))

    const { fetchJiraIssues, notLinked, loading } = useJira()
    await fetchJiraIssues()

    expect(notLinked.value).toBe(false)
    expect(fetchRawSpy).not.toHaveBeenCalled()
    expect(toastSpy.add).toHaveBeenCalledWith(
      expect.objectContaining({
        title: 'Jira 資料暫時無法取得',
        description: expect.stringContaining('稍後再試'),
        color: 'error',
      }),
    )
    expect(loading.value).toBe(false)
  })
})
