<script setup lang="ts">
import { computed } from 'vue'
import type { JiraIssue } from '~/types/jira'
import StaleDataBanner from './StaleDataBanner.vue'

const props = defineProps<{
  issues: JiraIssue[]
  loading: boolean
  domain?: string // 可選，從 props 傳入 Jira 網域
  isStale?: boolean
  syncedAt?: string | null
  authError?: boolean
  notLinked?: boolean
  // 不給就顯示全部——dashboard 卡片用小數字避免無限拉長，
  // /jira 這個完整清單頁面則不傳
  limit?: number
}>()

const displayedIssues = computed(() =>
  props.limit ? props.issues.slice(0, props.limit) : props.issues
)
const hasMoreIssues = computed(() => !!props.limit && props.issues.length > props.limit)

const openJiraIssue = (key: string) => {
  const domain = props.domain || 'nccu-software-development.atlassian.net'
  window.open(`https://${domain}/browse/${key}`, '_blank')
}
</script>

<template>
  <UCard>
    <template #header>
      <div class="flex items-center gap-2">
        <UIcon name="mdi:jira" class="w-5 h-5 text-blue-500" />
        <span class="text-lg font-semibold text-gray-900 dark:text-white">Jira 指派任務</span>
      </div>
    </template>

    <StaleDataBanner
      :stale="isStale ?? false"
      :synced-at="syncedAt ?? null"
      :auth-error="authError ?? false"
      platform-label="Jira"
    />

    <div v-if="loading">
      <USkeleton v-for="i in 3" :key="i" class="h-24 mb-4" />
    </div>

    <!-- 尚未綁定 Jira 帳號 -->
    <div
      v-else-if="notLinked"
      class="text-center text-sm text-gray-500 dark:text-gray-400 py-6"
    >
      尚未綁定 Jira 帳號，請先設定
    </div>

    <div v-else-if="issues.length" class="grid grid-cols-1 gap-4">
      <UCard
        v-for="issue in displayedIssues"
        :key="issue.id"
        :ui="{
          root: 'cursor-pointer hover:shadow-lg transition-transform duration-300 ease-in-out transform scale-100 hover:scale-105',
        }"
        @click="openJiraIssue(issue.key)"
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
          <img v-if="issue.iconUrl" :src="issue.iconUrl" alt="類型" class="w-5 h-5" >
          <span class="text-sm text-gray-600">{{ issue.type }}</span>
        </div>

        <div class="font-medium mb-2">{{ issue.title }}</div>

        <div class="flex items-center gap-2">
          <UAvatar v-if="issue.avatar" :src="issue.avatar" size="xs" />
          <span class="text-xs text-gray-500">{{ issue.assignee }}</span>
        </div>

        <template #footer>
          <div class="text-xs text-gray-400">
            更新於 {{ new Date(issue.updated_at).toLocaleDateString() }}
          </div>
        </template>
      </UCard>
    </div>

    <div
      v-else
      class="text-center text-sm text-gray-500 dark:text-gray-400 py-6"
    >
      尚無資料
    </div>

    <template v-if="hasMoreIssues" #footer>
      <NuxtLink to="/jira" class="text-sm text-primary hover:underline">
        查看全部（{{ issues.length }}）
      </NuxtLink>
    </template>
  </UCard>
</template>