import { ref, computed } from 'vue';
import { useRuntimeConfig } from '#imports';
import { useUser, useAuth } from '@clerk/vue';
import { until } from '@vueuse/core';
import { getFriendlyErrorTitle, isAlreadyLinkedError } from '@/utils/errorMessages';
import type { LinkedAccountRecord } from '@/types/linkedAccount';

// 各平台共用的形狀，欄位依平台使用
export interface LinkedAccountKey {
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
  // true：value 是後端遮罩過的值，不能複製；false：剛儲存的明文，可複製
  isMasked: boolean;
  // Jira 用：進入編輯時的 domain，儲存時判斷是否有改
  _originalDomain?: string;
}

interface LinkedAccountPayload {
  platform: string;
  status: string;
  username: string;
  apiKey?: string;
  domain?: string;
  password?: string;
}

export const useLinkedAccount = () => {
  const config = useRuntimeConfig();
  const BASE_URL = config.public.apiBaseUrl;

  const { isLoaded, getToken } = useAuth();
  const { user } = useUser();
  const toast = useToast();

  const currentUserName = computed(() => user.value?.username ?? '');

  const keys = ref<LinkedAccountKey[]>([
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
    const list = await $fetch<LinkedAccountRecord[]>(`${BASE_URL}/users/me/linked-accounts/`, {
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
          item.value = ac.password ?? '';
        }
        item.isMasked = true;
      }
    });
  };

  const openEdit = (keyItem: LinkedAccountKey) => {
    keyItem.inputValue = '';
    keyItem.domain = keyItem.domain ?? '';
    keyItem._originalDomain = keyItem.domain; // 存編輯前的 domain，存檔時判斷這次有沒有真的改到
    if (keyItem.platform == 'moodle') {  // 把 moodle 帳號寫進來
      keyItem.inputValue = keyItem.username ?? '';
    }
    keyItem.password = ''; // moodle 的密碼
    keyItem.editing = true;
  };

  const cancelEdit = (keyItem: LinkedAccountKey) => {
    keyItem.inputValue = '';
    keyItem.editing = false;
  };

  const saveKey = async (keyItem: LinkedAccountKey) => {
    keyItem.loading = true;
    const token = await getToken.value();
    const isNew = !keyItem.value;
    const payload: LinkedAccountPayload = {
      platform: keyItem.platform,
      status: 'connected',
      username: currentUserName.value,
    };

    if (keyItem.platform === 'github') {
      payload.apiKey = keyItem.inputValue;
    }
    else if (keyItem.platform === 'jira') { // 若是 Jira 類型，加上 domain
      payload.domain = keyItem.domain;
      // 編輯時留空代表不修改
      if (isNew || keyItem.inputValue) {
        payload.apiKey = keyItem.inputValue;
      }
    }
    else if (keyItem.platform === 'moodle') { // 若是 Moodle 類型，改成帳號和密碼
      payload.username = keyItem.inputValue;
      // 編輯時留空代表不修改
      if (isNew || keyItem.password) {
        payload.password = keyItem.password;
      }
    }

    // 儲存後欄位會被覆蓋，要先記下改了什麼
    const moodleUsernameChanged = keyItem.platform === 'moodle' && keyItem.inputValue !== keyItem.username;
    const moodlePasswordChanged = keyItem.platform === 'moodle' && !!keyItem.password;
    const jiraDomainChanged = keyItem.platform === 'jira' && keyItem.domain !== keyItem._originalDomain;
    const jiraApiKeyChanged = keyItem.platform === 'jira' && !!keyItem.inputValue;

    try {
      let avatarUrl: string | undefined;

      if (isNew) {
        const res = await $fetch<LinkedAccountRecord>(
          `${BASE_URL}/users/me/linked-accounts/`,
          {
            method: 'POST',
            headers: { Authorization: `Bearer ${token}` },
            body: payload,
          },
        );
        // username/avatar 是後端向平台查回來的，前端送出時不知道
        avatarUrl = res.avatar_url;
        if (res.avatar_url) keyItem.avatar = res.avatar_url;
        if (res.username) keyItem.username = res.username;
      } else {
        await $fetch(`${BASE_URL}/users/me/linked-accounts/${keyItem.platform}`, {
          method: 'PATCH',
          headers: { Authorization: `Bearer ${token}` },
          body: payload,
        });
      }

      keyItem.value = keyItem.inputValue;
      if (keyItem.platform === 'moodle') {
        keyItem.username = keyItem.inputValue; // 同步顯示用的帳號，避免編輯後畫面還顯示舊帳號
      }
      keyItem.inputValue = '';
      keyItem.editing = false;
      keyItem.isMasked = false;

      let title = `${keyItem.label} 儲存成功`;
      if (keyItem.platform === 'moodle' && !isNew) {
        if (moodleUsernameChanged && moodlePasswordChanged) {
          title = 'Moodle 帳號與密碼皆已更新';
        } else if (moodleUsernameChanged) {
          title = 'Moodle 帳號已更新';
        } else if (moodlePasswordChanged) {
          title = 'Moodle 密碼已更新';
        }
      } else if (keyItem.platform === 'jira' && !isNew) {
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
        title: isNew && isAlreadyLinkedError(err)
          ? `${keyItem.label} 已經綁定過，請重新整理頁面`
          : getFriendlyErrorTitle(err, `${keyItem.label} 儲存失敗`),
        color: 'error',
        icon: 'i-lucide-x',
      });
    } finally {
      keyItem.loading = false;
    }
  };

  const deleteKey = async (keyItem: LinkedAccountKey) => {
    try {
      const token = await getToken.value();
      // 不帶 body，避免把輸入框裡的明文送出去
      await $fetch(`${BASE_URL}/users/me/linked-accounts/${keyItem.platform}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
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
