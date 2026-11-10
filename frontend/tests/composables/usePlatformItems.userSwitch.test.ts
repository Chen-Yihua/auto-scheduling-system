// 搭配真的 useLinkedAccount（只 mock $fetch），測換使用者時帳號列表的狀態不會沿用到下一個使用者
import { describe, it, expect, vi } from 'vitest'
import { ref as vueRef, computed as vueComputed, nextTick, type Ref } from 'vue'

import { useLinkedAccount } from '~/composables/useLinkedAccount'
import { usePlatformItems } from '~/composables/usePlatformItems'

const clerk = vi.hoisted(() => ({ userId: null as unknown as Ref<string | null> }))
vi.mock('@clerk/vue', async () => {
  const { ref } = await import('vue')
  clerk.userId = ref<string | null>('user_a')
  return {
    useAuth: () => ({
      isLoaded: ref(true),
      getToken: { value: vi.fn().mockResolvedValue('jwt') },
      userId: clerk.userId,
    }),
    useUser: () => ({ user: ref({ username: 'tester' }) }),
  }
})

vi.stubGlobal('ref', vueRef)
vi.stubGlobal('computed', vueComputed)
vi.stubGlobal('useToast', () => ({ add: vi.fn() }))
vi.stubGlobal('useRuntimeConfig', () => ({ public: { apiBaseUrl: 'http://api' } }))
vi.stubGlobal('useLinkedAccount', useLinkedAccount)

const fetchSpy = vi.fn()
const fetchRawSpy = vi.fn()
vi.stubGlobal('$fetch', Object.assign((...args: unknown[]) => fetchSpy(...args), { raw: (...args: unknown[]) => fetchRawSpy(...args) }))

describe('usePlatformItems 換使用者', () => {
  it('AC20：A 的 GitHub 憑證無法讀取，換成沒有連結 GitHub 的 B 後 → 不沿用「憑證無法讀取」，顯示尚未綁定', async () => {
    fetchSpy.mockResolvedValueOnce([{ platform: 'github', username: 'a', needs_reauth: true }])
    const { fetchItems, needsReauth, notLinked } = usePlatformItems('github')
    await fetchItems()
    expect(needsReauth.value).toBe(true)

    clerk.userId.value = null
    await nextTick()
    clerk.userId.value = 'user_b'
    fetchSpy.mockResolvedValueOnce([])
    await fetchItems()

    expect(needsReauth.value).toBe(false)
    expect(notLinked.value).toBe(true)
    expect(fetchRawSpy).not.toHaveBeenCalled()
  })
})
