// utils/github.ts
import type { GitHubAPIRawItem, GitHubIssue } from '@/types/github'

export const transformGitHubItem = (item: GitHubAPIRawItem): GitHubIssue => ({
  id: item.number,
  title: item.title,
  state: item.state,
  created_at: item.created_at,
  updated_at: item.updated_at,
  url: item.html_url,
  isPR: !!item.pull_request,
  author: {
    username: item.user?.login,
    avatar: item.user?.avatar_url,
  },
  labels: item.labels?.map(label => label.name),
  comments: item.comments,
})
//送給後端 sync 用
export const transformGitHubItemForSync = (item: GitHubAPIRawItem) => ({
  id: item.number,
  title: item.title,
  state: item.state,
  created_at: item.created_at ?? new Date().toISOString(),
  updated_at: item.updated_at ?? new Date().toISOString(),
  url: item.html_url,
  isPR: !!item.pull_request,
  author: {
    username: item.user?.login,
    avatar: item.user?.avatar_url,
  },
  labels: item.labels?.map(label => label.name),
  comments: item.comments,
});