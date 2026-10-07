import { describe, it, expect } from 'vitest'
import {
  priorityLabel,
  taskStatusLabel,
  githubStateLabel,
  leetcodeDifficultyLabel,
} from '~/utils/labels'

describe('畫面顯示用的中文對照', () => {
  it('優先級、任務狀態、GitHub 狀態、LeetCode 難度都轉成中文', () => {
    expect(priorityLabel('High')).toBe('高')
    expect(priorityLabel('Medium')).toBe('中')
    expect(priorityLabel('Low')).toBe('低')
    expect(taskStatusLabel('To Do')).toBe('待辦')
    expect(taskStatusLabel('In Progress')).toBe('進行中')
    expect(taskStatusLabel('Done')).toBe('已完成')
    expect(githubStateLabel('open')).toBe('開啟中')
    expect(githubStateLabel('closed')).toBe('已關閉')
    expect(leetcodeDifficultyLabel('Hard')).toBe('困難')
  })

  it('對照表裡沒有的值原樣顯示，不會變成空白', () => {
    expect(priorityLabel('Urgent')).toBe('Urgent')
    expect(taskStatusLabel('Blocked')).toBe('Blocked')
  })

  it('沒有值（undefined / null / 空字串）時顯示空字串', () => {
    expect(priorityLabel(undefined)).toBe('')
    expect(githubStateLabel(null)).toBe('')
    expect(leetcodeDifficultyLabel('')).toBe('')
  })
})
