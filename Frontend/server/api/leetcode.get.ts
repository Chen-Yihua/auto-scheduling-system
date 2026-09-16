// server/api/leetcode.get.ts
import { DailyChallengeResponse } from '~/types/leetcode'

export default defineEventHandler(async (event) => {
  const query = `
    query GetDailyChallenge {
      activeDailyCodingChallengeQuestion {
        date
        link
        question {
          title
          difficulty
          topicTags {
            name
            slug
          }
          content
        }
      }
    }`

  const res = await $fetch<DailyChallengeResponse>('https://leetcode.com/graphql', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: { query }
  })

  return res.data.activeDailyCodingChallengeQuestion
})
