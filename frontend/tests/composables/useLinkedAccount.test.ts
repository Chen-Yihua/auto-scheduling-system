import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ref as vueRef, computed as vueComputed } from 'vue'

vi.mock('@vueuse/core', () => ({
  until: () => ({
    toBe: async () => {},   // 直接返回 resolved promise
  }),
}))

/* ---------- Clerk & Nuxt helpers mock ---------- */
vi.mock('@clerk/vue', () => ({
  useAuth: () => ({
    isLoaded: vueRef(true),
    getToken: { value: vi.fn().mockResolvedValue('jwt') },
  }),
  useUser: () => ({
    user: vueRef({ username: 'tester' }),
  }),
}))

/* ---------- 全域 auto-import helpers ---------- */
vi.stubGlobal('ref', vueRef)
vi.stubGlobal('computed', vueComputed)

/* ---------- $fetch / toast ---------- */
let fetchSpy = vi.fn()
vi.stubGlobal('$fetch', (...a: unknown[]) => fetchSpy(...a))
const toastSpy = { add: vi.fn() }
vi.stubGlobal('useToast', () => toastSpy)

/* ---------- 動態載入 Composable ---------- */
const load = async () =>
  (await import('~/composables/useLinkedAccount')).useLinkedAccount

/* ---------- 假資料 ---------- */
const list = [
  { platform: 'github', apiKey: 'GKEY*****', avatar_url: 'ava1' },
  { platform: 'jira', apiKey: 'JKEY*****', domain: 'https://j.atl', avatar_url: 'ava2' },
  { platform: 'moodle', password: 'm****', username: 'bob' },
]

describe('useLinkedAccount', () => {
  beforeEach(() => {
    fetchSpy = vi.fn()
    toastSpy.add.mockClear()
  })

  it('fetchKeys 會把伺服器資料寫入對應 key', async () => {
    fetchSpy.mockResolvedValueOnce(list)

    const { keys, fetchKeys } = (await load())()
    await fetchKeys()

    const git = keys.value.find((k) => k.platform === 'github')!
    const jira = keys.value.find((k) => k.platform === 'jira')!
    const moo = keys.value.find((k) => k.platform === 'moodle')!

    expect(git.value).toBe('GKEY*****')
    expect(jira.domain).toBe('https://j.atl')
    expect(moo.value).toBe('m****') // password 被寫到 value
    expect(moo.username).toBe('bob')
  })

  it('fetchKeys 從後端拿回來的一律標記為 isMasked，不可複製', async () => {
    fetchSpy.mockResolvedValueOnce(list)

    const { keys, fetchKeys } = (await load())()
    await fetchKeys()

    expect(keys.value.find((k) => k.platform === 'github')!.isMasked).toBe(true)
    expect(keys.value.find((k) => k.platform === 'jira')!.isMasked).toBe(true)
    expect(keys.value.find((k) => k.platform === 'moodle')!.isMasked).toBe(true)
  })

  it('openEdit / cancelEdit 切換編輯狀態', async () => {
    const { keys, openEdit, cancelEdit } = (await load())()
    const git = keys.value.find((k) => k.platform === 'github')!

    openEdit(git)
    expect(git.editing).toBe(true)

    cancelEdit(git)
    expect(git.editing).toBe(false)
    expect(git.inputValue).toBe('')
  })

  it('saveKey (新建) 會 POST 並顯示成功 toast', async () => {
    const { keys, openEdit, saveKey } = (await load())()
    const git = keys.value.find((k) => k.platform === 'github')!
    openEdit(git)
    git.inputValue = 'NEWKEY'

    // POST 回傳建立的帳號
    fetchSpy.mockResolvedValueOnce({ platform: 'github', username: 'octocat', avatar_url: 'a.png' })

    await saveKey(git)

    expect(fetchSpy).toHaveBeenCalledWith(
      'http://api/users/me/linked-accounts/',
      expect.objectContaining({ method: 'POST' }),
    )
    expect(git.value).toBe('NEWKEY')
    expect(git.editing).toBe(false)
    expect(git.isMasked).toBe(false) // 剛建立，這個 session 內允許複製一次
    expect(git.username).toBe('octocat')
    expect(git.avatar).toBe('a.png')
    expect(toastSpy.add).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'GitHub Key 儲存成功', color: 'success' }),
    )
  })

  it('saveKey (Jira 只改 domain) 不會送出 apiKey，並顯示「Jira Domain 已更新」', async () => {
    const { keys, fetchKeys, openEdit, saveKey } = (await load())()
    fetchSpy.mockResolvedValueOnce(list)
    await fetchKeys()

    const jira = keys.value.find((k) => k.platform === 'jira')!
    openEdit(jira)
    jira.domain = 'new-domain.atlassian.net' // 只改 domain，apiKey 欄位留空

    fetchSpy.mockResolvedValueOnce(undefined) // PATCH 不用回傳

    await saveKey(jira)

    const patchCall = fetchSpy.mock.calls.find(([url]) => url === 'http://api/users/me/linked-accounts/jira')
    expect(patchCall).toBeTruthy()
    expect(patchCall![1].method).toBe('PATCH')
    const sentPayload = patchCall![1].body
    expect(sentPayload.domain).toBe('new-domain.atlassian.net')
    expect(sentPayload).not.toHaveProperty('apiKey') // 沒改 apiKey 就不該送出這個 key

    expect(toastSpy.add).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Jira Domain 已更新', color: 'success' }),
    )
  })

  it('deleteKey 會 DELETE 並清空所有欄位', async () => {
    const { keys, deleteKey } = (await load())()
    const jira = keys.value.find((k) => k.platform === 'jira')!
    jira.value = 'JKEY*****'
    jira.domain = 'https://j.atl'

    fetchSpy.mockResolvedValueOnce(undefined) // DELETE 不用回傳

    await deleteKey(jira)

    expect(fetchSpy).toHaveBeenCalledWith(
      'http://api/users/me/linked-accounts/jira',
      expect.objectContaining({ method: 'DELETE' }),
    )
    // 不能把輸入框裡的 API Key／密碼明文放進刪除請求
    expect(fetchSpy.mock.calls[0][1]).not.toHaveProperty('body')
    expect(jira.value).toBe('')
    expect(jira.domain).toBe('')
    expect(toastSpy.add).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Jira Key 已刪除', color: 'success' }),
    )
  })

  it('saveKey 被限流（429）時，顯示「請求太頻繁」而不是一般的儲存失敗訊息', async () => {
    const { keys, openEdit, saveKey } = (await load())()
    const git = keys.value.find((k) => k.platform === 'github')!
    openEdit(git)
    git.inputValue = 'NEWKEY'

    fetchSpy.mockRejectedValueOnce({
      data: { error_code: 'RATE_LIMITED', detail: '請求太頻繁，請稍後再試' },
      response: { status: 429 },
    })

    await saveKey(git)

    expect(toastSpy.add).toHaveBeenCalledWith(
      expect.objectContaining({ title: '請求太頻繁，請稍後再試', color: 'error' }),
    )
  })
  /* ---------- fetchKeys 邊界情況 ---------- */

  /* ---------- openEdit ---------- */

  it('openEdit Moodle：把目前的帳號帶進輸入框、清空密碼欄，方便只改其中一個', async () => {
    const { keys, openEdit } = (await load())()
    const moo = keys.value.find((k) => k.platform === 'moodle')!
    moo.username = 'bob'
    moo.password = 'm****'

    openEdit(moo)

    expect(moo.inputValue).toBe('bob')
    expect(moo.password).toBe('')
    expect(moo.editing).toBe(true)
  })

  /* ---------- saveKey：Moodle ---------- */

  it('saveKey (Moodle 新建) 送出帳號和密碼，成功後同步顯示用的帳號', async () => {
    const { keys, openEdit, saveKey } = (await load())()
    const moo = keys.value.find((k) => k.platform === 'moodle')!
    openEdit(moo)
    moo.inputValue = 'stu001'
    moo.password = 'secret'

    fetchSpy.mockResolvedValueOnce({ platform: 'moodle', username: 'stu001' }) // 沒有 avatar

    await saveKey(moo)

    const [url, options] = fetchSpy.mock.calls[0]
    expect(url).toBe('http://api/users/me/linked-accounts/')
    expect(options.method).toBe('POST')
    expect(options.body).toMatchObject({ platform: 'moodle', username: 'stu001', password: 'secret' })
    expect(moo.username).toBe('stu001')
    // 沒有 avatar 就不帶 avatar 欄位，不能塞一個 src: undefined 的 avatar
    const toast = toastSpy.add.mock.calls[0][0]
    expect(toast.title).toBe('Moodle Key 儲存成功')
    expect(toast).not.toHaveProperty('avatar')
  })

  // 編輯既有的 Moodle 帳號：依實際改到的欄位顯示不同訊息
  it.each([
    { label: '帳號和密碼都改', username: 'new', password: 'pw', title: 'Moodle 帳號與密碼皆已更新' },
    { label: '只改帳號', username: 'new', password: '', title: 'Moodle 帳號已更新' },
    { label: '只改密碼', username: 'bob', password: 'pw', title: 'Moodle 密碼已更新' },
    { label: '都沒改', username: 'bob', password: '', title: 'Moodle Key 儲存成功' },
  ])('saveKey (Moodle 編輯，$label) → 「$title」', async ({ username, password, title }) => {
    const { keys, openEdit, saveKey } = (await load())()
    const moo = keys.value.find((k) => k.platform === 'moodle')!
    moo.value = 'm****'
    moo.username = 'bob'
    openEdit(moo)
    moo.inputValue = username
    moo.password = password

    fetchSpy.mockResolvedValueOnce(undefined)

    await saveKey(moo)

    const [url, options] = fetchSpy.mock.calls[0]
    expect(url).toBe('http://api/users/me/linked-accounts/moodle')
    expect(options.method).toBe('PATCH')
    // 密碼留空代表不修改，不能把空字串送出去把密碼清掉
    if (password) expect(options.body.password).toBe(password)
    else expect(options.body).not.toHaveProperty('password')
    expect(toastSpy.add).toHaveBeenCalledWith(expect.objectContaining({ title, color: 'success' }))
  })

  /* ---------- saveKey：Jira ---------- */

  it('saveKey (Jira 新建) 一定送出 apiKey 和 domain', async () => {
    const { keys, openEdit, saveKey } = (await load())()
    const jira = keys.value.find((k) => k.platform === 'jira')!
    openEdit(jira)
    jira.inputValue = 'JKEY'
    jira.domain = 'foo.atlassian.net'

    fetchSpy.mockResolvedValueOnce({ platform: 'jira', avatar_url: 'j.png' })

    await saveKey(jira)

    const [, options] = fetchSpy.mock.calls[0]
    expect(options.method).toBe('POST')
    expect(options.body).toMatchObject({ apiKey: 'JKEY', domain: 'foo.atlassian.net' })
    expect(toastSpy.add).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Jira Key 儲存成功', avatar: { src: 'j.png' } }),
    )
  })

  it.each([
    { label: 'domain 和 API Key 都改', domain: 'new.atl', apiKey: 'NEW', title: 'Jira Domain 與 API Key 皆已更新' },
    { label: '只改 API Key', domain: 'https://j.atl', apiKey: 'NEW', title: 'Jira API Key 已更新' },
    { label: '都沒改', domain: 'https://j.atl', apiKey: '', title: 'Jira Key 儲存成功' },
  ])('saveKey (Jira 編輯，$label) → 「$title」', async ({ domain, apiKey, title }) => {
    const { keys, fetchKeys, openEdit, saveKey } = (await load())()
    fetchSpy.mockResolvedValueOnce(list)
    await fetchKeys()
    const jira = keys.value.find((k) => k.platform === 'jira')!
    openEdit(jira)
    jira.domain = domain
    jira.inputValue = apiKey

    fetchSpy.mockResolvedValueOnce(undefined)

    await saveKey(jira)

    const [, options] = fetchSpy.mock.calls[1]
    if (apiKey) expect(options.body.apiKey).toBe(apiKey)
    else expect(options.body).not.toHaveProperty('apiKey')
    expect(toastSpy.add).toHaveBeenCalledWith(expect.objectContaining({ title, color: 'success' }))
  })

  it('saveKey 失敗時 loading 一定會恢復，編輯狀態保留讓使用者重試', async () => {
    const { keys, openEdit, saveKey } = (await load())()
    const git = keys.value.find((k) => k.platform === 'github')!
    openEdit(git)
    git.inputValue = 'NEWKEY'
    vi.spyOn(console, 'error').mockImplementationOnce(() => {})

    fetchSpy.mockRejectedValueOnce(new Error('boom'))

    await saveKey(git)

    expect(git.loading).toBe(false)
    expect(git.editing).toBe(true)
    expect(git.value).toBe('') // 沒存成功就不能把輸入值當成已儲存
    expect(toastSpy.add).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'GitHub Key 儲存失敗', color: 'error' }),
    )
  })

  /* ---------- deleteKey ---------- */

  it('deleteKey 失敗時顯示錯誤，不能把畫面上的資料清掉', async () => {
    const { keys, deleteKey } = (await load())()
    const git = keys.value.find((k) => k.platform === 'github')!
    git.value = 'GKEY*****'
    vi.spyOn(console, 'error').mockImplementationOnce(() => {})

    fetchSpy.mockRejectedValueOnce(new Error('boom'))

    await deleteKey(git)

    expect(git.value).toBe('GKEY*****')
    expect(toastSpy.add).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'GitHub Key 刪除失敗', color: 'error' }),
    )
  })
})
