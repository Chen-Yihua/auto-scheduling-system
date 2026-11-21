<script setup lang="ts">
import ColorModeButton from './ColorModeButton.vue';
import AccountSettings from './AccountSettings.vue';
import TaskEditModal from '~/components/tasks/TaskEditModal.vue';
import { useUser } from '@clerk/vue';
import { useTaskForm } from '~/composables/useTaskForm';
import { useUserSync } from '~/composables/useUserSync';

const { user, isSignedIn } = useUser();
const { ensureUserRecord } = useUserSync();
// 和 TaskEditModal 共用狀態，按「新增任務」才能打開它
const { showEditModal } = useTaskForm();

const navItems = [
  { label: '首頁', to: '/' },
  { label: '任務管理', to: '/tasks' },
  { label: '排程', to: '/schedule' },
  { label: '分析', to: '/productivity' },
];
const route = useRoute();
// /schedule/wizard 算在「排程」；首頁只比對 /，否則每一頁都會標示首頁
const isCurrent = (to: string) => (to === '/' ? route.path === '/' : route.path === to || route.path.startsWith(`${to}/`));

watch(user, (newUser) => {
  if (newUser) ensureUserRecord(newUser);
});
</script>

<template>
  <header
    class="w-full flex flex-wrap justify-end items-center px-6 py-3 border-b shadow-sm bg-white dark:bg-gray-900 gap-4"
  >
    <nav class="flex flex-wrap items-center gap-1 mr-auto">
      <NuxtLink
        v-for="item in navItems"
        :key="item.to"
        :to="item.to"
        :aria-current="isCurrent(item.to) ? 'page' : undefined"
        class="px-3 py-1.5 rounded-md text-sm text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800"
        :class="isCurrent(item.to) ? 'font-semibold !text-primary bg-gray-100 dark:bg-gray-800' : ''"
      >
        {{ item.label }}
      </NuxtLink>
    </nav>

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

    <TaskEditModal />
  </header>
</template>
