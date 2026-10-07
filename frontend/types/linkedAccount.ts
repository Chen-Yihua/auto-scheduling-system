// 對應後端 GET /users/me/linked-accounts/ 回傳的單筆資料
export interface LinkedAccountRecord {
  platform: string
  apiKey?: string
  domain?: string
  password?: string
  avatar_url?: string
  username?: string
}
