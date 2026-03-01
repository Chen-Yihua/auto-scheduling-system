export interface JiraIssue {
    id: string
    key: string
    summary: string
    status: string
    updated: string
    assignee?: string
    avatar?: string
    type?: string
    iconUrl?: string
  }
  
  export interface JiraAPIRawIssue {
    id: string
    key: string
    fields: {
      summary: string
      status?: {
        name: string
      }
      updated: string
      assignee?: {
        displayName: string
        avatarUrls: {
          [key: string]: string
        }
      }
      issuetype?: {
        name: string
        iconUrl: string
      }
    }
  }