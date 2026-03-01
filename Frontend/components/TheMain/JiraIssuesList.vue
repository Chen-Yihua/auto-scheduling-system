<script setup lang="ts">
import type { JiraIssue } from '~/types/jira'

const props = defineProps<{
  issues: JiraIssue[]
  loading: boolean
  domain?: string // 可選，從 props 傳入 Jira 網域
}>()

const openJiraIssue = (key: string) => {
  const domain = props.domain || 'nccu-software-development.atlassian.net'
  window.open(`https://${domain}/browse/${key}`, '_blank')
}
</script>

<template>
  <div class="space-y-4">
    <h2 class="text-xl font-bold">Jira 指派任務</h2>

    <div v-if="loading">
      <USkeleton class="h-24 mb-4" v-for="i in 3" :key="i" />
    </div>

    <div v-else-if="issues.length" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
      <UCard
        v-for="issue in issues"
        :key="issue.id"
        @click="openJiraIssue(issue.key)"
        :ui="{
          root: 'cursor-pointer hover:shadow-lg transition-transform duration-300 ease-in-out transform scale-100 hover:scale-105',
        }"
      >
        <template #header>
          <div class="flex items-center justify-between">
            <div class="text-sm font-semibold">{{ issue.key }}</div>
            <UBadge color="primary" variant="subtle" size="sm">
              {{ issue.status }}
            </UBadge>
          </div>
        </template>

        <div class="flex items-center gap-2 mb-1">
          <img v-if="issue.iconUrl" :src="issue.iconUrl" alt="type" class="w-5 h-5" />
          <span class="text-sm text-gray-600">{{ issue.type }}</span>
        </div>

        <div class="font-medium mb-2">{{ issue.summary }}</div>

        <div class="flex items-center gap-2">
          <UAvatar v-if="issue.avatar" :src="issue.avatar" size="xs" />
          <span class="text-xs text-gray-500">{{ issue.assignee }}</span>
        </div>

        <template #footer>
          <div class="text-xs text-gray-400">
            更新於 {{ new Date(issue.updated).toLocaleDateString() }}
          </div>
        </template>
      </UCard>
    </div>

    <p v-else class="text-gray-500 text-sm">尚無資料</p>
  </div>
</template>