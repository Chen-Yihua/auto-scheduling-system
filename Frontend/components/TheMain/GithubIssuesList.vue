<script setup lang="ts">
import { computed } from 'vue'
import type { GitHubIssue } from '~/types/github'
import { githubStateLabel } from '~/utils/labels'
import StaleDataBanner from './StaleDataBanner.vue'
const props = defineProps<{
  issues: GitHubIssue[]
  loading: boolean
  isStale?: boolean
  syncedAt?: string | null
  authError?: boolean
  notLinked?: boolean
  // 不給就顯示全部——dashboard 卡片用小數字避免無限拉長，
  // /github 這個完整清單頁面則不傳
  limit?: number
}>()

const displayedIssues = computed(() =>
  props.limit ? props.issues.slice(0, props.limit) : props.issues
)
const hasMoreIssues = computed(() => !!props.limit && props.issues.length > props.limit)

const openIssue = (url: string) => {
  window.open(url, '_blank')
}
</script>

<template>
  <UCard>
    <template #header>
      <div class="flex items-center gap-2">
        <UIcon name="mdi:github" class="w-5 h-5" />
        <span class="text-lg font-semibold text-gray-900 dark:text-white">GitHub 參與項目</span>
      </div>
    </template>

    <StaleDataBanner
      :stale="isStale ?? false"
      :synced-at="syncedAt ?? null"
      :auth-error="authError ?? false"
      platform-label="GitHub"
    />

    <div v-if="loading">
      <USkeleton v-for="i in 3" :key="i" class="h-24 mb-4" />
    </div>

    <!-- 尚未綁定 GitHub 帳號 -->
    <div
      v-else-if="notLinked"
      class="text-center text-sm text-gray-500 dark:text-gray-400 py-6"
    >
      尚未綁定 GitHub 帳號，請先設定
    </div>

    <div v-else-if="issues.length" class="grid grid-cols-1 gap-4">
      <UCard
        v-for="issue in displayedIssues"
        :key="issue.id"
        :ui="{
          root: 'cursor-pointer hover:shadow-lg transition-transform duration-300 ease-in-out transform scale-100 hover:scale-105',
        }"
        @click="openIssue(issue.url)"
      >
        <template #header>
          <div class="flex items-center justify-between">
            <div class="text-sm font-semibold">#{{ issue.number }}</div>
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
            {{ githubStateLabel(issue.status) }} · 更新於 {{ new Date(issue.updated_at ?? issue.created_at).toLocaleDateString() }}
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
      <NuxtLink to="/github" class="text-sm text-primary hover:underline">
        查看全部（{{ issues.length }}）
      </NuxtLink>
    </template>
  </UCard>
</template>
