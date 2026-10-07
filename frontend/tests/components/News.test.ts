import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { ref, defineComponent, h, Suspense } from 'vue'
import flushPromises from 'flush-promises'
import News from '@/components/dashboard/News.vue'

type Story = { title: string; url: string; publishedAt: string }

/* 把 useLazyAsyncData 直接放進 globalThis；回傳值由每個測試自己設定，
   傳進來的抓資料函式也記下來，才能單獨測「怎麼抓、怎麼轉格式」 */
const dataRef = ref<Story[] | null>(null)
const statusRef = ref('success')
const errorRef = ref<unknown>(null)
let capturedHandler: (() => Promise<Story[]>) | null = null
vi.stubGlobal('useLazyAsyncData', (_key: string, handler: () => Promise<Story[]>) => {
  capturedHandler = handler
  return { data: dataRef, status: statusRef, error: errorRef }
})

const fourStories: Story[] = [
  { title: 'Story A', url: 'https://a.com', publishedAt: '2025-05-16 12:00' },
  { title: 'Story B', url: 'https://b.com', publishedAt: '2025-05-16 13:00' },
  { title: 'Story C', url: 'https://c.com', publishedAt: '2025-05-16 14:00' },
  { title: 'Story D', url: 'https://d.com', publishedAt: '2025-05-16 15:00' },
]

/* stub 外部 UI（保留 slot 的照舊） */
const SlotStub = defineComponent({
  setup(_, { slots }) { return () => h('div', [slots.default?.(), slots.content?.()]) }
})
const Empty = defineComponent({ render: () => h('div') })
const stubs = {
  USkeleton: defineComponent({ render: () => h('div', { 'data-test': 'skeleton' }) }),
  UCard: SlotStub,
  UCollapsible: SlotStub,
  UButton: Empty,
  UIcon: Empty
}

/* <Suspense> 包裝 News */
const Wrapper = defineComponent({
  /* 直接回傳 VNode，不再寫 template / components */
  render() {
    return h(Suspense, null, { default: () => h(News) })
  }
})

async function render() {
  const wrapper = mount(Wrapper, { global: { stubs } })
  await flushPromises()            // 清所有 Promise → 等 async setup 完成
  return wrapper
}

describe('News.vue (plain Vue mount)', () => {
  beforeEach(() => {
    dataRef.value = fourStories
    statusRef.value = 'success'
    errorRef.value = null
    capturedHandler = null
  })

  it('前三則直接顯示，第四則以後收在折疊區，編號接著往下數', async () => {
    const wrapper = await render()

    const [visibleList, collapsedList] = wrapper.findAll('ul')
    const visibleLinks = visibleList.findAll('a[target="_blank"]')
    expect(visibleLinks.map((a) => a.text())).toEqual(['Story A', 'Story B', 'Story C'])

    const collapsedItems = collapsedList.findAll('li')
    expect(collapsedItems).toHaveLength(1)
    expect(collapsedItems[0].get('a').text()).toBe('Story D')
    // 折疊區的編號接著前三則往下數，不是從 1 重新開始
    expect(collapsedItems[0].get('span').text()).toBe('4')
  })

  it('載入中顯示 Skeleton，不顯示新聞或錯誤訊息', async () => {
    statusRef.value = 'pending'
    const wrapper = await render()

    expect(wrapper.find('[data-test="skeleton"]').exists()).toBe(true)
    expect(wrapper.find('a').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('暫時無法載入新聞')
  })

  it.each([
    ['抓資料出錯', { error: new Error('boom'), data: fourStories }],
    ['沒有資料', { error: null, data: null }],
    ['空清單', { error: null, data: [] }],
  ])('%s → 顯示錯誤訊息', async (_label, { error, data }) => {
    errorRef.value = error
    dataRef.value = data
    const wrapper = await render()

    expect(wrapper.text()).toContain('暫時無法載入新聞，請稍後再試。')
    expect(wrapper.find('a').exists()).toBe(false)
  })

})

describe('News.vue 抓資料函式', () => {
  const fetchSpy = vi.fn()

  beforeEach(() => {
    fetchSpy.mockReset()
    vi.stubGlobal('$fetch', fetchSpy)
    dataRef.value = fourStories
    statusRef.value = 'success'
    errorRef.value = null
  })

  it('抓前 10 則 top story，轉成 標題／網址／本地時間 的格式', async () => {
    await render()
    expect(capturedHandler).toBeTypeOf('function')

    const ids = Array.from({ length: 12 }, (_, i) => i + 1)
    // 2025-05-16 04:05 UTC，用本地時間的各欄位組出預期字串，不寫死時區
    const time = Date.UTC(2025, 4, 16, 4, 5) / 1000
    fetchSpy.mockImplementation(async (url: string) => {
      if (url.endsWith('topstories.json')) return ids
      const id = Number(url.match(/item\/(\d+)\.json/)![1])
      return { title: `Story ${id}`, url: `https://s${id}.com`, time }
    })

    const result = await capturedHandler!()

    expect(fetchSpy).toHaveBeenCalledWith('https://hacker-news.firebaseio.com/v0/topstories.json')
    // 只抓前 10 則的細節，第 11、12 則不能多打
    expect(fetchSpy).toHaveBeenCalledTimes(11)
    expect(fetchSpy).not.toHaveBeenCalledWith('https://hacker-news.firebaseio.com/v0/item/11.json')

    const d = new Date(time * 1000)
    const pad = (n: number) => String(n).padStart(2, '0')
    const expectedTime = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
    expect(result).toHaveLength(10)
    expect(result[0]).toEqual({ title: 'Story 1', url: 'https://s1.com', publishedAt: expectedTime })
  })
})
