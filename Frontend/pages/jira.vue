<script setup lang="ts">
import { useUser } from '@clerk/vue'
import { useJira } from '~/composables/useJira'
import TheHeader from '~/components/TheHeader/index.vue'
import JiraIssuesList from '~/components/TheMain/JiraIssuesList.vue'
import LoginRequiredCard from '~/components/TheMain/LoginRequiredCard.vue'

const { isSignedIn } = useUser()
const { issues, fetchJiraIssues, domain, isStale, syncedAt, authError, notLinked, loading } = useJira()

watch(isSignedIn, (signedIn) => {
  if (signedIn) fetchJiraIssues()
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

      <JiraIssuesList
        v-if="isSignedIn"
        :issues="issues"
        :loading="loading"
        :domain="domain"
        :is-stale="isStale"
        :synced-at="syncedAt"
        :auth-error="authError"
        :not-linked="notLinked"
      />
      <LoginRequiredCard
        v-else-if="isSignedIn === false"
        title="Jira 指派任務"
        icon="mdi:jira"
        icon-class="text-blue-500"
        message="登入後即可查看 Jira 指派任務"
      />
    </div>
  </div>
</template>
