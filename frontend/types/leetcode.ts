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

// GET /api/leetcode 的回傳內容
export type DailyChallenge = DailyChallengeResponse['data']['activeDailyCodingChallengeQuestion']
