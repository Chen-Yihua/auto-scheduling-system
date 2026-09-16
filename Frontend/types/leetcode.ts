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
  