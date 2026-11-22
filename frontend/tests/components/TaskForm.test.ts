// 任務管理頁的任務列表：6 欄、標籤、按鈕與同步提示；composable 的呼叫方式見 TaskForm.actions.test.ts
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { shallowMount, flushPromises, enableAutoUnmount } from '@vue/test-utils';
import { ref, computed, watch, defineComponent, h } from 'vue';
import type { Component } from 'vue';
import type { SchedulableTask } from '~/types/schedulableTask';

import TaskForm from '~/components/tasks/TaskForm.vue';
import { useTaskForm } from '~/composables/useTaskForm';
import { useSchedulableTasks } from '~/composables/useSchedulableTasks';

enableAutoUnmount(afterEach);

// ---------- Nuxt/全域依賴 Stub ----------
const tokenSpy = vi.fn().mockResolvedValue('dummy-token');
const toastSpy = { add: vi.fn() };
let fetchSpy = vi.fn();

// usePlatformItems 沒有 import 這些，靠 Nuxt 自動匯入
vi.stubGlobal('ref', ref)
vi.stubGlobal('computed', computed)
vi.stubGlobal('watch', watch)
vi.stubGlobal('useAuth',         () => ({ getToken: { value: tokenSpy } }))
vi.stubGlobal('useUser',         () => ({ user: ref({ id: 'u1' }) }))
vi.stubGlobal('useToast',        () => toastSpy)
vi.stubGlobal('useRuntimeConfig',() => ({ public: { apiBaseUrl: 'http://localhost:8000' } }))
vi.stubGlobal('$fetch',          (...args: unknown[]) => fetchSpy(...args))
vi.stubGlobal('useState',        (_key: string, init: () => unknown) => ref(init()))

// 帳號資料（GET /users/me/linked-accounts/）：每個測試自己決定回應
type LinkedKey = { platform: string; value: string; needsReauth?: boolean }
const linkedKeys = ref<LinkedKey[]>([])
let fetchKeysImpl: () => Promise<void> = async () => {}
vi.stubGlobal('useLinkedAccount', () => ({ keys: linkedKeys, fetchKeys: () => fetchKeysImpl() }))
const allLinked = (): LinkedKey[] => [
  { platform: 'github', value: 'KEY****' },
  { platform: 'jira', value: 'KEY****' },
  { platform: 'moodle', value: 'PW****' },
]
const noneLinked = (): LinkedKey[] => [
  { platform: 'github', value: '' },
  { platform: 'jira', value: '' },
  { platform: 'moodle', value: '' },
]

// useSchedulableTasks 明確 import useAuth，stubGlobal 攔不到，要 mock 整個模組
vi.mock('@clerk/vue', () => ({
  useAuth: () => ({ getToken: { value: tokenSpy } }),
}));

// useSchedulableTasks 用 useGoogleCalendar 重新載入日曆，這個檔案不測日曆
vi.mock('@/composables/useGoogleCalendar', () => ({
  useGoogleCalendar: () => ({ triggerCalendarReload: vi.fn() }),
}));

// ---------- UI 元件 Stub ----------
// 要轉傳原生事件，否則 @click.stop 會對 undefined 呼叫 stopPropagation
const StubButton = defineComponent({
  name: 'UButton',
  emits: ['click'],
  setup(_, { emit, slots }) {
    return () =>
      h('button', { onClick: (e: Event) => emit('click', e) }, slots.default ? slots.default() : '')
  },
})

const StubCard = defineComponent({
  name: 'UCard',
  setup(_, { slots }) {
    return () =>
      h('div', { class: 'u-card-stub' }, [
        slots.header && slots.header(),
        slots.default && slots.default(),
        slots.footer && slots.footer(),
      ])
  },
})

// 只留 TaskForm 用到的 props 與事件：目前頁碼、總筆數、每頁筆數
const StubPagination = defineComponent({
  name: 'UPagination',
  props: { page: { type: Number, default: 1 }, total: { type: Number, default: 0 }, itemsPerPage: { type: Number, default: 10 } },
  emits: ['update:page'],
  setup: () => () => h('div', { 'data-testid': 'pagination' }),
})

// 標籤的文字要看得到
const StubBadge = defineComponent({
  name: 'UBadge',
  setup: (_, { slots, attrs }) => () => h('span', attrs, slots.default?.()),
})

const uiStubs: Record<string, boolean | Component> = {
  UButton: StubButton,
  UCard: StubCard,
  UBadge: StubBadge,
  UPagination: StubPagination,
  USkeleton: true,
  UIcon: true,
}

// ---------- 假任務工具 ----------
// 固定「現在」：2026-11-21 10:00（Asia/Taipei，vitest.config.ts）；只假造 Date，不影響 promise 與 timer
const NOW = new Date('2026-11-21T10:00:00+08:00')

const fakeSchedulableTasks = (n = 1): SchedulableTask[] =>
  Array.from({ length: n }, (_, i) => ({
    id: `manual:t${i}`,
    source: 'manual',
    title: `任務${i}`,
    description: '測試內容',
    status: 'To Do',
    priority: 'Low',
    duration: null,
    due_date: '2026-11-25T12:00:00+08:00',
    sort_order: null,
    calendar_event_id: null,
    scheduled_start: null,
    scheduled_end: null,
    url: null,
  }))

const task = (overrides: Partial<SchedulableTask>): SchedulableTask => ({ ...fakeSchedulableTasks(1)[0]!, ...overrides })

// 依 URL 回傳對應的假資料，不依賴呼叫順序
function mockFetchByUrl(responses: Record<string, unknown>) {
  fetchSpy.mockImplementation(async (url: string) => {
    const match = Object.keys(responses).find((key) => url.includes(key))
    return match ? responses[match] : []
  })
}

async function render(tasks: SchedulableTask[]) {
  mockFetchByUrl({ '/schedule/tasks': tasks })
  const wrapper = shallowMount(TaskForm, { global: { stubs: uiStubs } })
  await flushPromises()
  return wrapper
}

type Wrapper = Awaited<ReturnType<typeof render>>
const rows = (wrapper: Wrapper) => wrapper.findAll('.task-row')
const cell = (row: ReturnType<Wrapper['find']>, name: string) => row.find(`[data-testid="${name}"]`).text()
const rowOf = (wrapper: Wrapper, title: string) => rows(wrapper).find((r) => r.text().includes(title))!

describe('TaskForm.vue（任務管理頁的任務列表）', () => {
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ['Date'] })
    vi.setSystemTime(NOW)
    fetchSpy = vi.fn()
    toastSpy.add.mockClear()
    tokenSpy.mockClear()
    linkedKeys.value = allLinked()
    fetchKeysImpl = async () => {}
    // jsdom 沒有 scrollIntoView；換頁會呼叫它
    Element.prototype.scrollIntoView = vi.fn()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  // ---------- 6 欄 ----------

  it('issue-178 AC21：沒有任務時顯示說明，抓取完成後不該一直卡在 Skeleton', async () => {
    const wrapper = await render([])

    expect(wrapper.findAll('u-skeleton-stub').length).toBe(0)
    expect(wrapper.text()).toContain('目前沒有任務，點擊右上角的「新增任務」新增一個吧')
  })

  it('issue-178 AC9：一筆手動任務，那一列有名稱、截止日、優先級、完成狀態、排程狀態、排程時間；不顯示描述', async () => {
    const wrapper = await render([task({ priority: 'High', description: '這段描述不該出現在列表上' })])

    const row = rows(wrapper)[0]!
    expect(row.text()).toContain('任務0')
    expect(cell(row, 'task-due')).toBe('11/25 12:00')
    expect(cell(row, 'task-priority')).toBe('高')
    expect(cell(row, 'task-status')).toBe('未開始')
    expect(cell(row, 'task-schedule-status')).toBe('未排程')
    expect(cell(row, 'task-schedule-time')).toBe('—')
    expect(wrapper.text()).not.toContain('這段描述不該出現在列表上')
  })

  it('issue-178 AC10：沒有優先級的任務與主任務，優先級欄顯示「—」；沒有截止日的任務截止日欄顯示「無期限」', async () => {
    const wrapper = await render([
      task({ id: 'manual:p1', title: '主任務', priority: null, is_parent: true }),
      task({ id: 'manual:t1', title: '沒設定的任務', priority: null, due_date: null }),
    ])

    expect(cell(rowOf(wrapper, '主任務'), 'task-priority')).toBe('—')
    expect(cell(rowOf(wrapper, '沒設定的任務'), 'task-priority')).toBe('—')
    expect(cell(rowOf(wrapper, '沒設定的任務'), 'task-due')).toBe('無期限')
  })

  it('issue-178 AC11：status 為 To Do、In Progress、Done 依序顯示「未開始」「進行中」「已完成」', async () => {
    const wrapper = await render([
      task({ id: 'manual:a', title: 'A', status: 'To Do' }),
      task({ id: 'manual:b', title: 'B', status: 'In Progress' }),
      task({ id: 'manual:c', title: 'C', status: 'Done' }),
    ])

    expect(rows(wrapper).map((r) => cell(r, 'task-status'))).toEqual(['未開始', '進行中', '已完成'])
  })

  it('issue-178 AC12：有 calendar_event_id 顯示「已排程」，沒有顯示「未排程」', async () => {
    const wrapper = await render([
      task({ id: 'manual:a', title: 'A', calendar_event_id: 'ev-1' }),
      task({ id: 'manual:b', title: 'B', calendar_event_id: null }),
    ])

    expect(rows(wrapper).map((r) => cell(r, 'task-schedule-status'))).toEqual(['已排程', '未排程'])
  })

  it('issue-178 AC13：有時段顯示開始與結束時間；已排程但沒有時段（舊資料）與未排程都顯示「—」', async () => {
    const wrapper = await render([
      task({ id: 'manual:a', title: 'A', calendar_event_id: 'ev-1', scheduled_start: '2026-11-23T14:00:00+08:00', scheduled_end: '2026-11-23T15:30:00+08:00' }),
      task({ id: 'manual:b', title: 'B', calendar_event_id: 'ev-2' }),
      task({ id: 'manual:c', title: 'C' }),
    ])

    const times = rows(wrapper).map((r) => cell(r, 'task-schedule-time'))
    expect(times[0]).toContain('14:00')
    expect(times[0]).toContain('15:30')
    expect(times.slice(1)).toEqual(['—', '—'])
  })

  it('issue-178 AC14：主任務的排程狀態與排程時間都顯示「—」', async () => {
    const wrapper = await render([
      task({ id: 'manual:p1', title: '主任務', is_parent: true, calendar_event_id: 'ev-1', scheduled_start: '2026-11-23T14:00:00+08:00', scheduled_end: '2026-11-23T15:00:00+08:00' }),
    ])

    const row = rows(wrapper)[0]!
    expect(cell(row, 'task-schedule-status')).toBe('—')
    expect(cell(row, 'task-schedule-time')).toBe('—')
  })

  // ---------- 已逾期 ----------

  it('issue-178 AC15：沒完成、截止日是昨天的任務與主任務，名稱旁都有「已逾期」', async () => {
    const wrapper = await render([
      task({ id: 'manual:a', title: 'A', due_date: '2026-11-20T12:00:00+08:00' }),
      task({ id: 'manual:p1', title: '主任務', is_parent: true, due_date: '2026-11-20T12:00:00+08:00' }),
    ])

    expect(rows(wrapper).map((r) => r.find('[data-testid="task-overdue"]').exists())).toEqual([true, true])
    expect(rowOf(wrapper, 'A').find('[data-testid="task-overdue"]').text()).toBe('已逾期')
  })

  it('issue-178 AC16：沒完成、時段結束時間是一小時前、截止日是明天的任務，名稱旁有「已逾期」', async () => {
    const wrapper = await render([
      task({ due_date: '2026-11-22T12:00:00+08:00', calendar_event_id: 'ev-1', scheduled_start: '2026-11-21T08:00:00+08:00', scheduled_end: '2026-11-21T09:00:00+08:00' }),
    ])

    expect(rows(wrapper)[0]!.find('[data-testid="task-overdue"]').exists()).toBe(true)
  })

  it('issue-178 AC17：已完成的任務即使截止日已過，不顯示「已逾期」', async () => {
    const wrapper = await render([task({ status: 'Done', due_date: '2026-11-20T12:00:00+08:00' })])

    expect(rows(wrapper)[0]!.find('[data-testid="task-overdue"]').exists()).toBe(false)
  })

  // ---------- 來源標籤 ----------

  it('issue-178 AC18：外部任務依序有「GitHub」「Jira」「Moodle」標籤，手動任務沒有來源標籤', async () => {
    const wrapper = await render([
      task({ id: 'manual:a', title: '手動' }),
      task({ id: 'github:1', title: 'GH', source: 'github' }),
      task({ id: 'jira:1', title: 'JR', source: 'jira' }),
      task({ id: 'moodle:1', title: 'MD', source: 'moodle' }),
    ])

    const sources = rows(wrapper).map((r) => r.find('[data-testid="task-source"]'))
    expect(sources.map((s) => (s.exists() ? s.text() : null))).toEqual([null, 'GitHub', 'Jira', 'Moodle'])
  })

  // ---------- 操作 ----------

  it('issue-178 AC19：外部平台項目沒有編輯按鈕，點擊那一列會開啟原始連結', async () => {
    const githubTask = task({ id: 'github:42', source: 'github', title: 'GitHub Issue', priority: null, due_date: null, url: 'https://github.com/x/y/issues/42' })
    const openSpy = vi.fn()
    vi.stubGlobal('open', openSpy)

    const wrapper = await render([githubTask])

    expect(wrapper.text()).toContain('GitHub Issue')
    expect(wrapper.text()).not.toContain('編輯')
    await rows(wrapper)[0]!.trigger('click')
    expect(openSpy).toHaveBeenCalledWith('https://github.com/x/y/issues/42', '_blank')
  })

  it('issue-178 AC19：按下「標記完成」會呼叫 PATCH /schedule/tasks/done', async () => {
    const wrapper = await render(fakeSchedulableTasks(1))

    const doneButton = wrapper.findAll('button').find((b) => b.text().includes('標記完成'))
    await doneButton!.trigger('click')
    await flushPromises()

    expect(fetchSpy).toHaveBeenCalledWith(
      'http://localhost:8000/schedule/tasks/done',
      expect.objectContaining({ method: 'PATCH', body: { task_id: 'manual:t0', done: true } }),
    )
  })

  it('issue-178 AC19：手動任務按「編輯」會去掉 "manual:" 前綴，用 all_tasks 裡完整的任務資料打開編輯視窗', async () => {
    const wrapper = await render(fakeSchedulableTasks(1))
    const { all_tasks, showEditModal, state, isEditMode, onCancel } = useTaskForm()
    // 編輯視窗在標題列，all_tasks 由它讀取；這裡直接放入完整資料
    all_tasks.value = [{ id: 't0', user_id: 'u1', title: '任務0', description: '測試內容', priority: 'Low', status: 'To Do', due_date: null }]

    const editButton = wrapper.findAll('button').find((b) => b.text().includes('編輯'))
    await editButton!.trigger('click')
    await flushPromises()

    expect(showEditModal.value).toBe(true)
    expect(isEditMode.value).toBe(true)
    expect(state.title).toBe('任務0')
    onCancel()
  })

  // ---------- 階段任務 ----------

  const stagedTasks = () => [
    task({ id: 'manual:p1', title: '期末報告', priority: null, status: 'In Progress', is_parent: true }),
    ...[1, 2, 3].map((stage) => task({
      id: `manual:s${stage}`, title: `階段任務${stage}`, status: stage === 1 ? 'Done' : 'To Do',
      parent_id: 'manual:p1', parent_title: '期末報告', stage, stage_count: 3,
      calendar_event_id: stage === 2 ? 'ev-2' : null,
      scheduled_start: stage === 2 ? '2026-11-23T14:00:00+08:00' : null,
      scheduled_end: stage === 2 ? '2026-11-23T15:00:00+08:00' : null,
    })),
  ]

  it('issue-178 AC20：主任務佔一列並顯示「進度 k/N」，子任務預設收合', async () => {
    const wrapper = await render(stagedTasks())

    expect(wrapper.text()).toContain('期末報告')
    expect(wrapper.text()).toContain('進度 1/3')
    expect(wrapper.text()).not.toContain('階段任務1')
  })

  it('issue-178 AC20、AC24：展開後 3 個階段出現在主任務下面，標上「階段 k/N」，各有 6 個欄位', async () => {
    const wrapper = await render(stagedTasks())

    const expandButton = wrapper.findAll('button').find((b) => b.text().includes('展開階段'))
    await expandButton!.trigger('click')

    expect(rows(wrapper).map((r) => r.find('.flex-1').text())).toEqual(['期末報告', '階段任務1', '階段任務2', '階段任務3'])
    expect(wrapper.text()).toContain('階段 2/3')
    const stage2 = rowOf(wrapper, '階段任務2')
    expect(cell(stage2, 'task-due')).toBe('11/25 12:00')
    expect(cell(stage2, 'task-priority')).toBe('低')
    expect(cell(stage2, 'task-status')).toBe('未開始')
    expect(cell(stage2, 'task-schedule-status')).toBe('已排程')
    expect(cell(stage2, 'task-schedule-time')).toContain('14:00')
    expect(wrapper.findAll('button').some((b) => b.text().includes('收合階段'))).toBe(true)
  })

  it('issue-178 AC19：主任務的完成按鈕不能按，按了也不會送出請求', async () => {
    const wrapper = await render(stagedTasks())
    fetchSpy.mockClear()

    const doneButton = rowOf(wrapper, '期末報告').findAll('button').find((b) => b.text().includes('完成'))
    expect(doneButton!.attributes('disabled')).toBeDefined()
    await doneButton!.trigger('click')
    await flushPromises()

    expect(fetchSpy).not.toHaveBeenCalledWith('http://localhost:8000/schedule/tasks/done', expect.anything())
  })

  it('issue-178 AC22：已登入時卡片右上角最右邊有「新增任務」按鈕（在同步按鈕右邊），按下後 showEditModal 變 true', async () => {
    const wrapper = await render(fakeSchedulableTasks(1))
    const { showEditModal } = useTaskForm()
    showEditModal.value = false

    const buttons = wrapper.findAll('[data-testid="tasks-sync-now"], [data-testid="tasks-add"]').map((b) => b.attributes('data-testid'))
    expect(buttons).toEqual(['tasks-sync-now', 'tasks-add'])
    await wrapper.get('[data-testid="tasks-add"]').trigger('click')

    expect(wrapper.get('[data-testid="tasks-add"]').text()).toBe('新增任務')
    expect(showEditModal.value).toBe(true)
    showEditModal.value = false
  })

  it('issue-178 AC23：三個平台都沒有金鑰時，仍有「新增任務」按鈕，沒有同步按鈕', async () => {
    linkedKeys.value = noneLinked()

    const wrapper = await render(fakeSchedulableTasks(1))

    expect(wrapper.find('[data-testid="tasks-add"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="tasks-sync-now"]').exists()).toBe(false)
  })

  // ---------- 同步按鈕與未連結提示 ----------

  const syncButton = (wrapper: Wrapper) => wrapper.find('[data-testid="tasks-sync-now"]')
  const notLinkedHint = (wrapper: Wrapper) => wrapper.find('[data-testid="tasks-not-linked"]')

  it('issue-178 AC27：帳號資料還在讀取時，沒有同步按鈕，也沒有未連結提示', async () => {
    fetchKeysImpl = () => new Promise(() => {})

    const wrapper = await render(fakeSchedulableTasks(1))

    expect(syncButton(wrapper).exists()).toBe(false)
    expect(notLinkedHint(wrapper).exists()).toBe(false)
  })

  it('issue-178 AC28：帳號資料讀取失敗時，有同步按鈕，沒有未連結提示', async () => {
    fetchKeysImpl = async () => { throw new Error('讀取失敗') }

    const wrapper = await render(fakeSchedulableTasks(1))

    expect(syncButton(wrapper).exists()).toBe(true)
    expect(notLinkedHint(wrapper).exists()).toBe(false)
  })

  it('issue-178 AC29：三個平台都沒有金鑰時，沒有同步按鈕；最上方有未連結提示，手動任務列在它下面', async () => {
    linkedKeys.value = noneLinked()

    const wrapper = await render(fakeSchedulableTasks(1))

    expect(syncButton(wrapper).exists()).toBe(false)
    expect(notLinkedHint(wrapper).text()).toBe('尚未連結外部平台，請前往 帳號設定 → 金鑰 新增')
    const html = wrapper.html()
    expect(html.indexOf('tasks-not-linked')).toBeLessThan(html.indexOf('任務0'))
  })

  it('issue-178 AC30：只有 GitHub 有金鑰時，有同步按鈕，沒有未連結提示', async () => {
    linkedKeys.value = [{ platform: 'github', value: 'KEY****' }, { platform: 'jira', value: '' }, { platform: 'moodle', value: '' }]

    const wrapper = await render(fakeSchedulableTasks(1))

    expect(syncButton(wrapper).exists()).toBe(true)
    expect(notLinkedHint(wrapper).exists()).toBe(false)
  })

  it('issue-178 AC30：只有 Moodle 是「要重新連結」（沒有可用的值）時，有同步按鈕，沒有未連結提示', async () => {
    linkedKeys.value = [{ platform: 'github', value: '' }, { platform: 'jira', value: '' }, { platform: 'moodle', value: '', needsReauth: true }]

    const wrapper = await render(fakeSchedulableTasks(1))

    expect(syncButton(wrapper).exists()).toBe(true)
    expect(notLinkedHint(wrapper).exists()).toBe(false)
  })

  // ---------- 分頁（fit-viewport-layout） ----------

  const manyTasks = (n: number) => fakeSchedulableTasks(n)
  const pagination = (wrapper: Wrapper) => wrapper.findComponent({ name: 'UPagination' })
  const titles = (wrapper: Wrapper) => rows(wrapper).map((r) => r.find('.flex-1').text())
  const goToPage = async (wrapper: Wrapper, page: number) => {
    pagination(wrapper).vm.$emit('update:page', page)
    await flushPromises()
  }
  // 換掉清單：和同步外部平台、刪除任務後重新讀取走同一條路
  const reload = async (tasks: SchedulableTask[]) => {
    mockFetchByUrl({ '/schedule/tasks': tasks })
    await useSchedulableTasks().fetchSchedulableTasks()
    await flushPromises()
  }

  it('fit-viewport-layout AC26：30 筆頂層項目一次顯示 30 列，沒有分頁元件', async () => {
    const wrapper = await render(manyTasks(30))

    expect(rows(wrapper)).toHaveLength(30)
    expect(pagination(wrapper).exists()).toBe(false)
  })

  it('fit-viewport-layout AC27：31 筆時第 1 頁 30 列、有分頁元件；切到第 2 頁只有第 31 筆', async () => {
    const wrapper = await render(manyTasks(31))

    expect(rows(wrapper)).toHaveLength(30)
    expect(titles(wrapper)).not.toContain('任務30')
    expect(pagination(wrapper).exists()).toBe(true)
    expect(pagination(wrapper).props()).toMatchObject({ page: 1, total: 31, itemsPerPage: 30 })

    await goToPage(wrapper, 2)

    expect(titles(wrapper)).toEqual(['任務30'])
  })

  it('fit-viewport-layout AC28：28 筆手動任務加 GitHub、Jira、Moodle 各 1 筆，外部平台項目也算一筆，第 2 頁只有 Moodle', async () => {
    const external = (source: 'github' | 'jira' | 'moodle') =>
      task({ id: `${source}:1`, source, title: `${source}項目`, url: 'https://example.com' })
    const wrapper = await render([...manyTasks(28), external('github'), external('jira'), external('moodle')])

    expect(rows(wrapper)).toHaveLength(30)
    expect(titles(wrapper).slice(-2)).toEqual(['github項目', 'jira項目'])

    await goToPage(wrapper, 2)

    expect(titles(wrapper)).toEqual(['moodle項目'])
  })

  it('fit-viewport-layout AC29：第 30 筆是主任務，展開後 3 個階段留在第 1 頁、不算進 30 筆；第 2 頁只有第 31 筆', async () => {
    const parent = task({ id: 'manual:p1', title: '主任務', is_parent: true })
    const stages = [1, 2, 3].map((stage) => task({
      id: `manual:s${stage}`, title: `階段任務${stage}`, parent_id: 'manual:p1', stage, stage_count: 3,
    }))
    const wrapper = await render([...manyTasks(29), parent, ...stages, task({ id: 'manual:last', title: '第31筆' })])

    await wrapper.findAll('button').find((b) => b.text().includes('展開階段'))!.trigger('click')

    expect(rows(wrapper)).toHaveLength(33)
    expect(titles(wrapper).slice(-3)).toEqual(['階段任務1', '階段任務2', '階段任務3'])
    expect(wrapper.text()).toContain('階段 3/3')

    await goToPage(wrapper, 2)

    expect(titles(wrapper)).toEqual(['第31筆'])
  })

  describe('換頁後捲到「任務列表」卡片的頂端', () => {
    const scrollSpy = vi.fn()
    beforeEach(() => {
      scrollSpy.mockClear()
      Element.prototype.scrollIntoView = scrollSpy
    })

    it('fit-viewport-layout AC30：使用者換頁時，對卡片的根元素呼叫一次 scrollIntoView，block 是 start', async () => {
      const wrapper = await render(manyTasks(31))

      await goToPage(wrapper, 2)

      expect(scrollSpy).toHaveBeenCalledTimes(1)
      expect(scrollSpy).toHaveBeenCalledWith(expect.objectContaining({ block: 'start' }))
      expect((scrollSpy.mock.contexts[0] as HTMLElement).classList.contains('u-card-stub')).toBe(true)
    })

    it('fit-viewport-layout AC30：筆數變少自動回到第 1 頁時不捲動', async () => {
      const wrapper = await render(manyTasks(31))
      await goToPage(wrapper, 2)
      scrollSpy.mockClear()

      await reload(manyTasks(30))

      expect(scrollSpy).not.toHaveBeenCalled()
    })
  })

  it('fit-viewport-layout AC31：在第 2 頁時筆數剩 30 筆，改顯示第 1 頁的 30 筆，分頁元件消失', async () => {
    const wrapper = await render(manyTasks(31))
    await goToPage(wrapper, 2)

    await reload(manyTasks(30))

    expect(rows(wrapper)).toHaveLength(30)
    expect(titles(wrapper)[0]).toBe('任務0')
    expect(pagination(wrapper).exists()).toBe(false)
  })

  it('fit-viewport-layout AC32：在第 1 頁新增一筆（插在第 31 筆的位置），仍停在第 1 頁、顯示原本的 30 筆', async () => {
    const wrapper = await render(manyTasks(61))
    const before = titles(wrapper)

    const grown = manyTasks(61)
    grown.splice(30, 0, task({ id: 'manual:new', title: '新任務' }))
    await reload(grown)

    expect(titles(wrapper)).toEqual(before)
    expect(pagination(wrapper).props()).toMatchObject({ page: 1, total: 62, itemsPerPage: 30 })
  })
})
