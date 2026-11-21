// 重新排程後的通知文字；rescheduleTasks 本身不跳通知，由呼叫端依結果選用
import type { ResolveRemovedEventsFailure } from '~/types/schedule'

export type RescheduleOutcome =
  | { kind: 'success'; failed: ResolveRemovedEventsFailure[] }
  | { kind: 'reauth'; failed: [] }
  | { kind: 'error'; message?: string; failed: [] }

type ReauthToast = { actions: { label: string; onClick: () => void }[] }

// 多行說明要搭配 whitespace-pre-line 才會分行
export const MULTILINE_TOAST_UI = { description: 'whitespace-pre-line' }

// 儲存表單之後重新排程這一個任務：只跳一個通知
export function afterSaveRescheduleToast(taskId: string, outcome: RescheduleOutcome, reauth: () => ReauthToast) {
  if (outcome.kind === 'reauth') {
    return {
      title: '已儲存，但需要重新連接 Google Calendar 才能重新排程',
      color: 'warning' as const,
      icon: 'i-lucide-alert-triangle',
      actions: reauth().actions,
    }
  }
  const failure = outcome.failed.find((f) => f.task_id === taskId)
  if (outcome.kind === 'error' || failure) {
    return {
      title: '已儲存，但重新排程失敗',
      description: outcome.kind === 'error' ? outcome.message : failure?.reason,
      color: 'warning' as const,
      icon: 'i-lucide-alert-triangle',
    }
  }
  return { title: '儲存成功', color: 'success' as const, icon: 'i-lucide-check' }
}

// 批次重新排程結束後的通知。reauth 是既有的重新連接提示；titleOf 用任務 id 找名稱
export function batchRescheduleToast(
  outcome: RescheduleOutcome,
  sentCount: number,
  titleOf: (taskId: string) => string,
  reauth: () => object,
) {
  if (outcome.kind === 'reauth') return reauth()
  if (outcome.kind === 'error') {
    return {
      title: '重新排程沒有全部完成',
      description: [outcome.message, '已處理的任務已放回排程清單，請再按一次處理剩下的任務'].filter(Boolean).join('\n'),
      color: 'error' as const,
      icon: 'i-lucide-x',
      ui: MULTILINE_TOAST_UI,
    }
  }
  if (outcome.failed.length > 0) {
    return {
      title: '部分任務重新排程失敗',
      description: outcome.failed.map((f) => `「${titleOf(f.task_id)}」：${f.reason}`).join('\n'),
      color: 'error' as const,
      icon: 'i-lucide-x',
      ui: MULTILINE_TOAST_UI,
    }
  }
  return { title: `已把 ${sentCount} 個任務放回排程清單`, color: 'success' as const, icon: 'i-lucide-check' }
}
