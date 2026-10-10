// 授權碼在背景換 token 時，讓行事曆卡片顯示「連接中」
export const useGoogleCalendarAuth = () => {
  const connecting = useState('googleCalendarConnecting', () => false)
  // 每次連接成功遞增，供其他元件 watch
  const connectedCount = useState('googleCalendarConnectedCount', () => 0)

  return { connecting, connectedCount }
}
