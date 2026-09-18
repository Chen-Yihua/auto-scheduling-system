// composables/useLinkedAccount.ts
import { ref, computed } from 'vue';
import { useRuntimeConfig } from '#imports';
import { useUser, useAuth } from '@clerk/vue';
import { until } from '@vueuse/core';
import { getFriendlyErrorTitle } from '@/utils/errorMessages';

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
      // true = value 來自後端遮罩過的字串，不可複製；false = 剛建立/更新，value 是這個 session 才知道的明文，可複製一次
      isMasked: boolean;
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
      isMasked: false,
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
      isMasked: false,
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
      isMasked: false,
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
        // 從後端拿回來的一律是遮罩值，不是完整明文，不能拿去複製
        item.isMasked = true;
      }
    });
  };

  const openEdit = (keyItem: any) => {
    keyItem.inputValue = '';
    keyItem.domain = keyItem.domain ?? '';
    keyItem._originalDomain = keyItem.domain; // 存編輯前的 domain，存檔時判斷這次有沒有真的改到
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
    const isNew = !keyItem.value;
    const payload: any = {
      platform: keyItem.platform,
      status: 'connected',
      username: currentUserName.value,
    };

    if (keyItem.platform === 'github') {
      payload.apiKey = keyItem.inputValue;
    }
    else if (keyItem.platform === 'jira') { // 若是 Jira 類型，加上 domain
      payload.domain = keyItem.domain;
      // 編輯既有帳號時，API Key 留空代表「不修改」，不送出這個欄位；
      // 新建帳號一定要有 API Key（Save 按鈕本身就會擋住空值，這裡一定有值）
      if (isNew || keyItem.inputValue) {
        payload.apiKey = keyItem.inputValue;
      }
    }
    else if (keyItem.platform === 'moodle') { // 若是 Moodle 類型，改成帳號和密碼
      payload.username = keyItem.inputValue;
      // 編輯既有帳號時，密碼留空代表「不修改密碼」，不送出這個欄位；
      // 新建帳號一定要有密碼（Save 按鈕本身就會擋住空密碼，這裡一定有值）
      if (isNew || keyItem.password) {
        payload.password = keyItem.password;
      }
    }

    // 存檔前先記錄「使用者這次實際改了什麼」，存檔後這些欄位會被覆蓋掉，要先比對
    const moodleUsernameChanged = keyItem.platform === 'moodle' && keyItem.inputValue !== keyItem.username;
    const moodlePasswordChanged = keyItem.platform === 'moodle' && !!keyItem.password;
    const jiraDomainChanged = keyItem.platform === 'jira' && keyItem.domain !== keyItem._originalDomain;
    const jiraApiKeyChanged = keyItem.platform === 'jira' && !!keyItem.inputValue;

    try {
      let avatarUrl: string | undefined;

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
      if (keyItem.platform === 'moodle') {
        keyItem.username = keyItem.inputValue; // 同步顯示用的帳號，避免編輯後畫面還顯示舊帳號
      }
      keyItem.inputValue = '';
      keyItem.editing = false;
      // 剛建立/更新，這裡的 value 是這個 session 才知道的明文，允許複製這一次
      keyItem.isMasked = false;

      let title = `${keyItem.label} 儲存成功`;
      if (keyItem.platform === 'moodle' && !isNew) {
        // Moodle 帳號、密碼是分開改的，明確告知使用者這次實際改到哪個欄位
        if (moodleUsernameChanged && moodlePasswordChanged) {
          title = 'Moodle 帳號與密碼皆已更新';
        } else if (moodleUsernameChanged) {
          title = 'Moodle 帳號已更新';
        } else if (moodlePasswordChanged) {
          title = 'Moodle 密碼已更新';
        }
      } else if (keyItem.platform === 'jira' && !isNew) {
        // Jira Domain、API Key 也是分開改的，同樣明確告知這次改到哪個欄位
        if (jiraDomainChanged && jiraApiKeyChanged) {
          title = 'Jira Domain 與 API Key 皆已更新';
        } else if (jiraDomainChanged) {
          title = 'Jira Domain 已更新';
        } else if (jiraApiKeyChanged) {
          title = 'Jira API Key 已更新';
        }
      }

      toast.add({
        title,
        color: 'success',
        icon: 'i-lucide-check',
        ...(avatarUrl ? { avatar: { src: avatarUrl } } : {}),
      });
    } catch (err) {
      console.error(err);
      toast.add({
        title: getFriendlyErrorTitle(err, `${keyItem.label} 儲存失敗`),
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
      keyItem.isMasked = false;

      toast.add({
        title: `${keyItem.label} 已刪除`,
        color: 'success',
        icon: 'i-lucide-trash-2',
      });
    } catch (err) {
      console.error(err);
      toast.add({
        title: getFriendlyErrorTitle(err, `${keyItem.label} 刪除失敗`),
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
