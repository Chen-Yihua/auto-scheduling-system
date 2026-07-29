import type { JiraAPIRawIssue, JiraIssue } from '@/types/jira';

export const transformJiraItem = (item: JiraAPIRawIssue): JiraIssue => ({
    id: item.id,
    key: item.key,
    summary: item.fields.summary,
    status: item.fields.status?.name ?? '',
    updated: item.fields.updated,
    assignee: item.fields.assignee?.displayName ?? '',
    avatar: item.fields.assignee?.avatarUrls?.["48x48"] ?? '',
    type: item.fields.issuetype?.name ?? '',
    iconUrl: item.fields.issuetype?.iconUrl ?? '',
  })