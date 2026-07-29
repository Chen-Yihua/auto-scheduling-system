// tests/utils/useLinkedAccount.test.ts
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
vi.stubGlobal('$fetch', (...a: any[]) => fetchSpy(...a))
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

    // 1st call => POST create, 回傳 avatar
    fetchSpy.mockResolvedValueOnce({ linkedAccounts: { github: { avatar_url: 'a.png' } } })

    await saveKey(git)

    expect(fetchSpy).toHaveBeenCalledWith(
      'http://api/user/linked-accounts/create',
      expect.objectContaining({ method: 'POST' }),
    )
    expect(git.value).toBe('NEWKEY')
    expect(git.editing).toBe(false)
    expect(toastSpy.add).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'GitHub Key 儲存成功', color: 'success' }),
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
      'http://api/user/linked-accounts/jira',
      expect.objectContaining({ method: 'DELETE' }),
    )
    expect(jira.value).toBe('')
    expect(jira.domain).toBe('')
    expect(toastSpy.add).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Jira Key 已刪除', color: 'success' }),
    )
  })
})
