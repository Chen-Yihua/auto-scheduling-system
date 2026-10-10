<script setup lang="ts">
import ColorModeButton from './ColorModeButton.vue';
import AccountSettings from './AccountSettings.vue';
import { useUser } from '@clerk/vue';
import { useTaskForm } from '~/composables/useTaskForm';
import { useUserSync } from '~/composables/useUserSync';

const { user, isSignedIn } = useUser();
const { ensureUserRecord } = useUserSync();
// 和 TaskForm 共用狀態，按「+」才能打開 TaskForm 裡的 Modal
const { showEditModal } = useTaskForm();

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
    <ColorModeButton />

    <!-- 訪客也顯示但停用，讓版面一致 -->
    <UButton
      icon="mdi-file-edit"
      aria-label="新增任務"
      :title="isSignedIn ? undefined : '登入後才能新增任務'"
      color="neutral"
      size="md"
      :disabled="!isSignedIn"
      @click="() => { showEditModal = true }"
    />

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
