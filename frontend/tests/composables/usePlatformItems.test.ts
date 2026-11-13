import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ref as vueRef, computed as vueComputed, nextTick, type Ref } from 'vue'

import { usePlatformItems, type PlatformName } from '~/composables/usePlatformItems'

// userId 要能切換，測登出／換使用者
const clerk = vi.hoisted(() => ({ userId: null as unknown as Ref<string | null> }))
vi.mock('@clerk/vue', async () => {
  const { ref } = await import('vue')
  clerk.userId = ref<string | null>('user_a')
  return {
    useAuth: () => ({
      getToken: { value: vi.fn().mockResolvedValue('jwt-token') },
      userId: clerk.userId,
    }),
  }
})

vi.stubGlobal('ref', vueRef)
vi.stubGlobal('computed', vueComputed)

const toastSpy = { add: vi.fn() }
const fetchKeysSpy = vi.fn().mockResolvedValue(undefined)
// value 是遮罩過的金鑰／密碼——有值代表「已連結」，這是要不要打 API 的依據
const linkedKeys = vueRef<{ platform: string; domain?: string; value?: string; needsReauth?: boolean }[]>([])

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

  it('憑證失效且沒有舊資料（REAUTH_REQUIRED）→ 顯示這個平台的「請重新連結」訊息', async () => {
    fetchRawSpy.mockRejectedValueOnce({ response: { status: 401 }, data: { error_code: 'REAUTH_REQUIRED' } })

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

  it('AC20(3)：連結帳號檢查本身失敗而且沒有已知的結果 → 暫時無法載入，不顯示尚未綁定，不跳 toast', async () => {
    fetchKeysSpy.mockRejectedValueOnce(new Error('網路爆炸'))

    const { fetchItems, notLinked, unavailable, loading } = usePlatformItems(platform as PlatformName)
    await fetchItems()

    expect(notLinked.value).toBe(false)
    expect(unavailable.value).toBe(true)
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

describe('usePlatformItems：依 error_code 判斷與最近一次已知的結果', () => {
  beforeEach(() => {
    fetchRawSpy = vi.fn()
    toastSpy.add.mockClear()
    fetchKeysSpy.mockReset()
    fetchKeysSpy.mockResolvedValue(undefined)
    clerk.userId.value = 'user_a'
    linkedKeys.value = [{ platform: 'github', value: 'KEY****' }]
  })

  it.each([
    ['UPSTREAM_RATE_LIMITED', 401, '請求太頻繁，請稍後再試'],
    ['UPSTREAM_ERROR', 401, 'GitHub 資料暫時無法取得'],
    ['UPSTREAM_TIMEOUT', 502, 'GitHub 資料暫時無法取得'],
    ['INTERNAL_ERROR', 401, 'GitHub 資料暫時無法取得'],
  ])('AC5、AC7：收到 %s（即使狀態碼是 %i）→ 不要求重新連結', async (code, status, title) => {
    fetchRawSpy.mockRejectedValueOnce({ response: { status }, data: { error_code: code, detail: '說明' } })

    const { fetchItems, authError, notLinked } = usePlatformItems('github')
    await fetchItems()

    expect(authError.value).toBe(false)
    expect(notLinked.value).toBe(false)
    const toast = toastSpy.add.mock.calls[0]![0]
    expect(toast.title).toBe(title)
    expect(toast.title).not.toContain('授權已失效')
  })

  it('AC12：收到 NOT_LINKED → 設成尚未綁定，不跳 toast', async () => {
    fetchRawSpy.mockRejectedValueOnce({ response: { status: 400 }, data: { error_code: 'NOT_LINKED' } })

    const { fetchItems, notLinked } = usePlatformItems('github')
    await fetchItems()

    expect(notLinked.value).toBe(true)
    expect(toastSpy.add).not.toHaveBeenCalled()
  })

  it('AC12：其他 error_code → 原本的說明後面附加後端的 detail', async () => {
    fetchRawSpy.mockRejectedValueOnce({ response: { status: 500 }, data: { error_code: 'INTERNAL_ERROR', detail: '後端說明' } })

    const { fetchItems } = usePlatformItems('github')
    await fetchItems()

    const description = toastSpy.add.mock.calls[0]![0].description as string
    expect(description).toContain('稍後再試')
    expect(description.endsWith('後端說明')).toBe(true)
  })

  it('AC9：帳號的憑證無法讀取（needs_reauth）→ 當成已連結、要重新連結，不顯示尚未綁定，也不打 API', async () => {
    linkedKeys.value = [{ platform: 'github', value: '', needsReauth: true }]

    const { fetchItems, notLinked, needsReauth } = usePlatformItems('github')
    await fetchItems()

    expect(notLinked.value).toBe(false)
    expect(needsReauth.value).toBe(true)
    expect(fetchRawSpy).not.toHaveBeenCalled()
  })

  it('AC20(1)：先載入成功，之後帳號檢查失敗 → 保留清單照常顯示', async () => {
    fetchRawSpy.mockResolvedValueOnce(ok([{ id: '1' }]))
    const { fetchItems, items, unavailable, notLinked } = usePlatformItems('github')
    await fetchItems()

    fetchKeysSpy.mockRejectedValueOnce(new Error('網路爆炸'))
    await fetchItems()

    expect(items.value).toEqual([{ id: '1' }])
    expect(unavailable.value).toBe(false)
    expect(notLinked.value).toBe(false)
  })

  it('AC20(2)：最近一次是尚未綁定，之後帳號檢查失敗 → 維持尚未綁定', async () => {
    linkedKeys.value = [{ platform: 'github', value: '' }]
    const { fetchItems, notLinked, unavailable } = usePlatformItems('github')
    await fetchItems()

    fetchKeysSpy.mockRejectedValueOnce(new Error('網路爆炸'))
    await fetchItems()

    expect(notLinked.value).toBe(true)
    expect(unavailable.value).toBe(false)
  })

  it('AC20(2)：最近一次是憑證無法讀取，之後帳號檢查失敗 → 維持要重新連結', async () => {
    linkedKeys.value = [{ platform: 'github', value: '', needsReauth: true }]
    const { fetchItems, needsReauth, unavailable } = usePlatformItems('github')
    await fetchItems()

    fetchKeysSpy.mockRejectedValueOnce(new Error('網路爆炸'))
    await fetchItems()

    expect(needsReauth.value).toBe(true)
    expect(unavailable.value).toBe(false)
  })

  it('AC20：登出再以另一個使用者登入後帳號檢查失敗 → 不顯示前一個使用者的清單', async () => {
    fetchRawSpy.mockResolvedValueOnce(ok([{ id: '1' }]))
    const { fetchItems, items, unavailable } = usePlatformItems('github')
    await fetchItems()

    clerk.userId.value = null
    await nextTick()
    expect(items.value).toEqual([])
    clerk.userId.value = 'user_b'
    fetchKeysSpy.mockRejectedValueOnce(new Error('網路爆炸'))
    await fetchItems()

    expect(items.value).toEqual([])
    expect(unavailable.value).toBe(true)
  })
})

describe.each([
  { platform: 'github', getPath: '/github/issues', syncPath: '/github/sync', label: 'GitHub' },
  { platform: 'jira', getPath: '/jira/issues', syncPath: '/jira/sync', label: 'Jira' },
  { platform: 'moodle', getPath: '/moodle/assignments', syncPath: '/moodle/sync', label: 'Moodle' },
] as const)('usePlatformItems($platform)：定時同步與立即同步（issue #13）', ({ platform, getPath, syncPath, label }) => {
  beforeEach(() => {
    fetchRawSpy = vi.fn()
    toastSpy.add.mockClear()
    fetchKeysSpy.mockReset()
    fetchKeysSpy.mockResolvedValue(undefined)
    clerk.userId.value = 'user_a'
    linkedKeys.value = [{ platform, value: 'KEY****', domain: 'team.atlassian.net' }]
  })

  it('AC30：打開頁面（fetchItems）只呼叫 GET，不呼叫立即同步的 POST', async () => {
    fetchRawSpy.mockResolvedValueOnce(ok([]))

    const { fetchItems } = usePlatformItems(platform as PlatformName)
    await fetchItems()

    expect(fetchRawSpy).toHaveBeenCalledTimes(1)
    const [url, options] = fetchRawSpy.mock.calls[0]!
    expect(url).toBe(`http://api${getPath}`)
    expect(options.method ?? 'GET').toBe('GET')
  })

  it('AC31：立即同步只呼叫這個平台的 POST，完成後更新清單與上次同步時間', async () => {
    fetchRawSpy.mockResolvedValueOnce(ok([{ id: 'old' }], { 'X-Synced-At': '2026-11-01T04:00:00Z' }))
    const { fetchItems, syncNow, items, syncedAt, isStale, syncing } = usePlatformItems(platform as PlatformName)
    await fetchItems()

    fetchRawSpy.mockResolvedValueOnce(ok([{ id: 'new' }], { 'X-Data-Stale': 'false', 'X-Synced-At': '2026-11-14T05:00:00Z' }))
    const pending = syncNow()
    expect(syncing.value).toBe(true)
    await pending

    expect(fetchRawSpy).toHaveBeenLastCalledWith(`http://api${syncPath}`, {
      method: 'POST',
      headers: { Authorization: 'Bearer jwt-token' },
    })
    expect(items.value).toEqual([{ id: 'new' }])
    expect(syncedAt.value).toBe('2026-11-14T05:00:00Z')
    expect(isStale.value).toBe(false)
    expect(syncing.value).toBe(false)
    expect(toastSpy.add).not.toHaveBeenCalled()
  })

  it.each([
    ['尚未綁定', { value: '' }, 'notLinked'],
    ['憑證無法讀取', { value: '', needsReauth: true }, 'needsReauth'],
  ] as const)('AC31：打開頁面時是%s，在頁面上連結後按立即同步成功 → 不再顯示這個狀態，清單已更新', async (_label, account, flag) => {
    linkedKeys.value = [{ platform, domain: 'team.atlassian.net', ...account }]
    const state = usePlatformItems(platform as PlatformName)
    await state.fetchItems()
    expect(state[flag].value).toBe(true)

    fetchRawSpy.mockResolvedValueOnce(ok([{ id: 'new' }], { 'X-Synced-At': '2026-11-14T05:00:00Z' }))
    await state.syncNow()

    expect(state.notLinked.value).toBe(false)
    expect(state.needsReauth.value).toBe(false)
    expect(state.unavailable.value).toBe(false)
    expect(state.items.value).toEqual([{ id: 'new' }])
  })

  it('AC31：打開頁面時暫時無法載入，之後按立即同步成功 → 不再顯示暫時無法載入，清單已更新', async () => {
    fetchKeysSpy.mockRejectedValueOnce(new Error('網路爆炸'))
    const { fetchItems, syncNow, items, unavailable, notLinked, needsReauth } = usePlatformItems(platform as PlatformName)
    await fetchItems()
    expect(unavailable.value).toBe(true)

    fetchRawSpy.mockResolvedValueOnce(ok([{ id: 'new' }], { 'X-Synced-At': '2026-11-14T05:00:00Z' }))
    await syncNow()

    expect(unavailable.value).toBe(false)
    expect(notLinked.value).toBe(false)
    expect(needsReauth.value).toBe(false)
    expect(items.value).toEqual([{ id: 'new' }])
  })

  it('AC31：尚未綁定時按立即同步，後端退回舊資料 → 不再顯示尚未綁定，顯示舊資料', async () => {
    linkedKeys.value = [{ platform, value: '' }]
    const { fetchItems, syncNow, items, isStale, notLinked } = usePlatformItems(platform as PlatformName)
    await fetchItems()

    fetchRawSpy.mockResolvedValueOnce(ok([{ id: 'old' }], { 'X-Data-Stale': 'true' }))
    await syncNow()

    expect(notLinked.value).toBe(false)
    expect(isStale.value).toBe(true)
    expect(items.value).toEqual([{ id: 'old' }])
  })

  it('需求 24：立即同步失敗但後端退回舊資料 → 顯示舊資料與提示（isStale），不跳 toast', async () => {
    fetchRawSpy.mockResolvedValueOnce(ok([{ id: 'old' }], { 'X-Data-Stale': 'true', 'X-Synced-At': '2026-11-01T04:00:00Z' }))

    const { syncNow, items, isStale } = usePlatformItems(platform as PlatformName)
    await syncNow()

    expect(items.value).toEqual([{ id: 'old' }])
    expect(isStale.value).toBe(true)
    expect(toastSpy.add).not.toHaveBeenCalled()
  })

  it('需求 24：立即同步失敗而且沒有舊資料 → 跳錯誤訊息，清單維持原樣', async () => {
    fetchRawSpy.mockResolvedValueOnce(ok([{ id: 'kept' }]))
    const { fetchItems, syncNow, items, syncing } = usePlatformItems(platform as PlatformName)
    await fetchItems()

    fetchRawSpy.mockRejectedValueOnce({ response: { status: 502 }, data: { error_code: 'UPSTREAM_ERROR', detail: '說明' } })
    await syncNow()

    expect(items.value).toEqual([{ id: 'kept' }])
    expect(syncing.value).toBe(false)
    expect(toastSpy.add).toHaveBeenCalledTimes(1)
    expect(toastSpy.add).toHaveBeenCalledWith(expect.objectContaining({ title: `${label} 資料暫時無法取得`, color: 'error' }))
  })

  it('AC39：GET 帶 X-Auth-Error（沒有 X-Data-Stale）→ authError 為 true', async () => {
    fetchRawSpy.mockResolvedValueOnce(ok([{ id: '1' }], { 'X-Auth-Error': 'true', 'X-Synced-At': '2026-11-01T04:00:00Z' }))

    const { fetchItems, authError, isStale } = usePlatformItems(platform as PlatformName)
    await fetchItems()

    expect(authError.value).toBe(true)
    expect(isStale.value).toBe(false)
  })

  it('AC33：GET 沒帶 X-Synced-At（尚未同步）→ syncedAt 為 null', async () => {
    fetchRawSpy.mockResolvedValueOnce(ok([]))

    const { fetchItems, syncedAt } = usePlatformItems(platform as PlatformName)
    await fetchItems()

    expect(syncedAt.value).toBeNull()
  })
})
