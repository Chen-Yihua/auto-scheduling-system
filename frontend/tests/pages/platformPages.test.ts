// GitHub、Jira、Moodle 三個平台頁面：打開時只讀資料，立即同步按鈕接到那一頁平台的 syncNow（issue #13）
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises, enableAutoUnmount } from '@vue/test-utils'
import { ref, watch, h, defineComponent } from 'vue'

import GithubPage from '~/pages/github.vue'
import JiraPage from '~/pages/jira.vue'
import MoodlePage from '~/pages/moodle.vue'

vi.stubGlobal('watch', watch)

vi.mock('@clerk/vue', async () => {
  const { ref } = await import('vue')
  return { useUser: () => ({ isSignedIn: ref(true) }) }
})

const spies = {
  github: { fetchItems: vi.fn(), syncNow: vi.fn() },
  jira: { fetchItems: vi.fn(), syncNow: vi.fn() },
  moodle: { fetchItems: vi.fn(), syncNow: vi.fn() },
}
const requested: string[] = []

vi.mock('~/composables/usePlatformItems', () => ({
  usePlatformItems: (platform: 'github' | 'jira' | 'moodle') => {
    requested.push(platform)
    return {
      items: ref([]),
      account: ref(undefined),
      fetchItems: spies[platform].fetchItems,
      syncNow: spies[platform].syncNow,
      syncing: ref(false),
      isStale: ref(false),
      syncedAt: ref('2026-11-14T04:00:00Z'),
      authError: ref(false),
      notLinked: ref(false),
      needsReauth: ref(false),
      unavailable: ref(false),
      loading: ref(false),
    }
  },
}))

const stubs = {
  AppHeader: defineComponent({ setup: () => () => h('div') }),
  NuxtLink: { template: '<a><slot /></a>' },
  UIcon: true,
  LoginRequiredCard: true,
  GithubIssuesList: true,
  JiraIssuesList: true,
  MoodleAssignmentsList: true,
}

enableAutoUnmount(afterEach)

describe.each([
  { platform: 'github', page: GithubPage, list: 'GithubIssuesList' },
  { platform: 'jira', page: JiraPage, list: 'JiraIssuesList' },
  { platform: 'moodle', page: MoodlePage, list: 'MoodleAssignmentsList' },
] as const)('pages/$platform 頁面', ({ platform, page, list }) => {
  beforeEach(() => {
    requested.length = 0
    Object.values(spies).forEach((s) => { s.fetchItems.mockReset(); s.syncNow.mockReset() })
  })

  it('AC30：打開頁面只讀資料（fetchItems），不呼叫立即同步', async () => {
    mount(page, { global: { stubs } })
    await flushPromises()

    expect(spies[platform].fetchItems).toHaveBeenCalledTimes(1)
    expect(spies[platform].syncNow).not.toHaveBeenCalled()
  })

  it('AC31、AC32：清單收到上次同步時間與立即同步按鈕，按鈕只同步這一頁的平台', async () => {
    const wrapper = mount(page, { global: { stubs } })
    await flushPromises()

    const card = wrapper.findComponent({ name: list })
    expect(card.props('syncedAt')).toBe('2026-11-14T04:00:00Z')
    await (card.props('onSync') as () => Promise<void>)()

    expect(requested).toEqual([platform])
    expect(spies[platform].syncNow).toHaveBeenCalledTimes(1)
  })
})
