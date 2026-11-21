import { describe, it, expect } from 'vitest'
import { buildTodayView, isOverdue } from '~/utils/todayTasks'
import type { SchedulableTask } from '~/types/schedulableTask'

// 測試時區固定為 Asia/Taipei（vitest.config.ts）
const NOW = new Date('2026-11-21T10:00:00+08:00')

function task(overrides: Partial<SchedulableTask> & { id: string }): SchedulableTask {
  return {
    source: 'manual', title: overrides.id, status: 'To Do', priority: 'Medium', duration: 30,
    due_date: null, calendar_event_id: null, scheduled_start: null, scheduled_end: null, url: null,
    ...overrides,
  }
}

const ids = (rows: { task: SchedulableTask }[]) => rows.map((r) => r.task.id)

describe('buildTodayView', () => {
  it('AC14：沒完成、截止日期是昨天的任務列在已逾期區，標「已逾期」', () => {
    const view = buildTodayView([task({ id: 'a', due_date: '2026-11-20T00:00:00+08:00' })], NOW)

    expect(view.overdue).toEqual([expect.objectContaining({ label: '已逾期', overdue: true })])
    expect(ids(view.overdue)).toEqual(['a'])
  })

  it('AC14a、AC20：截止日期是今天（00:00 或 09:00）、時段還沒結束或沒有時段的任務，今天不算已逾期，也不列在今日卡片', () => {
    const view = buildTodayView([
      task({ id: 'midnight', due_date: '2026-11-21T00:00:00+08:00', calendar_event_id: 'e1', scheduled_end: '2026-11-21T15:00:00+08:00' }),
      task({ id: 'nine', source: 'github', due_date: '2026-11-21T09:00:00+08:00', scheduled_end: '2026-11-21T18:00:00+08:00' }),
      task({ id: 'plain', due_date: '2026-11-21T00:00:00+08:00' }),
    ], NOW)

    expect(view.overdue).toEqual([])
    expect(view.today).toEqual([])
  })

  it('AC15：截止日期還沒到、時段結束時間早於現在的任務列在已逾期區', () => {
    const view = buildTodayView([
      task({ id: 'a', due_date: '2026-11-30T00:00:00+08:00', calendar_event_id: 'e', scheduled_start: '2026-11-21T08:00:00+08:00', scheduled_end: '2026-11-21T09:00:00+08:00' }),
    ], NOW)

    expect(ids(view.overdue)).toEqual(['a'])
    expect(view.today).toEqual([])
  })

  it('AC16：已完成的任務即使截止日期已過，也不列在已逾期區', () => {
    const view = buildTodayView([task({ id: 'done', status: 'Done', due_date: '2026-11-01T00:00:00+08:00' })], NOW)

    expect(view.overdue).toEqual([])
    expect(view.today).toEqual([])
  })

  it('AC17：已逾期區依截止日期與時段結束時間中較早的那個時間由早到晚排列', () => {
    const view = buildTodayView([
      task({ id: 'c', due_date: '2026-11-19T00:00:00+08:00' }),
      task({ id: 'a', due_date: '2026-11-30T00:00:00+08:00', scheduled_end: '2026-11-10T09:00:00+08:00', calendar_event_id: 'e' }),
      task({ id: 'b', due_date: '2026-11-15T00:00:00+08:00', scheduled_end: '2026-11-20T09:00:00+08:00', calendar_event_id: 'e' }),
    ], NOW)

    expect(ids(view.overdue)).toEqual(['a', 'b', 'c'])
  })

  it('AC18：今天有時段、還沒逾期的任務列在已逾期區下面，沒完成的依開始時間排列，已完成的排在最後', () => {
    const view = buildTodayView([
      task({ id: 'done', status: 'Done', scheduled_start: '2026-11-21T08:00:00+08:00', scheduled_end: '2026-11-21T09:00:00+08:00' }),
      task({ id: 'late', scheduled_start: '2026-11-21T16:00:00+08:00', scheduled_end: '2026-11-21T17:00:00+08:00', calendar_event_id: 'e' }),
      task({ id: 'early', scheduled_start: '2026-11-21T11:00:00+08:00', scheduled_end: '2026-11-21T12:00:00+08:00', calendar_event_id: 'e' }),
      task({ id: 'old', due_date: '2026-11-01T00:00:00+08:00' }),
    ], NOW)

    expect(ids(view.overdue)).toEqual(['old'])
    expect(ids(view.today)).toEqual(['early', 'late', 'done'])
  })

  it('AC19：時段不在今天、也沒有逾期的任務，不列在今日卡片', () => {
    const view = buildTodayView([
      task({ id: 'tomorrow', scheduled_start: '2026-11-22T09:00:00+08:00', scheduled_end: '2026-11-22T10:00:00+08:00', calendar_event_id: 'e' }),
    ], NOW)

    expect(view.overdue).toEqual([])
    expect(view.today).toEqual([])
  })

  it('AC21：主任務不列在今日卡片', () => {
    const view = buildTodayView([task({ id: 'parent', is_parent: true, due_date: '2026-11-01T00:00:00+08:00' })], NOW)

    expect(view.overdue).toEqual([])
  })

  it('AC22：不是已逾期的任務依 status 標「未開始」「進行中」「已完成」', () => {
    const slot = { scheduled_start: '2026-11-21T14:00:00+08:00', scheduled_end: '2026-11-21T15:00:00+08:00', calendar_event_id: 'e' }
    const view = buildTodayView([
      task({ id: 'todo', ...slot }),
      task({ id: 'doing', status: 'In Progress', ...slot }),
      task({ id: 'done', status: 'Done', ...slot }),
    ], NOW)

    expect(Object.fromEntries(view.today.map((r) => [r.task.id, r.label]))).toEqual({
      todo: '未開始', doing: '進行中', done: '已完成',
    })
  })

  it('AC36：批次重新排程的任務是已逾期、有 calendar_event_id 的任務；今天未逾期的不算', () => {
    const view = buildTodayView([
      task({ id: 'o1', due_date: '2026-11-01T00:00:00+08:00', calendar_event_id: 'e1' }),
      task({ id: 'o2', due_date: '2026-11-02T00:00:00+08:00', calendar_event_id: 'e2' }),
      task({ id: 'o3', due_date: '2026-11-03T00:00:00+08:00' }),
      task({ id: 'today', scheduled_start: '2026-11-21T14:00:00+08:00', scheduled_end: '2026-11-21T15:00:00+08:00', calendar_event_id: 'e4' }),
    ], NOW)

    expect(view.batchIds).toEqual(['o1', 'o2'])
  })

  it('AC36b：已逾期的階段 1 後面有排在今天、還沒逾期的階段 2，後面階段的數量是 1', () => {
    const view = buildTodayView([
      task({ id: 's1', parent_id: 'p', stage: 1, due_date: '2026-11-01T00:00:00+08:00', calendar_event_id: 'e1' }),
      task({ id: 's2', parent_id: 'p', stage: 2, scheduled_start: '2026-11-21T14:00:00+08:00', scheduled_end: '2026-11-21T15:00:00+08:00', calendar_event_id: 'e2' }),
      task({ id: 's3', parent_id: 'p', stage: 3, status: 'Done', calendar_event_id: 'e3' }),
      task({ id: 's4', parent_id: 'p', stage: 4 }),
    ], NOW)

    expect(view.batchIds).toEqual(['s1'])
    expect(view.laterStageCount).toBe(1)
  })

  it('AC36b：後面階段也在已逾期的批次裡時不重複算，兩個階段共同的後面階段只算一次', () => {
    const view = buildTodayView([
      task({ id: 's1', parent_id: 'p', stage: 1, due_date: '2026-11-01T00:00:00+08:00', calendar_event_id: 'e1' }),
      task({ id: 's2', parent_id: 'p', stage: 2, due_date: '2026-11-02T00:00:00+08:00', calendar_event_id: 'e2' }),
      task({ id: 's3', parent_id: 'p', stage: 3, scheduled_start: '2026-11-21T14:00:00+08:00', scheduled_end: '2026-11-21T15:00:00+08:00', calendar_event_id: 'e3' }),
    ], NOW)

    expect(view.laterStageCount).toBe(1)
  })
})

describe('isOverdue（任務管理頁與今日卡片共用）', () => {
  it('issue-178 AC15：沒完成、截止日期是昨天 → 已逾期；主任務只看自己的截止日期，也一樣', () => {
    expect(isOverdue(task({ id: 'a', due_date: '2026-11-20T00:00:00+08:00' }), NOW)).toBe(true)
    expect(isOverdue(task({ id: 'p', is_parent: true, due_date: '2026-11-20T00:00:00+08:00' }), NOW)).toBe(true)
  })

  it('issue-178 AC16：沒完成、時段結束時間已過、截止日期還沒到 → 已逾期', () => {
    expect(isOverdue(task({ id: 'a', due_date: '2026-11-22T00:00:00+08:00', scheduled_end: '2026-11-21T09:00:00+08:00' }), NOW)).toBe(true)
  })

  it('issue-178 AC17：已完成的任務即使截止日期已過 → 不算已逾期', () => {
    expect(isOverdue(task({ id: 'a', status: 'Done', due_date: '2026-11-20T00:00:00+08:00' }), NOW)).toBe(false)
  })
})
