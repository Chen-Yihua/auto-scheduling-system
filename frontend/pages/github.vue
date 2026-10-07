<script setup lang="ts">
import { useUser } from '@clerk/vue'
import { usePlatformItems } from '~/composables/usePlatformItems'
import AppHeader from '~/components/header/AppHeader.vue'
import GithubIssuesList from '~/components/platforms/GithubIssuesList.vue'
import LoginRequiredCard from '~/components/LoginRequiredCard.vue'

const { isSignedIn } = useUser()
const { items, fetchItems, isStale, syncedAt, authError, notLinked, loading } = usePlatformItems('github')

watch(isSignedIn, (signedIn) => {
  if (signedIn) fetchItems()
}, { immediate: true })
</script>

<template>
  <div>
    <AppHeader />
    <div class="p-4 max-w-2xl mx-auto mt-4">
      <NuxtLink to="/" class="inline-flex items-center gap-1 text-sm text-primary hover:underline mb-4">
        <UIcon name="i-lucide-arrow-left" class="w-4 h-4" />
        返回主頁
      </NuxtLink>

      <GithubIssuesList
        v-if="isSignedIn"
        :issues="items"
        :loading="loading"
        :is-stale="isStale"
        :synced-at="syncedAt"
        :auth-error="authError"
        :not-linked="notLinked"
      />
      <LoginRequiredCard
        v-else-if="isSignedIn === false"
        title="GitHub 參與項目"
        icon="mdi:github"
        message="登入後即可查看 GitHub 參與項目"
      />
    </div>
  </div>
</template>
