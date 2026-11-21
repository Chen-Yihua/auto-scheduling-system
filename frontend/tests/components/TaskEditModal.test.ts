// 新增、編輯任務的視窗：接真的 useTaskForm，只假造網路請求；元件怎麼呼叫 composable 見 TaskEditModal.actions.test.ts
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { mount, shallowMount, flushPromises, enableAutoUnmount } from '@vue/test-utils';
import { ref, defineComponent, h } from 'vue';
import type { Component } from 'vue';

import TaskEditModal from '~/components/tasks/TaskEditModal.vue';
import TodayTasks from '~/components/dashboard/TodayTasks.vue';
import { useTaskForm } from '~/composables/useTaskForm';

enableAutoUnmount(afterEach);

const tokenSpy = vi.fn().mockResolvedValue('dummy-token');
let fetchSpy = vi.fn();
const userRef = ref<{ id: string } | null>({ id: 'u1' });

vi.stubGlobal('useAuth', () => ({ getToken: { value: tokenSpy } }));
vi.stubGlobal('useUser', () => ({ user: userRef }));
vi.stubGlobal('useToast', () => ({ add: vi.fn() }));
vi.stubGlobal('useRuntimeConfig', () => ({ public: { apiBaseUrl: 'http://localhost:8000' } }));
vi.stubGlobal('$fetch', (...args: unknown[]) => fetchSpy(...args));
vi.stubGlobal('useState', (_key: string, init: () => unknown) => ref(init()));

// useSchedulableTasks 明確 import useAuth，stubGlobal 攔不到，要 mock 整個模組
vi.mock('@clerk/vue', () => ({
  useAuth: () => ({ getToken: { value: tokenSpy } }),
}));
vi.mock('@/composables/useGoogleCalendar', () => ({
  useGoogleCalendar: () => ({ triggerCalendarReload: vi.fn() }),
}));

// 反映 open prop 的 UModal，同時把 content slot 畫出來
const StubModal = defineComponent({
  name: 'UModal',
  props: { open: { type: Boolean, default: false } },
  setup(props, { slots }) {
    return () =>
      h('div', { class: 'u-modal-stub', 'data-open': props.open ? 'true' : 'false' }, [
        slots.default?.(),
        slots.content?.(),
      ]);
  },
});
const StubButton = defineComponent({
  name: 'UButton',
  emits: ['click'],
  setup(_, { emit, slots }) {
    return () => h('button', { onClick: (e: Event) => emit('click', e) }, slots.default?.());
  },
});

const uiStubs: Record<string, boolean | Component> = {
  UButton: StubButton,
  UModal: StubModal,
  UForm: defineComponent({ name: 'UForm', setup: (_, { slots }) => () => h('form', slots.default?.()) }),
  UInput: true,
  UTextarea: true,
  UFormField: true,
  USelect: true,
  UPopover: true,
  UCalendar: true,
  USkeleton: true,
  UBadge: true,
  UIcon: true,
};

const fullTask = (eventId: string | null = null) => ({
  id: 't0', user_id: 'u1', title: '任務0', description: '', priority: 'Low' as const, status: 'To Do',
  due_date: null, calendar_event_id: eventId,
});

function mockFetchByUrl(responses: Record<string, unknown>) {
  fetchSpy.mockImplementation(async (url: string) => {
    const match = Object.keys(responses).find((key) => url.includes(key));
    return match ? responses[match] : [];
  });
}

describe('TaskEditModal.vue', () => {
  beforeEach(() => {
    fetchSpy = vi.fn();
    userRef.value = { id: 'u1' };
    mockFetchByUrl({ '/manual-tasks/me': [], '/schedule/tasks': [] });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('跟任務列表的新增任務按鈕共用同一份 showEditModal：設成 true 視窗就打開', async () => {
    const wrapper = shallowMount(TaskEditModal, { global: { stubs: uiStubs } });
    await flushPromises();
    expect(wrapper.find('.u-modal-stub').attributes('data-open')).toBe('false');

    const { showEditModal } = useTaskForm();
    showEditModal.value = true;
    await flushPromises();

    expect(wrapper.find('.u-modal-stub').attributes('data-open')).toBe('true');
    showEditModal.value = false;
  });

  it('issue-178 AC19：startEditTask 帶入完整的任務資料後，視窗打開並進入編輯模式', async () => {
    const wrapper = shallowMount(TaskEditModal, { global: { stubs: uiStubs } });
    await flushPromises();
    const { startEditTask, state, isEditMode, onCancel } = useTaskForm();

    startEditTask({ ...fullTask(), title: '要編輯的任務' });
    await flushPromises();

    expect(wrapper.find('.u-modal-stub').attributes('data-open')).toBe('true');
    expect(isEditMode.value).toBe(true);
    expect(state.title).toBe('要編輯的任務');
    onCancel();
  });

  it('schedule-wizard-empty AC27：從今日卡片打開有 calendar_event_id 的任務，表單上方顯示會移除時段的說明；沒有編號、或從別處打開時不顯示', async () => {
    const wrapper = shallowMount(TaskEditModal, { global: { stubs: uiStubs } });
    await flushPromises();
    const { startEditTask } = useTaskForm();

    startEditTask(fullTask('ev-1'), { fromToday: true });
    await flushPromises();
    expect(wrapper.find('[data-testid="reschedule-note"]').text()).toContain('儲存後會從 Google 日曆移除這個任務的時段');
    expect(wrapper.find('[data-testid="reschedule-note"]').text()).toContain('任務回到排程清單');

    startEditTask(fullTask(null), { fromToday: true });
    await flushPromises();
    expect(wrapper.find('[data-testid="reschedule-note"]').exists()).toBe(false);

    startEditTask(fullTask('ev-1'));
    await flushPromises();
    expect(wrapper.find('[data-testid="reschedule-note"]').exists()).toBe(false);
  });

  it('issue-178 AC8：視窗掛載後讀取 all_tasks，今日卡片按手動任務的「修改」，視窗打開並帶入那筆任務的資料', async () => {
    // 固定「現在」，今日卡片才一定列出今天 14:00 的任務；只假造 Date，不影響 promise
    vi.useFakeTimers({ toFake: ['Date'] });
    vi.setSystemTime(new Date('2026-11-21T10:00:00+08:00'));
    const slot = { scheduled_start: '2026-11-21T14:00:00+08:00', scheduled_end: '2026-11-21T15:00:00+08:00' };
    mockFetchByUrl({
      '/manual-tasks/me': [{ ...fullTask('ev-1'), title: '今天要做的任務' }],
      '/schedule/tasks': [{
        id: 'manual:t0', source: 'manual', title: '今天要做的任務', status: 'To Do', priority: 'Low',
        calendar_event_id: 'ev-1', due_date: null, url: null, ...slot,
      }],
    });
    // 只掛載視窗與今日卡片，不掛載任務列表：視窗負責讀 all_tasks
    const Page = defineComponent({ setup: () => () => h('div', [h(TaskEditModal), h(TodayTasks)]) });
    const wrapper = mount(Page, { global: { stubs: uiStubs } });
    await flushPromises();

    await wrapper.find('[data-testid="today-edit"]').trigger('click');
    await flushPromises();

    const { state, showEditModal } = useTaskForm();
    expect(showEditModal.value).toBe(true);
    expect(state.title).toBe('今天要做的任務');
    showEditModal.value = false;
  });
});
