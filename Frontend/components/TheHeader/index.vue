<script setup lang="ts">
import ColorModeButton from './components/ColorModeButton.vue';
import AccountSettings from './components/AccountSettings.vue';
import { useUser } from '@clerk/vue';
import { useTaskForm } from '~/composables/useTaskForm';
import { useUserSync } from '~/composables/useUserSync';

const { user } = useUser();
const { ensureUserRecord } = useUserSync();
// 跟 TaskForm.vue 共用同一份狀態（見 useTaskForm.ts 的 createSharedComposable）
// 這裡按下「+」，TaskForm 裡的 Modal 才會真的打開
const { showEditModal } = useTaskForm();

// 使用者登入後，確認後端資料庫有這個使用者，沒有就建立（建立失敗會提示使用者）
watch(user, (newUser) => {
  if (newUser) ensureUserRecord(newUser);
});
</script>

<template>
  <header
    class="w-full flex justify-end items-center px-6 py-3 border-b shadow-sm bg-white dark:bg-gray-900 gap-4"
  >
    <p>
      歡迎！
      {{
        user?.fullName ? (user.lastName ?? '') + (user.firstName ?? '') : '訪客，請先登入'
      }}
    </p>
    <!-- 切換 Light/Dark 模式 -->
    <ColorModeButton />

    <!-- 手動新增任務 -->
    <SignedIn>
      <UButton
        icon="mdi-file-edit"
        aria-label="新增任務"
        color="neutral"
        size="md"
        @click="() => { showEditModal = true }"
      />
    </SignedIn>

    <!-- 登入按鈕 -->
    <SignedOut>
      <SignInButton
        mode="modal"
        after-sign-in-url="/"
        :appearance="{
          elements: {
            button: 'bg-green-500 hover:bg-green-600 text-white rounded px-3 py-2',
          },
        }"
      >
        <UButton color="secondary" variant="soft" icon="i-lucide-user">登入</UButton>
      </SignInButton>
    </SignedOut>
    <SignedIn>
      <AccountSettings />
    </SignedIn>
  </header>
</template>
