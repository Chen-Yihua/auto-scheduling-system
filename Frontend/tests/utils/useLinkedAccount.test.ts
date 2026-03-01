// tests/useLinkedAccount.test.ts
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ref } from 'vue'

// ======== Mock global function and variable ======== 
const tokenSpy = vi.fn().mockResolvedValue('dummy-token') // 模擬從 Clerk 拿的 token，固定回傳 'dummy-token'
const toastSpy = { add: vi.fn() } // 模擬 toast，只有 add 方法
let fetchSpy = vi.fn() // 模擬 $fetch

vi.stubGlobal('useAuth',         () => ({ isLoaded: ref(true), getToken: { value: tokenSpy } }))
vi.stubGlobal('useUser',         () => ({ user: ref({ id: 'u1' }) }))
vi.stubGlobal('useToast',        () => toastSpy)
vi.stubGlobal('useRuntimeConfig',() => ({ public: { apiBaseUrl: 'http://localhost:8000' } }))
vi.stubGlobal('$fetch', fetchSpy);

// ======== 被測 hook ========
import { useLinkedAccount } from '@/composables/useLinkedAccount';

// ======== 測試 ========
describe('useLinkedAccount', () => {
  let linkedAccount: ReturnType<typeof useLinkedAccount>;

  beforeEach(() => {
    linkedAccount = useLinkedAccount();
    vi.clearAllMocks();
  });

  // ======== 初始化檢查 ======== 
  it('初始化 platform 的 keys', () => {
    expect(linkedAccount.keys.value).toHaveLength(3);
    expect(linkedAccount.keys.value[0].platform).toBe('github');
    expect(linkedAccount.keys.value[1].platform).toBe('jira');
    expect(linkedAccount.keys.value[2].platform).toBe('moodle');
  });

  it('fetch 會呼叫 API 並更新 keys', async () => {
    const mockApiResponse = [
      { platform: 'github', apiKey: 'gh-key' },
      { platform: 'jira', apiKey: 'jira-key', domain: 'example.atlassian.net' },
      { platform: 'moodle', password: 'moodle-pwd', username: 'moodle-user' },
    ];

    (global.$fetch as any).mockResolvedValue(mockApiResponse);

    await linkedAccount.fetchKeys();

    const [github, jira, moodle] = linkedAccount.keys.value;

    expect(github.value).toBe('gh-key');
    expect(jira.value).toBe('jira-key');
    expect(jira.domain).toBe('example.atlassian.net');
    expect(moodle.value).toBe('moodle-pwd');
    expect(moodle.username).toBe('moodle-user');
  });

  

// ======== github ======== 
  it('openEdit 對 github 不會預填資料', () => {
    const github = linkedAccount.keys.value.find(k => k.platform === 'github')!;
    github.inputValue = 'something';
    linkedAccount.openEdit(github);
    expect(github.inputValue).toBe('');
    expect(github.editing).toBe(true);
  });

  it('saveKey (github PUT) 應正確送出並顯示 toast 提示', async () => {
    const keyItem = linkedAccount.keys.value.find((k) => k.platform === 'github')!;
    keyItem.inputValue = 'new-github-key';
    keyItem.value = 'old-key';

    (global.$fetch as any).mockResolvedValue({
      linkedAccounts: { github: { avatar_url: 'https://avatar.url' }, },
    });

    await linkedAccount.saveKey(keyItem);

    expect(fetchSpy).toHaveBeenCalledWith('http://localhost:8000/user/linked-accounts/',expect.objectContaining({
      method: 'PUT',
      headers: { Authorization: 'Bearer dummy-token' },
      body: {
        platform: 'github', 
        data: {
          payload: {
            status: 'connected',
            username: '',
            apiKey: 'new-github-key',
            platform: 'github',      
          },
        },
      },
  }));
    expect(toastSpy.add).toHaveBeenCalledWith(expect.objectContaining({
      title: 'GitHub Key 儲存成功',
      color: 'success',
    }));
  });

  it('saveKey (github POST) 應正確送出並顯示 toast 提示', async () => {
    const keyItem = linkedAccount.keys.value.find((k) => k.platform === 'github')!;
    keyItem.inputValue = 'new-github-key';
    keyItem.value = '';

    (global.$fetch as any).mockResolvedValue({
      linkedAccounts: { github: { avatar_url: 'https://avatar.url' }, },
    });

    await linkedAccount.saveKey(keyItem);

    expect(fetchSpy).toHaveBeenCalledWith('http://localhost:8000/user/linked-accounts/create',expect.objectContaining({
      method: 'POST',
      headers: { Authorization: 'Bearer dummy-token' },
      body: {
        platform: 'github', 
        status: 'connected',
        username: '',
        apiKey: 'new-github-key',
      },
  }));
    expect(toastSpy.add).toHaveBeenCalledWith(expect.objectContaining({
      title: 'GitHub Key 儲存成功',
      color: 'success',
    }));
  });

  it('saveKey 錯誤處理', async () => {
    const keyItem = linkedAccount.keys.value[0];
    keyItem.inputValue = 'new-gh-key';

    (global.$fetch as any).mockRejectedValue(new Error('Failed to save'));

    await linkedAccount.saveKey(keyItem);

    expect(toastSpy.add).toHaveBeenCalledWith(
      expect.objectContaining({
        title: 'GitHub Key 儲存失敗',
        color: 'error',
      }),
    );
  });

  it('deleteKey (github) 清空欄位並顯示 toast 提示', async () => {
    const github = linkedAccount.keys.value.find(k => k.platform === 'github')!;
    github.inputValue = 'to-delete';
    github.value = 'to-delete';

    fetchSpy.mockResolvedValueOnce({});

    await linkedAccount.deleteKey(github);

    expect(github.value).toBe('');
    expect(toastSpy.add).toHaveBeenCalledWith(expect.objectContaining({
      title: 'GitHub Key 已刪除',
      color: 'success',
    }));
  });

  it('deleteKey 錯誤處理', async () => {
    const keyItem = linkedAccount.keys.value[0];
    keyItem.inputValue = 'key';

    (global.$fetch as any).mockRejectedValue(new Error('Failed to delete'));

    await linkedAccount.deleteKey(keyItem);

    expect(toastSpy.add).toHaveBeenCalledWith(
      expect.objectContaining({
        title: 'GitHub Key 刪除失敗',
        color: 'error',
      }),
    );
  });

  it('cancelEdit 應清空輸入欄位', () => {
    const keyItem = linkedAccount.keys.value[0];
    keyItem.inputValue = 'something';
    keyItem.editing = true;
    linkedAccount.cancelEdit(keyItem);
    expect(keyItem.editing).toBe(false);
    expect(keyItem.inputValue).toBe('');
  });



  // ======== jira ======== 
  it('openEdit 對 jira 會預填資料', () => {
    const jira = linkedAccount.keys.value.find(k => k.platform === 'jira')!;
    jira.inputValue = 'something';
    linkedAccount.openEdit(jira);
    expect(jira.inputValue).toBe('');
    expect(jira.editing).toBe(true);
  });

  it('saveKey (jira PUT) 應正確送出並顯示 toast 提示', async () => {
    const jira = linkedAccount.keys.value.find(k => k.platform === 'jira')!;
    jira.inputValue = 'new-jira-key';
    jira.domain = 'example.atlassian.net';
    jira.value = 'old-key';

    fetchSpy.mockResolvedValue({});

    await linkedAccount.saveKey(jira);

    expect(fetchSpy).toHaveBeenCalledWith('http://localhost:8000/user/linked-accounts/', expect.objectContaining({
      method: 'PUT',
      headers: { Authorization: 'Bearer dummy-token' },
      body: {
        platform: 'jira',
        data: {
          payload: {
            status: 'connected',
            username: '',
            apiKey: 'new-jira-key',
            domain: 'example.atlassian.net',
            platform: 'jira',
          },
        },
      },
    }));
    expect(toastSpy.add).toHaveBeenCalledWith(expect.objectContaining({
      title: 'Jira Key 儲存成功',
      color: 'success',
      }));
  });

  it('saveKey (jira POST) 應正確送出並顯示 toast 提示', async () => {
    const jira = linkedAccount.keys.value.find(k => k.platform === 'jira')!;
    jira.inputValue = 'new-jira-key';
    jira.domain = 'example.atlassian.net';
    jira.value = '';

    fetchSpy.mockResolvedValue({});

    await linkedAccount.saveKey(jira);

    expect(fetchSpy).toHaveBeenCalledWith('http://localhost:8000/user/linked-accounts/create', expect.objectContaining({
      method: 'POST',
      headers: { Authorization: 'Bearer dummy-token' },
      body: {
        platform: 'jira',
        status: 'connected',
        username: '',
        apiKey: 'new-jira-key',
        domain: 'example.atlassian.net',
      },
    }));
    expect(toastSpy.add).toHaveBeenCalledWith(expect.objectContaining({
      title: 'Jira Key 儲存成功',
      color: 'success',
      }));
  });

    it('deleteKey (jira) 清空欄位並顯示 toast 提示', async () => {
    const jira = linkedAccount.keys.value.find(k => k.platform === 'jira')!;
    jira.inputValue = 'to-delete';
    jira.domain = 'jira-domain.com';

    fetchSpy.mockResolvedValueOnce({});
    await linkedAccount.deleteKey(jira);

    expect(fetchSpy).toHaveBeenCalledWith(expect.stringContaining('/jira'), expect.objectContaining({
      method: 'DELETE',
      body: expect.objectContaining({
        platform: 'jira',
        domain: 'jira-domain.com',
        apiKey: 'to-delete',
      }),
    }));
    expect(toastSpy.add).toHaveBeenCalledWith(expect.objectContaining({
      title: 'Jira Key 已刪除',
      color: 'success',
    }));
  });

  it('deleteKey 錯誤處理', async () => {
    const keyItem = linkedAccount.keys.value[1];
    keyItem.inputValue = 'key';

    (global.$fetch as any).mockRejectedValue(new Error('Failed to delete'));

    await linkedAccount.deleteKey(keyItem);

    expect(toastSpy.add).toHaveBeenCalledWith(
      expect.objectContaining({
        title: 'Jira Key 刪除失敗',
        color: 'error',
      }),
    );
  });

  it('cancelEdit 應清空輸入欄位', () => {
    const keyItem = linkedAccount.keys.value[1];
    keyItem.inputValue = 'something';
    keyItem.editing = true;
    linkedAccount.cancelEdit(keyItem);
    expect(keyItem.editing).toBe(false);
    expect(keyItem.inputValue).toBe('');
  });



  // ======== moodle ======== 
  it('openEdit 對 moodle 會預填資料', () => {
    const moodle = linkedAccount.keys.value.find(k => k.platform === 'moodle')!;
    moodle.username = 'moodle-user';
    linkedAccount.openEdit(moodle);
    expect(moodle.inputValue).toBe('moodle-user');
    expect(moodle.editing).toBe(true);
  });

  it('saveKey (moodle PUT) 應正確送出並顯示 toast 提示', async () => {
    const moodle = linkedAccount.keys.value.find(k => k.platform === 'moodle')!;
    moodle.inputValue = 'new-moodle-user';
    moodle.password = 'pwd123';
    moodle.value = 'old-key';

    fetchSpy.mockResolvedValueOnce({});

    await linkedAccount.saveKey(moodle);

    expect(fetchSpy).toHaveBeenCalledWith('http://localhost:8000/user/linked-accounts/', expect.objectContaining({
      method: 'PUT',
      headers: { Authorization: 'Bearer dummy-token' },
      body:{
        platform: 'moodle',
        data: {
          payload: {
            status: 'connected',
            username: 'new-moodle-user',
            password: 'pwd123',
            platform: 'moodle',
          },
        },
      },
    }));
    expect(toastSpy.add).toHaveBeenCalledWith(expect.objectContaining({
      title: 'Moodle Key 儲存成功',
      color: 'success',
      }));
  });

  it('saveKey (moodle POST) 應正確送出並顯示 toast 提示', async () => {
    const moodle = linkedAccount.keys.value.find(k => k.platform === 'moodle')!;
    moodle.inputValue = 'new-moodle-user';
    moodle.password = 'pwd123';
    moodle.value = '';

    fetchSpy.mockResolvedValueOnce({});

    await linkedAccount.saveKey(moodle);

    expect(fetchSpy).toHaveBeenCalledWith('http://localhost:8000/user/linked-accounts/create', expect.objectContaining({
      method: 'POST',
      headers: { Authorization: 'Bearer dummy-token' },
      body:{
        platform: 'moodle',
        status: 'connected',
        username: 'new-moodle-user',
        password: 'pwd123',
      },
    }));
    expect(toastSpy.add).toHaveBeenCalledWith(expect.objectContaining({
      title: 'Moodle Key 儲存成功',
      color: 'success',
      }));
  });

  it('deleteKey (moodle) 清空欄位並顯示 toast 提示', async () => {
    const moodle = linkedAccount.keys.value.find(k => k.platform === 'moodle')!;
    moodle.inputValue = 'user';
    moodle.password = 'pwd123';

    fetchSpy.mockResolvedValueOnce({});
    await linkedAccount.deleteKey(moodle);

    expect(fetchSpy).toHaveBeenCalledWith(expect.stringContaining('/moodle'), expect.objectContaining({
      method: 'DELETE',
      body: expect.objectContaining({
        password: 'pwd123',
      }),
    }));
    expect(toastSpy.add).toHaveBeenCalledWith(expect.objectContaining({
      title: 'Moodle Key 已刪除',
      color: 'success',
    }));
  });

  it('deleteKey 錯誤處理', async () => {
    const keyItem = linkedAccount.keys.value[2];
    keyItem.inputValue = 'key';

    (global.$fetch as any).mockRejectedValue(new Error('Failed to delete'));

    await linkedAccount.deleteKey(keyItem);

    expect(toastSpy.add).toHaveBeenCalledWith(
      expect.objectContaining({
        title: 'Moodle Key 刪除失敗',
        color: 'error',
      }),
    );
  });

  it('cancelEdit 應清空輸入欄位', () => {
    const keyItem = linkedAccount.keys.value[2];
    keyItem.inputValue = 'something';
    keyItem.editing = true;
    linkedAccount.cancelEdit(keyItem);
    expect(keyItem.editing).toBe(false);
    expect(keyItem.inputValue).toBe('');
  });
});
