export interface GitHubAuthor {
    username?: string
    avatar?: string
  }
  
  export interface GitHubIssue {
    id: number  // GitHub 全域唯一 id（列表 key 用）
    number: number  // repo 內的編號，顯示用的 "#123"
    title: string
    status: string
    created_at: string
    updated_at?: string
    url: string
    isPR: boolean
    author?: GitHubAuthor
    labels?: string[]
    comments?: number
  }
