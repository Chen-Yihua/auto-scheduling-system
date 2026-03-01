<script setup lang="ts">
import type { GitHubIssue } from '~/types/github'
defineProps<{
  issues: GitHubIssue[]
  loading: boolean
}>()

const openIssue = (url: string) => {
  window.open(url, '_blank')
}
</script>

<template>
  <div class="space-y-4">
    <h2 class="text-xl font-bold">GitHub 參與項目</h2>

    <div v-if="loading">
      <USkeleton class="h-24 mb-4" v-for="i in 3" :key="i" />
    </div>

    <div v-else-if="issues.length" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
      <UCard
        v-for="issue in issues"
        :key="issue.id"
        @click="openIssue(issue.url)"
        :ui="{
          root: 'cursor-pointer hover:shadow-lg transition-transform duration-300 ease-in-out transform scale-100 hover:scale-105',
        }"
      >
        <template #header>
          <div class="flex items-center justify-between">
            <div class="text-sm font-semibold">#{{ issue.id }}</div>
            <UBadge :color="issue.isPR ? 'info' : 'success'" variant="subtle" size="sm">
              {{ issue.isPR ? 'PR' : 'Issue' }}
            </UBadge>
          </div>
        </template>

        <div class="space-y-2">
          <div class="font-medium truncate">
            {{ issue.title }}
          </div>

          <div class="flex items-center gap-2 text-sm text-gray-600">
            <UAvatar v-if="issue.author?.avatar" :src="issue.author.avatar" size="2xs" />
            <span v-if="issue.author?.username">@{{ issue.author.username }}</span>
            <UBadge v-if="issue.comments" color="neutral" variant="soft" size="xs">
              💬 {{ issue.comments }}
            </UBadge>
          </div>

          <div class="flex flex-wrap gap-1">
            <UBadge
              v-for="label in issue.labels"
              :key="label"
              size="xs"
              color="primary"
              variant="soft"
              class="capitalize"
            >
              {{ label }}
            </UBadge>
          </div>
        </div>

        <template #footer>
          <div class="text-xs text-gray-500">
            {{ issue.state }} · 更新於 {{ new Date(issue.updated_at ?? issue.created_at).toLocaleDateString() }}
          </div>
        </template>
      </UCard>
    </div>

    <p v-else class="text-gray-500 text-sm">尚無資料</p>
  </div>
</template>
