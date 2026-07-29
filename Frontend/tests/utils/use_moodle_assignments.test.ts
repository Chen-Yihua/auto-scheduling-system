import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ref as vueRef, computed as vueComputed } from 'vue' 

// 模擬 Nuxt 的 #imports
const toastSpy = { add: vi.fn() }
vi.mock(
    '#imports', 
    () => ({
        useRuntimeConfig: () => ({ public: { apiBaseUrl: 'http://api' } }),
        useToast: () => toastSpy,
    }),
)

// Clerk mock
vi.mock('@clerk/vue', () => ({
  useAuth: () => ({
    getToken: { value: vi.fn().mockResolvedValue('jwt-token') },
    isLoaded: { value: true },
  }),
}))

// 模擬 Vue 的 ref 和 computed
vi.stubGlobal('ref', vueRef) 
vi.stubGlobal('computed', vueComputed) 

// 模擬 $fetch 函式
let fetchSpy = vi.fn()
vi.stubGlobal('$fetch', (...args: any[]) => fetchSpy(...args))

//  模擬 API 回傳的 linked-accounts
const linked = (ok: boolean) =>
  ok ? [{ platform: 'moodle', username: 'u', password: 'p' }] : [{ platform: 'git' }]

// 動態載入 composable，避免測試時載入整個 Nuxt 應用
const loadComposable = async () =>
  (await import('~/composables/useMoodleAssignments')).useMoodleAssignments

describe('useMoodleAssignments', () => {
  beforeEach(() => {
    fetchSpy = vi.fn()
    toastSpy.add.mockClear()
  })

  it('沒有 Moodle 帳號時僅提示 warning', async () => {
    // 1st call: linked-accounts
    fetchSpy.mockResolvedValueOnce(linked(false))

    const useMoodleAssignments = await loadComposable()
    const ctx = useMoodleAssignments()
    await ctx.fetchMoodleAssignments()

    expect(ctx.hasAccount.value).toBe(false)
    expect(fetchSpy).toHaveBeenCalledTimes(1) 
    expect(toastSpy.add).toHaveBeenCalled()
  })

  it('有帳號時成功取得作業', async () => {
    const list = [
      {
        course_name: '課程 A',
        assignment_title: 'Moodle 作業',
        due_date: '2025-07-01',
        assignment_url: 'https://moodle/hw1',
      },
    ]
    fetchSpy.mockResolvedValueOnce(linked(true)).mockResolvedValueOnce(list)

    const useMoodleAssignments = await loadComposable()
    const ctx = useMoodleAssignments()
    await ctx.fetchMoodleAssignments()

    expect(ctx.hasAccount.value).toBeTruthy()
    expect(ctx.moodleAssignments.value).toEqual(list)
    expect(fetchSpy).toHaveBeenCalledTimes(2)
  })
})
