<script setup lang="ts">
import ColorModeButton from './components/ColorModeButton.vue';
import AccountSettings from './components/AccountSettings.vue';
import { useUser, useAuth } from '@clerk/vue';

const config = useRuntimeConfig();

const BASE_URL = config.public.apiBaseUrl;

const { user } = useUser();
const { getToken } = useAuth();

// Watch for user changes

watch(user, async (newUser) => {
  if (!newUser) return;
  const token = await getToken.value({ template: 'jwt' });
  try {
    // Call GET /user/me
    const response = await fetch(`${BASE_URL}/users/me`, {
      method: 'GET',
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });

    if (response.status === 404) {
      // If the response is 404, use POST to create a new user
      await fetch(`${BASE_URL}/users/`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          clerk_id: newUser.id,
          email: newUser.primaryEmailAddress?.emailAddress,
          name: newUser.fullName,
        }),
      });
    }
  } catch (error) {
    console.error('Error fetching or creating user:', error);
  }
});
</script>

<template>
  <header
    class="w-full flex justify-end items-center px-6 py-3 border-b shadow-sm bg-white dark:bg-gray-900 gap-4"
  >
    <p>
      Welcome !
      {{
        user?.fullName ? (user.lastName ?? '') + (user.firstName ?? '') : 'guest, please login !!'
      }}
    </p>
    <!-- 切換 Light/Dark 模式 -->
    <ColorModeButton />

    <!-- GitHub icon + hover 展開 -->
    <UButton
      class="group relative overflow-hidden transition-all duration-300 w-[40px] hover:w-[120px]"
      icon="i-lucide-github"
    >
      <span class="ml-2 opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap"
        >GitHub</span
      >
    </UButton>

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
      <!-- <UserButton /> -->
      <AccountSettings />
    </SignedIn>
  </header>
</template>
