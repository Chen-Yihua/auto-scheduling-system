// 對應後端 GET /users/me/linked-accounts/ 回傳的單筆資料，POST 建立後也回傳同樣格式
export interface LinkedAccountRecord {
  platform: string
  apiKey?: string
  domain?: string
  password?: string
  avatar_url?: string
  username?: string
  // 已存的憑證無法解密，要重新連結；這時沒有 apiKey、password
  needs_reauth: boolean
}
