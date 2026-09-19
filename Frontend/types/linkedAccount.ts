// 對應後端 GET /user/linked-accounts/me 回傳的單筆資料
export interface LinkedAccountRecord {
  platform: string
  apiKey?: string
  domain?: string
  password?: string
  avatar_url?: string
  username?: string
}
