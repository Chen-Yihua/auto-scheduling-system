<script setup lang="ts">
import { useLinkedAccount } from '~/composables/useLinkedAccount';
import { UserButton } from '@clerk/vue';
import { onMounted, ref } from 'vue'

const { keys, fetchKeys, openEdit, cancelEdit, saveKey, deleteKey } = useLinkedAccount();
const { getToken } = useAuth();

onMounted(fetchKeys);

const copiedKey = ref<string | null>(null);

const copyKey = (platform: string, key: string) => {
  navigator.clipboard.writeText(key).then(() => {
    copiedKey.value = platform
    setTimeout(() => (copiedKey.value = null), 2000)
  }).catch((err) => {
    console.error('Failed to copy key: ', err)
  })
}

const config = useRuntimeConfig()
const FRONT_END_URL = config.public.frontEndUrl
const GOOGLE_CLIENT_ID = config.public.apiGoogleClientId
const REDIRECT_URI = `${FRONT_END_URL}/oauth/callback`
const BASE_URL = config.public.apiBaseUrl;

const isConnected = ref(false);

const goToGoogleAuth = () => {
  const params = new URLSearchParams({
    client_id: GOOGLE_CLIENT_ID,
    redirect_uri: REDIRECT_URI,
    response_type: 'code',
    scope: 'https://www.googleapis.com/auth/calendar.readonly',
    access_type: 'offline',
    prompt: 'consent',
  })

  window.location.href = `https://accounts.google.com/o/oauth2/v2/auth?${params.toString()}`;
};

onMounted(async () => {
  try {
    const token = await getToken.value();
    if (!token) throw new Error('找不到 JWT');

    await $fetch(`${BASE_URL}/oauth/calendars`, {
      method: 'GET',
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });
    isConnected.value = true;
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
  } catch (error) {
    isConnected.value = false;
  }
});
</script>


<template>
  <header>
    <UserButton>
      <UserButton.UserProfilePage label="Key" url="custom">
        <template #labelIcon>
          <Icon name="mdi:key" class="w-4 h-4" />
        </template>

        <div class="cl-header mb-4">
          <h1 class="text-xl font-semibold">Key</h1>
        </div>

        <div
          v-for="keyItem in keys"
          :key="keyItem.platform"
          class="mb-6 border border-gray-200 dark:border-gray-700 rounded-lg p-4 bg-white dark:bg-gray-800"
        >
          <!-- Title -->
          <div class="flex items-center gap-2 mb-3">
            <UIcon :name="keyItem.icon" class="w-5 h-5" />
            <span class="font-medium text-base">{{ keyItem.label }}</span>
          </div>

          <!-- Linked Info -->
          <template v-if="keyItem.value && !keyItem.editing">
            <div class="flex items-center gap-2 mb-2">
              <UAvatar v-if="keyItem.avatar" :src="keyItem.avatar" size="sm" />
              <span v-if="keyItem.username" class="text-sm text-gray-600">{{
                keyItem.username
              }}</span>
            </div>

            <div class="grid grid-cols-[1fr_auto_auto] gap-x-2 items-center">
              <div class="text-sm text-gray-400 truncate">****{{ keyItem.value.slice(-4) ?? '' }}</div>
              <UButton
                size="sm"
                :icon="copiedKey === keyItem.platform ? 'i-lucide-check' : 'i-lucide-copy'"
                color="neutral"
                @click="() => copyKey(keyItem.platform, keyItem.value ?? '')"
              />
              <UButton 
                size="sm" 
                color="primary" 
                @click="() => openEdit(keyItem)"
                > Edit 
              </UButton>
            </div>
          </template>

          <!-- Input Mode -->
          <template v-else>
            <div class="flex flex-col gap-2">
              <!-- Jira 需要 Domain -->
              <UInput
                v-if="keyItem.platform === 'jira'"
                v-model="keyItem.domain"
                size="sm"
                variant="outline"
                placeholder="請輸入 Jira Domain (e.g. your-company.atlassian.net)"
                :ui="{ base: 'w-full' }"
              />

              <!-- api key -->
              <UInput
                v-if="keyItem.platform != 'moodle'"
                v-model="keyItem.inputValue"
                :type="keyItem.showPassword ? 'text' : 'password'"
                size="sm"
                variant="outline"
                placeholder="請輸入 API Token 或 Base64"
                :ui="{ trailing: 'pe-1', base: 'w-full' }"
              >
                <template #trailing>
                  <UButton
                    variant="link"
                    size="xs"
                    :icon="keyItem.showPassword ? 'i-lucide-eye-off' : 'i-lucide-eye'"
                    @click="keyItem.showPassword = !keyItem.showPassword"
                  />
                </template>
              </UInput>

              <!-- account & password -->
              <UInput
                v-if="keyItem.platform === 'moodle'"
                v-model="keyItem.inputValue"
                size="sm"
                variant="outline"
                placeholder="請輸入 Moodle 帳號"
                :ui="{ base: 'w-full' }"
              />
              <UInput
                v-if="keyItem.platform === 'moodle'"
                v-model="keyItem.password"
                :type="keyItem.showPassword ? 'text' : 'password'"
                size="sm"
                variant="outline"
                placeholder="請輸入 Moodle 密碼"
                :ui="{ trailing: 'pe-1', base: 'w-full' }"
              >
                <template #trailing>
                    <UButton
                      variant="link"
                      size="xs"
                      :icon="keyItem.showPassword ? 'i-lucide-eye-off' : 'i-lucide-eye'"
                      @click="keyItem.showPassword = !keyItem.showPassword"
                    />
                  </template>
              </UInput>

              <div class="flex gap-2 justify-end">
                <UButton
                  v-if="keyItem.value"
                  size="sm"
                  variant="outline"
                  color="neutral"
                  @click="() => cancelEdit(keyItem)"
                >
                  Cancel
                </UButton>
                <UButton
                  v-if="keyItem.value"
                  size="sm"
                  variant="outline"
                  color="neutral"
                  @click="() => deleteKey(keyItem)"
                >
                  Delete
                </UButton>
                <UButton
                  size="sm"
                  color="primary"
                  :loading="keyItem.loading"
                  :disabled="
                    (keyItem.platform === 'github' && !keyItem.inputValue) ||
                    (keyItem.platform === 'jira' && (!keyItem.inputValue || !keyItem.domain)) ||
                    (keyItem.platform === 'moodle' && (!keyItem.inputValue || !keyItem.password))
                  "
                  @click="() => saveKey(keyItem)"
                >
                  Save
                </UButton>
              </div>
            </div>
          </template>
        </div>
          <UButton color="primary" icon="i-lucide-calendar" @click="goToGoogleAuth">
            連接 Google Calendar
          </UButton>
      </UserButton.UserProfilePage>
    </UserButton>
  </header>
</template>