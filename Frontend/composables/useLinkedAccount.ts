// composables/useLinkedAccount.ts
import { ref, computed } from 'vue';
// import { useRuntimeConfig } from '#imports';
// import { useUser, useAuth } from '@clerk/vue';
import { until } from '@vueuse/core';

export const useLinkedAccount = () => {
  const config = useRuntimeConfig();
  const BASE_URL = config.public.apiBaseUrl;

  const { isLoaded, getToken } = useAuth();
  const { user } = useUser();
  const toast = useToast();

  const currentUserName = computed(() => user.value?.username ?? '');

  const keys = ref<
    Array<{
      platform: string;
      label: string;
      value: string;
      inputValue: string;
      domain?: string;
      password?: string;
      loading: boolean;
      editing: boolean;
      showPassword: boolean;
      icon: string;
      avatar?: string;
      username?: string;
    }>
  >([
    {
      platform: 'github',
      label: 'GitHub Key',
      value: '',
      inputValue: '',
      domain: '',
      password: '',
      loading: false,
      editing: false,
      showPassword: false,
      icon: 'mdi:github',
    },
    {
      platform: 'jira',
      label: 'Jira Key',
      value: '',
      inputValue: '',
      domain: '',
      password: '',
      loading: false,
      editing: false,
      showPassword: false,
      icon: 'mdi:jira',
    },
    {
      platform: 'moodle',
      label: 'Moodle Key',
      value: '',
      inputValue: '',
      domain: '',
      password: '',
      loading: false,
      editing: false,
      showPassword: false,
      icon: 'custom:moodle',
    },
  ]);

  const fetchKeys = async () => {
    await until(isLoaded).toBe(true);
    const token = await getToken.value();
    const list = await $fetch<any[]>(`${BASE_URL}/user/linked-accounts/me`, {
      headers: { Authorization: `Bearer ${token}` },
    });

    list.forEach((ac) => {
      const item = keys.value.find((k) => k.platform === ac.platform);
      if (item) {
        item.value = ac.apiKey ?? ''; // 取得遮罩過的 apiKey
        item.domain = ac.domain ?? ''; // 取得 domain
        item.password = ac.password ?? ''; // 取得 moodle 密碼
        if (ac.avatar_url) item.avatar = ac.avatar_url;
        if (ac.username) item.username = ac.username;
        if (item.platform == 'moodle') {  // 取得遮罩過的 moodle 密碼
          item.value = ac.password;
        }
      }
    });
  };

  const openEdit = (keyItem: any) => {
    keyItem.inputValue = '';
    keyItem.domain = keyItem.domain ?? '';
    if (keyItem.platform == 'moodle') {  // 把 moodle 帳號寫進來
      keyItem.inputValue = keyItem.username;
    }
    keyItem.password = ''; // moodle 的密碼
    keyItem.editing = true;
  };

  const cancelEdit = (keyItem: any) => {
    keyItem.inputValue = '';
    keyItem.editing = false;
  };

  const saveKey = async (keyItem: any) => {
    keyItem.loading = true;
    const token = await getToken.value();
    const payload: any = {
      platform: keyItem.platform,
      status: 'connected',
      username: currentUserName.value,
    };

    if (keyItem.platform === 'github') {
      payload.apiKey = keyItem.inputValue;
    } 
    else if (keyItem.platform === 'jira' && keyItem.domain) { // 若是 Jira 類型，加上 domain
      payload.apiKey = keyItem.inputValue;
      payload.domain = keyItem.domain;
    } 
    else if (keyItem.platform === 'moodle') { // 若是 Moodle 類型，改成帳號和密碼
      payload.username = keyItem.inputValue;
      payload.password = keyItem.password;
    }

    try {
      let avatarUrl: string | undefined;
      const isNew = !keyItem.value;

      if (isNew) {
        const res = await $fetch<{ linkedAccounts: any }>(
          `${BASE_URL}/user/linked-accounts/create`,
          {
            method: 'POST',
            headers: { Authorization: `Bearer ${token}` },
            body: payload,
          },
        );
        avatarUrl = res?.linkedAccounts?.[keyItem.platform]?.avatar_url;
      } else {
        await $fetch(`${BASE_URL}/user/linked-accounts/`, {
          method: 'PUT',
          headers: { Authorization: `Bearer ${token}` },
          body: {
            platform: keyItem.platform,
            data: {
              payload,
            },
          },
        });
      }

      keyItem.value = keyItem.inputValue;
      keyItem.inputValue = '';
      keyItem.editing = false;

      toast.add({
        title: `${keyItem.label} 儲存成功`,
        color: 'success',
        icon: 'i-lucide-check',
        ...(avatarUrl ? { avatar: { src: avatarUrl } } : {}),
      });
    } catch (err) {
      console.error(err);
      toast.add({
        title: `${keyItem.label} 儲存失敗`,
        color: 'error',
        icon: 'i-lucide-x',
      });
    } finally {
      keyItem.loading = false;
    }
  };

  const deleteKey = async (keyItem: any) => {
    try {
      const token = await getToken.value();
      await $fetch(`${BASE_URL}/user/linked-accounts/${keyItem.platform}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
        body: {
          platform: keyItem.platform,
          status: 'connected',
          username: currentUserName.value,
          apiKey: keyItem.inputValue,
          ...(keyItem.platform === 'github' && { apiKey: keyItem.inputValue }),
          ...(keyItem.platform === 'jira' && { apiKey: keyItem.inputValue, domain: keyItem.domain }),
          ...(keyItem.platform === 'moodle' && { apiKey: keyItem.inputValue, password: keyItem.password }),
        },
      });
      keyItem.value = '';
      keyItem.inputValue = '';
      keyItem.domain = '';
      keyItem.password = '';
      keyItem.editing = false;

      toast.add({
        title: `${keyItem.label} 已刪除`,
        color: 'success',
        icon: 'i-lucide-trash-2',
      });
    } catch (err) {
      console.error(err);
      toast.add({
        title: `${keyItem.label} 刪除失敗`,
        color: 'error',
        icon: 'i-lucide-x',
      });
    }
  };

  return {
    keys,
    fetchKeys,
    openEdit,
    cancelEdit,
    saveKey,
    deleteKey,
  };
};
