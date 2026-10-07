// Google 授權完成後，要把授權碼交給後端換 token（偶爾要好幾秒）。
// 這段時間使用者已經回到首頁（見 composables/useGoogleOAuthCallback.ts），
// 用這份跨元件共用的狀態，讓「行事曆」卡片顯示「連接中」，其他區塊照常顯示。
export const useGoogleCalendarAuth = () => {
  // 正在把授權碼交給後端換 token
  const connecting = useState('googleCalendarConnecting', () => false)
  // 每成功連接一次就加 1，讓想更新行事曆狀態的元件用 watch 監聽
  const connectedCount = useState('googleCalendarConnectedCount', () => 0)

  return { connecting, connectedCount }
}
