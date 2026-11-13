// 授權碼在背景換 token 時，讓行事曆卡片顯示「連接中」
export const useGoogleCalendarAuth = () => {
  const connecting = useState('googleCalendarConnecting', () => false)
  // 每次連接成功遞增，供其他元件 watch
  const connectedCount = useState('googleCalendarConnectedCount', () => 0)

  const config = useRuntimeConfig()
  const goToGoogleAuth = () => {
    const params = new URLSearchParams({
      client_id: config.public.apiGoogleClientId,
      redirect_uri: `${config.public.frontEndUrl}/oauth/callback`,
      response_type: 'code',
      // calendar.events 用來寫入排程事件；不需要完整的 calendar 權限
      scope: 'https://www.googleapis.com/auth/calendar.readonly https://www.googleapis.com/auth/calendar.events',
      access_type: 'offline',
      prompt: 'consent',
    })

    window.location.href = `https://accounts.google.com/o/oauth2/v2/auth?${params.toString()}`
  }

  // 後端回 REAUTH_REQUIRED 代表要重新連接，等待或重試都沒用，所以直接給按鈕
  const reauthToast = () => ({
    title: 'Google Calendar 授權已失效',
    description: '你的 Google 授權可能已過期或被撤銷，請重新連接 Google Calendar',
    color: 'error' as const,
    icon: 'i-lucide-x',
    actions: [{ label: '重新連接 Google Calendar', onClick: goToGoogleAuth }],
  })

  return { connecting, connectedCount, goToGoogleAuth, reauthToast }
}
