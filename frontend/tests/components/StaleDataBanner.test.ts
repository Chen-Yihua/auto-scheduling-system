import { describe, it, expect, vi } from 'vitest';
import { mount } from '@vue/test-utils';
import StaleDataBanner from '~/components/platforms/StaleDataBanner.vue';

describe('StaleDataBanner.vue', () => {
  it('stale=false 時不顯示任何提示', () => {
    const wrapper = mount(StaleDataBanner, {
      props: { stale: false, syncedAt: '2026-09-03T11:00:00Z', hasItems: false },
      global: { stubs: { UAlert: true } },
    });

    expect(wrapper.find('u-alert-stub').exists()).toBe(false);
  });

  it('stale=true 時顯示提示，並帶上相對時間', () => {
    vi.useFakeTimers().setSystemTime(new Date('2026-09-03T11:15:00Z'));

    const wrapper = mount(StaleDataBanner, {
      props: { stale: true, syncedAt: '2026-09-03T11:00:00Z', hasItems: false },
      global: { stubs: { UAlert: true } },
    });

    const alert = wrapper.find('u-alert-stub');
    expect(alert.exists()).toBe(true);
    expect(alert.attributes('title')).toBe('資料可能非即時，上次同步：15 分鐘前');

    vi.useRealTimers();
  });

  it('authError=true 時顯示授權失效的訊息，而不是一般的過期提示', () => {
    vi.useFakeTimers().setSystemTime(new Date('2026-09-03T11:15:00Z'));

    const wrapper = mount(StaleDataBanner, {
      props: {
        stale: true,
        syncedAt: '2026-09-03T11:00:00Z',
        authError: true,
        platformLabel: 'GitHub',
        hasItems: true,
      },
      global: { stubs: { UAlert: true } },
    });

    const alert = wrapper.find('u-alert-stub');
    expect(alert.exists()).toBe(true);
    expect(alert.attributes('title')).toBe(
      'GitHub 授權可能已失效，目前顯示的是快取資料（上次同步：15 分鐘前），請重新連結帳號',
    );
    expect(alert.attributes('color')).toBe('error');

    vi.useRealTimers();
  });

  it('AC1：授權失效、有清單項目且有同步時間時顯示快取資料與上次同步時間', () => {
    vi.useFakeTimers().setSystemTime(new Date('2026-09-03T11:15:00Z'));

    const wrapper = mount(StaleDataBanner, {
      props: {
        stale: true,
        syncedAt: '2026-09-03T11:00:00Z',
        authError: true,
        platformLabel: 'GitHub',
        hasItems: true,
      },
      global: { stubs: { UAlert: true } },
    });

    expect(wrapper.find('u-alert-stub').attributes('title')).toBe(
      'GitHub 授權可能已失效，目前顯示的是快取資料（上次同步：15 分鐘前），請重新連結帳號',
    );

    vi.useRealTimers();
  });

  it('AC2：授權失效、無清單項目且無同步時間時省略快取資料與未知時間', () => {
    const wrapper = mount(StaleDataBanner, {
      props: {
        stale: true,
        syncedAt: null,
        authError: true,
        platformLabel: 'Jira',
        hasItems: false,
      },
      global: { stubs: { UAlert: true } },
    });

    const title = wrapper.find('u-alert-stub').attributes('title');
    expect(title).toBe('Jira 授權可能已失效，請重新連結帳號');
    expect(title).not.toContain('快取資料');
    expect(title).not.toContain('未知時間');
  });

  it('AC3：授權失效、有清單項目但無同步時間時省略未知時間', () => {
    const wrapper = mount(StaleDataBanner, {
      props: {
        stale: true,
        syncedAt: null,
        authError: true,
        platformLabel: 'Moodle',
        hasItems: true,
      },
      global: { stubs: { UAlert: true } },
    });

    const title = wrapper.find('u-alert-stub').attributes('title');
    expect(title).toBe('Moodle 授權可能已失效，目前顯示的是快取資料，請重新連結帳號');
    expect(title).not.toContain('未知時間');
  });

  it('AC4：授權失效、無清單項目但有同步時間時省略快取資料', () => {
    vi.useFakeTimers().setSystemTime(new Date('2026-09-03T11:15:00Z'));

    const wrapper = mount(StaleDataBanner, {
      props: {
        stale: true,
        syncedAt: '2026-09-03T11:00:00Z',
        authError: true,
        platformLabel: 'GitHub',
        hasItems: false,
      },
      global: { stubs: { UAlert: true } },
    });

    const title = wrapper.find('u-alert-stub').attributes('title');
    expect(title).toBe('GitHub 授權可能已失效（上次同步：15 分鐘前），請重新連結帳號');
    expect(title).not.toContain('快取資料');

    vi.useRealTimers();
  });

  it('AC5：一般過期提示有或沒有清單項目時維持既有文字', () => {
    vi.useFakeTimers().setSystemTime(new Date('2026-09-03T11:15:00Z'));

    for (const hasItems of [true, false]) {
      const wrapper = mount(StaleDataBanner, {
        props: {
          stale: true,
          syncedAt: '2026-09-03T11:00:00Z',
          authError: false,
          hasItems,
        },
        global: { stubs: { UAlert: true } },
      });

      expect(wrapper.find('u-alert-stub').attributes('title')).toBe(
        '資料可能非即時，上次同步：15 分鐘前',
      );
    }

    vi.useRealTimers();
  });
});
