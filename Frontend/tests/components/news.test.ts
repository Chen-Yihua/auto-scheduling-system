import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { ref, defineComponent, h, Suspense } from 'vue'
import flushPromises from 'flush-promises'
import News from '@/components/TheMain/News.vue'

/* 1️⃣ 把 useLazyAsyncData 直接放進 globalThis */
vi.stubGlobal('useLazyAsyncData', () => ({
  data: ref([
    { title: 'Story A', url: 'https://a.com', publishedAt: '2025-05-16 12:00' },
    { title: 'Story B', url: 'https://b.com', publishedAt: '2025-05-16 13:00' },
    { title: 'Story C', url: 'https://c.com', publishedAt: '2025-05-16 14:00' },
    { title: 'Story D', url: 'https://d.com', publishedAt: '2025-05-16 15:00' }
  ]),
  status: ref('success'),
  error: ref(null)
}))

/* 2️⃣ stub 外部 UI（保留 slot 的照舊） */
const SlotStub = defineComponent({
  setup(_, { slots }) { return () => h('div', slots.default?.()) }
})
const Empty = defineComponent({ render: () => h('div') })
const stubs = {
  USkeleton: Empty,
  UCard: SlotStub,
  UCollapsible: SlotStub,
  UButton: Empty
}

/* 3️⃣ <Suspense> 包裝 News */
const Wrapper = defineComponent({
  /* 直接回傳 VNode，不再寫 template / components */
  render() {
    return h(Suspense, null, { default: () => h(News) })
  }
})

describe('News.vue (plain Vue mount)', () => {
  it('應只顯示前三則新聞連結', async () => {
    const wrapper = mount(Wrapper, { global: { stubs } })

    await flushPromises()            // 清所有 Promise → 等 async setup 完成

    const links = wrapper.findAll('a[target="_blank"]')
    expect(links).toHaveLength(3)
    expect(links[0].text()).toBe('Story A')
    expect(links[1].text()).toBe('Story B')
    expect(links[2].text()).toBe('Story C')
  })
})
