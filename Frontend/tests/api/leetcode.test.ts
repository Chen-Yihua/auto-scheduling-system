import { describe, it, expect, vi } from 'vitest'
import { $fetch } from '@nuxt/test-utils'

vi.mock('@nuxt/test-utils', () => ({
  $fetch: vi.fn(() => ({
    date: '2025-01-01',
    link: 'https://leetcode.com/daily-challenge',
    question: {
      title: 'Example Question',
      difficulty: 'Easy',
      content: 'This is an example question.',
      topicTags: ['example', 'test'],
    },
  })),
}))

describe('Leetcode API', () => {
  it('should return valid daily challenge data', async () => {
    const json = await $fetch('/api/leetcode')

    expect(json).toHaveProperty('date')
    expect(json).toHaveProperty('link')
    expect(json).toHaveProperty('question')
    expect(json.question).toHaveProperty('title')
    expect(json.question).toHaveProperty('difficulty')
    expect(json.question).toHaveProperty('content')
    expect(Array.isArray(json.question.topicTags)).toBe(true)
  })
})