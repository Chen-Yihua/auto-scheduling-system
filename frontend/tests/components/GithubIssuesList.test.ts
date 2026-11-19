import { describe, it, expect } from 'vitest';
import { mount } from '@vue/test-utils';
import { defineComponent, h } from 'vue';
import GithubIssuesList from '~/components/platforms/GithubIssuesList.vue';
import StaleDataBanner from '~/components/platforms/StaleDataBanner.vue';

// UCard 預設的 stub 不渲染 slot，改用會渲染 slot 的假元件
const UCardStub = defineComponent({
  name: 'UCard',
  setup(_, { slots }) {
    return () => h('div', { class: 'u-card-stub' }, [slots.header?.(), slots.default?.(), slots.footer?.()])
  },
})

const uiStubs = { USkeleton: true, UBadge: true, UAvatar: true, UCard: UCardStub, UAlert: true, UIcon: true }

const render = (props: Record<string, unknown>) =>
  mount(GithubIssuesList, { props: { issues: [], loading: false, ...props }, global: { stubs: uiStubs } })

describe('GithubIssuesList.vue', () => {
  it('AC20：帳號檢查失敗而且沒有已知的結果（unavailable）→ 顯示暫時無法載入，不顯示尚未綁定', () => {
    const wrapper = render({ unavailable: true })

    expect(wrapper.text()).toContain('暫時無法載入，請稍後再試')
    expect(wrapper.text()).not.toContain('尚未綁定')
  })

  it('AC9：憑證無法讀取（needsReauth）→ 顯示要重新連結，不顯示尚未綁定', () => {
    const wrapper = render({ needsReauth: true })

    expect(wrapper.text()).toContain('重新連結')
    expect(wrapper.text()).not.toContain('尚未綁定')
  });

  it('AC5：授權失效提示收到 GitHub 清單是否有項目的資料狀態', () => {
    const withItem = render({
      issues: [{ id: '1', number: 1, title: 'Issue', isPR: false, status: 'open', labels: [], author: null, comments: 0, url: 'https://example.test/1', created_at: '2026-09-03T11:00:00Z', updated_at: '2026-09-03T11:00:00Z' }],
      authError: true,
      syncedAt: null,
    })
    const empty = render({ issues: [], authError: true, syncedAt: null })

    expect(withItem.findComponent(StaleDataBanner).props('hasItems')).toBe(true)
    expect(empty.findComponent(StaleDataBanner).props('hasItems')).toBe(false)
  })

  it('尚未綁定時照常顯示尚未綁定', () => {
    expect(render({ notLinked: true }).text()).toContain('尚未綁定 GitHub 帳號')
  });
})
