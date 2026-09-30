<script setup lang="ts">
import { useUser } from '@clerk/vue'
import { useGithub } from '~/composables/useGithub'
import TheHeader from '~/components/TheHeader/index.vue'
import GithubIssuesList from '~/components/TheMain/GithubIssuesList.vue'
import LoginRequiredCard from '~/components/TheMain/LoginRequiredCard.vue'

const { isSignedIn } = useUser()
const { issues, fetchGithubIssues, isStale, syncedAt, authError, notLinked, loading } = useGithub()

watch(isSignedIn, (signedIn) => {
  if (signedIn) fetchGithubIssues()
}, { immediate: true })
</script>

<template>
  <div>
    <TheHeader />
    <div class="p-4 max-w-2xl mx-auto mt-4">
      <NuxtLink to="/" class="inline-flex items-center gap-1 text-sm text-primary hover:underline mb-4">
        <UIcon name="i-lucide-arrow-left" class="w-4 h-4" />
        返回主頁
      </NuxtLink>

      <GithubIssuesList
        v-if="isSignedIn"
        :issues="issues"
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
