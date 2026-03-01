// tests/utils/github.test.ts
import { describe, it, expect } from 'vitest'
import { transformGitHubItem } from '@/utils/github'

describe('transformGitHubItem', () => {
  it('should transform GitHub API raw item into internal format', () => {
    const raw = {
      number: 123,
      title: 'Fix bug',
      state: 'open',
      created_at: '2024-01-01T00:00:00Z',
      updated_at: '2024-01-02T00:00:00Z',
      html_url: 'https://github.com/owner/repo/issues/123',
      pull_request: {},
      user: { login: 'dev', avatar_url: 'avatar.png' },
      labels: [{ name: 'bug' }, { name: 'urgent' }],
      comments: 5,
    }

    const result = transformGitHubItem(raw as any)
    expect(result).toMatchObject({
      id: 123,
      isPR: true,
      author: { username: 'dev', avatar: 'avatar.png' },
      labels: ['bug', 'urgent'],
    })
  })
})
