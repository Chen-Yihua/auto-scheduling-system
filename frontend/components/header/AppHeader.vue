<script setup lang="ts">
import AccountSettings from './AccountSettings.vue';
import { useUser } from '@clerk/vue';
import { useUserSync } from '~/composables/useUserSync';

const { user } = useUser();
const { ensureUserRecord } = useUserSync();
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
    class="w-full flex flex-wrap justify-end items-center gap-x-6 gap-y-2 px-6 py-2.5 bg-palette-2 border-b border-palette-1/50"
  >
    <div class="flex items-center gap-2.5 shrink-0" aria-hidden="true">
      <span class="size-8 rounded-lg bg-default flex items-center justify-center shadow-sm">
        <UIcon name="i-lucide-calendar-clock" class="size-4.5 text-steel-700" />
      </span>
      <span class="text-base font-bold tracking-wide">Auto Scheduling</span>
    </div>

    <nav class="flex flex-wrap items-center gap-1 mr-auto">
      <NuxtLink
        v-for="item in navItems"
        :key="item.to"
        :to="item.to"
        :aria-current="isCurrent(item.to) ? 'page' : undefined"
        class="px-4 py-1.5 rounded-lg text-sm text-highlighted transition-colors"
        :class="isCurrent(item.to) ? 'font-semibold bg-default shadow-sm' : 'hover:bg-default/50'"
      >
        {{ item.label }}
      </NuxtLink>
    </nav>

    <p class="text-sm text-toned">
      歡迎！
      {{
        user?.fullName ? (user.lastName ?? '') + (user.firstName ?? '') : '訪客，請先登入'
      }}
    </p>

    <SignedOut>
      <SignInButton mode="modal" after-sign-in-url="/">
        <UButton icon="i-lucide-user">登入</UButton>
      </SignInButton>
    </SignedOut>
    <SignedIn>
      <AccountSettings />
    </SignedIn>

  </header>
</template>
