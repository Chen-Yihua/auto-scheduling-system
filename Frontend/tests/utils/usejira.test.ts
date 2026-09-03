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

// 1. Mock '@/utils/jira'
vi.mock('@/utils/jira', () => {
  const spy = vi.fn((x) => ({ ...x, done: true }))
  return { transformJiraItem: spy }
})

// 2. 全域 stub
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

// ---------- 3. 被測 Composable ----------
import { transformJiraItem } from '@/utils/jira'
import { useJira } from '~/composables/useJira'

describe('useJira composable', () => {
  beforeEach(() => {
    fetchSpy  = vi.fn()
    fetchRawSpy = vi.fn()
    ;(transformJiraItem as any).mockClear()
    toastSpy.add.mockClear()
    fetchKeysSpy.mockClear()
  })

  it('成功取得 Jira Issues 並轉換', async () => {
    // 假資料
    const raw = [{ id: 'ISSUE-1' }, { id: 'ISSUE-2' }]
    fetchRawSpy.mockResolvedValueOnce({
      _data: raw,
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

    // 3) transformJiraItem 針對每筆 raw 被呼叫
    expect(transformJiraItem).toHaveBeenCalledTimes(raw.length)

    // 4) issues ref 已轉成 done:true
    expect((issues.value as any[]).every((i) => i.done)).toBe(true)

    // 5) domain 去掉 protocol
    expect(domain.value).toBe('example.atlassian.net')

    // 6) stale 相關資訊也正確傳出
    expect(isStale.value).toBe(false)
    expect(syncedAt.value).toBe('2026-09-03T00:00:00Z')
  })

  it('API 失敗時 toast.add 會被呼叫', async () => {
    fetchRawSpy.mockRejectedValueOnce(new Error('爆炸'))

    const { fetchJiraIssues } = useJira()
    await fetchJiraIssues()

    expect(toastSpy.add).toHaveBeenCalledWith(
      expect.objectContaining({
        title: 'Jira 資料抓取失敗',
        color: 'error',
      }),
    )
    // transform 不應被呼叫
    expect(transformJiraItem).not.toHaveBeenCalled()
  })
})
