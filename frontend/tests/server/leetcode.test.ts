// defineEventHandler、$fetch 在 Nitro 是全域的，用 stubGlobal 補上後直接呼叫 handler
import { describe, it, expect, vi, beforeAll, beforeEach } from 'vitest'

const fetchSpy = vi.fn()
vi.stubGlobal('defineEventHandler', (handler: unknown) => handler)
vi.stubGlobal('$fetch', fetchSpy)

const dailyChallenge = {
  date: '2025-01-01',
  link: '/problems/two-sum/',
  question: {
    title: 'Two Sum',
    difficulty: 'Easy',
    content: '<p>Given an array...</p>',
    topicTags: [{ name: 'Array', slug: 'array' }],
  },
}

let handler: () => Promise<unknown>

describe('GET /api/leetcode', () => {
  beforeAll(async () => {
    // stubGlobal 要在載入模組之前完成，defineEventHandler 才會用到 stub
    handler = (await import('~/server/api/leetcode.get')).default as unknown as typeof handler
  })

  beforeEach(() => {
    fetchSpy.mockReset()
    fetchSpy.mockResolvedValue({ data: { activeDailyCodingChallengeQuestion: dailyChallenge } })
  })

  it('用 POST 打 LeetCode GraphQL，查詢每日一題需要的欄位', async () => {
    await handler()

    expect(fetchSpy).toHaveBeenCalledTimes(1)
    const [url, options] = fetchSpy.mock.calls[0]
    expect(url).toBe('https://leetcode.com/graphql')
    expect(options.method).toBe('POST')
    expect(options.headers).toEqual({ 'Content-Type': 'application/json' })
    expect(options.body.query).toContain('activeDailyCodingChallengeQuestion')
    for (const field of ['date', 'link', 'title', 'difficulty', 'topicTags', 'content']) {
      expect(options.body.query).toContain(field)
    }
  })

  it('只回傳 activeDailyCodingChallengeQuestion 這一層，前端不用自己拆 data 外殼', async () => {
    const result = await handler()

    expect(result).toEqual(dailyChallenge)
  })

  it('LeetCode 打不通時把錯誤往外拋，交給 Nuxt 回錯誤狀態碼，不是回一個空物件假裝成功', async () => {
    fetchSpy.mockRejectedValue(new Error('network down'))

    await expect(handler()).rejects.toThrow('network down')
  })
})
