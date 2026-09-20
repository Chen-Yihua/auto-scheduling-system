// types/leetcode.ts
export interface DailyChallengeResponse {
    data: {
      activeDailyCodingChallengeQuestion: {
        date: string;
        link: string;
        question: {
          title: string;
          difficulty: string;
          topicTags: {
            name: string;
            slug: string;
          }[];
          content: string;
        };
      };
    };
  }

// GET /api/leetcode 回傳的內容（每日一題本身，不含外層的 data）
export type DailyChallenge = DailyChallengeResponse['data']['activeDailyCodingChallengeQuestion']
