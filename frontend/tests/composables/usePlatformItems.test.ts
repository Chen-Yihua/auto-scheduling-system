import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ref as vueRef, computed as vueComputed } from 'vue'

import { usePlatformItems, type PlatformName } from '~/composables/usePlatformItems'

vi.mock('@clerk/vue', () => ({
  useAuth: () => ({
    getToken: { value: vi.fn().mockResolvedValue('jwt-token') },
  }),
}))

vi.stubGlobal('ref', vueRef)
vi.stubGlobal('computed', vueComputed)

const toastSpy = { add: vi.fn() }
const fetchKeysSpy = vi.fn().mockResolvedValue(undefined)
// value 是遮罩過的金鑰／密碼——有值代表「已連結」，這是要不要打 API 的依據
const linkedKeys = vueRef<{ platform: string; domain?: string; value?: string }[]>([])

vi.stubGlobal('useToast', () => toastSpy)
vi.stubGlobal('useRuntimeConfig', () => ({ public: { apiBaseUrl: 'http://api' } }))
vi.stubGlobal('useLinkedAccount', () => ({ keys: linkedKeys, fetchKeys: fetchKeysSpy }))

let fetchRawSpy = vi.fn()
vi.stubGlobal('$fetch', Object.assign(vi.fn(), { raw: (...args: unknown[]) => fetchRawSpy(...args) }))

const ok = (data: unknown[], headers: Record<string, string> = {}) => ({ _data: data, headers: new Headers(headers) })

// 每個平台跑同一套流程，確認 API 路徑跟錯誤訊息都是各自的
describe.each([
  { platform: 'github', path: '/github/issues', label: 'GitHub', authFailedTitle: 'GitHub 授權已失效' },
  { platform: 'jira', path: '/jira/issues', label: 'Jira', authFailedTitle: 'Jira 授權已失效' },
  { platform: 'moodle', path: '/moodle/assignments', label: 'Moodle', authFailedTitle: 'Moodle 帳號或密碼已失效' },
] as const)('usePlatformItems($platform)', ({ platform, path, label, authFailedTitle }) => {
  beforeEach(() => {
    fetchRawSpy = vi.fn()
    toastSpy.add.mockClear()
    fetchKeysSpy.mockClear()
    linkedKeys.value = [{ platform, value: 'KEY****', domain: 'team.atlassian.net' }]
  })

  it('已連結帳號：帶 Bearer token 打後端 API，回傳的就是最終顯示格式，並讀出資料狀態 header', async () => {
    const data = [{ id: '1' }, { id: '2' }]
    fetchRawSpy.mockResolvedValueOnce(ok(data, { 'X-Data-Stale': 'true', 'X-Synced-At': '2026-09-03T00:00:00Z' }))

    const { items, fetchItems, isStale, syncedAt, authError, notLinked, loading } = usePlatformItems(platform as PlatformName)
    await fetchItems()

    expect(fetchKeysSpy).toHaveBeenCalledTimes(1)
    expect(fetchRawSpy).toHaveBeenCalledWith(`http://api${path}`, { headers: { Authorization: 'Bearer jwt-token' } })
    expect(items.value).toEqual(data)
    expect(isStale.value).toBe(true)
    expect(syncedAt.value).toBe('2026-09-03T00:00:00Z')
    expect(authError.value).toBe(false)
    expect(notLinked.value).toBe(false)
    expect(loading.value).toBe(false)
  })

  it('回傳 X-Auth-Error（憑證失效但還有舊資料）→ authError 為 true，不跳 toast', async () => {
    fetchRawSpy.mockResolvedValueOnce(ok([], { 'X-Data-Stale': 'true', 'X-Auth-Error': 'true' }))

    const { fetchItems, authError } = usePlatformItems(platform as PlatformName)
    await fetchItems()

    expect(authError.value).toBe(true)
    expect(toastSpy.add).not.toHaveBeenCalled()
  })

  it('憑證失效且沒有舊資料（401）→ 顯示這個平台的「請重新連結」訊息', async () => {
    fetchRawSpy.mockRejectedValueOnce({ response: { status: 401 } })

    const { fetchItems, authError } = usePlatformItems(platform as PlatformName)
    await fetchItems()

    expect(authError.value).toBe(true)
    expect(toastSpy.add).toHaveBeenCalledWith(expect.objectContaining({ title: authFailedTitle, color: 'error' }))
  })

  it('暫時性錯誤（例如 500）→ 顯示「稍後再試」，不是叫使用者重新連結', async () => {
    fetchRawSpy.mockRejectedValueOnce({ response: { status: 500 } })

    const { fetchItems, authError, items, loading } = usePlatformItems(platform as PlatformName)
    await fetchItems()

    expect(authError.value).toBe(false)
    expect(items.value).toEqual([])
    expect(loading.value).toBe(false)
    expect(toastSpy.add).toHaveBeenCalledWith(expect.objectContaining({
      title: `${label} 資料暫時無法取得`,
      description: expect.stringContaining('稍後再試'),
    }))
  })

  it('尚未連結帳號 → 根本不打 API（Moodle 還要開瀏覽器爬），也不跳 toast', async () => {
    linkedKeys.value = [{ platform, value: '' }]

    const { fetchItems, notLinked, loading } = usePlatformItems(platform as PlatformName)
    await fetchItems()

    expect(notLinked.value).toBe(true)
    expect(fetchRawSpy).not.toHaveBeenCalled()
    expect(toastSpy.add).not.toHaveBeenCalled()
    // 一定要收回 loading，不然畫面會永遠卡在載入中
    expect(loading.value).toBe(false)
  })

  it('連結帳號檢查本身失敗（例如網路問題）→ 安靜降級成尚未綁定，不跳 toast', async () => {
    fetchKeysSpy.mockRejectedValueOnce(new Error('網路爆炸'))

    const { fetchItems, notLinked, loading } = usePlatformItems(platform as PlatformName)
    await fetchItems()

    expect(notLinked.value).toBe(true)
    expect(fetchRawSpy).not.toHaveBeenCalled()
    expect(toastSpy.add).not.toHaveBeenCalled()
    expect(loading.value).toBe(false)
  })
})

describe('usePlatformItems 其他', () => {
  beforeEach(() => {
    fetchRawSpy = vi.fn()
    toastSpy.add.mockClear()
    linkedKeys.value = [{ platform: 'jira', value: 'KEY****', domain: 'team.atlassian.net' }]
  })

  it('account 是這個平台的連結帳號（Jira 用它的 domain 組 issue 連結）', () => {
    const { account } = usePlatformItems('jira')
    expect(account.value?.domain).toBe('team.atlassian.net')
  })

  it('被限流（429）→ toast 顯示「請求太頻繁」，不是一般的抓取失敗訊息', async () => {
    fetchRawSpy.mockRejectedValueOnce({
      data: { error_code: 'RATE_LIMITED', detail: '請求太頻繁，請稍後再試' },
      response: { status: 429 },
    })

    const { fetchItems } = usePlatformItems('jira')
    await fetchItems()

    expect(toastSpy.add).toHaveBeenCalledWith(expect.objectContaining({ title: '請求太頻繁，請稍後再試', color: 'error' }))
  })
})
