// 任務管理頁的立即同步接上真的 usePlatformItems：一個平台失敗時，其他平台照常更新，只對失敗的平台跳錯誤訊息（issue #13）
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { shallowMount, flushPromises, enableAutoUnmount } from '@vue/test-utils';
import { ref, computed, watch, onMounted, h, defineComponent } from 'vue';

import TaskForm from '~/components/tasks/TaskForm.vue';

vi.stubGlobal('ref', ref);
vi.stubGlobal('computed', computed);
vi.stubGlobal('watch', watch);
vi.stubGlobal('onMounted', onMounted);
vi.stubGlobal('useRuntimeConfig', () => ({ public: { apiBaseUrl: 'http://api' } }));

vi.mock('@clerk/vue', async () => {
  const { ref } = await import('vue');
  return {
    useAuth: () => ({ getToken: { value: async () => 'jwt-token' }, userId: ref('user_a') }),
  };
});

const toastSpy = { add: vi.fn() };
vi.stubGlobal('useToast', () => toastSpy);
const linkedKeys = ref([
  { platform: 'github', value: 'KEY****' },
  { platform: 'jira', value: 'KEY****', domain: 'team.atlassian.net' },
  { platform: 'moodle', value: 'PW****' },
]);
vi.stubGlobal('useLinkedAccount', () => ({ keys: linkedKeys, fetchKeys: vi.fn().mockResolvedValue(undefined) }));

const fetchRaw = vi.fn();
vi.stubGlobal('$fetch', Object.assign(vi.fn(), { raw: (...args: unknown[]) => fetchRaw(...args) }));
const ok = (data: unknown[]) => ({ _data: data, headers: new Headers({ 'X-Synced-At': '2026-11-14T05:00:00Z' }) });

vi.mock('~/composables/useTaskForm', async () => {
  const { ref } = await import('vue');
  return { useTaskForm: () => ({ user: ref({ id: 'u1' }), all_tasks: ref([]), startEditTask: vi.fn() }) };
});

const fetchSchedulableTasksSpy = vi.fn();
vi.mock('~/composables/useSchedulableTasks', async () => {
  const { ref } = await import('vue');
  return {
    useSchedulableTasks: () => ({
      tasks: ref([]),
      loading: ref(false),
      fetchSchedulableTasks: fetchSchedulableTasksSpy,
      toggleDone: vi.fn(),
    }),
  };
});

const uiStubs = {
  UCard: defineComponent({ setup: (_p, { slots }) => () => h('div', [slots.header?.(), slots.default?.()]) }),
  UIcon: true,
  UBadge: true,
  USkeleton: true,
  UButton: defineComponent({
    name: 'UButton',
    emits: ['click'],
    setup(_props, { slots, emit, attrs }) {
      return () => h('button', { ...attrs, onClick: () => emit('click') }, slots.default?.());
    },
  }),
};

enableAutoUnmount(afterEach);

describe('tasks/TaskForm.vue 立即同步', () => {
  beforeEach(() => {
    toastSpy.add.mockClear();
    fetchRaw.mockReset();
    fetchSchedulableTasksSpy.mockReset();
    linkedKeys.value = [
      { platform: 'github', value: 'KEY****' },
      { platform: 'jira', value: 'KEY****', domain: 'team.atlassian.net' },
      { platform: 'moodle', value: 'PW****' },
    ];
  });

  it('AC23、AC24：三個平台各呼叫自己的 POST；Jira 失敗時 GitHub、Moodle 仍完成，只跳一個 Jira 的錯誤訊息；結束後重新讀取任務列表', async () => {
    const wrapper = shallowMount(TaskForm, { global: { stubs: uiStubs } });
    await flushPromises();
    fetchSchedulableTasksSpy.mockClear();

    fetchRaw.mockImplementation(async (url: string) => {
      if (url === 'http://api/jira/sync') throw { response: { status: 502 }, data: { error_code: 'UPSTREAM_ERROR', detail: '說明' } };
      return ok([{ id: url }]);
    });
    await wrapper.find('[data-testid="tasks-sync-now"]').trigger('click');
    await flushPromises();

    const posted = fetchRaw.mock.calls.map(([url, options]) => [url, options.method]);
    expect(posted).toEqual(expect.arrayContaining([
      ['http://api/github/sync', 'POST'],
      ['http://api/jira/sync', 'POST'],
      ['http://api/moodle/sync', 'POST'],
    ]));
    expect(posted).toHaveLength(3);
    expect(toastSpy.add).toHaveBeenCalledTimes(1);
    expect(toastSpy.add.mock.calls[0]![0].title).toContain('Jira');
    expect(fetchSchedulableTasksSpy).toHaveBeenCalledTimes(1);
  });

  it('AC24：三個平台都同步失敗時，一樣重新讀取任務列表', async () => {
    const wrapper = shallowMount(TaskForm, { global: { stubs: uiStubs } });
    await flushPromises();
    fetchSchedulableTasksSpy.mockClear();

    fetchRaw.mockRejectedValue({ response: { status: 502 }, data: { error_code: 'UPSTREAM_ERROR', detail: '說明' } });
    await wrapper.find('[data-testid="tasks-sync-now"]').trigger('click');
    await flushPromises();

    expect(fetchSchedulableTasksSpy).toHaveBeenCalledTimes(1);
  });
});
