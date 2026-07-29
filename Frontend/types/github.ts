export interface GitHubAuthor {
    username?: string
    avatar?: string
  }
  
  export interface GitHubIssue {
    id: number
    title: string
    state: string
    created_at: string
    updated_at?: string
    url: string
    isPR: boolean
    author?: GitHubAuthor
    labels?: string[]
    comments?: number
  }
  
  export interface GitHubAPIRawItem {
    number: number
    title: string
    state: string
    created_at: string
    updated_at?: string
    html_url: string
    pull_request?: object
    user?: {
      login?: string
      avatar_url?: string
    }
    labels?: { name: string }[]
    comments?: number
  }
  