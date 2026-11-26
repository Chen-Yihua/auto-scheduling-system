// 外部平台的標籤、圖示、統計長條用各平台自己的品牌色，使用者一眼認得出來；手動任務用 palette 色
export interface PlatformBrand {
  icon: string
  background: string
  text: string
}

export const platformBrands: Record<string, PlatformBrand> = {
  manual: { icon: 'i-lucide-list-todo', background: '#7E9BAB', text: '#000' },
  github: { icon: 'mdi:github', background: '#24292F', text: '#fff' },
  jira: { icon: 'mdi:jira', background: '#0052CC', text: '#fff' },
  // Moodle 橘配白字對比不夠，用黑字
  moodle: { icon: 'custom:moodle', background: '#F98012', text: '#000' },
}
